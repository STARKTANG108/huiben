from __future__ import annotations

import re

# 给 LLM 编剧用（不直接塞进 Flux）
SAFE_CONTENT_RULES_CN = (
    "内容必须适合 3–8 岁儿童阅读："
    "温暖正向、无暴力、无恐怖、无色情、无裸露、无仇恨、无政治敏感。"
    "禁止描写身体隐私部位、成人情节、血腥伤害。"
    "情绪可用委婉词：难过、想妈妈、紧张、勇敢、安心。"
)

# Flux 只用正向短描述；避免 no/不要/版权相关词（易误触 CatsAPI）
FLUX_STYLE_EN = (
    "soft watercolor children's picture book illustration, "
    "cute cartoon child, pastel colors, warm and friendly"
)

HAIR_LOCK_EN = "keep the same short hair and bangs in every picture"

_SENSITIVE_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"裸(?:体|露)?|裸体|脱光|赤裸", re.I), "穿着衣服"),
    (re.compile(r"\b(nude|naked|nsfw|sexy|erotic|porn|sexual|nudity)\b", re.I), "cute"),
    (re.compile(r"血腥|屠杀|杀害|枪杀|肢解", re.I), "有点难过"),
    (re.compile(r"\b(blood|gore|kill|murder|gunshot|violence|violent)\b", re.I), "gentle"),
    (re.compile(r"自杀|自残", re.I), "心里难过"),
    (re.compile(r"恐怖|鬼怪|僵尸", re.I), "有点紧张"),
    (re.compile(r"\b(horror|zombie|demon|bloody|weapon)\b", re.I), "soft mood"),
    (re.compile(r"\b(crying|cry|tears|sobbing|weeping)\b", re.I), "a little sad"),
    (re.compile(r"哭(?:泣|闹)?|大哭|流泪", re.I), "有点难过"),
    (re.compile(r"\b\d{1,2}[-\s]?year[-\s]?old\b", re.I), "young kindergarten-age"),
    (re.compile(r"\b(no text|no watermark|no logo|without text|without watermark)\b", re.I), ""),
    (re.compile(r"\b(no nudity|no violence|no blood|no horror|no sexual(?: content)?)\b", re.I), ""),
    # 只删到逗号/句号为止，避免 [^.]* 贪婪把 "do not change hair or hairstyle, consistent character…"
    # 之后的整段角色锁定描述一起吞掉
    (re.compile(r"\b(?:do not|don't|never)\b[^,.]*", re.I), ""),
    (re.compile(r"fully clothed", re.I), "neat clothes"),
    (re.compile(r"CRITICAL IDENTITY LOCK[:\s]*", re.I), ""),
    (re.compile(r"\b(innocent|pajama|pajamas|underwear|apron)\b", re.I), "soft day clothes"),
    (re.compile(r"wheat skin", re.I), "warm fair skin"),
]


def sanitize_prompt_text(text: str) -> str:
    """Light content sanitize for story/profile fields (keeps Chinese)."""
    out = (text or "").strip()
    for pattern, repl in _SENSITIVE_REPLACEMENTS:
        out = pattern.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def sanitize_flux_prompt(text: str) -> str:
    """Flux-only sanitize: also strip Chinese to reduce CatsAPI false positives."""
    out = sanitize_prompt_text(text)
    out = re.sub(r"[\u4e00-\u9fff]+", " ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" .,;")
    return out


def with_safe_scene(scene_prompt: str) -> str:
    base = sanitize_flux_prompt(scene_prompt)
    if len(base) > 220:
        base = base[:220].rsplit(" ", 1)[0]
    return f"{base}, {FLUX_STYLE_EN}"


def flux_character_lock(character_prompt: str) -> str:
    """Compact English identity lock for Flux."""
    base = sanitize_flux_prompt(character_prompt)
    if len(base) > 200:
        base = base[:200].rsplit(" ", 1)[0]
    return f"{base}, {HAIR_LOCK_EN}"


def ultra_safe_character_prompt(character_prompt: str, view_hint: str) -> str:
    """Fallback prompt when CatsAPI moderation rejects the first attempt."""
    base = sanitize_flux_prompt(character_prompt)
    # Keep only coarse traits
    base = re.sub(r"[^a-zA-Z0-9 ,.'-]", " ", base)
    base = re.sub(r"\s{2,}", " ", base).strip()
    if len(base) > 120:
        base = base[:120].rsplit(" ", 1)[0]
    view = sanitize_flux_prompt(view_hint)[:80]
    return (
        f"{FLUX_STYLE_EN}. Cute young child character, {base}. "
        f"{view}. Simple clean background."
    )


def is_moderation_error(message: str) -> bool:
    m = (message or "").lower()
    keys = ("敏感", "铭感", "版权", "sensitive", "nsfw", "policy", "moderat", "违规")
    return any(k in m or k in (message or "") for k in keys)
