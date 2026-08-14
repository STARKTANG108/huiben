"""Flux image generation via CatsAPI (flux2Pro)."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app.runtime_config import runtime_config

logger = logging.getLogger(__name__)

CATS_API_BASE = "https://catsapi.com/api"
DEFAULT_MODEL = "flux2Pro"


class FluxError(Exception):
    pass


def _token() -> str:
    for env_key in ("CATS_API_TOKEN", "FLUX_API_TOKEN", "REPLICATE_API_TOKEN"):
        env_token = (os.environ.get(env_key) or "").strip()
        if env_token:
            return env_token
    cfg = runtime_config.get()
    dedicated = (cfg.replicate_api_token or "").strip()
    if dedicated:
        return dedicated
    token = (cfg.image_api_key or "").strip()
    if cfg.image_preset == "flux" and token:
        return token
    if token.startswith(("cats-", "r8_")):
        return token
    raise FluxError(
        "custom-book 需要 Flux（CatsAPI）。请在定制绘本页填写 API Key（cats-…）"
    )


def _model() -> str:
    cfg = runtime_config.get()
    if cfg.image_preset == "flux":
        model = (cfg.image_model or "").strip()
        if model and "/" not in model:
            return model
    env_model = (os.environ.get("FLUX_MODEL") or "").strip()
    if env_model and "/" not in env_model:
        return env_model
    return DEFAULT_MODEL


def _cats_aspect(aspect_ratio: str) -> str:
    """Map common ratios to CatsAPI aspectRatio enum."""
    ar = (aspect_ratio or "").strip().lower()
    if ar in ("square", "1:1"):
        return "square"
    if ar in ("landscape", "16:9", "4:3", "3:2"):
        return "landscape"
    if ar in ("portrait", "3:4", "2:3", "9:16"):
        return "portrait"
    return "portrait"


async def generate_flux_image(
    *,
    prompt: str,
    out_path: Path,
    aspect_ratio: str = "3:4",
    reference_image_urls: list[str] | None = None,
    rewrite_prompt: bool = False,
) -> Path:
    """
    generate_character / generate_page backend.
    CatsAPI: POST /api/tasks → poll GET /api/tasks/{id} → download result_images.
    """
    del reference_image_urls  # V1 text-to-image only
    token = _token()
    model = _model()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt[:2000],
        "task_type": "image",
        "num_images": 1,
        "params": {
            "rewritePrompt": bool(rewrite_prompt),
            "aspectRatio": _cats_aspect(aspect_ratio),
        },
    }

    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True, trust_env=False) as client:
        res = await client.post(f"{CATS_API_BASE}/tasks", headers=headers, json=body)
        if res.status_code >= 400:
            raise FluxError(f"Flux 创建任务失败 ({res.status_code}): {res.text[:400]}")

        data = res.json()
        task_id = data.get("id")
        if not task_id:
            raise FluxError(f"Flux 未返回 task id: {data}")

        if data.get("status") != "completed":
            data = await _poll_task(client, str(task_id), headers)

        if data.get("status") != "completed":
            err = data.get("error_message") or data.get("status") or "unknown"
            raise FluxError(f"Flux 失败: {err}")

        image_url = _first_image_url(data.get("result_images"))
        if not image_url:
            raise FluxError(f"Flux 未返回图片 URL: {data}")

        img_res = await client.get(image_url)
        if img_res.status_code >= 400:
            raise FluxError(f"下载 Flux 图片失败 ({img_res.status_code})")
        out_path.write_bytes(img_res.content)

    await asyncio.sleep(0.05)
    return out_path


async def _poll_task(
    client: httpx.AsyncClient,
    task_id: str,
    headers: dict[str, str],
    *,
    max_wait_sec: float = 180.0,
) -> dict[str, Any]:
    url = f"{CATS_API_BASE}/tasks/{task_id}"
    elapsed = 0.0
    while elapsed < max_wait_sec:
        res = await client.get(url, headers=headers)
        if res.status_code >= 400:
            raise FluxError(f"Flux 轮询失败 ({res.status_code}): {res.text[:300]}")
        data = res.json()
        status = (data.get("status") or "").lower()
        if status == "completed":
            return data
        if status in ("failed", "error", "canceled", "cancelled"):
            raise FluxError(
                f"Flux 失败: {data.get('error_message') or status}"
            )
        await asyncio.sleep(2.0)
        elapsed += 2.0
    raise FluxError("Flux 生成超时")


def _first_image_url(result_images: Any) -> str | None:
    if isinstance(result_images, str) and result_images.startswith("http"):
        return result_images
    if isinstance(result_images, list) and result_images:
        first = result_images[0]
        if isinstance(first, str) and first.startswith("http"):
            return first
        if isinstance(first, dict):
            for key in ("url", "image", "image_url"):
                val = first.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    return val
    return None


async def generate_character(
    *,
    character_prompt: str,
    view_hint: str,
    out_path: Path,
) -> Path:
    from app.services.custom_book.prompt_safety import (
        FLUX_STYLE_EN,
        flux_character_lock,
        is_moderation_error,
        ultra_safe_character_prompt,
    )

    locked = flux_character_lock(character_prompt)
    from app.services.custom_book.prompt_safety import sanitize_flux_prompt

    view = sanitize_flux_prompt(view_hint)
    prompt = (
        f"{FLUX_STYLE_EN}. Character design. {locked}. "
        f"View: {view}. Simple clean background."
    )
    try:
        return await generate_flux_image(
            prompt=prompt, out_path=out_path, aspect_ratio="3:4"
        )
    except FluxError as exc:
        if not is_moderation_error(str(exc)):
            raise
        logger.warning("character moderated, retry ultra-safe: %s", exc)
        safe = ultra_safe_character_prompt(character_prompt, view_hint)
        return await generate_flux_image(
            prompt=safe,
            out_path=out_path,
            aspect_ratio="3:4",
            rewrite_prompt=True,
        )


async def generate_page(
    *,
    character_prompt: str,
    scene_prompt: str,
    emotion: str,
    out_path: Path,
) -> Path:
    from app.services.custom_book.prompt_safety import (
        FLUX_STYLE_EN,
        flux_character_lock,
        is_moderation_error,
        sanitize_flux_prompt,
        ultra_safe_character_prompt,
        with_safe_scene,
    )

    locked = flux_character_lock(character_prompt)
    scene = with_safe_scene(scene_prompt)
    emo = sanitize_flux_prompt(emotion or "warm")
    if emo.lower() in ("crying", "cry", "sob", "a little sad") or not emo:
        emo = "gentle soft mood"
    prompt = (
        f"{FLUX_STYLE_EN}. Same character: {locked}. "
        f"Scene: {scene}. Mood: {emo}."
    )
    try:
        return await generate_flux_image(
            prompt=prompt, out_path=out_path, aspect_ratio="3:4"
        )
    except FluxError as exc:
        if not is_moderation_error(str(exc)):
            raise
        logger.warning("page moderated, retry ultra-safe: %s", exc)
        safe = (
            f"{ultra_safe_character_prompt(character_prompt, 'story scene')}. "
            f"{sanitize_flux_prompt(scene_prompt)[:120]}"
        )
        return await generate_flux_image(
            prompt=safe,
            out_path=out_path,
            aspect_ratio="3:4",
            rewrite_prompt=True,
        )


async def check_similarity(_photo_path: Path, _generated_path: Path) -> float | None:
    """Reserved for InstantID / face embedding. MVP returns None."""
    return None


class FluxImageProvider:
    """主流水线（绘本视频/书籍/人生）生图：走 CatsAPI flux2Pro。

    与 custom-book 共用 replicate_api_token / CatsAPI Token；
    仅在用户把「模型配置 → 生图」显式选为 Flux 时启用。
    """

    name = "flux"

    async def generate(self, req: Any) -> Any:
        from app.config import get_settings
        from app.models.schemas import AssetRef
        from app.providers.media_utils import (
            asset_url,
            ensure_portrait_9_16,
            new_asset_id,
            project_dir,
        )
        from app.services.custom_book.prompt_safety import (
            FLUX_STYLE_EN,
            flux_character_lock,
            sanitize_flux_prompt,
        )

        lock = (
            flux_character_lock(req.characters_lock)
            if (req.characters_lock or "").strip()
            else ""
        )
        scene = sanitize_flux_prompt(req.shot.visual_prompt or "")
        mood = sanitize_flux_prompt(req.shot.mood or "warm")
        prompt = f"{FLUX_STYLE_EN}. {lock}. Scene: {scene}. Mood: {mood}."

        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"shot_{req.shot.index:02d}_{asset_id}.png"
        out = project_dir(settings, req.storage_key or req.project_id) / filename
        await generate_flux_image(
            prompt=prompt,
            out_path=out,
            aspect_ratio="9:16",
        )
        ensure_portrait_9_16(out)
        return AssetRef(
            id=asset_id,
            kind="image",
            filename=filename,
            mime_type="image/png",
            url=asset_url(
                req.project_id,
                asset_id,
                api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
            ),
            meta={
                "shot_index": req.shot.index,
                "path": str(out),
                "provider": self.name,
                "aspect": "9:16",
            },
        )
