"""Shared creative constraints for children's picture-book pipeline."""

from __future__ import annotations

WATERCOLOR_STYLE_EN = (
    "consistent soft watercolor children's picture book illustration, "
    "hand-painted watercolor washes, gentle paper texture, pastel palette, "
    "same art style in every frame, no photorealism, no 3D render, no collage, "
    "no text, no watermark, vertical 9:16 full-bleed composition"
)

WATERCOLOR_NEGATIVE = (
    "photorealistic, 3d, cgi, anime screenshot, collage, mixed styles, "
    "text, logo, watermark, adult, scary, dark horror"
)


def _iter_characters(characters: list):
    for c in characters or []:
        name = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else "")
        appearance = getattr(c, "appearance_en", None) or (
            c.get("appearance_en") if isinstance(c, dict) else ""
        )
        role = getattr(c, "role", None) or (c.get("role") if isinstance(c, dict) else "")
        name = str(name or "").strip()
        appearance = str(appearance or "").strip()
        role = str(role or "").strip()
        if name or appearance:
            yield name, appearance, role


def character_cards(characters: list) -> list[dict[str, str]]:
    """Normalize story cast into compact character cards."""
    cards: list[dict[str, str]] = []
    for name, appearance, role in _iter_characters(characters):
        if not name or not appearance:
            continue
        cards.append({"name": name, "appearance_en": appearance, "role": role})
    return cards


def cast_block_en(characters: list) -> str:
    """Named cast block for prompts / storyboard injection."""
    parts: list[str] = []
    for name, appearance, _role in _iter_characters(characters):
        if name and appearance:
            parts.append(f"{name}: {appearance}")
        elif appearance:
            parts.append(appearance)
    if not parts:
        return (
            "Keep the same animal/character designs across all shots; "
            "do not replace animals with human children unless the story says so."
        )
    return "; ".join(parts)


def characters_lock_en(characters: list) -> str:
    """Build a character consistency lock string from Story.characters."""
    block = cast_block_en(characters)
    if block.startswith("Keep the same"):
        return block
    return (
        "CHARACTER LOCK (must match exactly, do not invent humans unless listed): "
        + block
    )


def life_characters_lock_en(characters: list) -> str:
    """Stricter lock for 人生副本."""
    base = characters_lock_en(characters)
    return (
        f"{base}. SAME FACE, hairstyle, age, outfit palette across every frame; "
        "one consistent protagonist; do not swap actors or ethnicity."
    )


def cast_reference_prompt_en(characters: list) -> str:
    """
    Prompt for a one-shot character design sheet (合影设定稿).
    Used as MiniMax subject_reference for all later pages.
    """
    cards = character_cards(characters)
    if not cards:
        return (
            f"{WATERCOLOR_STYLE_EN}. Character design reference sheet, "
            "front view of the main story animal characters on a plain soft cream background, "
            "full body, clear silhouette, no scene, no text"
        )
    lines = []
    for i, card in enumerate(cards, start=1):
        lines.append(f"{i}) {card['name']}: {card['appearance_en']}")
    cast = " | ".join(lines)
    return (
        f"{WATERCOLOR_STYLE_EN}. "
        "Character design reference sheet / model sheet, front view, full body, "
        "plain soft cream background, even lighting, clear readable silhouettes, "
        "all cast standing side by side as a group design sheet, "
        "no environment, no props clutter, no text, no watermark. "
        f"Cast: {cast}"
    )[:1500]


def inject_cast_into_visual_prompt(visual_prompt: str, characters: list) -> str:
    """Force every page prompt to name-lock character appearances."""
    block = cast_block_en(characters)
    raw = (visual_prompt or "").strip()
    if not block or block.startswith("Keep the same"):
        return raw[:500]
    prefix = f"CAST: {block}. "
    if raw.upper().startswith("CAST:"):
        return raw[:500]
    return (prefix + raw)[:500]
