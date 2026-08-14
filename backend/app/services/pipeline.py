from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from app.config import get_settings
from app.models.schemas import (
    PIPELINE_STEPS,
    AssetRef,
    JobStatus,
    Project,
    Shot,
    StepName,
    StepStatus,
    utcnow,
)
from app.providers.base import (
    BGMRequest,
    ImageRequest,
    ScriptRequest,
    StoryboardRequest,
    StoryRequest,
    TTSRequest,
    VideoRequest,
)
from app.providers import registry
from app.providers.media_utils import asset_url, new_asset_id, project_dir
from app.providers.style_lock import (
    cast_reference_prompt_en,
    characters_lock_en,
    inject_cast_into_visual_prompt,
)
from app.store.memory import store

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


def _mark_step(project: Project, step: StepName, status: StepStatus, error: str | None = None) -> None:
    state = project.steps[step.value]
    state.status = status
    state.error = error
    state.updated_at = utcnow()
    project.current_step = step
    project.updated_at = utcnow()


def _require(project: Project, *attrs: str) -> None:
    for a in attrs:
        if getattr(project, a, None) is None:
            raise PipelineError(f"Step requires '{a}' to be ready first")


async def _generate_cast_reference(project: Project) -> str | None:
    """
    Bootstrap a cast design sheet (ref_cast.png), then use it as subject_reference
    for every story page — no LoRA training.
    """
    assert project.story
    if not project.story.characters:
        return None

    provider = registry.get_image_provider()
    settings = get_settings()
    root = project_dir(settings, project.id)
    cast_path = root / "ref_cast.png"

    # Reuse existing sheet if present (reruns)
    if cast_path.exists() and cast_path.stat().st_size > 1000:
        return str(cast_path)

    lock = characters_lock_en(project.story.characters)
    cast_shot = Shot(
        index=-2,
        narration="character design sheet",
        visual_prompt=cast_reference_prompt_en(project.story.characters),
        duration_sec=1.0,
        mood=project.story.mood,
        shot_kind="character",
        characters_in_shot=[c.name for c in project.story.characters if c.name],
        on_screen_text="",
    )
    asset = await provider.generate(
        ImageRequest(
            project_id=project.id,
            shot=cast_shot,
            style="watercolor",
            theme=project.theme,
            characters_lock=lock,
        )
    )
    src = Path(asset.meta.get("path", ""))
    if not src.exists():
        logger.warning("Cast reference generate returned no file")
        return None

    try:
        shutil.copyfile(src, cast_path)
    except OSError:
        cast_path = src

    # Keep as project asset for UI / debugging
    asset_id = new_asset_id()
    ref_asset = AssetRef(
        id=asset_id,
        kind="cast_ref",
        filename=cast_path.name,
        mime_type="image/png",
        url=asset_url(project.id, asset_id),
        meta={
            "path": str(cast_path),
            "provider": asset.meta.get("provider"),
            "raw_id": asset.id,
            "role": "subject_reference",
        },
    )
    project.assets[asset.id] = asset
    project.assets[ref_asset.id] = ref_asset
    return str(cast_path)


async def run_step(project: Project, step: StepName) -> Project:
    _mark_step(project, step, StepStatus.running)
    store.save(project)

    try:
        if step == StepName.story:
            provider = registry.get_story_provider()
            project.story = await provider.generate(
                StoryRequest(
                    theme=project.theme,
                    age_range=project.age_range,
                    style=project.style,
                )
            )
        elif step == StepName.script:
            _require(project, "story")
            assert project.story
            provider = registry.get_script_provider()
            project.script = await provider.generate(
                ScriptRequest(story=project.story, target_sec=80.0)
            )
        elif step == StepName.storyboard:
            _require(project, "story", "script")
            assert project.story and project.script
            provider = registry.get_storyboard_provider()
            shot_count = max(12, len(project.script.lines))
            project.storyboard = await provider.generate(
                StoryboardRequest(
                    story=project.story,
                    script=project.script,
                    style="watercolor",
                    shot_count=shot_count,
                )
            )
        elif step == StepName.images:
            _require(project, "storyboard", "story")
            assert project.storyboard and project.story
            provider = registry.get_image_provider()
            lock = characters_lock_en(project.story.characters)

            # 1) 角色设定合影图 → subject_reference 锚点
            cast_ref_path = await _generate_cast_reference(project)
            store.save(project)

            # 2) 每页提示词强制点名角色长相 + 合影参考图
            for i, shot in enumerate(project.storyboard.shots):
                if i > 0:
                    await asyncio.sleep(0.8)
                shot.visual_prompt = inject_cast_into_visual_prompt(
                    shot.visual_prompt, project.story.characters
                )
                asset = await provider.generate(
                    ImageRequest(
                        project_id=project.id,
                        shot=shot,
                        style="watercolor",
                        theme=project.theme,
                        characters_lock=lock,
                        reference_image_path=cast_ref_path,
                    )
                )
                project.assets[asset.id] = asset
                shot.image_asset_id = asset.id
        elif step == StepName.tts:
            _require(project, "script", "storyboard")
            assert project.script and project.storyboard
            provider = registry.get_tts_provider()
            project.tts = await provider.generate(
                TTSRequest(
                    project_id=project.id,
                    script=project.script,
                    storyboard=project.storyboard,
                    api_prefix="/api/projects",
                )
            )
            project.assets[project.tts.asset.id] = project.tts.asset
        elif step == StepName.bgm:
            _require(project, "story", "storyboard")
            assert project.story and project.storyboard
            provider = registry.get_bgm_provider()
            dur = project.storyboard.total_sec or 60.0
            if project.tts:
                dur = max(dur, project.tts.duration_sec)
            project.bgm = await provider.generate(
                BGMRequest(
                    project_id=project.id,
                    mood=project.story.mood,
                    duration_sec=dur,
                )
            )
            project.assets[project.bgm.asset.id] = project.bgm.asset
        elif step == StepName.video:
            _require(project, "story", "storyboard", "tts", "bgm")
            assert project.story and project.storyboard and project.tts and project.bgm
            image_assets: list[AssetRef] = []
            for shot in project.storyboard.shots:
                if shot.image_asset_id and shot.image_asset_id in project.assets:
                    image_assets.append(project.assets[shot.image_asset_id])
            if not image_assets:
                raise PipelineError("No images generated — run 'images' step first")
            provider = registry.get_video_provider()
            project.video = await provider.generate(
                VideoRequest(
                    project_id=project.id,
                    storyboard=project.storyboard,
                    image_assets=image_assets,
                    tts=project.tts,
                    bgm=project.bgm,
                    title=project.story.title,
                )
            )
            project.assets[project.video.asset.id] = project.video.asset
        else:
            raise PipelineError(f"Unknown step: {step}")

        _mark_step(project, step, StepStatus.completed)
        store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        logger.exception("Step %s failed for project %s", step, project.id)
        _mark_step(project, step, StepStatus.failed, error=str(exc))
        store.save(project)
        raise


def steps_from(from_step: StepName | None) -> list[StepName]:
    if from_step is None:
        return list(PIPELINE_STEPS)
    idx = PIPELINE_STEPS.index(from_step)
    return PIPELINE_STEPS[idx:]


async def run_pipeline(project_id: str, from_step: StepName | None = None) -> Project:
    project = store.get(project_id)
    if not project:
        raise PipelineError("Project not found")

    project.job_status = JobStatus.running
    project.job_error = None
    store.save(project)

    try:
        for step in steps_from(from_step):
            project = store.get(project_id)
            if not project:
                raise PipelineError("Project disappeared")
            await run_step(project, step)

        project = store.get(project_id)
        assert project
        project.job_status = JobStatus.completed
        project.current_step = None
        project.updated_at = utcnow()
        store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        project = store.get(project_id)
        if project:
            project.job_status = JobStatus.failed
            project.job_error = str(exc)
            project.updated_at = utcnow()
            store.save(project)
        raise


def resolve_asset_path(project: Project, asset_id: str) -> tuple[Path, AssetRef]:
    asset = project.assets.get(asset_id)
    if not asset:
        raise PipelineError("Asset not found")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise PipelineError("Asset file missing on disk")
    return path, asset
