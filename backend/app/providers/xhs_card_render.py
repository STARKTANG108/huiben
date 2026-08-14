from __future__ import annotations

"""Premium full-bleed content-viz cards for 小红绿书."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import get_settings
from app.models.xhs_schemas import XhsAsset, XhsCard
from app.providers.media_utils import new_asset_id, project_dir

CARD_SIZE = (1188, 1584)

_BOLD_FONTS = [
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
]
_REG_FONTS = [
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/STHeiti Light.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
]

_THEMES = (
    {
        "name": "ink",
        "bg_top": (16, 18, 24),
        "bg_bot": (32, 36, 48),
        "hook_bg": (240, 88, 56),
        "hook_fg": (255, 255, 255),
        "title_fg": (255, 248, 240),
        "row_bg": (255, 252, 248),
        "row_alt": (245, 242, 236),
        "body": (24, 26, 30),
        "muted": (150, 154, 164),
        "accent": (255, 196, 72),
        "chip_bg": (255, 196, 72),
        "chip_fg": (24, 26, 30),
        "watermark": (255, 255, 255),
    },
    {
        "name": "paper",
        "bg_top": (255, 246, 236),
        "bg_bot": (255, 228, 204),
        "hook_bg": (20, 20, 22),
        "hook_fg": (255, 220, 64),
        "title_fg": (20, 20, 22),
        "row_bg": (255, 255, 255),
        "row_alt": (255, 248, 240),
        "body": (28, 28, 28),
        "muted": (120, 110, 100),
        "accent": (232, 64, 64),
        "chip_bg": (232, 64, 64),
        "chip_fg": (255, 255, 255),
        "watermark": (0, 0, 0),
    },
    {
        "name": "sage",
        "bg_top": (228, 240, 234),
        "bg_bot": (196, 220, 208),
        "hook_bg": (18, 92, 68),
        "hook_fg": (255, 255, 255),
        "title_fg": (14, 44, 32),
        "row_bg": (255, 255, 255),
        "row_alt": (238, 248, 242),
        "body": (22, 40, 32),
        "muted": (90, 110, 100),
        "accent": (18, 92, 68),
        "chip_bg": (18, 92, 68),
        "chip_fg": (255, 255, 255),
        "watermark": (18, 92, 68),
    },
)


def _load_font(candidates: list[tuple[str, int]], size: int) -> ImageFont.ImageFont:
    for path, index in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=index)
            except OSError:
                try:
                    return ImageFont.truetype(path, size=size)
                except OSError:
                    continue
    return ImageFont.load_default()


def _bold(size: int) -> ImageFont.ImageFont:
    return _load_font(_BOLD_FONTS, size)


def _reg(size: int) -> ImageFont.ImageFont:
    return _load_font(_REG_FONTS, size)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_w: int,
    *,
    max_lines: int = 6,
) -> list[str]:
    text = (text or "").replace("\n", " ").strip()
    if not text:
        return []
    lines: list[str] = []
    buf = ""
    for ch in text:
        trial = buf + ch
        if draw.textlength(trial, font=font) <= max_w:
            buf = trial
        else:
            if buf:
                lines.append(buf)
            buf = ch
            if len(lines) >= max_lines:
                break
    if buf and len(lines) < max_lines:
        lines.append(buf)
    if len(lines) == max_lines and sum(len(x) for x in lines) < len(text):
        last = lines[-1]
        if len(last) > 1:
            lines[-1] = last[:-1] + "…"
    return lines


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bot: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        # ease
        t = t * t * (3 - 2 * t)
        rgb = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = rgb  # type: ignore[assignment]
    return img


def _round_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _circle(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    r: int,
    fill: tuple[int, int, int],
) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)


def _asset_url(project_id: str, asset_id: str) -> str:
    return f"/api/xhs/{project_id}/assets/{asset_id}"


def _fit_point_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    max_h: int,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    """Pick largest font that fits the row."""
    for size in range(56, 28, -2):
        font = _bold(size)
        lines = _wrap(draw, text, font, max_w, max_lines=2)
        line_h = size + 12
        if len(lines) * line_h <= max_h - 4:
            return font, lines, line_h
    font = _bold(30)
    lines = _wrap(draw, text, font, max_w, max_lines=2)
    return font, lines, 42


def render_content_card(
    *,
    project_id: str,
    card: XhsCard,
    card_total: int,
) -> XhsAsset:
    w, h = CARD_SIZE
    theme = _THEMES[card.index % len(_THEMES)]

    base = _gradient(CARD_SIZE, theme["bg_top"], theme["bg_bot"])
    overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-200, -100, 640, 560), fill=(*theme["accent"], 40))
    od.ellipse((w - 520, h - 640, w + 220, h + 120), fill=(*theme["hook_bg"], 36))
    overlay = overlay.filter(ImageFilter.GaussianBlur(100))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    margin = 44
    x0 = margin
    cw = w - margin * 2
    y = 36

    # brand
    brand_font = _bold(26)
    brand = "小红绿书"
    bw = int(draw.textlength(brand, font=brand_font)) + 40
    _round_rect(draw, (x0, y, x0 + bw, y + 46), 23, theme["chip_bg"])
    draw.text((x0 + 20, y + 10), brand, fill=theme["chip_fg"], font=brand_font)
    page_font = _bold(28)
    page = f"{card.index + 1}/{card_total}"
    pw = draw.textlength(page, font=page_font)
    draw.text((w - margin - pw, y + 8), page, fill=theme["muted"], font=page_font)
    y += 62

    # —— giant hook: ~38% canvas ——
    hook = (card.hook or card.title or "核心要点").strip()
    hook_font = _bold(88)
    hook_lines = _wrap(draw, hook, hook_font, cw - 40, max_lines=2)
    hook_h = max(320, 64 + len(hook_lines) * 104 + 48)
    _round_rect(draw, (x0, y, x0 + cw, y + hook_h), 40, theme["hook_bg"])
    draw.rectangle((x0, y, x0 + 18, y + hook_h), fill=theme["accent"])
    # decorative corner mark
    draw.polygon(
        [(x0 + cw - 90, y), (x0 + cw, y), (x0 + cw, y + 90)],
        fill=theme["accent"],
    )
    hy = y + (hook_h - len(hook_lines) * 104) / 2
    for line in hook_lines:
        tw = draw.textlength(line, font=hook_font)
        draw.text((x0 + (cw - tw) / 2, hy), line, fill=theme["hook_fg"], font=hook_font)
        hy += 104
    y += hook_h + 26

    title = (card.title or "").strip()
    if title and title != hook:
        title_font = _bold(36)
        for line in _wrap(draw, title, title_font, cw, max_lines=2):
            draw.text((x0, y), line, fill=theme["title_fg"], font=title_font)
            y += 46
        y += 8

    points = [p.strip() for p in card.points if p.strip()][:4] or ["暂无要点"]
    footer_h = 76
    n = len(points)
    gap = 14
    # compact dense rows — not stretched empty
    row_h = 152
    block_h = n * row_h + (n - 1) * gap
    avail = h - y - footer_h - 12
    if block_h > avail:
        row_h = max(118, (avail - gap * (n - 1)) // n)
        block_h = n * row_h + (n - 1) * gap
    # pin block toward bottom for balance if leftover
    if avail - block_h > 40:
        y += min(48, (avail - block_h) // 3)

    num_font = _bold(34)
    ghost_font = _bold(120)

    for i, point in enumerate(points):
        top = y + i * (row_h + gap)
        bot = top + row_h
        fill = theme["row_bg"] if i % 2 == 0 else theme["row_alt"]

        sh = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle(
            (x0 + 3, top + 6, x0 + cw + 3, bot + 6),
            radius=26,
            fill=(0, 0, 0, 50),
        )
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        base = Image.alpha_composite(base.convert("RGBA"), sh).convert("RGB")
        draw = ImageDraw.Draw(base)

        _round_rect(draw, (x0, top, x0 + cw, bot), 26, fill)
        draw.rectangle((x0, top, x0 + 12, bot), fill=theme["accent"])

        ghost = str(i + 1)
        gw = draw.textlength(ghost, font=ghost_font)
        wm = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        wd = ImageDraw.Draw(wm)
        wd.text(
            (x0 + cw - gw - 16, top + (row_h - 120) / 2),
            ghost,
            fill=(*theme["watermark"], 16),
            font=ghost_font,
        )
        base = Image.alpha_composite(base.convert("RGBA"), wm).convert("RGB")
        draw = ImageDraw.Draw(base)

        cx, cy = x0 + 62, top + row_h // 2
        _circle(draw, cx, cy, 36, theme["accent"])
        nw = draw.textlength(str(i + 1), font=num_font)
        draw.text((cx - nw / 2, cy - 18), str(i + 1), fill=(255, 255, 255), font=num_font)

        max_tw = cw - 170 - 60
        point_font, lines, line_h = _fit_point_text(draw, point, max_tw, row_h - 28)
        block = len(lines) * line_h
        ty = top + (row_h - block) / 2
        for line in lines:
            draw.text((x0 + 116, ty), line, fill=theme["body"], font=point_font)
            ty += line_h

    draw.rectangle((0, h - footer_h, w, h), fill=theme["hook_bg"])
    foot_font = _reg(26)
    footer = (card.footer or "原文提炼 · 内容可视化").strip()[:30]
    draw.text((margin, h - 48), footer, fill=theme["hook_fg"], font=foot_font)
    dots_y = h - 36
    span = card_total * 14 + max(0, card_total - 1) * 16
    dx = w - margin - span
    for i in range(card_total):
        active = i == card.index
        c = (255, 220, 80) if active and theme["name"] == "ink" else (
            theme["accent"] if active else (255, 255, 255)
        )
        _circle(draw, int(dx + i * 30 + 7), dots_y, 8 if active else 5, c)

    settings = get_settings()
    asset_id = new_asset_id()
    filename = f"viz_{card.index:02d}_{asset_id}.png"
    path = project_dir(settings, f"xhs/{project_id}") / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    base.save(path, format="PNG", optimize=True)

    return XhsAsset(
        id=asset_id,
        kind="image",
        filename=filename,
        mime_type="image/png",
        url=_asset_url(project_id, asset_id),
        meta={
            "path": str(path),
            "index": card.index,
            "aspect": "3:4",
            "size": f"{w}x{h}",
            "renderer": "content_viz_v5",
            "theme": theme["name"],
        },
    )
