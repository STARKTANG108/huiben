from __future__ import annotations

"""小红绿书卡片图：baoyu 风格提示词 + MiniMax image-01 出图。"""

import base64
import logging
import re
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.xhs_schemas import XhsAsset, XhsCard
from app.providers.media_utils import ensure_cover_size, new_asset_id, project_dir
from app.providers.minimax_media import (
    DEFAULT_BASE,
    DEFAULT_IMAGE_MODEL,
    _check_base_resp,
    _minimax_api_key,
    _minimax_base,
)
from app.runtime_config import runtime_config

logger = logging.getLogger(__name__)

CARD_SIZE = (1188, 1584)  # 3:4
MAX_PROMPT = 1500
MAX_REF_BYTES = 10 * 1024 * 1024


def build_baoyu_prompt(card: XhsCard, *, style: str = "notion", layout: str = "balanced") -> str:
    """Assemble prompt following baoyu-xhs-images prompt-assembly structure."""
    hook = (card.hook or card.title or "核心要点").strip()
    title = (card.title or "").strip()
    points = [p.strip() for p in card.points if p.strip()][:5]
    bullets = "\n".join(f"- {p}" for p in points)
    footer = (card.footer or "").strip()

    style_blurb = {
        "notion": (
            "Style: notion — minimalist hand-drawn line art, intellectual aesthetic, "
            "pure white / off-white background, black ink lines, pastel accents, "
            "maximum whitespace, clean stick-figure doodles."
        ),
        "bold": (
            "Style: bold — high impact, strong contrast, attention-grabbing headlines, "
            "flat color blocks, poster energy."
        ),
        "cute": (
            "Style: cute — sweet girly aesthetic, soft rounded shapes, pastel colors, "
            "adorable decorations."
        ),
        "fresh": (
            "Style: fresh — clean refreshing natural look, light greens and airy layout."
        ),
        "warm": (
            "Style: warm — cozy friendly approachable, soft peach and earth tones."
        ),
        "minimal": (
            "Style: minimal — ultra-clean sophisticated, sparse elegant composition."
        ),
        "sketch-notes": (
            "Style: sketch-notes — hand-drawn educational infographic, macaron pastels "
            "on warm cream, wobble lines, highlighter marks."
        ),
        "chalkboard": (
            "Style: chalkboard — colorful chalk on black board, educational classroom feel."
        ),
    }.get(style, "")

    layout_blurb = {
        "sparse": "Layout: sparse — 1-2 points, maximum visual impact, large title.",
        "balanced": "Layout: balanced — 3-4 points, clear hierarchy, comfortable scanning.",
        "dense": "Layout: dense — knowledge-card density, compact but readable.",
        "list": "Layout: list — numbered enumeration, ranking style.",
    }.get(layout, "Layout: balanced.")

    content = f"Main hook: 「{hook}」\n"
    if title and title != hook:
        content += f"Subtitle: 「{title}」\n"
    content += f"Key points:\n{bullets}\n"
    if footer:
        content += f"Footer: 「{footer}」\n"

    prompt = f"""Xiaohongshu infographic card, portrait 3:4, hand-drawn cartoon (NOT photo).
Clear correct Chinese text on image. No watermark, no logo, no English lorem.
{style_blurb}
{layout_blurb}
Text hierarchy: big hook, bold keywords, highlighter accents.
## Content (MUST appear clearly)
{content}"""
    prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip()
    if len(prompt) > MAX_PROMPT:
        # Prefer keeping Chinese content
        head = (
            "Xiaohongshu 3:4 infographic, hand-drawn, clear Chinese text, no watermark.\n"
            f"{style_blurb}\n{layout_blurb}\n## Content\n"
        )
        budget = MAX_PROMPT - len(head) - 20
        prompt = head + content[: max(200, budget)]
    return prompt[:MAX_PROMPT]


def _asset_url(project_id: str, asset_id: str) -> str:
    return f"/api/xhs/{project_id}/assets/{asset_id}"


def _subject_reference(ref_image: Path | None) -> list[dict] | None:
    if not ref_image or not ref_image.exists():
        return None
    raw = ref_image.read_bytes()
    if len(raw) > MAX_REF_BYTES:
        logger.warning("xhs ref image too large, skip subject_reference")
        return None
    ext = ref_image.suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(raw).decode("ascii")
    return [{"type": "character", "image_file": f"data:{mime};base64,{b64}"}]


async def generate_xhs_viz_via_baoyu(
    *,
    project_id: str,
    card: XhsCard,
    card_total: int,
    style: str = "notion",
    layout: str = "balanced",
    ref_image: Path | None = None,
) -> XhsAsset:
    """Generate card image via MiniMax (keeps baoyu-style prompt assembly)."""
    api_key = _minimax_api_key()
    cfg = runtime_config.get()
    model = (cfg.image_model or DEFAULT_IMAGE_MODEL).strip() or DEFAULT_IMAGE_MODEL
    if not model.startswith("image-"):
        model = DEFAULT_IMAGE_MODEL
    try:
        base = _minimax_base()
    except Exception:  # noqa: BLE001
        base = DEFAULT_BASE

    settings = get_settings()
    work = project_dir(settings, f"xhs/{project_id}")
    prompts_dir = work / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_baoyu_prompt(card, style=style, layout=layout)
    prompt_file = prompts_dir / f"{card.index:02d}-card.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    asset_id = new_asset_id()
    filename = f"viz_{card.index:02d}_{asset_id}.png"
    out_path = work / filename

    body: dict = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": "3:4",
        "response_format": "base64",
        "n": 1,
        "prompt_optimizer": True,
    }
    refs = _subject_reference(ref_image)
    if refs:
        body["subject_reference"] = refs

    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        res = await client.post(
            f"{base}/v1/image_generation",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if res.status_code >= 400:
            # Retry without subject_reference if ref caused failure
            if refs and res.status_code in (400, 422, 2013):
                body.pop("subject_reference", None)
                res = await client.post(
                    f"{base}/v1/image_generation",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            if res.status_code >= 400:
                raise RuntimeError(
                    f"MiniMax 小红绿书生图失败 ({res.status_code}): {res.text[:400]}"
                )
        data = res.json()
        _check_base_resp(data)

        payload = data.get("data") or {}
        b64_list = payload.get("image_base64") or []
        urls = payload.get("image_urls") or []
        if b64_list:
            raw_b64 = b64_list[0]
            if "," in raw_b64[:80]:
                raw_b64 = raw_b64.split(",", 1)[1]
            out_path.write_bytes(base64.b64decode(raw_b64))
        elif urls:
            img = await client.get(urls[0])
            if img.status_code >= 400:
                raise RuntimeError(f"下载 MiniMax 图片失败 ({img.status_code})")
            out_path.write_bytes(img.content)
        else:
            raise RuntimeError("MiniMax 生图返回中无图片数据")

    ensure_cover_size(out_path, CARD_SIZE)
    return XhsAsset(
        id=asset_id,
        kind="image",
        filename=filename,
        mime_type="image/png",
        url=_asset_url(project_id, asset_id),
        meta={
            "path": str(out_path),
            "index": card.index,
            "aspect": "3:4",
            "size": f"{CARD_SIZE[0]}x{CARD_SIZE[1]}",
            "renderer": "minimax",
            "style": style,
            "layout": layout,
            "prompt_file": str(prompt_file),
            "card_total": card_total,
            "model": model,
            "used_ref": bool(refs),
        },
    )
