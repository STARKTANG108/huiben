from __future__ import annotations

import hashlib
import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.models.life_schemas import (
    LIFE_API_PREFIX,
    LIFE_BGM_MOOD,
    LIFE_BGM_VOLUME,
    LIFE_COVER_PROMPT_EN,
    LIFE_DEFAULT_BGM_TRACK_ID,
    LIFE_DEFAULT_TTS_VOICE,
    LIFE_PIPELINE_STEPS,
    LIFE_SERIES_PREFIX,
    LIFE_VISUAL_STYLE_EN,
    LifeProject,
)
from app.models.schemas import (
    AssetRef,
    JobStatus,
    Script,
    ScriptLine,
    Shot,
    Storyboard,
    StepName,
    StepStatus,
    utcnow,
)
from app.providers import registry
from app.providers.base import (
    BGMRequest,
    ImageRequest,
    TTSRequest,
    VideoRequest,
)
from app.providers.life_bgm import LifeBGMProvider
from app.providers.life_user_story import build_script_from_user, build_story_from_user
from app.providers.media_utils import (
    asset_url,
    compose_channels_cover,
    new_asset_id,
    project_dir,
)
from app.providers.openai_compat import LLMError, chat_json
from app.providers.style_lock import characters_lock_en, life_characters_lock_en
from app.store.life_memory import life_store

logger = logging.getLogger(__name__)

# 爽文漫画：动作人物 + 场景冲击交替
_SHOT_KIND_CYCLE = ("character", "scenery", "character", "metaphor", "character", "scenery")


class LifePipelineError(Exception):
    pass


def _storage_key(project_id: str) -> str:
    return f"life/{project_id}"


def _mark_step(
    project: LifeProject, step: StepName, status: StepStatus, error: str | None = None
) -> None:
    state = project.steps[step.value]
    state.status = status
    state.error = error
    state.updated_at = utcnow()
    project.current_step = step
    project.updated_at = utcnow()


def _require(project: LifeProject, *attrs: str) -> None:
    for a in attrs:
        if getattr(project, a, None) is None:
            raise LifePipelineError(f"Step requires '{a}' to be ready first")


def _pick_kind(index: int) -> str:
    return _SHOT_KIND_CYCLE[index % len(_SHOT_KIND_CYCLE)]


def life_intro_line(episode_title: str) -> str:
    title = (episode_title or "").strip()
    if not title:
        return LIFE_SERIES_PREFIX.rstrip("之")
    if title.startswith(LIFE_SERIES_PREFIX):
        return title
    return f"{LIFE_SERIES_PREFIX}{title}"


def inject_life_intro(script: Script, story) -> Script:
    intro_text = life_intro_line(story.title)
    if script.lines and script.lines[0].text.strip().startswith(LIFE_SERIES_PREFIX):
        script.lines[0].text = intro_text
        script.lines[0].caption = intro_text
        script.lines[0].estimated_sec = max(script.lines[0].estimated_sec or 4.5, 4.8)
        total = sum(l.estimated_sec for l in script.lines)
        script.total_sec = round(total, 2)
        return script

    intro = ScriptLine(
        index=0,
        text=intro_text,
        caption=intro_text,
        estimated_sec=4.8,
    )
    new_lines = [intro]
    for line in script.lines:
        line.index = len(new_lines)
        line.caption = line.text
        new_lines.append(line)
    total = sum(l.estimated_sec for l in new_lines)
    return Script(
        lines=new_lines,
        total_sec=round(total, 2),
        provider=script.provider,
    )


def _shot_mood_for_line(index: int, total: int, story_mood: str) -> str:
    if index == 0:
        return "hook"
    if index >= total - 1:
        if story_mood in ("triumphant", "inspiring", "fierce"):
            return "triumphant"
        return "reflective"
    if index == total - 2 and story_mood in ("fierce", "tense"):
        return "climax"
    return story_mood or "inspiring"


def _project_image_seed(project_id: str) -> int:
    return int(hashlib.md5(project_id.encode()).hexdigest()[:8], 16) % (2**31 - 1)


def _image_style(story) -> str:
    style = (getattr(story, "visual_style_en", None) or "").strip() or LIFE_VISUAL_STYLE_EN
    return (
        "custom:"
        + style
        + ", Japanese healing cute character + realistic Chinese county town, "
        "warm muted palette, soft film grain, vertical 9:16, no text no watermark"
    )


def _shots_from_script(story, script) -> list[Shot]:
    from app.models.life_schemas import LIFE_NARRATIVE_LOCK_EN

    style = (story.visual_style_en or LIFE_VISUAL_STYLE_EN).strip()
    story_mood = (story.mood or "inspiring").strip()
    total = len(script.lines)
    shots: list[Shot] = []
    for i, line in enumerate(script.lines):
        kind = _pick_kind(i)
        if i == 0:
            kind = "character"
        chars: list[str] = []
        if kind == "character":
            chars = [c.name for c in story.characters if c.name in line.text]
            if not chars and story.characters:
                chars = [story.characters[0].name]
        narration = (line.text or "").strip()
        shot_mood = _shot_mood_for_line(i, total, story_mood)
        if kind == "scenery":
            visual = (
                f"{style}. {LIFE_NARRATIVE_LOCK_EN}. "
                f"Realistic Chinese county town environment "
                f"(street, school, market, home), warm still. Scene: {narration}"
            )
        elif kind == "metaphor":
            visual = (
                f"{style}. Quiet everyday detail or symbolic prop "
                f"(e-bike, home-cooked dish, rattan chair, plane tree, river). "
                f"Scene: {narration}"
            )
        else:
            visual = (
                f"{style}. Cute round-faced healing character in realistic county setting, "
                f"soft expression, characters: {', '.join(chars)}. "
                f"Scene: {narration}"
            )
        shots.append(
            Shot(
                index=i,
                narration=narration,
                visual_prompt=visual[:500],
                duration_sec=round(max(3.5, min(5.5, line.estimated_sec or 4.5)), 2),
                camera="slow_zoom",
                mood=shot_mood,
                characters_in_shot=chars,
                shot_kind=kind,
                on_screen_text=narration,
            )
        )
    if not shots:
        shots.append(
            Shot(
                index=0,
                narration=story.summary or story.title,
                visual_prompt=f"{style}. Scene: {story.title}"[:500],
                duration_sec=5.0,
                mood=story.mood,
                shot_kind="character",
                on_screen_text=(story.cover_hook or story.title)[:16],
            )
        )
    return shots


async def _build_storyboard(story, script, *, enrich: bool = True) -> Storyboard:
    shots = _shots_from_script(story, script)
    style = (story.visual_style_en or LIFE_VISUAL_STYLE_EN).strip()
    if not enrich:
        total = round(sum(s.duration_sec for s in shots), 2)
        return Storyboard(shots=shots, total_sec=total, provider="user_story")
    try:
        script_text = "\n".join(
            f"{s.index + 1}. [{s.shot_kind}] narr={s.narration} | caption={s.on_screen_text}"
            for s in shots[:20]
        )
        cast_lock = life_characters_lock_en(story.characters)
        data = await chat_json(
            system=(
                "为现代写实电影感「人生副本」短视频写英文分镜。输出 JSON："
                '{"items":[{"index":0,"shot_kind":"character|scenery|metaphor",'
                '"visual_prompt":"short English modern cinematic still"}]}。'
                "要求：contemporary realism，不要漫画描边；人物镜带环境；"
                "禁止画面写字；角色外观必须与 CHARACTER LOCK 完全一致；"
                "同一主角脸型/发型/服装色系全片一致。"
            ),
            user=(
                f"画风：{style}\n角色：{cast_lock}\n分镜：\n{script_text}\n"
                f"共 {len(shots)} 条，index 0..{len(shots) - 1}。"
            ),
            temperature=0.35,
        )
        items = {
            int(row.get("index", -1)): row
            for row in (data.get("items") or [])
            if str(row.get("visual_prompt", "")).strip()
        }
        for shot in shots:
            row = items.get(shot.index)
            if not row:
                continue
            enriched = str(row.get("visual_prompt", "")).strip()
            kind = str(row.get("shot_kind") or shot.shot_kind).strip().lower()
            if kind not in ("scenery", "character", "metaphor"):
                kind = shot.shot_kind
            shot.shot_kind = kind
            if kind != "character":
                shot.characters_in_shot = []
            elif not shot.characters_in_shot and story.characters:
                shot.characters_in_shot = [story.characters[0].name]
            chars = ", ".join(shot.characters_in_shot) or "environment"
            shot.visual_prompt = f"{style}. {kind}. {chars}. {enriched}"[:500]
    except LLMError as exc:
        logger.warning("Life storyboard enrich skipped: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Life storyboard enrich failed: %s", exc)

    total = round(sum(s.duration_sec for s in shots), 2)
    return Storyboard(shots=shots, total_sec=total, provider="llm_life")


async def _generate_cover(project: LifeProject, storage: str, *, ref_path: str | None = None) -> None:
    assert project.story
    provider = registry.get_image_provider()
    lock = life_characters_lock_en(project.story.characters)
    intro = life_intro_line(project.story.title)
    cover_shot = Shot(
        index=-1,
        narration=intro,
        visual_prompt=(
            f"{project.story.visual_style_en or LIFE_VISUAL_STYLE_EN}. "
            f"{(project.story.cover_prompt_en or '').strip() or LIFE_COVER_PROMPT_EN}"
        )[:500],
        duration_sec=2.8,
        mood="hook",
        shot_kind="character",
        on_screen_text=intro,
        characters_in_shot=[project.story.characters[0].name] if project.story.characters else [],
    )
    raw = await provider.generate(
        ImageRequest(
            project_id=project.id,
            shot=cover_shot,
            style=_image_style(project.story),
            theme=project.premise or project.story.title,
            characters_lock=lock,
            api_prefix=LIFE_API_PREFIX,
            storage_key=storage,
            reference_image_path=ref_path,
            seed=_project_image_seed(project.id),
        )
    )
    settings = get_settings()
    src = Path(raw.meta.get("path", ""))
    if not src.exists():
        project.assets[raw.id] = raw
        project.cover_asset_id = raw.id
        return

    asset_id = new_asset_id()
    filename = f"cover_{asset_id}.png"
    dst = project_dir(settings, storage) / filename
    compose_channels_cover(
        src,
        dst,
        hook=intro,
        subtitle=project.story.cover_hook or "",
    )
    cover = AssetRef(
        id=asset_id,
        kind="cover",
        filename=filename,
        mime_type="image/png",
        url=asset_url(project.id, asset_id, api_prefix=LIFE_API_PREFIX),
        meta={"path": str(dst), "hook": intro, "raw_id": raw.id},
    )
    project.assets[raw.id] = raw
    project.assets[cover.id] = cover
    project.cover_asset_id = cover.id


async def run_step(project: LifeProject, step: StepName) -> LifeProject:
    _mark_step(project, step, StepStatus.running)
    life_store.save(project)
    storage = _storage_key(project.id)

    try:
        if step == StepName.story:
            if not (project.story_text or "").strip():
                raise LifePipelineError("请先在创建页填写故事正文")
            project.story = build_story_from_user(
                story_text=project.story_text,
                title=project.title,
                premise=project.premise,
                notes=project.notes,
            )
        elif step == StepName.script:
            _require(project, "story")
            assert project.story
            project.script = build_script_from_user(project.story)
            project.script = inject_life_intro(project.script, project.story)
        elif step == StepName.storyboard:
            _require(project, "story", "script")
            assert project.story and project.script
            # 用户自写故事：分镜提示词用模板，不再调 DeepSeek
            project.storyboard = await _build_storyboard(
                project.story, project.script, enrich=False
            )
        elif step == StepName.tts:
            _require(project, "script", "storyboard")
            assert project.script and project.storyboard
            provider = registry.get_tts_provider()
            from app.runtime_config import runtime_config

            cfg = runtime_config.get()
            voice = (
                (project.tts_voice or "").strip()
                or LIFE_DEFAULT_TTS_VOICE
                or (cfg.book_tts_voice or "").strip()
                or (cfg.tts_voice or "").strip()
            )
            project.tts = await provider.generate(
                TTSRequest(
                    project_id=project.id,
                    script=project.script,
                    storyboard=project.storyboard,
                    voice=voice,
                    api_prefix=LIFE_API_PREFIX,
                    storage_key=storage,
                )
            )
            project.assets[project.tts.asset.id] = project.tts.asset
            # 配音时长回写分镜：后续配图镜时长 / 字幕 / 成片都跟口播走
            project.storyboard.total_sec = round(
                sum(s.duration_sec for s in project.storyboard.shots), 2
            )
            if project.script:
                project.script.total_sec = project.storyboard.total_sec
        elif step == StepName.images:
            _require(project, "storyboard", "story", "tts")
            assert project.storyboard and project.story and project.tts
            provider = registry.get_image_provider()
            lock = life_characters_lock_en(project.story.characters)
            style = _image_style(project.story)
            seed = _project_image_seed(project.id)
            char_ref_path: str | None = None
            for i, shot in enumerate(project.storyboard.shots):
                if i > 0:
                    # 降低 MiniMax RPM：镜间稍作间隔
                    await asyncio.sleep(1.2)
                use_ref = char_ref_path if shot.shot_kind == "character" else None
                asset = await provider.generate(
                    ImageRequest(
                        project_id=project.id,
                        shot=shot,
                        style=style,
                        theme=project.premise or project.story.title,
                        characters_lock=lock,
                        api_prefix=LIFE_API_PREFIX,
                        storage_key=storage,
                        reference_image_path=use_ref,
                        seed=seed,
                    )
                )
                project.assets[asset.id] = asset
                shot.image_asset_id = asset.id
                if shot.shot_kind == "character" and not char_ref_path:
                    char_ref_path = asset.meta.get("path")
            await asyncio.sleep(1.2)
            await _generate_cover(project, storage, ref_path=char_ref_path)
        elif step == StepName.bgm:
            _require(project, "story", "storyboard", "tts")
            assert project.story and project.storyboard and project.tts
            provider = LifeBGMProvider()
            dur = max(
                project.tts.duration_sec,
                project.storyboard.total_sec,
                sum(s.duration_sec for s in project.storyboard.shots),
            )
            project.bgm = await provider.generate(
                BGMRequest(
                    project_id=project.id,
                    mood=LIFE_BGM_MOOD,
                    duration_sec=dur,
                    api_prefix=LIFE_API_PREFIX,
                    storage_key=storage,
                    track_id=(project.bgm_track_id or "").strip()
                    or LIFE_DEFAULT_BGM_TRACK_ID,
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
                raise LifePipelineError("No images — run images step first")
            cover_path = None
            if project.cover_asset_id and project.cover_asset_id in project.assets:
                cover_path = project.assets[project.cover_asset_id].meta.get("path")
            provider = registry.get_video_provider()
            project.video = await provider.generate(
                VideoRequest(
                    project_id=project.id,
                    storyboard=project.storyboard,
                    image_assets=image_assets,
                    tts=project.tts,
                    bgm=project.bgm,
                    title=project.story.title,
                    api_prefix=LIFE_API_PREFIX,
                    storage_key=storage,
                    burn_captions=True,
                    cover_path=cover_path,
                    cover_sec=2.5,
                    bgm_volume=LIFE_BGM_VOLUME,
                )
            )
            project.assets[project.video.asset.id] = project.video.asset
        else:
            raise LifePipelineError(f"Unknown step: {step}")

        _mark_step(project, step, StepStatus.completed)
        life_store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        logger.exception("Life step %s failed for %s", step, project.id)
        _mark_step(project, step, StepStatus.failed, error=str(exc))
        life_store.save(project)
        raise


def steps_from(from_step: StepName | None) -> list[StepName]:
    if from_step is None:
        return list(LIFE_PIPELINE_STEPS)
    return LIFE_PIPELINE_STEPS[LIFE_PIPELINE_STEPS.index(from_step) :]


async def run_pipeline(project_id: str, from_step: StepName | None = None) -> LifeProject:
    project = life_store.get(project_id)
    if not project:
        raise LifePipelineError("Life project not found")

    project.job_status = JobStatus.running
    project.job_error = None
    life_store.save(project)

    try:
        for step in steps_from(from_step):
            project = life_store.get(project_id)
            if not project:
                raise LifePipelineError("Project disappeared")
            await run_step(project, step)

        project = life_store.get(project_id)
        assert project
        project.job_status = JobStatus.completed
        project.current_step = None
        project.updated_at = utcnow()
        life_store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        project = life_store.get(project_id)
        if project:
            project.job_status = JobStatus.failed
            project.job_error = str(exc)
            project.updated_at = utcnow()
            life_store.save(project)
        raise


def resolve_asset_path(project: LifeProject, asset_id: str) -> tuple[Path, AssetRef]:
    asset = project.assets.get(asset_id)
    if not asset:
        raise LifePipelineError("Asset not found")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise LifePipelineError("Asset file missing on disk")
    return path, asset
