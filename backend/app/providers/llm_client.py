from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.runtime_config import RuntimeConfig, runtime_config

logger = logging.getLogger(__name__)

POLLINATIONS_CHAT = "https://text.pollinations.ai/openai"
POLLINATIONS_TEXT = "https://text.pollinations.ai"


class LLMError(Exception):
    pass


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
        if m:
            return json.loads(m.group(0))
        raise


async def chat_completion(
    *,
    system: str,
    user: str,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str:
    """Route text generation by runtime config: custom OpenAI-compat or free Pollinations."""
    cfg = runtime_config.get()
    if cfg.text_preset != "mock":
        return await _openai_compat_chat(
            cfg, system=system, user=user, json_mode=json_mode, temperature=temperature
        )
    # mock 已由调用方选择 mock provider；此处回退免费 Pollinations
    return await _pollinations_chat(
        system=system, user=user, json_mode=json_mode, temperature=temperature
    )


async def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.5,
) -> Any:
    raw = await chat_completion(
        system=system + "\n只输出合法 JSON，不要 markdown 代码块。",
        user=user,
        json_mode=True,
        temperature=temperature,
    )
    return _extract_json(raw)


async def _openai_compat_chat(
    cfg: RuntimeConfig,
    *,
    system: str,
    user: str,
    json_mode: bool,
    temperature: float,
) -> str:
    if not cfg.base_url.strip():
        raise LLMError("自定义文本模型未填写 Base URL")
    if not cfg.api_key.strip():
        raise LLMError("自定义文本模型未填写 API Key")
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.api_key.strip()}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": cfg.model.strip() or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(url, headers=headers, json=body)
        if res.status_code >= 400:
            raise LLMError(f"文本模型调用失败 ({res.status_code}): {res.text[:400]}")
        data = res.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"文本模型返回格式异常: {data}") from exc


async def _pollinations_chat(
    *,
    system: str,
    user: str,
    json_mode: bool,
    temperature: float,
) -> str:
    body: dict[str, Any] = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            res = await client.post(
                POLLINATIONS_CHAT,
                json=body,
                headers={"Content-Type": "application/json"},
            )
            if res.status_code < 400:
                data = res.json()
                if isinstance(data, dict) and "choices" in data:
                    return data["choices"][0]["message"]["content"]
                if isinstance(data, str):
                    return data
                return json.dumps(data, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pollinations openai endpoint failed: %s", exc)

        # Fallback: simple GET text endpoint
        prompt = f"{system}\n\n{user}"
        if json_mode:
            prompt += "\n\nRespond with JSON only."
        url = f"{POLLINATIONS_TEXT}/{quote(prompt[:3500])}"
        res = await client.get(url)
        if res.status_code >= 400:
            raise LLMError(
                f"免费文本模型不可用 ({res.status_code})。可在「模型设置」里改用自定义 URL+Key。"
            )
        return res.text
