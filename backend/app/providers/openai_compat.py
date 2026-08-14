from __future__ import annotations

import logging
from typing import Any

import httpx

from app.runtime_config import RuntimeConfig, runtime_config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def _resolve_text_endpoint(cfg: RuntimeConfig) -> tuple[str, str, str]:
    base = (cfg.text_base_url or "").rstrip("/")
    key = cfg.text_api_key or ""
    model = cfg.text_model or ""

    if cfg.text_preset == "gemini":
        base = base or "https://generativelanguage.googleapis.com/v1beta/openai"
        model = model or "gemini-2.0-flash"
    elif cfg.text_preset == "groq":
        base = base or "https://api.groq.com/openai/v1"
        model = model or "llama-3.3-70b-versatile"
    elif cfg.text_preset == "deepseek":
        base = base or "https://api.deepseek.com"
        model = model or "deepseek-v4-flash"

    if not base:
        raise LLMError("未配置文本模型 Base URL")
    if cfg.text_preset != "mock" and not key:
        raise LLMError("请先在「模型配置」里填写文本 API Key")
    if not model:
        raise LLMError("请先在「模型配置」里填写模型名")

    return base, key, model


def _extract_message_text(message: dict[str, Any]) -> str:
    """Prefer final content; fall back to reasoning if it contains JSON."""
    content = (message.get("content") or "").strip()
    if content:
        return content
    reasoning = (message.get("reasoning_content") or "").strip()
    if "{" in reasoning and "}" in reasoning:
        return reasoning
    # Some gateways nest text
    for key in ("text", "output_text"):
        val = message.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


async def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
) -> dict[str, Any]:
    cfg = runtime_config.get()
    if cfg.text_preset == "mock":
        raise LLMError("当前为 mock，不应调用 chat_json")

    base, key, model = _resolve_text_endpoint(cfg)
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # DeepSeek flash/reasoner often burns tokens on reasoning and returns empty content
    system_strict = (
        system
        + "\n重要：只输出一个合法 JSON 对象；字符串内不要换行；不要输出思考过程或 Markdown。"
    )

    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": system_strict},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    # Best-effort: disable thinking on DeepSeek-compatible gateways
    if cfg.text_preset == "deepseek" or "deepseek" in model.lower():
        payload["thinking"] = {"type": "disabled"}

    data = await _post_chat(url, headers, payload, user=user)

    message = data["choices"][0]["message"]
    content = _extract_message_text(message)
    finish = data["choices"][0].get("finish_reason")
    usage = data.get("usage") or {}

    if not content:
        logger.warning(
            "Empty LLM content finish=%s usage=%s; retrying without thinking + higher tokens",
            finish,
            usage,
        )
        payload.pop("thinking", None)
        payload["max_tokens"] = 12000
        payload["temperature"] = min(temperature, 0.25)
        payload["messages"] = [
            {
                "role": "system",
                "content": system_strict
                + "\n再次强调：content 字段必须是完整 JSON，禁止只输出推理。",
            },
            {
                "role": "user",
                "content": user + "\n\n请直接给出 JSON，从 { 开始到 } 结束。",
            },
        ]
        data = await _post_chat(url, headers, payload, user=user)
        message = data["choices"][0]["message"]
        content = _extract_message_text(message)

    if not content:
        raise LLMError(
            "文本模型返回空内容（可能被推理占满 token）。"
            f" finish={finish} usage={usage}"
        )

    try:
        return _parse_json_content(content)
    except LLMError as first_err:
        logger.warning("JSON parse failed (%s), one more retry", first_err)
        payload["temperature"] = 0.2
        payload["messages"][-1]["content"] = (
            user + "\n\n只输出一行紧凑 JSON，不要换行字符。"
        )
        data = await _post_chat(url, headers, payload, user=user)
        content = _extract_message_text(data["choices"][0]["message"])
        if not content:
            raise LLMError("文本模型重试仍返回空内容") from first_err
        return _parse_json_content(content)


async def _post_chat(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    user: str,
) -> dict[str, Any]:
    try:
        # trust_env=False：避免继承失效的 HTTP(S)_PROXY（Cursor/沙箱代理会导致 ConnectError）
        async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code >= 400:
                # Drop unsupported fields and retry
                body_text = res.text or ""
                retry_payload = dict(payload)
                changed = False
                if "thinking" in retry_payload and (
                    res.status_code in (400, 422) or "thinking" in body_text.lower()
                ):
                    retry_payload.pop("thinking", None)
                    changed = True
                if "response_format" in retry_payload and res.status_code in (400, 422):
                    retry_payload.pop("response_format", None)
                    retry_payload["messages"] = list(retry_payload["messages"])
                    retry_payload["messages"][-1] = {
                        "role": "user",
                        "content": user + "\n\n请只输出合法 JSON，不要 Markdown。",
                    }
                    changed = True
                if changed:
                    res = await client.post(url, headers=headers, json=retry_payload)
                if res.status_code >= 400:
                    raise LLMError(
                        f"文本模型调用失败 ({res.status_code}): {res.text[:400]}"
                    )
            return res.json()
    except httpx.ConnectError as exc:
        raise LLMError(
            f"文本模型网络错误: 无法连接 {url}（{exc}）。"
            "请检查本机网络，或确认 DeepSeek Base URL / API Key 是否正确。"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"文本模型网络错误: {exc}") from exc


def _fix_control_chars_in_strings(s: str) -> str:
    """Escape raw control characters inside JSON string literals."""
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\" and in_string:
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ord(ch) < 32:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(f"\\u{ord(ch):04x}")
            continue
        out.append(ch)
    return "".join(out)


def _parse_json_content(content: str) -> dict[str, Any]:
    import json
    import re

    text = content.strip().lstrip("\ufeff")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))

    errors: list[str] = []
    for raw in candidates:
        for variant in (raw, _fix_control_chars_in_strings(raw)):
            try:
                data = json.loads(variant)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
                continue

    raise LLMError(
        f"无法解析 JSON: {errors[-1] if errors else 'unknown'}; {text[:300]}"
    )
