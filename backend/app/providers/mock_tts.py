from __future__ import annotations

import asyncio

from app.config import get_settings
from app.models.schemas import AssetRef, TTSResult
from app.providers.base import TTSRequest
from app.providers.media_utils import (
    asset_url,
    new_asset_id,
    project_dir,
    write_tone_wav,
)


class MockTTSProvider:
    name = "mock"

    async def generate(self, req: TTSRequest) -> TTSResult:
        await asyncio.sleep(0.3)
        settings = get_settings()
        duration = req.storyboard.total_sec or req.script.total_sec or 60.0
        asset_id = new_asset_id()
        filename = f"tts_{asset_id}.wav"
        path = project_dir(settings, req.project_id) / filename
        # Soft mid tone as stand-in for narration
        write_tone_wav(path, duration_sec=duration, frequency=392.0, volume=0.12)
        asset = AssetRef(
            id=asset_id,
            kind="audio",
            filename=filename,
            mime_type="audio/wav",
            url=asset_url(req.project_id, asset_id),
            meta={"path": str(path), "voice": req.voice, "provider": self.name},
        )
        return TTSResult(asset=asset, duration_sec=round(duration, 2), provider=self.name)
