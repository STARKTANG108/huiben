from __future__ import annotations

import asyncio

from app.config import get_settings
from app.models.schemas import AssetRef, BGMResult
from app.providers.base import BGMRequest
from app.providers.media_utils import (
    asset_url,
    new_asset_id,
    project_dir,
    write_tone_wav,
)

MOOD_FREQ = {
    "warm": 261.63,
    "adventure": 329.63,
    "calm": 196.0,
    "playful": 392.0,
}


class MockBGMProvider:
    name = "mock"

    async def generate(self, req: BGMRequest) -> BGMResult:
        await asyncio.sleep(0.2)
        settings = get_settings()
        freq = MOOD_FREQ.get(req.mood, 261.63)
        asset_id = new_asset_id()
        filename = f"bgm_{asset_id}.wav"
        path = project_dir(settings, req.project_id) / filename
        duration = write_tone_wav(
            path, duration_sec=req.duration_sec, frequency=freq, volume=0.06
        )
        asset = AssetRef(
            id=asset_id,
            kind="audio",
            filename=filename,
            mime_type="audio/wav",
            url=asset_url(req.project_id, asset_id),
            meta={"path": str(path), "mood": req.mood, "provider": self.name},
        )
        return BGMResult(
            asset=asset,
            duration_sec=round(duration, 2),
            mood=req.mood,
            provider=self.name,
        )
