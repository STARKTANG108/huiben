from __future__ import annotations

import logging
from pathlib import Path

from app.models.book_schemas import (
    BOOK_API_PREFIX,
    BOOK_BGM_MOOD,
    BOOK_BGM_VOLUME,
    BOOK_MAX_SEC,
    BOOK_MOTION_AUDIO_VOLUME,
    BOOK_MOTION_SEC,
    BOOK_MOTION_SKIP_SHOTS,
    BOOK_SHOT_KIND_CYCLE,
    BOOK_VISUAL_STYLE_EN,
    BookProject,
)
from app.models.schemas import (
    PIPELINE_STEPS,
    AssetRef,
    JobStatus,
    Shot,
    Storyboard,
    StepName,
    StepStatus,
    utcnow,
)
from app.providers.base import (
    BGMRequest,
    ImageRequest,
    ScriptRequest,
    StoryRequest,
    TTSRequest,
    VideoRequest,
)
from app.providers import registry
from app.providers.llm_book import BookScriptProvider, BookStoryProvider
from app.providers.media_utils import (
    asset_url,
    compose_channels_cover,
    new_asset_id,
    project_dir,
)
from app.providers.openai_compat import LLMError, chat_json
from app.providers.style_lock import characters_lock_en
from app.store.book_memory import book_store
from app.config import get_settings

logger = logging.getLogger(__name__)

# 《一生》模版：景色/象征为主，画面随故事走
_SHOT_KIND_CYCLE = BOOK_SHOT_KIND_CYCLE


def _story_style(story) -> str:
    style = (getattr(story, "visual_style_en", None) or "").strip()
    return style or BOOK_VISUAL_STYLE_EN


def _split_caption_payload(raw: str) -> tuple[str, str]:
    """Return (bilingual_caption, visual_hint_en)."""
    text = (raw or "").strip()
    if "\x1e" in text:
        cap, hint = text.split("\x1e", 1)
        return cap.strip(), hint.strip()
    return text, ""


class BookPipelineError(Exception):
    pass


def _storage_key(project_id: str) -> str:
    return f"book/{project_id}"


def _mark_step(
    project: BookProject, step: StepName, status: StepStatus, error: str | None = None
) -> None:
    state = project.steps[step.value]
    state.status = status
    state.error = error
    state.updated_at = utcnow()
    project.current_step = step
    project.updated_at = utcnow()


def _require(project: BookProject, *attrs: str) -> None:
    for a in attrs:
        if getattr(project, a, None) is None:
            raise BookPipelineError(f"Step requires '{a}' to be ready first")


def _pick_kind(index: int) -> str:
    return _SHOT_KIND_CYCLE[index % len(_SHOT_KIND_CYCLE)]


def _shots_from_script(story, script) -> list[Shot]:
    style = _story_style(story)
    story.visual_style_en = style
    shots: list[Shot] = []
    for i, line in enumerate(script.lines):
        kind = _pick_kind(i)
        if i < 2:
            kind = "scenery" if i == 0 else "metaphor"
        chars: list[str] = []
        if kind == "character":
            chars = [c.name for c in story.characters if c.name in line.text]
            if not chars and story.characters:
                chars = [story.characters[0].name]
        caption, visual_hint = _split_caption_payload(line.caption or "")
        # 逐字稿：画面字幕必须与口播/TTS 一致
        transcript = (line.text or "").strip() or caption
        scene_seed = visual_hint or transcript
        if kind == "scenery":
            visual = (
                f"{style}. Wide atmospheric scenery matching the story beat, "
                f"no close-up faces. Scene: {scene_seed}"
            )
        elif kind == "metaphor":
            visual = (
                f"{style}. Symbolic cinematic detail or metaphor still, "
                f"minimal faces. Scene: {scene_seed}"
            )
        else:
            visual = (
                f"{style}. Character in environment (not face-only close-up), "
                f"characters: {', '.join(chars)}. Scene: {scene_seed}"
            )
        dur = float(line.estimated_sec or 16.0)
        dur = max(10.0, min(28.0, dur))
        shots.append(
            Shot(
                index=i,
                narration=transcript,
                visual_prompt=visual[:500],
                duration_sec=round(dur, 2),
                camera="slow_zoom",
                mood=story.mood,
                characters_in_shot=chars,
                shot_kind=kind,
                on_screen_text=transcript,
            )
        )
    if not shots:
        seed = (story.summary or story.title or "").strip()
        shots.append(
            Shot(
                index=0,
                narration=seed,
                visual_prompt=f"{style}. Scene: {story.title}"[:500],
                duration_sec=5.0,
                mood=story.mood,
                shot_kind="scenery",
                on_screen_text=seed,
            )
        )
    return shots


async def _build_storyboard(story, script) -> Storyboard:
    shots = _shots_from_script(story, script)
    style = _story_style(story)
    try:
        script_text = "\n".join(
            f"{s.index + 1}. [{s.shot_kind}] {s.narration}" for s in shots[:40]
        )
        cast_lock = characters_lock_en(story.characters)
        data = await chat_json(
            system=(
                "为《一生》式金句说书短视频写英文画面。输出 JSON："
                '{"items":[{"index":0,"shot_kind":"scenery|character|metaphor",'
                '"visual_prompt":"short English scene matching THIS story beat"}]}。'
                "硬性：画面必须贴合旁白情节与给定画风，禁止千篇一律空镜头；"
                "scenery/metaphor 为主；人物镜带环境、禁止连续人脸特写；"
                "不要在画面里写字；不要枪械/血腥/暴力/色情描写，用象征与风景表达情绪。"
            ),
            user=(
                f"画风：{style}\n角色锁定：{cast_lock}\n旁白：\n{script_text}\n"
                f"共 {len(shots)} 条，index 从 0 到 {len(shots) - 1}。"
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
            chars = ", ".join(shot.characters_in_shot) or "environment focus"
            shot.visual_prompt = f"{style}. {kind}. {chars}. {enriched}"[:500]
    except LLMError as exc:
        logger.warning("Book storyboard enrich skipped: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Book storyboard enrich failed: %s", exc)

    total = round(sum(s.duration_sec for s in shots), 2)
    return Storyboard(shots=shots, total_sec=total, provider="llm_book")


def _image_style(story) -> str:
    style = _story_style(story)
    if story is not None:
        story.visual_style_en = style
    return "custom:" + style


def _book_title_header(project: BookProject) -> str:
    title = (project.book_title or "").strip() or "书籍金句"
    return f"《{title}》" if not title.startswith("《") else title


async def _generate_cover(project: BookProject, storage: str) -> None:
    assert project.story
    from app.models.book_schemas import BOOK_COVER_PROMPT_EN

    style = _story_style(project.story)
    project.story.visual_style_en = style
    project.story.cover_prompt_en = project.story.cover_prompt_en or BOOK_COVER_PROMPT_EN
    provider = registry.get_image_provider()
    lock = characters_lock_en(project.story.characters)
    cover_shot = Shot(
        index=-1,
        narration=project.story.cover_hook or project.story.title,
        visual_prompt=(
            f"{style}. {project.story.cover_prompt_en or BOOK_COVER_PROMPT_EN}"
        )[:500],
        duration_sec=2.8,
        mood=project.story.mood,
        shot_kind="scenery",
        on_screen_text=project.story.cover_hook,
        characters_in_shot=[],
    )
    raw = await provider.generate(
        ImageRequest(
            project_id=project.id,
            shot=cover_shot,
            style=_image_style(project.story),
            theme=project.book_title,
            characters_lock=lock,
            api_prefix=BOOK_API_PREFIX,
            storage_key=storage,
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
        hook=project.story.cover_hook or project.story.title,
        subtitle=_book_title_header(project),
    )
    from app.providers.media_utils import asset_url

    cover = AssetRef(
        id=asset_id,
        kind="cover",
        filename=filename,
        mime_type="image/png",
        url=asset_url(project.id, asset_id, api_prefix=BOOK_API_PREFIX),
        meta={"path": str(dst), "hook": project.story.cover_hook, "raw_id": raw.id},
    )
    project.assets[raw.id] = raw
    project.assets[cover.id] = cover
    project.cover_asset_id = cover.id


async def run_step(project: BookProject, step: StepName) -> BookProject:
    _mark_step(project, step, StepStatus.running)
    book_store.save(project)
    storage = _storage_key(project.id)

    try:
        if step == StepName.story:
            provider = BookStoryProvider()
            project.story = await provider.generate(
                StoryRequest(
                    theme=project.theme,
                    age_range="general",
                    style="book",
                ),
                book_title=project.book_title,
                notes=project.notes,
                key_lessons=project.key_lessons,
            )
        elif step == StepName.script:
            _require(project, "story")
            assert project.story
            provider = BookScriptProvider()
            project.script = await provider.generate(
                ScriptRequest(story=project.story, target_sec=project.target_sec)
            )
        elif step == StepName.storyboard:
            _require(project, "story", "script")
            assert project.story and project.script
            project.storyboard = await _build_storyboard(project.story, project.script)
        elif step == StepName.images:
            _require(project, "storyboard", "story")
            assert project.storyboard and project.story
            provider = registry.get_image_provider()
            lock = characters_lock_en(project.story.characters)
            style = _image_style(project.story)
            for shot in project.storyboard.shots:
                # 景色镜不锁死人物
                shot_lock = lock if shot.shot_kind == "character" else ""
                asset = await provider.generate(
                    ImageRequest(
                        project_id=project.id,
                        shot=shot,
                        style=style,
                        theme=project.book_title,
                        characters_lock=shot_lock,
                        api_prefix=BOOK_API_PREFIX,
                        storage_key=storage,
                    )
                )
                project.assets[asset.id] = asset
                shot.image_asset_id = asset.id
            await _generate_cover(project, storage)
        elif step == StepName.tts:
            _require(project, "script", "storyboard")
            assert project.script and project.storyboard
            provider = registry.get_tts_provider()
            from app.runtime_config import runtime_config

            cfg = runtime_config.get()
            book_voice = (cfg.book_tts_voice or cfg.tts_voice or "").strip()
            project.tts = await provider.generate(
                TTSRequest(
                    project_id=project.id,
                    script=project.script,
                    storyboard=project.storyboard,
                    voice=book_voice,
                    api_prefix=BOOK_API_PREFIX,
                    storage_key=storage,
                )
            )
            project.assets[project.tts.asset.id] = project.tts.asset
        elif step == StepName.bgm:
            _require(project, "story", "storyboard")
            assert project.story and project.storyboard
            from app.providers.minimax_music import MinimaxBGMProvider

            provider = MinimaxBGMProvider()
            dur = project.storyboard.total_sec or project.target_sec
            if project.tts:
                dur = max(dur, project.tts.duration_sec)
            dur = min(dur, BOOK_MAX_SEC + 5.0)
            # 配乐提示只用英文情绪词，避免中文摘要触发涉敏
            mood = BOOK_BGM_MOOD
            story_mood = (project.story.mood or "").strip()
            if story_mood and story_mood.isascii():
                mood = f"{story_mood}, {BOOK_BGM_MOOD}"
            project.bgm = await provider.generate(
                BGMRequest(
                    project_id=project.id,
                    mood=mood[:500],
                    duration_sec=dur,
                    api_prefix=BOOK_API_PREFIX,
                    storage_key=storage,
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
                raise BookPipelineError("No images generated — run images step first")
            cover_path = None
            if project.cover_asset_id and project.cover_asset_id in project.assets:
                cover_path = project.assets[project.cover_asset_id].meta.get("path")

            motion_clip_path = None
            shots_sorted = sorted(project.storyboard.shots, key=lambda s: s.index)
            if len(shots_sorted) >= 2:
                first_asset = (
                    project.assets.get(shots_sorted[0].image_asset_id or "")
                    if shots_sorted[0].image_asset_id
                    else None
                )
                last_asset = (
                    project.assets.get(shots_sorted[1].image_asset_id or "")
                    if shots_sorted[1].image_asset_id
                    else None
                )
                first_p = Path((first_asset.meta or {}).get("path", "")) if first_asset else None
                last_p = Path((last_asset.meta or {}).get("path", "")) if last_asset else None
                if first_p and last_p and first_p.exists() and last_p.exists():
                    from app.providers.toapis_video import ToAPIsVideoProvider

                    settings = get_settings()
                    motion_out = (
                        project_dir(settings, storage)
                        / f"motion_open_{project.id[:8]}.mp4"
                    )
                    prompt_bits = [
                        (shots_sorted[0].visual_prompt or "").strip(),
                        (shots_sorted[1].visual_prompt or "").strip(),
                        "slow cinematic camera drift, atmospheric book trailer motion",
                    ]
                    try:
                        await ToAPIsVideoProvider().generate_first_last(
                            first_path=first_p,
                            last_path=last_p,
                            out_path=motion_out,
                            prompt=" | ".join(b for b in prompt_bits if b),
                            duration_sec=int(BOOK_MOTION_SEC),
                        )
                        motion_clip_path = str(motion_out)
                        motion_asset_id = new_asset_id()
                        project.assets[motion_asset_id] = AssetRef(
                            id=motion_asset_id,
                            kind="video",
                            filename=motion_out.name,
                            mime_type="video/mp4",
                            url=asset_url(
                                project.id,
                                motion_asset_id,
                                api_prefix=BOOK_API_PREFIX,
                            ),
                            meta={
                                "path": str(motion_out),
                                "role": "book_opening_motion",
                                "duration_sec": BOOK_MOTION_SEC,
                                "provider": "toapis_veo",
                                "model": "veo3.1-fast",
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Book opening motion failed for %s, fallback slideshow: %s",
                            project.id,
                            exc,
                        )
                        motion_clip_path = None

            provider = registry.get_video_provider()
            project.video = await provider.generate(
                VideoRequest(
                    project_id=project.id,
                    storyboard=project.storyboard,
                    image_assets=image_assets,
                    tts=project.tts,
                    bgm=project.bgm,
                    title=project.story.title,
                    api_prefix=BOOK_API_PREFIX,
                    storage_key=storage,
                    burn_captions=True,
                    cover_path=cover_path,
                    cover_sec=2.8,
                    caption_header=_book_title_header(project),
                    prefer_on_screen_text=True,
                    bgm_volume=BOOK_BGM_VOLUME,
                    motion_clip_path=motion_clip_path,
                    motion_sec=BOOK_MOTION_SEC,
                    keep_motion_audio=True,
                    motion_audio_volume=BOOK_MOTION_AUDIO_VOLUME,
                    motion_skip_shot_count=BOOK_MOTION_SKIP_SHOTS,
                )
            )
            project.assets[project.video.asset.id] = project.video.asset
        else:
            raise BookPipelineError(f"Unknown step: {step}")

        _mark_step(project, step, StepStatus.completed)
        book_store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        logger.exception("Book step %s failed for %s", step, project.id)
        _mark_step(project, step, StepStatus.failed, error=str(exc))
        book_store.save(project)
        raise


def steps_from(from_step: StepName | None) -> list[StepName]:
    if from_step is None:
        return list(PIPELINE_STEPS)
    idx = PIPELINE_STEPS.index(from_step)
    return PIPELINE_STEPS[idx:]


async def run_pipeline(project_id: str, from_step: StepName | None = None) -> BookProject:
    project = book_store.get(project_id)
    if not project:
        raise BookPipelineError("Book project not found")

    project.job_status = JobStatus.running
    project.job_error = None
    book_store.save(project)

    try:
        for step in steps_from(from_step):
            project = book_store.get(project_id)
            if not project:
                raise BookPipelineError("Project disappeared")
            await run_step(project, step)

        project = book_store.get(project_id)
        assert project
        project.job_status = JobStatus.completed
        project.current_step = None
        project.updated_at = utcnow()
        book_store.save(project)
        return project
    except Exception as exc:  # noqa: BLE001
        project = book_store.get(project_id)
        if project:
            project.job_status = JobStatus.failed
            project.job_error = str(exc)
            project.updated_at = utcnow()
            book_store.save(project)
        raise


def resolve_asset_path(project: BookProject, asset_id: str) -> tuple[Path, AssetRef]:
    asset = project.assets.get(asset_id)
    if not asset:
        raise BookPipelineError("Asset not found")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise BookPipelineError("Asset file missing on disk")
    return path, asset
