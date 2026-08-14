from __future__ import annotations

"""Custom OpenAI-compatible image & TTS — fill Base URL + API Key in settings."""

import base64
import re

import httpx

from app.config import get_settings
from app.models.schemas import AssetRef, TTSResult
from app.providers.base import ImageRequest, TTSRequest
from app.providers.media_utils import (
    asset_url,
    ensure_portrait_9_16,
    new_asset_id,
    project_dir,
)
from app.runtime_config import runtime_config

# Keep prompts short — jimeng/suxi rejects long/complex payloads with vague 400s
_STYLE = (
    "soft watercolor children's picture book, pastel washes, consistent style, "
    "no text, no watermark, vertical portrait composition"
)


def _build_prompt(req: ImageRequest) -> str:
    narration = (req.shot.narration or "").strip()
    # Prefer a compact scene description; strip duplicated lock boilerplate from storyboard
    raw = (req.shot.visual_prompt or "").strip()
    # Drop oversized prefix locks if present — keep the trailing "Scene:" part when possible
    scene = raw
    for marker in ("Scene:", "scene:", "Detailed scene:"):
        if marker in raw:
            scene = raw.split(marker, 1)[-1].strip()
            break
    # If still huge, take narration-driven scene
    if len(scene) > 280:
        scene = scene[:280]

    lock = (req.characters_lock or "").strip()
    # Compress character lock
    if lock.startswith("CHARACTER LOCK"):
        lock = lock.replace(
            "CHARACTER LOCK (must match exactly, do not invent humans unless listed): ",
            "characters: ",
        )
    if len(lock) > 220:
        lock = lock[:220]

    chars = ", ".join(req.shot.characters_in_shot) if req.shot.characters_in_shot else ""
    parts = [
        _STYLE,
        f"narration: {narration}" if narration else "",
        f"draw only: {chars}" if chars else "",
        f"{lock}" if lock else "",
        f"scene: {scene}" if scene else "",
    ]
    prompt = ". ".join(p for p in parts if p)
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt[:750]


class CustomOpenAIImageProvider:
    name = "custom_openai"

    async def generate(self, req: ImageRequest) -> AssetRef:
        cfg = runtime_config.get()
        if not cfg.image_api_key:
            raise RuntimeError("请在模型配置里填写「生图 API Key」")
        if not cfg.image_api_key.isascii() or not cfg.image_api_key.strip().startswith(
            ("sk-", "key-", "api-")
        ):
            raise RuntimeError(
                "生图 API Key 无效（可能被误存成报错文案）。"
                "请到「模型配置」重新粘贴 suxi 的 sk- 开头 Key"
            )
        base = (cfg.image_base_url or "https://new.suxi.ai/v1").rstrip("/")
        model = cfg.image_model or "jimeng-3.0"
        settings = get_settings()
        prompt = _build_prompt(req)
        # Prefer English-heavy prompt for gateway stability
        prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")

        # jimeng via suxi: minimal body is most reliable (size often causes 400)
        bodies = [
            {"model": model, "prompt": prompt, "n": 1},
            {"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"},
            {
                "model": model,
                "prompt": f"{_STYLE}. {req.shot.narration}"[:400],
                "n": 1,
            },
        ]

        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            last_err = ""
            data = None
            for body in bodies:
                res = await client.post(
                    f"{base}/images/generations",
                    headers={
                        "Authorization": f"Bearer {cfg.image_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if res.status_code < 400:
                    data = res.json()
                    break
                last_err = f"{res.status_code}: {res.text[:300]}"

            if data is None:
                raise RuntimeError(f"生图失败 ({last_err})")

            item = (data.get("data") or [{}])[0]
            b64 = item.get("b64_json")
            url_out = item.get("url")
            asset_id = new_asset_id()
            filename = f"shot_{req.shot.index:02d}_{asset_id}.png"
            path = project_dir(settings, req.project_id) / filename
            if b64:
                path.write_bytes(base64.b64decode(b64))
            elif url_out:
                img = await client.get(url_out)
                if img.status_code >= 400:
                    raise RuntimeError(f"下载生图失败 ({img.status_code})")
                path.write_bytes(img.content)
            else:
                raise RuntimeError("生图返回中无图片数据")

        # Force 9:16 full-bleed locally (API size params are unreliable on suxi/jimeng)
        ensure_portrait_9_16(path)

        return AssetRef(
            id=asset_id,
            kind="image",
            filename=filename,
            mime_type="image/png",
            url=asset_url(req.project_id, asset_id),
            meta={
                "shot_index": req.shot.index,
                "path": str(path),
                "provider": self.name,
                "model": model,
                "aspect": "9:16",
                "prompt_len": len(prompt),
            },
        )


class CustomOpenAITTSProvider:
    name = "custom_openai"

    async def generate(self, req: TTSRequest) -> TTSResult:
        from app.providers.edge_tts_provider import EdgeTTSProvider

        return await EdgeTTSProvider().generate(req)
