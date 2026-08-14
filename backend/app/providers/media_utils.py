from __future__ import annotations

import math
import struct
import subprocess
import uuid
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings, get_settings


def new_asset_id() -> str:
    return uuid.uuid4().hex[:12]


def project_dir(settings: Settings, project_id: str) -> Path:
    path = settings.storage_path / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_url(
    project_id: str,
    asset_id: str,
    *,
    api_prefix: str = "/api/projects",
) -> str:
    return f"{api_prefix.rstrip('/')}/{project_id}/assets/{asset_id}"


def ensure_cover_size(path: Path, size: tuple[int, int]) -> None:
    """Center-crop / cover-resize image to an exact pixel size."""
    img = Image.open(path).convert("RGB")
    tw, th = size
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    img = img.crop((left, top, left + tw, top + th))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def ensure_portrait_9_16(path: Path, size: tuple[int, int] = (1080, 1920)) -> None:
    """Center-crop / cover-resize image to vertical 9:16 for full-screen phone video."""
    ensure_cover_size(path, size)


def write_placeholder_png(
    path: Path,
    *,
    title: str,
    subtitle: str,
    color: tuple[int, int, int],
    size: tuple[int, int] = (1080, 1920),
) -> None:
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    w, h = size
    draw.rounded_rectangle(
        (48, 48, w - 48, h - 48), radius=36, outline=(255, 255, 255), width=4
    )
    try:
        font_lg = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 48
        )
        font_sm = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 28
        )
    except OSError:
        font_lg = ImageFont.load_default()
        font_sm = font_lg

    draw.text((80, h // 2 - 60), title[:40], fill=(255, 255, 255), font=font_lg)
    draw.text((80, h // 2 + 20), subtitle[:60], fill=(255, 245, 230), font=font_sm)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def write_tone_wav(
    path: Path,
    *,
    duration_sec: float,
    frequency: float = 440.0,
    volume: float = 0.15,
    sample_rate: int = 22050,
) -> float:
    duration_sec = max(0.5, duration_sec)
    n_frames = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            t = i / sample_rate
            env = min(1.0, t * 4) * min(1.0, (duration_sec - t) * 4)
            sample = int(volume * env * 32767 * math.sin(2 * math.pi * frequency * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    return duration_sec


def _ffprobe_has_audio(path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return "audio" in (result.stdout or "").lower()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _ffprobe_duration_sec(path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return None
    return None


def compose_book_with_motion(
    motion_path: Path,
    still_paths: list[Path],
    still_durations: list[float],
    tts_path: Path | None,
    bgm_path: Path | None,
    output_path: Path,
    *,
    motion_sec: float = 8.0,
    keep_motion_audio: bool = True,
    motion_audio_volume: float = 0.42,
    bgm_volume: float = 0.13,
    width: int = 1080,
    height: int = 1920,
    timeout_sec: int = 600,
) -> bool:
    """
    Book final cut:
    - [0, motion_sec]: AI motion clip (first→last frame), keep its original audio
    - after: captioned still slideshow
    - full length: MiniMax TTS narration + soft BGM underlay
    """
    if not motion_path.exists():
        return False
    try:
        root = output_path.parent
        stills_mp4 = root / f"_book_stills_{output_path.stem}.mp4"
        motion_norm = root / f"_book_motion_{output_path.stem}.mp4"
        target = max(1.0, float(motion_sec))
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps=30"
        )
        has_src_audio = _ffprobe_has_audio(motion_path)
        src_dur = _ffprobe_duration_sec(motion_path) or target

        # Normalize motion: scale to 9:16; pad with last frame if shorter than target
        m_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(motion_path),
            "-vf",
            vf,
            "-t",
            f"{target:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
        ]
        if has_src_audio:
            m_cmd.extend(["-c:a", "aac", "-ac", "2", "-ar", "44100"])
        else:
            m_cmd.append("-an")
        # If clip shorter than target, loop/pad by freezing via -stream_loop before -i
        if src_dur + 0.15 < target:
            m_cmd = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "1",
                "-i",
                str(motion_path),
                "-vf",
                vf,
                "-t",
                f"{target:.3f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
            ]
            if has_src_audio:
                m_cmd.extend(["-c:a", "aac", "-ac", "2", "-ar", "44100"])
            else:
                m_cmd.append("-an")
        m_cmd.append(str(motion_norm))
        m_res = subprocess.run(
            m_cmd, capture_output=True, text=True, timeout=timeout_sec
        )
        if m_res.returncode != 0 or not motion_norm.exists():
            return False

        stills_ok = False
        if still_paths:
            stills_ok = try_ffmpeg_slideshow(
                still_paths,
                None,
                stills_mp4,
                still_durations,
                bgm_path=None,
                width=width,
                height=height,
                timeout_sec=timeout_sec,
                bgm_volume=bgm_volume,
            )

        has_tts = bool(tts_path and tts_path.exists())
        has_bgm = bool(bgm_path and bgm_path.exists())
        use_motion_audio = bool(
            keep_motion_audio and _ffprobe_has_audio(motion_norm)
        )

        cmd: list[str] = ["ffmpeg", "-y", "-i", str(motion_norm)]
        next_idx = 1
        stills_idx: int | None = None
        if stills_ok and stills_mp4.exists():
            cmd.extend(["-i", str(stills_mp4)])
            stills_idx = next_idx
            next_idx += 1
        tts_idx: int | None = None
        if has_tts:
            cmd.extend(["-i", str(tts_path)])
            tts_idx = next_idx
            next_idx += 1
        bgm_idx: int | None = None
        if has_bgm:
            cmd.extend(["-stream_loop", "-1", "-i", str(bgm_path)])
            bgm_idx = next_idx
            next_idx += 1

        filters: list[str] = []
        if stills_idx is not None:
            filters.append(f"[0:v][{stills_idx}:v]concat=n=2:v=1:a=0[vout]")
        else:
            filters.append("[0:v]setpts=PTS-STARTPTS[vout]")

        audio_labels: list[str] = []
        if tts_idx is not None:
            filters.append(f"[{tts_idx}:a]volume=1.0[atts]")
            audio_labels.append("[atts]")
        if use_motion_audio:
            vol = max(0.05, min(0.8, float(motion_audio_volume)))
            filters.append(
                f"[0:a]volume={vol:.3f},atrim=0:{target:.3f},"
                f"asetpts=PTS-STARTPTS[ama]"
            )
            audio_labels.append("[ama]")
        if bgm_idx is not None:
            bvol = max(0.05, min(0.45, float(bgm_volume)))
            filters.append(f"[{bgm_idx}:a]volume={bvol:.3f}[abgm]")
            audio_labels.append("[abgm]")

        map_args: list[str] = ["-map", "[vout]"]
        if len(audio_labels) >= 2:
            filters.append(
                f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:"
                f"duration=first:dropout_transition=2:normalize=0[aout]"
            )
            map_args.extend(["-map", "[aout]", "-c:a", "aac"])
        elif len(audio_labels) == 1:
            only = audio_labels[0].strip("[]")
            filters.append(f"[{only}]anull[aout]")
            map_args.extend(["-map", "[aout]", "-c:a", "aac"])

        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                *map_args,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
            ]
        )
        if audio_labels:
            cmd.append("-shortest")
        cmd.append(str(output_path))

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec
        )
        stills_mp4.unlink(missing_ok=True)
        motion_norm.unlink(missing_ok=True)
        return (
            result.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 1000
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def try_ffmpeg_slideshow(
    image_paths: list[Path],
    audio_path: Path | None,
    output_path: Path,
    duration_per_image: float | list[float],
    *,
    bgm_path: Path | None = None,
    width: int = 1080,
    height: int = 1920,
    timeout_sec: int = 480,
    bgm_volume: float = 0.16,
) -> bool:
    """Build vertical 9:16 slideshow; optionally mix soft BGM under narration."""
    if not image_paths:
        return False
    try:
        if isinstance(duration_per_image, (int, float)):
            durations = [float(duration_per_image)] * len(image_paths)
        else:
            durations = list(duration_per_image)
            if len(durations) < len(image_paths):
                durations.extend([durations[-1] if durations else 4.5] * (
                    len(image_paths) - len(durations)
                ))

        list_file = output_path.with_suffix(".txt")
        lines: list[str] = []
        for img, dur in zip(image_paths, durations):
            lines.append(f"file '{img.resolve()}'")
            lines.append(f"duration {max(0.5, dur):.3f}")
        lines.append(f"file '{image_paths[-1].resolve()}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")

        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
        ]

        has_tts = bool(audio_path and audio_path.exists())
        has_bgm = bool(bgm_path and bgm_path.exists())
        if has_tts:
            cmd.extend(["-i", str(audio_path)])
        if has_bgm:
            cmd.extend(["-stream_loop", "-1", "-i", str(bgm_path)])

        cmd.extend(["-vf", vf, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-r", "30"])

        if has_tts and has_bgm:
            # TTS loud, BGM soft bed
            tts_idx = 1
            bgm_idx = 2
            bgm_vol = max(0.05, min(0.45, float(bgm_volume)))
            cmd.extend(
                [
                    "-filter_complex",
                    (
                        f"[{tts_idx}:a]volume=1.0[a1];"
                        f"[{bgm_idx}:a]volume={bgm_vol:.3f}[a2];"
                        f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                    ),
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                    "-c:a",
                    "aac",
                    "-shortest",
                ]
            )
        elif has_tts:
            cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"])
        elif has_bgm:
            cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"])

        cmd.append(str(output_path))
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec
        )
        list_file.unlink(missing_ok=True)
        return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

# 听页：书法主标题（马善政楷书 ≈ 尚巍手书力量感；站酷快乐体兜底）
_POEM_FONT_CANDIDATES = (
    str(_FONTS_DIR / "MaShanZheng-Regular.ttf"),
    str(_FONTS_DIR / "ZCOOLKuaiLe-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)

# 二级角标 / 底部字幕：粗黑 vs 常规（思源黑体替代：苹方 SC）
_SANS_BOLD_CANDIDATES = (
    ("/System/Library/Fonts/PingFang.ttc", 8),  # PingFang SC Semibold
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),  # W6
    ("/System/Library/Fonts/STHeiti Medium.ttc", 1),  # Heiti SC Medium
    (str(_FONTS_DIR / "ZCOOLKuaiLe-Regular.ttf"), 0),
)

_SANS_REGULAR_CANDIDATES = (
    ("/System/Library/Fonts/PingFang.ttc", 2),  # PingFang SC Regular
    ("/System/Library/Fonts/STHeiti Light.ttc", 1),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
)

_CN_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)


def _load_font_from(
    candidates: tuple[str, ...] | tuple[tuple[str, int], ...],
    size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for item in candidates:
        if isinstance(item, tuple):
            path, index = item
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                continue
        else:
            try:
                return ImageFont.truetype(item, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _load_cn_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font_from(_CN_FONT_CANDIDATES, size)


def _load_poem_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font_from(_POEM_FONT_CANDIDATES, size)


def _load_sans_bold(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font_from(_SANS_BOLD_CANDIDATES, size)


def _load_sans_regular(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font_from(_SANS_REGULAR_CANDIDATES, size)


def _wrap_cn(
    text: str,
    font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_w: int,
    *,
    max_lines: int = 4,
) -> list[str]:
    text = (text or "").replace("\n", "").strip()
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
    if buf:
        lines.append(buf)
    return lines[:max_lines]


def _wrap_poem(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_w: int) -> list[str]:
    """Prefer breaking poems at Chinese punctuation."""
    raw = (text or "").strip().replace("\n", "")
    if not raw:
        return []
    # Soft split on ，？！；、
    parts: list[str] = []
    buf = ""
    for ch in raw:
        buf += ch
        if ch in "，？！；、。":
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    if len(parts) <= 1:
        return _wrap_cn(raw, font, draw, max_w, max_lines=3)

    lines: list[str] = []
    cur = ""
    for part in parts:
        trial = cur + part
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = part
        else:
            cur = trial
    if cur:
        lines.append(cur)
    # Final safety wrap
    out: list[str] = []
    for line in lines:
        out.extend(_wrap_cn(line, font, draw, max_w, max_lines=2))
    return out[:3]


def _auto_caption_font_size(text: str, base: int = 72) -> int:
    length = len((text or "").replace("\n", "").strip())
    if length <= 14:
        return base
    if length <= 22:
        return int(base * 0.88)
    if length <= 32:
        return int(base * 0.76)
    return int(base * 0.64)


def _stroke_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    *,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke: tuple[int, int, int, int] = (0, 0, 0, 220),
    width: int = 3,
) -> None:
    x, y = xy
    for dx, dy in (
        (-width, 0),
        (width, 0),
        (0, -width),
        (0, width),
        (-width + 1, -width + 1),
        (width - 1, width - 1),
    ):
        draw.text((x + dx, y + dy), text, font=font, fill=stroke)
    draw.text((x, y), text, font=font, fill=fill)


def _split_bilingual_caption(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", ""
    if "\n" in raw:
        zh, en = raw.split("\n", 1)
        return zh.strip(), en.strip()
    for i, ch in enumerate(raw):
        if ("A" <= ch <= "Z" or "a" <= ch <= "z") and i >= 6:
            return raw[:i].strip(), raw[i:].strip()
    return raw, ""


def burn_caption_on_image(
    src: Path,
    dst: Path,
    text: str,
    *,
    size: tuple[int, int] = (1080, 1920),
    font_size: int | None = None,
    header: str | None = None,
    poem: str | None = None,
    layout: str = "auto",
) -> None:
    """Burn captions.
    layout=lifetime → 《一生》顶部书名 + 底部中英金句
    layout=tingye → 听页三层（兼容旧项目）
    其他 → 底部口播字幕
    """
    layout_l = (layout or "auto").strip().lower()
    if layout_l == "lifetime":
        burn_lifetime_frame(
            src, dst, text=text, header=header or "", size=size, font_size=font_size
        )
        return
    use_tingye = layout_l == "tingye" or (
        layout_l == "auto" and bool((poem or "").strip())
    )
    if use_tingye:
        burn_tingye_frame(
            src,
            dst,
            poem=poem or "",
            narration=text,
            header=header or "",
            size=size,
            poem_font_size=font_size,
        )
        return

    ensure_portrait_9_16(src, size)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    body = (text or "").strip()
    if not body:
        img.convert("RGB").save(dst, format="PNG", optimize=True)
        return

    resolved_size = font_size or _auto_caption_font_size(body, 56)
    font = _load_sans_regular(resolved_size)
    max_w = int(w * 0.86)
    lines = _wrap_cn(body, font, draw, max_w, max_lines=3)
    line_gap = int(resolved_size * 1.25)
    block_h = line_gap * len(lines) + 28
    top = int(h * 0.78)
    box = (int(w * 0.06), top, int(w * 0.94), min(h - 90, top + block_h))
    draw.rounded_rectangle(box, radius=18, fill=(0, 0, 0, 150))
    y = top + 14
    for line in lines:
        tw = draw.textlength(line, font=font)
        _stroke_text(draw, ((w - tw) / 2, y), line, font, width=2)
        y += line_gap

    out = Image.alpha_composite(img, overlay).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="PNG", optimize=True)


def burn_lifetime_frame(
    src: Path,
    dst: Path,
    *,
    text: str,
    header: str = "",
    size: tuple[int, int] = (1080, 1920),
    font_size: int | None = None,
) -> None:
    """《一生》布局：顶部居中书名 + 底部口播逐字稿（与 TTS 一致）。"""
    ensure_portrait_9_16(src, size)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    header_text = (header or "").strip()
    if header_text:
        draw.rectangle((0, 0, w, int(h * 0.16)), fill=(0, 0, 0, 80))
        h_font = _load_cn_font(76)
        label = header_text[:18]
        tw = draw.textlength(label, font=h_font)
        _stroke_text(
            draw,
            ((w - tw) / 2, int(h * 0.04)),
            label,
            h_font,
            fill=(255, 214, 96, 255),
            stroke=(40, 24, 0, 220),
            width=3,
        )

    # 逐字稿：整段旁白；若误带英文分行，仍优先整段中文可读
    body = (text or "").strip().replace("\x1e", " ").strip()
    if "\n" in body:
        # 旧双语数据：只取中文行作为逐字稿主体
        first, rest = body.split("\n", 1)
        if any("\u4e00" <= ch <= "\u9fff" for ch in first) and not any(
            "\u4e00" <= ch <= "\u9fff" for ch in rest[:20]
        ):
            body = first.strip()
        else:
            body = body.replace("\n", "")

    if not body:
        out = Image.alpha_composite(img, overlay).convert("RGB")
        dst.parent.mkdir(parents=True, exist_ok=True)
        out.save(dst, format="PNG", optimize=True)
        return

    draw.rectangle((0, int(h * 0.58), w, h), fill=(0, 0, 0, 130))
    base = 52 if len(body) > 70 else 58
    if len(body) > 100:
        base = 44
    zh_size = font_size or _auto_caption_font_size(body, base)
    zh_font = _load_sans_regular(zh_size)
    max_w = int(w * 0.88)
    zh_lines = _wrap_cn(body, zh_font, draw, max_w, max_lines=6)
    zh_gap = int(zh_size * 1.22)
    block_h = zh_gap * len(zh_lines) + 28
    top = int(h * 0.68)
    if top + block_h > h - 90:
        top = max(int(h * 0.58), h - 90 - block_h)
    box = (int(w * 0.05), top, int(w * 0.95), min(h - 80, top + block_h))
    draw.rounded_rectangle(box, radius=18, fill=(0, 0, 0, 150))

    y = float(top + 12)
    for line in zh_lines:
        tw = draw.textlength(line, font=zh_font)
        _stroke_text(draw, ((w - tw) / 2, y), line, zh_font, width=2)
        y += zh_gap

    out = Image.alpha_composite(img, overlay).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="PNG", optimize=True)


def burn_tingye_frame(
    src: Path,
    dst: Path,
    *,
    poem: str,
    narration: str,
    header: str = "",
    size: tuple[int, int] = (1080, 1920),
    poem_font_size: int | None = None,
) -> None:
    """抖音听页三层：左上角书名角标 + 中央书法诗词 + 底部口播字幕。"""
    ensure_portrait_9_16(src, size)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 暗角：保住白字可读
    draw.rectangle((0, 0, w, int(h * 0.14)), fill=(0, 0, 0, 70))
    draw.rectangle((0, int(h * 0.72), w, h), fill=(0, 0, 0, 100))

    header_text = (header or "").strip()
    if header_text:
        h_font = _load_sans_bold(34)
        # 左上角：第149本 / 书名
        _stroke_text(
            draw,
            (int(w * 0.06), int(h * 0.055)),
            header_text[:28],
            h_font,
            fill=(255, 255, 255, 245),
            stroke=(0, 0, 0, 200),
            width=2,
        )

    poem_text = (poem or "").strip()
    if poem_text:
        p_size = poem_font_size or _auto_caption_font_size(poem_text, 78)
        p_font = _load_poem_font(p_size)
        max_w = int(w * 0.88)
        p_lines = _wrap_poem(poem_text, p_font, draw, max_w)
        gap = int(p_size * 1.28)
        block_h = gap * len(p_lines)
        # 画面核心视觉区（约 38%–58%）
        y = int(h * 0.42) - block_h // 2
        y = max(int(h * 0.28), min(y, int(h * 0.55)))
        for line in p_lines:
            tw = draw.textlength(line, font=p_font)
            _stroke_text(
                draw,
                ((w - tw) / 2, y),
                line,
                p_font,
                fill=(255, 255, 255, 255),
                stroke=(0, 0, 0, 230),
                width=3,
            )
            y += gap

    narr = (narration or "").strip()
    if narr:
        n_size = _auto_caption_font_size(narr, 40 if len(narr) > 60 else 44)
        n_font = _load_sans_regular(n_size)
        max_w = int(w * 0.86)
        # 3 分钟长旁白：允许多行底部字幕，尽量跟口播同步可读
        n_lines = _wrap_cn(narr, n_font, draw, max_w, max_lines=5)
        gap = int(n_size * 1.22)
        block_h = gap * len(n_lines) + 24
        top = int(h * 0.80)
        box = (int(w * 0.06), top, int(w * 0.94), min(h - 80, top + block_h))
        draw.rounded_rectangle(box, radius=16, fill=(0, 0, 0, 155))
        y = top + 12
        for line in n_lines:
            tw = draw.textlength(line, font=n_font)
            _stroke_text(
                draw,
                ((w - tw) / 2, y),
                line,
                n_font,
                fill=(255, 255, 255, 250),
                stroke=(0, 0, 0, 180),
                width=2,
            )
            y += gap

    out = Image.alpha_composite(img, overlay).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="PNG", optimize=True)


def compose_channels_cover(
    src: Path,
    dst: Path,
    *,
    hook: str,
    subtitle: str = "",
    size: tuple[int, int] = (1080, 1920),
) -> None:
    """《一生》式封面：顶部居中书名 + 底部大字金句。"""
    ensure_portrait_9_16(src, size)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, w, int(h * 0.18)), fill=(0, 0, 0, 80))
    draw.rectangle((0, int(h * 0.58), w, h), fill=(0, 0, 0, 140))

    title_line = (subtitle or "").strip() or "书籍金句"
    title_font = _load_cn_font(80)
    label = title_line[:18]
    tw = draw.textlength(label, font=title_font)
    _stroke_text(
        draw,
        ((w - tw) / 2, int(h * 0.05)),
        label,
        title_font,
        fill=(255, 214, 96, 255),
        stroke=(40, 24, 0, 220),
        width=3,
    )

    hook_font = _load_cn_font(78)
    hook_lines = _wrap_cn(hook[:22], hook_font, draw, int(w * 0.88), max_lines=2)
    if not hook_lines:
        hook_lines = [hook[:14] or "读懂这一本"]

    y = int(h * 0.68)
    for line in hook_lines[:2]:
        tw = draw.textlength(line, font=hook_font)
        _stroke_text(
            draw,
            ((w - tw) / 2, y),
            line,
            hook_font,
            fill=(255, 248, 230, 255),
            stroke=(0, 0, 0, 230),
            width=3,
        )
        y += int(78 * 1.2)

    out = Image.alpha_composite(img, overlay).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="PNG", optimize=True)


def write_minimal_mp4_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
        b"\x00\x00\x00\x08free"
        b"PICTALE_MOCK_VIDEO"
    )


def get_storage() -> Path:
    return get_settings().storage_path
