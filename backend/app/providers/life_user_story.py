from __future__ import annotations

"""人生副本：用户自写故事 → 本地切句成脚本（不调用 DeepSeek，不限总时长）。"""

import re

from app.models.life_schemas import (
    LIFE_COVER_PROMPT_EN,
    LIFE_VISUAL_STYLE_EN,
)
from app.models.schemas import Script, ScriptLine, Story, StoryCharacter, StoryParagraph

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*")


def _clean_lines(text: str) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return []
    chunks: list[str] = []
    for para in raw.split("\n"):
        para = para.strip()
        if not para:
            continue
        para = re.sub(r"^[\-\*\d]+[\.\)、]\s*", "", para)
        parts = [p.strip() for p in _SENT_SPLIT.split(para) if p and p.strip()]
        if parts:
            chunks.extend(parts)
        else:
            chunks.append(para)
    return chunks


def _split_long(lines: list[str], max_chars: int = 36) -> list[str]:
    """Only split very long lines for readability; never drop content."""
    out: list[str] = []
    for line in lines:
        if len(line) <= max_chars:
            out.append(line)
            continue
        buf = ""
        for ch in line:
            buf += ch
            if len(buf) >= max_chars and ch in "，、, ":
                out.append(buf.strip())
                buf = ""
        if buf.strip():
            out.append(buf.strip())
    return out


def _estimate_sec(text: str) -> float:
    n = len(text)
    return round(max(2.8, n / 3.4), 2)


def resolve_episode_title(*, title: str, premise: str, story_text: str) -> str:
    t = (title or "").strip()
    if t:
        return t[:40]
    p = (premise or "").strip()
    if p:
        return p[:40]
    first = _clean_lines(story_text)
    if first:
        return first[0][:20].rstrip("。！？!?，,")
    return "平行人生"


def build_story_from_user(
    *,
    story_text: str,
    title: str = "",
    premise: str = "",
    notes: str = "",
) -> Story:
    lines = _clean_lines(story_text)
    if not lines:
        raise ValueError("请先填写故事正文")

    episode = resolve_episode_title(title=title, premise=premise, story_text=story_text)
    paragraphs = [StoryParagraph(index=i, text=t) for i, t in enumerate(lines)]
    summary = " ".join(lines[:2])[:80]
    cover_hook = episode[:14] if len(episode) <= 14 else episode[:12]

    appearance = (
        (notes or "").strip()
        or "young East Asian adult, contemporary casual clothes, natural look, consistent face across frames"
    )
    if notes and not re.search(r"[A-Za-z]{4,}", notes):
        appearance = (
            f"East Asian adult matching description: {notes[:120]}, "
            "contemporary clothes, consistent face across frames"
        )

    return Story(
        title=episode,
        summary=summary,
        age_range="general",
        paragraphs=paragraphs,
        characters=[
            StoryCharacter(
                name="主角",
                appearance_en=appearance[:280],
                role="主角",
            )
        ],
        mood="inspiring",
        provider="user_story",
        cover_hook=cover_hook,
        visual_style_en=LIFE_VISUAL_STYLE_EN,
        cover_prompt_en=(
            "modern cinematic cover, contemporary East Asian scene, strong focal, no text"
        ),
        lessons=[],
    )


def build_script_from_user(story: Story, target_sec: float | None = None) -> Script:
    _ = target_sec  # 时长跟配音走，不再按目标裁切
    raw = [p.text.strip() for p in story.paragraphs if p.text.strip()]
    if not raw:
        raw = [(story.summary or story.title or "这一次，路不同了。").strip()]

    lines_text = _split_long(raw)
    script_lines = [
        ScriptLine(
            index=i,
            text=text,
            estimated_sec=_estimate_sec(text),
            caption=text,
        )
        for i, text in enumerate(lines_text)
    ]
    total = sum(l.estimated_sec for l in script_lines)
    return Script(
        lines=script_lines,
        total_sec=round(total, 2),
        provider="user_story",
    )
