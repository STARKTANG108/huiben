from __future__ import annotations

from app.config import Settings, get_settings
from app.models.schemas import ProviderInfo, ProvidersResponse
from app.providers.base import (
    BGMProvider,
    ImageProvider,
    ScriptProvider,
    StoryboardProvider,
    StoryProvider,
    TTSProvider,
    VideoProvider,
)
from app.providers.custom_openai_media import (
    CustomOpenAIImageProvider,
    CustomOpenAITTSProvider,
)
from app.providers.edge_tts_provider import EdgeTTSProvider
from app.providers.llm_script import LLMScriptProvider
from app.providers.llm_story import LLMStoryProvider
from app.providers.llm_storyboard import LLMStoryboardProvider
from app.providers.minimax_media import MinimaxImageProvider, MinimaxTTSProvider
from app.providers.mock_bgm import MockBGMProvider  # noqa: F401 — available for future switch
from app.providers.mock_image import MockImageProvider
from app.providers.mock_script import MockScriptProvider
from app.providers.mock_story import MockStoryProvider
from app.providers.mock_storyboard import MockStoryboardProvider
from app.providers.mock_tts import MockTTSProvider
from app.providers.mock_video import MockVideoProvider
from app.providers.procedural_bgm import ProceduralBGMProvider
from app.providers.pollinations_image import PollinationsImageProvider
from app.runtime_config import runtime_config


def _text_is_llm() -> bool:
    return runtime_config.get().text_preset != "mock"


def get_story_provider(settings: Settings | None = None) -> StoryProvider:
    _ = settings or get_settings()
    return LLMStoryProvider() if _text_is_llm() else MockStoryProvider()


def get_script_provider(settings: Settings | None = None) -> ScriptProvider:
    _ = settings or get_settings()
    return LLMScriptProvider() if _text_is_llm() else MockScriptProvider()


def get_storyboard_provider(settings: Settings | None = None) -> StoryboardProvider:
    _ = settings or get_settings()
    return LLMStoryboardProvider() if _text_is_llm() else MockStoryboardProvider()


def get_image_provider(settings: Settings | None = None) -> ImageProvider:
    _ = settings or get_settings()
    preset = runtime_config.get().image_preset
    if preset == "minimax":
        return MinimaxImageProvider()
    if preset == "pollinations":
        return PollinationsImageProvider()
    if preset == "custom":
        return CustomOpenAIImageProvider()
    return MockImageProvider()


def get_tts_provider(settings: Settings | None = None) -> TTSProvider:
    _ = settings or get_settings()
    preset = runtime_config.get().tts_preset
    if preset == "minimax":
        return MinimaxTTSProvider()
    if preset == "edge":
        return EdgeTTSProvider()
    if preset == "custom":
        return CustomOpenAITTSProvider()
    return MockTTSProvider()


def get_bgm_provider(settings: Settings | None = None) -> BGMProvider:
    _ = settings or get_settings()
    return ProceduralBGMProvider()


def get_video_provider(settings: Settings | None = None) -> VideoProvider:
    _ = settings or get_settings()
    return MockVideoProvider()


def list_providers(settings: Settings | None = None) -> ProvidersResponse:
    _ = settings or get_settings()
    cfg = runtime_config.get()
    text_current = f"llm:{cfg.text_preset}" if cfg.text_preset != "mock" else "mock"
    return ProvidersResponse(
        providers=[
            ProviderInfo(
                module="story",
                current=text_current,
                available=["mock", "deepseek", "gemini", "groq", "custom"],
            ),
            ProviderInfo(
                module="script",
                current=text_current,
                available=["mock", "deepseek", "gemini", "groq", "custom"],
            ),
            ProviderInfo(
                module="storyboard",
                current=text_current,
                available=["mock", "deepseek", "gemini", "groq", "custom"],
            ),
            ProviderInfo(
                module="image",
                current=cfg.image_preset,
                available=["mock", "minimax", "pollinations", "custom"],
            ),
            ProviderInfo(
                module="tts",
                current=cfg.tts_preset,
                available=["mock", "minimax", "edge", "custom"],
            ),
            ProviderInfo(module="bgm", current="procedural", available=["procedural", "mock"]),
            ProviderInfo(module="video", current="mock", available=["mock"]),
        ]
    )
