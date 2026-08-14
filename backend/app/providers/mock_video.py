from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings
from app.models.schemas import AssetRef, VideoResult
from app.providers.base import VideoRequest
from app.providers.media_utils import (
    asset_url,
    burn_caption_on_image,
    compose_book_with_motion,
    new_asset_id,
    project_dir,
    try_ffmpeg_slideshow,
    write_minimal_mp4_placeholder,
)


class MockVideoProvider:
    name = "mock"

    async def generate(self, req: VideoRequest) -> VideoResult:
        await asyncio.sleep(0.2)
        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"video_{asset_id}.mp4"
        root = project_dir(settings, getattr(req, "storage_key", None) or req.project_id)
        out = root / filename

        shots = sorted(req.storyboard.shots, key=lambda s: s.index)
        motion_path_raw = getattr(req, "motion_clip_path", None)
        motion_file = Path(motion_path_raw) if motion_path_raw else None
        use_motion = bool(motion_file and motion_file.exists())
        skip_n = int(getattr(req, "motion_skip_shot_count", 2) or 0) if use_motion else 0

        image_paths: list[Path] = []
        durations: list[float] = []
        burn = bool(getattr(req, "burn_captions", False))
        caption_dir = root / f"_captioned_{asset_id}"
        if burn:
            caption_dir.mkdir(parents=True, exist_ok=True)

        cover_path = getattr(req, "cover_path", None)
        cover_file = Path(cover_path) if cover_path else None
        # 有开场动效时不用封面替换首镜（首两镜已进首尾帧视频）
        use_cover_first = bool(cover_file and cover_file.exists()) and not use_motion

        for i, shot in enumerate(shots):
            if use_motion and i < skip_n:
                continue
            if not shot.image_asset_id:
                continue
            asset = next(
                (a for a in req.image_assets if a.id == shot.image_asset_id),
                None,
            )
            if not asset:
                continue
            p = Path(asset.meta.get("path", ""))
            if not p.exists():
                continue
            # 首镜用冲击力封面，保证视频号自动缩略图也有点击欲
            if use_cover_first and i == 0:
                p = cover_file  # type: ignore[assignment]
            if burn and not (use_cover_first and i == 0):
                prefer_ost = bool(getattr(req, "prefer_on_screen_text", False))
                poem = (shot.on_screen_text or "").strip()
                narr = (shot.narration or "").strip()
                if prefer_ost:
                    # 书籍：字幕=口播逐字稿（与 TTS 一致），顶部仍可挂书名
                    text = narr or poem
                    layout = "lifetime"
                    poem_arg = None
                else:
                    text = narr or poem
                    layout = "simple"
                    poem_arg = None
                capped = caption_dir / f"shot_{shot.index:02d}.png"
                header = getattr(req, "caption_header", None)
                try:
                    burn_caption_on_image(
                        p,
                        capped,
                        text,
                        header=header,
                        poem=poem_arg,
                        layout=layout,
                    )
                    image_paths.append(capped)
                except Exception:  # noqa: BLE001
                    image_paths.append(p)
            else:
                image_paths.append(p)
            durations.append(max(3.0, float(shot.duration_sec or 4.5)))

        tts_path = Path(req.tts.asset.meta.get("path", ""))
        bgm_path = Path(req.bgm.asset.meta.get("path", ""))
        motion_sec = float(getattr(req, "motion_sec", 8.0) or 8.0)
        duration = (
            (motion_sec if use_motion else 0.0)
            + (sum(durations) if durations else 0.0)
        ) or (req.tts.duration_sec or 60.0)

        ok = False
        if use_motion and motion_file is not None:
            # ffmpeg 合成耗时可达数分钟：放到线程池，避免阻塞 asyncio 事件循环
            ok = await asyncio.to_thread(
                compose_book_with_motion,
                motion_file,
                image_paths,
                durations,
                tts_path if tts_path.exists() else None,
                bgm_path if bgm_path.exists() else None,
                out,
                motion_sec=motion_sec,
                keep_motion_audio=bool(getattr(req, "keep_motion_audio", True)),
                motion_audio_volume=float(
                    getattr(req, "motion_audio_volume", 0.42) or 0.42
                ),
                bgm_volume=float(getattr(req, "bgm_volume", 0.16) or 0.16),
                width=1080,
                height=1920,
            )
        elif image_paths:
            ok = await asyncio.to_thread(
                try_ffmpeg_slideshow,
                image_paths,
                tts_path if tts_path.exists() else None,
                out,
                durations,
                bgm_path=bgm_path if bgm_path.exists() else None,
                width=1080,
                height=1920,
                bgm_volume=float(getattr(req, "bgm_volume", 0.16) or 0.16),
            )
        if not ok:
            write_minimal_mp4_placeholder(out)

        asset = AssetRef(
            id=asset_id,
            kind="video",
            filename=filename,
            mime_type="video/mp4",
            url=asset_url(
                req.project_id,
                asset_id,
                api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
            ),
            meta={
                "path": str(out),
                "title": req.title,
                "ffmpeg": ok,
                "provider": self.name,
                "aspect": "9:16",
                "shot_count": len(image_paths) + (skip_n if use_motion else 0),
                "burn_captions": burn,
                "has_cover": bool(cover_path),
                "has_motion": use_motion,
                "motion_sec": motion_sec if use_motion else 0,
            },
        )
        return VideoResult(
            asset=asset, duration_sec=round(duration, 2), provider=self.name
        )
