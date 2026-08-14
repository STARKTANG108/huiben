from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime_config import (
    IMAGE_PRESETS,
    MINIMAX_VOICES,
    TEXT_PRESETS,
    TTS_PRESETS,
    runtime_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    text_preset: Literal["mock", "gemini", "groq", "deepseek", "custom"] | None = None
    text_base_url: str | None = None
    text_api_key: str | None = None
    text_model: str | None = None

    image_preset: Literal["mock", "pollinations", "custom", "minimax", "flux"] | None = None
    image_base_url: str | None = None
    image_api_key: str | None = None
    image_model: str | None = None

    tts_preset: Literal["mock", "edge", "custom", "minimax"] | None = None
    tts_base_url: str | None = None
    tts_api_key: str | None = None
    tts_model: str | None = None
    tts_voice: str | None = None
    book_tts_voice: str | None = None

    minimax_api_key: str | None = None
    toapis_api_key: str | None = None
    toapis_base_url: str | None = None
    toapis_video_model: str | None = None


@router.get("")
async def get_settings() -> dict[str, Any]:
    return runtime_config.public_view()


@router.put("")
async def put_settings(body: SettingsUpdate) -> dict[str, Any]:
    patch = body.model_dump(exclude_none=True)
    # When switching to a named free preset, refill URL/model from catalog
    if "text_preset" in patch and patch["text_preset"] in TEXT_PRESETS:
        p = TEXT_PRESETS[patch["text_preset"]]
        if patch["text_preset"] != "custom":
            patch.setdefault("text_base_url", p["base_url"])
            patch.setdefault("text_model", p["model"])
            # Force apply preset URL/model on preset change
            patch["text_base_url"] = p["base_url"]
            patch["text_model"] = p["model"]
    if "image_preset" in patch and patch["image_preset"] in IMAGE_PRESETS:
        p = IMAGE_PRESETS[patch["image_preset"]]
        if patch["image_preset"] != "custom":
            patch["image_base_url"] = p["base_url"]
            patch["image_model"] = p["model"]
    if "tts_preset" in patch and patch["tts_preset"] in TTS_PRESETS:
        p = TTS_PRESETS[patch["tts_preset"]]
        if patch["tts_preset"] == "edge":
            patch["tts_base_url"] = ""
            patch["tts_model"] = ""
        elif patch["tts_preset"] == "minimax":
            patch["tts_base_url"] = p["base_url"]
            patch["tts_model"] = p["model"]
            if not patch.get("tts_voice") or str(patch.get("tts_voice", "")).startswith(
                "zh-CN-"
            ):
                patch["tts_voice"] = "Chinese (Mandarin)_Warm_Girl"
    try:
        runtime_config.update(patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return runtime_config.public_view()


@router.get("/presets")
async def list_presets() -> dict[str, Any]:
    return {
        "text": TEXT_PRESETS,
        "image": IMAGE_PRESETS,
        "tts": TTS_PRESETS,
        "minimax_voices": MINIMAX_VOICES,
    }
