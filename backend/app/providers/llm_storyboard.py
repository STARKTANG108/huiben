from __future__ import annotations

import logging

from app.models.schemas import Shot, Storyboard
from app.providers.base import StoryboardRequest
from app.providers.openai_compat import LLMError, chat_json
from app.providers.style_lock import cast_block_en, characters_lock_en, inject_cast_into_visual_prompt
from app.runtime_config import runtime_config

logger = logging.getLogger(__name__)


def _shots_from_script(req: StoryboardRequest) -> list[Shot]:
    """Deterministic 1:1 storyboard from script — never depends on LLM JSON."""
    cast = cast_block_en(req.story.characters)
    shots: list[Shot] = []
    lines = req.script.lines
    if not lines:
        lines_text = [req.story.summary or req.story.title]
        for i, text in enumerate(lines_text):
            visual = (
                f"watercolor children's book. CAST: {cast}. Scene: {text}"
            )
            shots.append(
                Shot(
                    index=i,
                    narration=text,
                    visual_prompt=visual[:500],
                    duration_sec=5.0,
                    mood=req.story.mood,
                    characters_in_shot=[
                        c.name for c in req.story.characters if c.name in text
                    ],
                )
            )
        return shots

    for i, line in enumerate(lines):
        chars = [c.name for c in req.story.characters if c.name in line.text]
        # Always name-lock full appearances (not just names)
        visual = (
            f"watercolor children's picture book, soft pastel. "
            f"CAST: {cast}. "
            f"draw: {', '.join(chars) if chars else 'story cast only'}. "
            f"Scene matching: {line.text}"
        )
        shots.append(
            Shot(
                index=i,
                narration=line.text,
                visual_prompt=visual[:500],
                duration_sec=round(max(3.5, min(5.5, line.estimated_sec or 4.5)), 2),
                camera="slow_zoom",
                mood=req.story.mood,
                characters_in_shot=chars,
            )
        )
    return shots


class LLMStoryboardProvider:
    name = "llm"

    async def generate(self, req: StoryboardRequest) -> Storyboard:
        cfg = runtime_config.get()
        # Base: always build from script so this step cannot fail on empty LLM content
        shots = _shots_from_script(req)

        # Optional: enrich English visual prompts via LLM (best-effort)
        try:
            script_text = "\n".join(f"{s.index + 1}. {s.narration}" for s in shots)
            cast_lock = characters_lock_en(req.story.characters)
            data = await chat_json(
                system=(
                    "为儿童水彩绘本分镜写英文画面描述。输出 JSON："
                    '{"items":[{"index":0,"visual_prompt":"short English scene"}]}。'
                    "每条对应一句旁白；只写短英文场景，不要换行；"
                    "角色外观必须与 CHARACTER LOCK 完全一致，禁止换装换色换物种。"
                ),
                user=(
                    f"角色锁定：{cast_lock}\n旁白：\n{script_text}\n"
                    f"共 {len(shots)} 条，index 从 0 到 {len(shots) - 1}。"
                ),
                temperature=0.3,
            )
            items = {
                int(row.get("index", -1)): str(row.get("visual_prompt", "")).strip()
                for row in (data.get("items") or [])
                if str(row.get("visual_prompt", "")).strip()
            }
            for shot in shots:
                enriched = items.get(shot.index)
                if enriched:
                    chars = ", ".join(shot.characters_in_shot) or "story characters"
                    shot.visual_prompt = inject_cast_into_visual_prompt(
                        f"watercolor children's book, {chars}. {enriched}",
                        req.story.characters,
                    )
        except LLMError as exc:
            logger.warning("Storyboard LLM enrich skipped: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Storyboard LLM enrich failed: %s", exc)

        # Defense: ensure cast injection even if enrich skipped
        for shot in shots:
            shot.visual_prompt = inject_cast_into_visual_prompt(
                shot.visual_prompt, req.story.characters
            )

        total = round(sum(s.duration_sec for s in shots), 2)
        return Storyboard(
            shots=shots,
            total_sec=total,
            provider=f"llm:{cfg.text_preset}+script",
        )
