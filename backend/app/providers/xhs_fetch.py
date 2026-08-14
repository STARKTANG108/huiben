from __future__ import annotations

"""Fetch article / X (Twitter) link text for summarization."""

import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _normalize_url(url: str) -> str:
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def _is_x_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(h in host for h in ("x.com", "twitter.com", "mobile.twitter.com"))


def _tweet_id(url: str) -> str | None:
    m = re.search(r"/status(?:es)?/(\d+)", url)
    return m.group(1) if m else None


async def _fetch_jina(url: str) -> str:
    """Jina Reader: reliable article/tweet text extraction."""
    target = f"https://r.jina.ai/{url}"
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        res = await client.get(target, headers={"User-Agent": _UA, "Accept": "text/plain"})
        if res.status_code >= 400:
            raise RuntimeError(f"链接读取失败 ({res.status_code})")
        text = res.text.strip()
        if len(text) < 40:
            raise RuntimeError("链接内容过短或无法解析")
        return text[:12000]


async def _fetch_vxtwitter(tweet_id: str) -> str | None:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        res = await client.get(
            f"https://api.vxtwitter.com/Twitter/status/{tweet_id}",
            headers={"User-Agent": _UA},
        )
        if res.status_code >= 400:
            return None
        data = res.json()
        user = data.get("user_name") or data.get("user_screen_name") or ""
        text = data.get("text") or data.get("full_text") or ""
        if not text:
            return None
        return f"作者：{user}\n内容：{text}".strip()


async def fetch_source_text(url: str) -> tuple[str, str]:
    """
    Returns (title_hint, body_text).
    Supports general articles and X/Twitter status links.
    """
    url = _normalize_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RuntimeError("仅支持 http/https 链接")

    if _is_x_url(url):
        tid = _tweet_id(url)
        if tid:
            vx = await _fetch_vxtwitter(tid)
            if vx:
                return f"X 帖子 {tid}", vx

    raw = await _fetch_jina(url)
    title = ""
    for line in raw.splitlines()[:20]:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[-1].strip()
            break
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = parsed.netloc or "来源文章"
    return title[:200], raw
