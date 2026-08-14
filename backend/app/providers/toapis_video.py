from __future__ import annotations

"""ToAPIs veo3.1-fast first/last-frame opening clip for book module."""

import asyncio
import logging
from pathlib import Path

import httpx

from app.runtime_config import runtime_config

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://toapis.com"
DEFAULT_MODEL = "veo3.1-fast"
BOOK_MOTION_SEC = 8


def _toapis_api_key() -> str:
    cfg = runtime_config.get()
    key = (cfg.toapis_api_key or "").strip()
    if not key:
        raise RuntimeError(
            "请在模型配置填写 ToAPIs API Key（toapis.com），用于书籍开场视频"
        )
    return key


def _toapis_base() -> str:
    cfg = runtime_config.get()
    base = (getattr(cfg, "toapis_base_url", None) or DEFAULT_BASE).strip().rstrip("/")
    return base or DEFAULT_BASE


def _toapis_model() -> str:
    cfg = runtime_config.get()
    model = (getattr(cfg, "toapis_video_model", None) or DEFAULT_MODEL).strip()
    return model or DEFAULT_MODEL


def _safe_prompt(prompt: str) -> str:
    text = " ".join((prompt or "").split())
    if len(text) < 12:
        text = (
            "Cinematic slow camera drift, atmospheric book-trailer motion, "
            "soft film grain, natural light shift"
        )
    return text[:1800]


class ToAPIsVideoProvider:
    """Book opening motion via ToAPIs veo3.1-fast (first→last frame)."""

    name = "toapis_veo"

    async def generate_first_last(
        self,
        *,
        first_path: Path,
        last_path: Path,
        out_path: Path,
        prompt: str,
        duration_sec: int = BOOK_MOTION_SEC,
    ) -> Path:
        if not first_path.exists():
            raise RuntimeError("首帧图片不存在，无法生成开场视频")
        if not last_path.exists():
            raise RuntimeError("尾帧图片不存在，无法生成开场视频")

        api_key = _toapis_api_key()
        base = _toapis_base()
        model = _toapis_model()
        headers = {"Authorization": f"Bearer {api_key}"}
        # Veo3 only supports 8s
        duration = 8
        motion_prompt = _safe_prompt(prompt)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            first_url = await self._upload_image(client, base, headers, first_path)
            last_url = await self._upload_image(client, base, headers, last_path)
            task_id = await self._create_task(
                client,
                base=base,
                headers=headers,
                model=model,
                prompt=motion_prompt,
                image_urls=[first_url, last_url],
                duration=duration,
            )
            download_url = await self._poll_task(
                client, base=base, headers=headers, task_id=task_id
            )
            await self._download(client, download_url, out_path)

        if not out_path.exists() or out_path.stat().st_size < 1000:
            raise RuntimeError("ToAPIs 开场视频下载失败或文件过小")
        logger.info("ToAPIs %s motion ready → %s", model, out_path.name)
        return out_path

    async def _upload_image(
        self,
        client: httpx.AsyncClient,
        base: str,
        headers: dict,
        path: Path,
    ) -> str:
        # Compress large frames to stay under 10MB upload limit
        upload_path = path
        tmp: Path | None = None
        try:
            if path.stat().st_size > 8_000_000 or path.suffix.lower() not in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            ):
                from PIL import Image
                import io

                img = Image.open(path).convert("RGB")
                img.thumbnail((1280, 2276), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=88, optimize=True)
                tmp = path.parent / f"_toapis_up_{path.stem}.jpg"
                tmp.write_bytes(buf.getvalue())
                upload_path = tmp

            mime = "image/jpeg"
            suf = upload_path.suffix.lower()
            if suf == ".png":
                mime = "image/png"
            elif suf == ".webp":
                mime = "image/webp"

            with upload_path.open("rb") as f:
                files = {"file": (upload_path.name, f, mime)}
                res = await client.post(
                    f"{base}/v1/uploads/images",
                    headers=headers,
                    files=files,
                )
            if res.status_code >= 400:
                raise RuntimeError(
                    f"ToAPIs 上传图片失败 ({res.status_code}): {res.text[:400]}"
                )
            data = res.json()
            if data.get("success") is False:
                raise RuntimeError(f"ToAPIs 上传失败: {data.get('message') or data}")
            url = ((data.get("data") or {}).get("url") or "").strip()
            if not url:
                raise RuntimeError(f"ToAPIs 上传未返回 URL: {str(data)[:300]}")
            return url
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    async def _create_task(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        model: str,
        prompt: str,
        image_urls: list[str],
        duration: int,
    ) -> str:
        # First/last frame mode for Veo3（与官方示例一致）
        body = {
            "model": model,
            "prompt": prompt,
            "duration": int(duration),
            "aspect_ratio": "9:16",
            "image_urls": image_urls,
            "metadata": {
                "generation_type": "frame",
                "resolution": "1080p",
                "enable_gif": False,
            },
        }
        res = await client.post(
            f"{base}/v1/videos/generations",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
        )
        if res.status_code >= 400:
            raise RuntimeError(
                f"ToAPIs 创建视频失败 ({res.status_code}): {res.text[:500]}"
            )
        data = res.json()
        task_id = str(data.get("id") or data.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError(f"ToAPIs 未返回任务 ID: {str(data)[:400]}")
        return task_id

    async def _poll_task(
        self,
        client: httpx.AsyncClient,
        *,
        base: str,
        headers: dict,
        task_id: str,
        timeout_sec: float = 900.0,
    ) -> str:
        url = f"{base}/v1/videos/generations/{task_id}"
        await asyncio.sleep(5.0)
        elapsed = 5.0
        interval = 10.0
        while elapsed < timeout_sec:
            res = await client.get(url, headers=headers)
            if res.status_code == 429:
                retry = int(res.headers.get("Retry-After") or interval)
                await asyncio.sleep(retry + 1)
                elapsed += retry + 1
                interval = min(interval * 1.5, 60)
                continue
            if res.status_code >= 400:
                raise RuntimeError(
                    f"ToAPIs 查询失败 ({res.status_code}): {res.text[:400]}"
                )
            data = res.json()
            status = str(data.get("status") or "").lower()
            progress = data.get("progress", 0)
            logger.info(
                "ToAPIs video %s status=%s progress=%s", task_id, status, progress
            )
            if status == "completed":
                result = data.get("result") or {}
                items = result.get("data") or []
                if items and items[0].get("url"):
                    return str(items[0]["url"])
                raise RuntimeError(f"ToAPIs completed 但无视频 URL: {str(data)[:400]}")
            if status == "failed":
                err = data.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else err
                raise RuntimeError(f"ToAPIs 视频生成失败: {msg or data}")
            await asyncio.sleep(interval)
            elapsed += interval
        raise RuntimeError("ToAPIs 视频生成超时")

    async def _download(
        self, client: httpx.AsyncClient, url: str, out_path: Path
    ) -> None:
        res = await client.get(url, timeout=180.0)
        if res.status_code >= 400:
            raise RuntimeError(f"下载 ToAPIs 视频失败 ({res.status_code})")
        out_path.write_bytes(res.content)
