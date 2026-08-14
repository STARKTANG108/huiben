"""Stub TTS provider for CosyVoice / similar APIs."""

from __future__ import annotations

from app.models.schemas import TTSResult
from app.providers.base import TTSRequest


class CosyVoiceTTSProvider:
    name = "cosyvoice"

    async def generate(self, req: TTSRequest) -> TTSResult:
        raise NotImplementedError(
            "CosyVoiceTTSProvider is a stub. Implement generate() and set PROVIDER_TTS=cosyvoice."
        )
