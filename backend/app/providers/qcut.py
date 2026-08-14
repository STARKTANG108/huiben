from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
QCUT_CANDIDATES = [
    REPO_ROOT / ".agents" / "skills" / "qiaomu-cut" / "scripts" / "qcut.js",
    REPO_ROOT / ".cursor" / "skills" / "qiaomu-cut" / "scripts" / "qcut.js",
]


def qcut_js() -> Path:
    for path in QCUT_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "未找到 qiaomu-cut：请确认 .agents/skills/qiaomu-cut 已安装"
    )


def _parse_qcut_stdout(out: str) -> dict[str, Any] | str | list[Any]:
    if not out:
        return {}
    for chunk in reversed(out.split("\n")):
        chunk = chunk.strip()
        if chunk.startswith("{") or chunk.startswith("["):
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def run_qcut(
    *args: str,
    cwd: Path | None = None,
    timeout: int = 300,
    allow_nonzero: bool = False,
) -> dict[str, Any] | str | list[Any]:
    cmd = ["node", str(qcut_js()), *args]
    if "--json" not in args:
        cmd.append("--json")
    logger.info("qcut: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0 and not allow_nonzero:
        raise RuntimeError(err or out or f"qcut exit {result.returncode}")
    parsed = _parse_qcut_stdout(out)
    if result.returncode != 0 and allow_nonzero and parsed == {}:
        raise RuntimeError(err or out or f"qcut exit {result.returncode}")
    return parsed


def scaffold_project(
    project_root: Path,
    *,
    brief: str,
    workflow: str,
    duration: int,
    fmt: str,
) -> dict[str, Any]:
    project_root.mkdir(parents=True, exist_ok=True)
    return run_qcut(
        "scaffold",
        str(project_root),
        "--brief",
        brief,
        "--workflow",
        workflow,
        "--duration",
        str(duration),
        "--format",
        fmt,
        "--force",
        timeout=60,
    )


def clipseek_search(text: str, *, limit: int = 5) -> list[dict[str, Any]]:
    try:
        data = run_qcut(
            "clipseek",
            text,
            "--type",
            "video",
            "--limit",
            str(limit),
            timeout=45,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("clipseek failed: %s", exc)
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    return []


def try_qcut_render(project_root: Path, *, profile: str = "preview") -> dict[str, Any] | None:
    try:
        return run_qcut(
            "render",
            str(project_root),
            "--profile",
            profile,
            timeout=240,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("qcut render failed: %s", exc)
        return None


def doctor_summary() -> str:
    # qcut doctor exits 1 when ffmpeg.ok is false — that is a capability report, not a crash.
    try:
        data = run_qcut("doctor", timeout=30, allow_nonzero=True)
    except Exception as exc:  # noqa: BLE001
        return f"doctor 不可用: {exc}"
    if not isinstance(data, dict):
        return "doctor 返回非 JSON"
    tips: list[str] = []
    ffmpeg = data.get("ffmpeg") or {}
    if isinstance(ffmpeg, dict) and not ffmpeg.get("ok", True):
        missing = ffmpeg.get("missing") or []
        miss = "、".join(str(m) for m in missing[:4]) if missing else "字幕能力"
        tips.append(
            f"当前 ffmpeg 缺 {miss}：预览仍可用；完整 ASS 字幕请 "
            f"`brew install ffmpeg-full` 并设置 QIAOMU_FFMPEG"
        )
    adapters = data.get("adapters") or {}
    listenhub = adapters.get("listenhub") or {}
    tc = adapters.get("33tc") or {}
    if not listenhub.get("available") and not tc.get("available"):
        tips.append("ListenHub / 33tc 未装：默认生图静帧 + 本地预览（不扣费）")
    if data.get("ok"):
        return "qcut doctor OK"
    return "；".join(tips) if tips else "qcut doctor 有能力缺口，预览仍可继续"


def which_node() -> str | None:
    return shutil.which("node")
