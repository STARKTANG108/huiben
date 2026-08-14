from __future__ import annotations

"""MiniMax Music Generation → instrumental BGM for book / video."""

import logging

import httpx

from app.config import get_settings
from app.models.schemas import AssetRef, BGMResult
from app.providers.base import BGMRequest
from app.providers.media_utils import asset_url, new_asset_id, project_dir
from app.providers.minimax_media import (
    _minimax_api_key,
    _minimax_base,
    _minimax_post_json,
    sanitize_minimax_prompt,
)
from app.providers.procedural_bgm import ProceduralBGMProvider

logger = logging.getLogger(__name__)

# China (minimaxi.com) + international model ids
MUSIC_MODELS = ("music-2.6", "music-3.0", "music-2.6-free", "music-3.0-free")


def _bgm_prompt(mood: str, duration_sec: float) -> str:
    mood = sanitize_minimax_prompt(mood or "", drop_cjk=True)
    mood = mood or "melancholic cinematic piano"
    # 纯音乐：明确禁止人声，适合旁白压底；避免涉敏叙事细节
    return (
        "Pure instrumental soundtrack only. "
        f"{mood}. "
        "Absolutely no vocals, no singing, no lyrics, no choir, no humming. "
        f"Soft underscoring for spoken book narration, around {int(max(60, duration_sec))} seconds, "
        "gentle dynamics, warm and reflective, loop-friendly, low presence so voice stays clear. "
        "Cinematic piano and soft strings preferred. Not dance, not EDM, not pop vocal."
    )[:1800]


class MinimaxBGMProvider:
    name = "minimax"

    async def generate(self, req: BGMRequest) -> BGMResult:
        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"bgm_{asset_id}.mp3"
        root = project_dir(settings, getattr(req, "storage_key", None) or req.project_id)
        path = root / filename
        duration = max(60.0, float(req.duration_sec or 180.0))
        mood = (req.mood or "").strip() or "melancholic cinematic piano"
        prompt = _bgm_prompt(mood, duration)

        try:
            audio_bytes, api_dur, model_used = await self._generate_instrumental(prompt)
            if not audio_bytes or len(audio_bytes) < 1000:
                raise RuntimeError("MiniMax 纯音乐返回为空或过短")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio_bytes)
            out_dur = float(api_dur or duration)
            return BGMResult(
                asset=AssetRef(
                    id=asset_id,
                    kind="audio",
                    filename=filename,
                    mime_type="audio/mpeg",
                    url=asset_url(
                        req.project_id,
                        asset_id,
                        api_prefix=getattr(req, "api_prefix", "/api/projects")
                        or "/api/projects",
                    ),
                    meta={
                        "path": str(path),
                        "mood": mood,
                        "provider": self.name,
                        "model": model_used,
                        "instrumental": True,
                        "bytes": len(audio_bytes),
                    },
                ),
                duration_sec=round(out_dur, 2),
                mood=mood,
                provider=self.name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MiniMax BGM failed, fallback procedural: %s", exc)
            fallback = await ProceduralBGMProvider().generate(
                BGMRequest(
                    project_id=req.project_id,
                    mood="melancholic piano with rain",
                    duration_sec=duration,
                    api_prefix=getattr(req, "api_prefix", "/api/projects")
                    or "/api/projects",
                    storage_key=getattr(req, "storage_key", None),
                )
            )
            # keep short provider tag (avoid huge validation/log spam)
            fallback.provider = "procedural(fallback)"
            return fallback

    async def _generate_instrumental(
        self, prompt: str
    ) -> tuple[bytes, float | None, str]:
        api_key = _minimax_api_key()
        base = _minimax_base()
        url = f"{base}/v1/music_generation"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        last_err: Exception | None = None
        async with httpx.AsyncClient(timeout=240.0, follow_redirects=True) as client:
            for model in MUSIC_MODELS:
                for output_format in ("hex", "url"):
                    body = {
                        "model": model,
                        "prompt": prompt,
                        "is_instrumental": True,
                        "output_format": output_format,
                        "audio_setting": {
                            "sample_rate": 44100,
                            "bitrate": 128000,
                            "format": "mp3",
                        },
                    }
                    try:
                        data = await _minimax_post_json(
                            client, url, headers=headers, body=body, retries=3
                        )
                        payload = data.get("data") or {}
                        extra = data.get("extra_info") or {}
                        ms = extra.get("music_duration")
                        dur = (float(ms) / 1000.0) if ms else None

                        audio_hex = payload.get("audio") or ""
                        if audio_hex:
                            return bytes.fromhex(audio_hex), dur, model

                        audio_url = (
                            payload.get("audio_url")
                            or payload.get("url")
                            or ""
                        )
                        if audio_url:
                            res = await client.get(str(audio_url))
                            res.raise_for_status()
                            return res.content, dur, model

                        raise RuntimeError("MiniMax 配乐返回中无音频数据")
                    except Exception as exc:  # noqa: BLE001
                        last_err = exc
                        logger.warning(
                            "MiniMax music %s/%s failed: %s",
                            model,
                            output_format,
                            exc,
                        )
                        continue
        assert last_err
        raise last_err
