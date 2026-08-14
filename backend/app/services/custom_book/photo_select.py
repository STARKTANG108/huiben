from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def score_photo(path: Path) -> float:
    """Higher is better: resolution + sharpness + file size proxy."""
    try:
        size_score = min(path.stat().st_size / (500 * 1024), 2.0)  # up to ~2
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            res_score = min((w * h) / (1280 * 1280), 2.0)
            gray = img.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            sharp = ImageStat.Stat(edges).mean[0] / 40.0  # typical 0–2+
            aspect = w / max(h, 1)
            portrait_bonus = 0.3 if 0.55 <= aspect <= 0.95 else 0.0
        return float(res_score + sharp + size_score + portrait_bonus)
    except Exception:  # noqa: BLE001
        return 0.0


def select_best_photos(paths: list[Path], *, max_keep: int = 5) -> list[Path]:
    ranked = sorted(paths, key=score_photo, reverse=True)
    return ranked[:max_keep]
