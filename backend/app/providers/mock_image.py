from __future__ import annotations

import asyncio

from app.config import get_settings
from app.models.schemas import AssetRef
from app.providers.base import ImageRequest
from app.providers.media_utils import (
    asset_url,
    ensure_portrait_9_16,
    new_asset_id,
    project_dir,
    write_placeholder_png,
)
from app.providers.style_lock import WATERCOLOR_STYLE_EN

PALETTE = [
    (232, 145, 110),
    (120, 168, 140),
    (110, 148, 196),
    (196, 140, 168),
    (168, 140, 96),
    (100, 160, 170),
    (180, 120, 100),
    (140, 150, 110),
]


class MockImageProvider:
    name = "mock"

    async def generate(self, req: ImageRequest) -> AssetRef:
        await asyncio.sleep(0.2)
        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"shot_{req.shot.index:02d}_{asset_id}.png"
        path = project_dir(settings, req.project_id) / filename
        color = PALETTE[req.shot.index % len(PALETTE)]
        write_placeholder_png(
            path,
            title=f"镜头 {req.shot.index + 1}",
            subtitle=req.shot.narration[:48],
            color=color,
            size=(1080, 1920),
        )
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
                "style": "watercolor",
                "provider": self.name,
                "aspect": "9:16",
                "lock": WATERCOLOR_STYLE_EN[:40],
            },
        )
