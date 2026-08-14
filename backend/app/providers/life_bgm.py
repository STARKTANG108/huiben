from __future__ import annotations

"""人生副本固定 BGM：曲目循环裁剪，缺失时回退程序化配乐。"""

import asyncio
import hashlib
import logging
import subprocess
from pathlib import Path

from app.config import get_settings
from app.models.life_schemas import LIFE_BGM_MOOD, LIFE_BGM_TRACKS
from app.models.schemas import AssetRef, BGMResult
from app.providers.base import BGMRequest
from app.providers.media_utils import asset_url, new_asset_id, project_dir
from app.providers.procedural_bgm import ProceduralBGMProvider

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "bgm" / "life"
_AUDIO_EXTS = (".mp3", ".ogg", ".flac", ".wav", ".m4a")


def _resolve_track_file(track: dict[str, str]) -> Path | None:
    names = [
        track["filename"],
        f"{track['title']}.mp3",
        f"{track['title'].lower().replace(' ', '_')}.mp3",
    ]
    stem = Path(track["filename"]).stem
    for name in names:
        path = _ASSETS_DIR / name
        if path.exists() and path.stat().st_size > 1000:
            return path
    for ext in _AUDIO_EXTS:
        path = _ASSETS_DIR / f"{stem}{ext}"
        if path.exists() and path.stat().st_size > 1000:
            return path
    return None


def available_life_bgm_tracks() -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for track in LIFE_BGM_TRACKS:
        if _resolve_track_file(track):
            found.append(track)
    return found


def pick_life_bgm_track(project_id: str, preferred_id: str | None = None) -> dict[str, str]:
    tracks = available_life_bgm_tracks() or list(LIFE_BGM_TRACKS)
    pref = (preferred_id or "").strip()
    if pref:
        for track in tracks:
            if track["id"] == pref:
                return track
        for track in LIFE_BGM_TRACKS:
            if track["id"] == pref:
                # preferred exists in catalog but file missing — still try resolve
                return track
    idx = int(hashlib.md5(project_id.encode()).hexdigest(), 16) % len(tracks)
    return tracks[idx]


def _ffmpeg_trim_loop(src: Path, dst: Path, duration_sec: float) -> bool:
    """Loop source until duration is covered, with soft in/out fades."""
    duration_sec = max(8.0, duration_sec + 2.0)
    fade_out_start = max(0.5, duration_sec - 1.8)
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(src),
            "-t",
            f"{duration_sec:.2f}",
            "-af",
            (
                f"afade=t=in:st=0:d=1.2,"
                f"afade=t=out:st={fade_out_start:.2f}:d=1.8,"
                "volume=0.85"
            ),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(dst),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.warning("Life BGM ffmpeg: %s", (result.stderr or "")[-400:])
        return (
            result.returncode == 0
            and dst.exists()
            and dst.stat().st_size > 1000
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Life BGM ffmpeg failed: %s", exc)
        return False


class LifeBGMProvider:
    name = "life_tracks"

    async def generate(self, req: BGMRequest) -> BGMResult:
        track = pick_life_bgm_track(req.project_id, getattr(req, "track_id", None))
        src = _resolve_track_file(track)
        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"bgm_{asset_id}.mp3"
        path = project_dir(
            settings, getattr(req, "storage_key", None) or req.project_id
        ) / filename

        if src:
            # ffmpeg 裁剪/循环配乐耗时较长：放到线程池，避免阻塞事件循环
            ok = await asyncio.to_thread(_ffmpeg_trim_loop, src, path, req.duration_sec)
            if ok:
                asset = AssetRef(
                    id=asset_id,
                    kind="audio",
                    filename=filename,
                    mime_type="audio/mpeg",
                    url=asset_url(
                        req.project_id,
                        asset_id,
                        api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
                    ),
                    meta={
                        "path": str(path),
                        "mood": track["title"],
                        "track_id": track["id"],
                        "provider": self.name,
                        "source": str(src),
                        "looped": True,
                    },
                )
                return BGMResult(
                    asset=asset,
                    duration_sec=round(req.duration_sec + 2.0, 2),
                    mood=track["title"],
                    provider=self.name,
                )
            logger.warning("Life BGM ffmpeg failed for %s, fallback procedural", src)

        logger.warning(
            "Life BGM track missing (%s), place audio in %s — using procedural fallback",
            track["title"],
            _ASSETS_DIR,
        )
        fallback = ProceduralBGMProvider()
        result = await fallback.generate(
            BGMRequest(
                project_id=req.project_id,
                mood=LIFE_BGM_MOOD,
                duration_sec=req.duration_sec,
                api_prefix=req.api_prefix,
                storage_key=req.storage_key,
            )
        )
        result.mood = f"{track['title']} (fallback)"
        return result
