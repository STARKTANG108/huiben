"""Stub providers — implement generate() and register in registry to go live."""

from __future__ import annotations

from app.models.schemas import Story
from app.providers.base import StoryRequest


class OpenAIStoryProvider:
    """Placeholder for OpenAI / compatible chat models."""

    name = "openai"

    async def generate(self, req: StoryRequest) -> Story:
        raise NotImplementedError(
            "OpenAIStoryProvider is a stub. Implement generate() and set PROVIDER_STORY=openai."
        )
