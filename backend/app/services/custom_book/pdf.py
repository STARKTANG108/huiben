from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.models.custom_book_schemas import OrderStatus, PageStatus
from app.services.custom_book.character import order_dir
from app.store.custom_book_db import custom_book_store

PAGE_SIZE = (1080, 1440)  # 3:4


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "ZCOOLKuaiLe-Regular.ttf"),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_cover(src: Path, size: tuple[int, int] = PAGE_SIZE) -> Image.Image:
    img = Image.open(src).convert("RGB")
    tw, th = size
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _wrap(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            trial = line + ch
            if draw.textlength(trial, font=font) <= max_w:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = ch
        lines.append(line)
    return lines or [""]


def _text_page(
    *,
    title: str,
    body: str,
    bg: tuple[int, int, int] = (255, 248, 240),
) -> Image.Image:
    img = Image.new("RGB", PAGE_SIZE, bg)
    draw = ImageDraw.Draw(img)
    title_font = _font(56)
    body_font = _font(36)
    tw, th = PAGE_SIZE
    title_lines = _wrap(title, title_font, draw, tw - 160)
    y = 180
    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((tw - w) / 2, y), line, fill=(58, 42, 34), font=title_font)
        y += 70
    y += 40
    for line in _wrap(body, body_font, draw, tw - 160):
        w = draw.textlength(line, font=body_font)
        draw.text(((tw - w) / 2, y), line, fill=(90, 70, 58), font=body_font)
        y += 52
    return img


def _story_page(image_path: Path, text: str) -> Image.Image:
    base = _fit_cover(image_path)
    overlay = Image.new("RGBA", PAGE_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    band_h = 280
    od.rectangle((0, PAGE_SIZE[1] - band_h, PAGE_SIZE[0], PAGE_SIZE[1]), fill=(255, 248, 240, 230))
    base = base.convert("RGBA")
    base = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(base)
    font = _font(32)
    y = PAGE_SIZE[1] - band_h + 36
    for line in _wrap(text, font, draw, PAGE_SIZE[0] - 100)[:5]:
        draw.text((50, y), line, fill=(58, 42, 34), font=font)
        y += 46
    return base


async def create_pdf(order_id: str) -> Path:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise RuntimeError("订单不存在")
    parent_message = (order.get("parent_message") or "").strip()
    if not parent_message:
        raise RuntimeError("请先填写父母寄语再生成 PDF")

    pages_rows = order.get("pages") or []
    if len(pages_rows) != 8:
        raise RuntimeError("需要 8 页故事")
    for p in pages_rows:
        if p.get("status") not in (PageStatus.ready.value, PageStatus.locked.value):
            raise RuntimeError(f"第 {p['page_no']} 页尚未完成")
        if not p.get("image_path"):
            raise RuntimeError(f"第 {p['page_no']} 页缺少图片")

    title = order.get("title") or f"{order['child_name']}的绘本"
    # Prefer full-body character as cover art if available
    cover_src: Path | None = None
    for asset in order.get("character_assets") or []:
        if asset.get("view_type") == "full" and asset.get("path"):
            cover_src = Path(asset["path"])
            break
    if cover_src is None and pages_rows[0].get("image_path"):
        cover_src = Path(pages_rows[0]["image_path"])

    sheets: list[Image.Image] = []
    if cover_src and cover_src.exists():
        cover = _fit_cover(cover_src)
        draw = ImageDraw.Draw(cover)
        # soft title band
        band = Image.new("RGBA", PAGE_SIZE, (0, 0, 0, 0))
        bd = ImageDraw.Draw(band)
        bd.rectangle((0, 80, PAGE_SIZE[0], 260), fill=(255, 248, 240, 210))
        cover = Image.alpha_composite(cover.convert("RGBA"), band).convert("RGB")
        draw = ImageDraw.Draw(cover)
        font = _font(52)
        for i, line in enumerate(_wrap(title, font, draw, PAGE_SIZE[0] - 120)[:3]):
            w = draw.textlength(line, font=font)
            draw.text(((PAGE_SIZE[0] - w) / 2, 120 + i * 60), line, fill=(58, 42, 34), font=font)
        sheets.append(cover)
    else:
        sheets.append(_text_page(title=title, body="儿童成长绘本"))

    for p in pages_rows:
        sheets.append(_story_page(Path(p["image_path"]), p.get("text") or ""))

    sheets.append(
        _text_page(
            title="父母寄语",
            body=parent_message,
            bg=(255, 250, 245),
        )
    )

    out = order_dir(order_id) / "book.pdf"
    first, rest = sheets[0], sheets[1:]
    first.save(out, "PDF", save_all=True, append_images=rest, resolution=150.0)
    custom_book_store.update_order(
        order_id,
        pdf_path=str(out),
        status=OrderStatus.pdf_ready.value,
        error=None,
    )
    return out
