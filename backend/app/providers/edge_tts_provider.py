from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from app.config import get_settings
from app.models.schemas import AssetRef, TTSResult
from app.providers.base import TTSRequest
from app.providers.media_utils import asset_url, new_asset_id, project_dir
from app.runtime_config import runtime_config


def _ffprobe_duration(path: Path) -> float | None:
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
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return None
    return None


def _concat_mp3(parts: list[Path], out: Path) -> bool:
    if not parts:
        return False
    list_file = out.with_suffix(".concat.txt")
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in parts),
        encoding="utf-8",
    )
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        list_file.unlink(missing_ok=True)
        if result.returncode == 0 and out.exists():
            return True
        # re-encode fallback
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out),
        ]
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in parts),
            encoding="utf-8",
        )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        list_file.unlink(missing_ok=True)
        return result.returncode == 0 and out.exists()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        list_file.unlink(missing_ok=True)
        return False


class EdgeTTSProvider:
    """Per-shot Edge TTS so narration length matches each image."""

    name = "edge"

    async def generate(self, req: TTSRequest) -> TTSResult:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "未安装 edge-tts，请在 backend 执行: pip install edge-tts"
            ) from exc

        cfg = runtime_config.get()
        settings = get_settings()
        # 优先用请求指定的音色（书籍/人生会传 book_tts_voice）；占位音色回退到配置；
        # Edge 只认 zh-CN-* 语音，MiniMax 风格音色 ID 一律回退默认
        _PLACEHOLDER = frozenset({"", "child_warm", "default"})
        voice = (req.voice or "").strip()
        if voice in _PLACEHOLDER:
            voice = (cfg.tts_voice or "").strip()
        if not voice or not voice.startswith("zh-CN-") or "Neural" not in voice:
            voice = "zh-CN-XiaoxiaoNeural"
        root = project_dir(settings, getattr(req, "storage_key", None) or req.project_id)
        part_paths: list[Path] = []
        # 绘本慢讲；书籍说书稍快。Edge rate：负值更慢
        api = (getattr(req, "api_prefix", None) or "/api/projects").strip()
        if api.startswith("/api/book"):
            rate = "-5%"
        else:
            rate = "-15%"  # 绘本讲故事

        for shot in req.storyboard.shots:
            text = (shot.narration or "").strip()
            if not text:
                text = "……"
            part = root / f"tts_shot_{shot.index:02d}.mp3"
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(part))
            dur = _ffprobe_duration(part)
            if dur and dur > 0.3:
                shot.duration_sec = round(dur + 0.35, 2)
            else:
                shot.duration_sec = round(max(4.5, len(text) / 2.8), 2)
            part_paths.append(part)
            await asyncio.sleep(0.05)

        req.storyboard.total_sec = round(sum(s.duration_sec for s in req.storyboard.shots), 2)

        asset_id = new_asset_id()
        filename = f"tts_{asset_id}.mp3"
        path = root / filename
        if not _concat_mp3(part_paths, path):
            # last resort: single communicate of joined text
            joined = "。".join(
                s.narration.strip() for s in req.storyboard.shots if s.narration.strip()
            )
            await edge_tts.Communicate(joined, voice).save(str(path))

        duration = _ffprobe_duration(path) or req.storyboard.total_sec
        asset = AssetRef(
            id=asset_id,
            kind="audio",
            filename=filename,
            mime_type="audio/mpeg",
            url=asset_url(req.project_id, asset_id),
            meta={
                "path": str(path),
                "voice": voice,
                "provider": self.name,
                "per_shot": True,
                "shot_durations": [s.duration_sec for s in req.storyboard.shots],
            },
        )
        return TTSResult(
            asset=asset, duration_sec=round(duration, 2), provider=self.name
        )
