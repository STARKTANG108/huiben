from __future__ import annotations

"""Stock / B-roll stills for混剪 — reuses suxi image API from runtime_config."""

import base64
import re

import httpx

from app.config import get_settings
from app.models.cut_schemas import CutAsset
from app.providers.media_utils import ensure_cover_size, new_asset_id, project_dir
from app.runtime_config import runtime_config

# 9:16 vertical
CUT_SIZE = (1080, 1920)
CUT_SIZE_LABEL = "1080x1920"

_NEGATIVE = (
    "watermark, logo, text overlay, subtitle, garbled text, extra limbs, "
    "deformed hands, low quality, blurry, AI watermark"
)


def _asset_url(project_id: str, asset_id: str) -> str:
    return f"/api/cut/{project_id}/assets/{asset_id}"


async def generate_cut_still(
    *,
    project_id: str,
    index: int,
    image_prompt: str,
    scene_id: str,
) -> CutAsset:
    cfg = runtime_config.get()
    if not cfg.image_api_key:
        raise RuntimeError("请先在「模型配置」填写生图 API Key（与绘本共用）")
    if not cfg.image_api_key.isascii() or not cfg.image_api_key.strip().startswith(
        ("sk-", "key-", "api-")
    ):
        raise RuntimeError("生图 API Key 无效，请到模型配置重新粘贴 suxi 的 sk- Key")

    base = (cfg.image_base_url or "https://new.suxi.ai/v1").rstrip("/")
    model = cfg.image_model or "jimeng-3.0"
    settings = get_settings()

    prompt = re.sub(r"\s+", " ", (image_prompt or "").strip())[:2200]
    if not prompt:
        raise RuntimeError("画面提示词为空")

    bodies = [
        {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": CUT_SIZE_LABEL,
            "watermark": False,
        },
        {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "720x1280",
            "watermark": False,
        },
        {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": "9:16",
            "watermark": False,
        },
        {"model": model, "prompt": prompt, "n": 1, "watermark": False},
        {"model": model, "prompt": prompt, "n": 1},
        {
            "model": model,
            "prompt": f"{prompt}. Avoid: {_NEGATIVE}",
            "n": 1,
            "watermark": False,
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
        filename = f"cut_{index:02d}_{asset_id}.png"
        path = project_dir(settings, f"cut/{project_id}") / filename
        if b64:
            path.write_bytes(base64.b64decode(b64))
        elif url_out:
            img = await client.get(url_out)
            if img.status_code >= 400:
                raise RuntimeError(f"下载生图失败 ({img.status_code})")
            path.write_bytes(img.content)
        else:
            raise RuntimeError("生图返回中无图片数据")

    ensure_cover_size(path, CUT_SIZE)
    return CutAsset(
        id=asset_id,
        kind="image",
        filename=filename,
        mime_type="image/png",
        url=_asset_url(project_id, asset_id),
        meta={
            "path": str(path),
            "index": index,
            "scene_id": scene_id,
            "model": model,
            "aspect": "9:16",
            "size": CUT_SIZE_LABEL,
        },
    )
