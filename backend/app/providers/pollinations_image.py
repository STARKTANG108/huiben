from __future__ import annotations

import asyncio
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.models.schemas import AssetRef
from app.providers.base import ImageRequest
from app.providers.media_utils import (
    asset_url,
    ensure_portrait_9_16,
    new_asset_id,
    project_dir,
)
from app.providers.style_lock import WATERCOLOR_STYLE_EN
from app.runtime_config import runtime_config


class PollinationsImageProvider:
    """Free image generation via Pollinations (no API key)."""

    name = "pollinations"

    async def generate(self, req: ImageRequest) -> AssetRef:
        cfg = runtime_config.get()
        settings = get_settings()
        model = cfg.image_model or "flux"
        lock = req.characters_lock or ""
        prompt = (
            f"{WATERCOLOR_STYLE_EN}. {lock}. "
            f"Scene matching narration '{req.shot.narration}': {req.shot.visual_prompt}"
        )
        encoded = quote(prompt[:500], safe="")
        base = (cfg.image_base_url or "https://image.pollinations.ai").rstrip("/")
        url = (
            f"{base}/prompt/{encoded}"
            f"?width=1080&height=1920&model={quote(model)}&nologo=true"
        )

        asset_id = new_asset_id()
        filename = f"shot_{req.shot.index:02d}_{asset_id}.png"
        path = project_dir(settings, req.project_id) / filename

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code >= 400:
                raise RuntimeError(
                    f"Pollinations 生图失败 ({res.status_code}): {res.text[:200]}"
                )
            path.write_bytes(res.content)

        ensure_portrait_9_16(path)
        await asyncio.sleep(0.05)
        return AssetRef(
            id=asset_id,
            kind="image",
            filename=filename,
            mime_type="image/png",
            url=asset_url(req.project_id, asset_id),
            meta={
                "shot_index": req.shot.index,
                "path": str(path),
                "style": "watercolor",
                "provider": self.name,
                "model": model,
                "aspect": "9:16",
            },
        )
