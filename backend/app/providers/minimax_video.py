from __future__ import annotations

"""MiniMax first/last-frame video generation for book opening clip."""

import asyncio
import base64
import logging
from pathlib import Path

import httpx

from app.providers.minimax_media import (
    _check_base_resp,
    _minimax_api_key,
    _minimax_base,
)

logger = logging.getLogger(__name__)

DEFAULT_H3_MODEL = "MiniMax-H3"
DEFAULT_HAILUO_MODEL = "MiniMax-Hailuo-02"
BOOK_MOTION_SEC = 8
# Hailuo-02 start-end only supports 6 or 10; prefer 6 then pad to 8 in compose
HAILUO_DURATION = 6


def _encode_frame_image(path: Path) -> str:
    """Encode frame for MiniMax video API (keep detail, stay under size limits)."""
    try:
        from PIL import Image
        import io

        img = Image.open(path).convert("RGB")
        img.thumbnail((1280, 2276), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        raw = buf.getvalue()
        if len(raw) > 18_000_000:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            raw = buf.getvalue()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:  # noqa: BLE001
        raw = path.read_bytes()
        if len(raw) > 18_000_000:
            raise RuntimeError("首尾帧图片过大，无法提交 MiniMax 视频生成")
        b64 = base64.b64encode(raw).decode("ascii")
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64,{b64}"


def _safe_motion_prompt(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        text = (
            "Cinematic slow camera drift, gentle atmospheric motion, "
            "soft film grain, natural light shift, book trailer mood"
        )
    # Keep ASCII-heavy prompt to reduce sensitive-word hits on Chinese APIs
    cleaned = "".join(ch if ord(ch) < 128 or ch.isspace() else " " for ch in text)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) < 24:
        cleaned = (
            "Slow cinematic push-in, dust motes in golden light, "
            "subtle parallax, reflective book-trailer atmosphere"
        )
    return cleaned[:1800]


class MinimaxVideoProvider:
    """Generate an opening clip from first + last still frames."""

    name = "minimax_video"

    async def generate_first_last(
        self,
        *,
        first_path: Path,
        last_path: Path,
        out_path: Path,
        prompt: str,
        duration_sec: int = BOOK_MOTION_SEC,
    ) -> Path:
        if not first_path.exists() or not last_path.exists():
            raise RuntimeError("首尾帧图片不存在，无法生成开场视频")
        api_key = _minimax_api_key()
        base = _minimax_base()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        first_url = await asyncio.to_thread(_encode_frame_image, first_path)
        last_url = await asyncio.to_thread(_encode_frame_image, last_path)
        motion_prompt = _safe_motion_prompt(prompt)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            last_err: Exception | None = None
            # Prefer H3 V2 (native audio, exact 8s); fallback Hailuo-02 V1
            for attempt in (
                ("v2", DEFAULT_H3_MODEL, max(4, min(15, int(duration_sec)))),
                ("v1", DEFAULT_HAILUO_MODEL, HAILUO_DURATION),
            ):
                kind, model, dur = attempt
                try:
                    if kind == "v2":
                        task_id = await self._create_v2(
                            client,
                            base=base,
                            headers=headers,
                            model=model,
                            prompt=motion_prompt,
                            first_url=first_url,
                            last_url=last_url,
                            duration=dur,
                        )
                        download_url = await self._poll_v2(
                            client, base=base, headers=headers, task_id=task_id
                        )
                    else:
                        task_id = await self._create_v1(
                            client,
                            base=base,
                            headers=headers,
                            model=model,
                            prompt=motion_prompt,
                            first_url=first_url,
                            last_url=last_url,
                            duration=dur,
                        )
                        download_url = await self._poll_v1(
                            client, base=base, headers=headers, task_id=task_id
                        )
                    await self._download(client, download_url, out_path)
                    if out_path.exists() and out_path.stat().st_size > 1000:
                        logger.info(
                            "MiniMax motion clip ready via %s/%s → %s",
                            kind,
                            model,
                            out_path.name,
                        )
                        return out_path
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    logger.warning(
                        "MiniMax video %s/%s failed: %s", kind, model, exc
                    )
            raise RuntimeError(
                f"MiniMax 开场视频生成失败：{last_err or 'unknown'}"
            )

    async def _create_v2(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        model: str,
        prompt: str,
        first_url: str,
        last_url: str,
        duration: int,
    ) -> str:
        body = {
            "model": model,
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": first_url},
                    "role": "first_frame",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": last_url},
                    "role": "last_frame",
                },
            ],
            "duration": int(duration),
            "resolution": "768P",
        }
        res = await client.post(
            f"{base}/v2/video_generation", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise RuntimeError(
                f"MiniMax V2 创建失败 ({res.status_code}): {res.text[:400]}"
            )
        data = res.json()
        if isinstance(data.get("base_resp"), dict):
            _check_base_resp(data)
        task_id = str(data.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError(f"MiniMax V2 未返回 task_id: {str(data)[:300]}")
        return task_id

    async def _poll_v2(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        task_id: str,
        timeout_sec: float = 600.0,
    ) -> str:
        url = f"{base}/v2/query/video_generation/{task_id}"
        elapsed = 0.0
        while elapsed < timeout_sec:
            await asyncio.sleep(8.0)
            elapsed += 8.0
            res = await client.get(url, headers=headers)
            if res.status_code >= 400:
                raise RuntimeError(
                    f"MiniMax V2 查询失败 ({res.status_code}): {res.text[:300]}"
                )
            data = res.json()
            task = data.get("task") or data
            status = str(task.get("status") or "").lower()
            if status in ("succeeded", "success"):
                content = task.get("content") or {}
                download = (
                    content.get("url")
                    or task.get("file_url")
                    or task.get("download_url")
                    or ""
                )
                if download:
                    return str(download)
                raise RuntimeError("MiniMax V2 成功但无下载地址")
            if status in ("failed", "cancelled", "error"):
                err = task.get("error") or task.get("base_resp") or data
                raise RuntimeError(f"MiniMax V2 任务失败: {err}")
            logger.info("MiniMax V2 task %s status=%s", task_id, status)
        raise RuntimeError("MiniMax V2 视频生成超时")

    async def _create_v1(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        model: str,
        prompt: str,
        first_url: str,
        last_url: str,
        duration: int,
    ) -> str:
        body = {
            "model": model,
            "prompt": prompt,
            "first_frame_image": first_url,
            "last_frame_image": last_url,
            "duration": int(duration),
            "resolution": "768P",
            "prompt_optimizer": True,
        }
        res = await client.post(
            f"{base}/v1/video_generation", headers=headers, json=body
        )
        if res.status_code >= 400:
            raise RuntimeError(
                f"MiniMax V1 创建失败 ({res.status_code}): {res.text[:400]}"
            )
        data = res.json()
        _check_base_resp(data)
        task_id = str(data.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError(f"MiniMax V1 未返回 task_id: {str(data)[:300]}")
        return task_id

    async def _poll_v1(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        task_id: str,
        timeout_sec: float = 600.0,
    ) -> str:
        url = f"{base}/v1/query/video_generation"
        elapsed = 0.0
        while elapsed < timeout_sec:
            await asyncio.sleep(8.0)
            elapsed += 8.0
            res = await client.get(
                url, headers=headers, params={"task_id": task_id}
            )
            if res.status_code >= 400:
                raise RuntimeError(
                    f"MiniMax V1 查询失败 ({res.status_code}): {res.text[:300]}"
                )
            data = res.json()
            _check_base_resp(data)
            status = str(data.get("status") or "").lower()
            if status in ("success", "succeeded"):
                # Prefer direct URL; else retrieve via file_id
                for key in ("file_url", "download_url", "video_url"):
                    if data.get(key):
                        return str(data[key])
                file_id = str(data.get("file_id") or "").strip()
                if not file_id:
                    content = data.get("content") or {}
                    if content.get("url"):
                        return str(content["url"])
                    raise RuntimeError("MiniMax V1 成功但无 file_id")
                return await self._retrieve_file_url(
                    client, base=base, headers=headers, file_id=file_id
                )
            if status in ("failed", "fail", "error", "cancelled"):
                raise RuntimeError(f"MiniMax V1 任务失败: {data}")
            logger.info("MiniMax V1 task %s status=%s", task_id, status)
        raise RuntimeError("MiniMax V1 视频生成超时")

    async def _retrieve_file_url(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        file_id: str,
    ) -> str:
        res = await client.get(
            f"{base}/v1/files/retrieve",
            headers=headers,
            params={"file_id": file_id},
        )
        if res.status_code >= 400:
            raise RuntimeError(
                f"MiniMax 取文件失败 ({res.status_code}): {res.text[:300]}"
            )
        data = res.json()
        _check_base_resp(data)
        file_obj = data.get("file") or data
        url = (
            file_obj.get("download_url")
            or file_obj.get("url")
            or data.get("download_url")
            or ""
        )
        if not url:
            raise RuntimeError(f"MiniMax 文件无下载地址: {str(data)[:300]}")
        return str(url)

    async def _download(
        self, client: httpx.AsyncClient, url: str, out_path: Path
    ) -> None:
        res = await client.get(url, timeout=180.0)
        if res.status_code >= 400:
            raise RuntimeError(f"下载开场视频失败 ({res.status_code})")
        out_path.write_bytes(res.content)
