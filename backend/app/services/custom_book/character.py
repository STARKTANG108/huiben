from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings
from app.models.custom_book_schemas import CHARACTER_VIEWS, OrderStatus
from app.providers.flux_image import generate_character
from app.store.custom_book_db import custom_book_store

logger = logging.getLogger(__name__)


def order_dir(order_id: str) -> Path:
    path = get_settings().storage_path / "custom-book" / order_id
    path.mkdir(parents=True, exist_ok=True)
    return path


async def generate_character_sheet(order_id: str, *, is_regen: bool = False) -> None:
    order = custom_book_store.get_order(order_id)
    if not order or not order.get("character"):
        raise RuntimeError("角色档案不存在，请先生成故事与档案")

    profile = order["character"]
    prompt = (profile.get("character_prompt") or "").strip()
    if not prompt:
        raise RuntimeError("character_prompt 为空")

    regen_count = int(order.get("character_regen_count") or 0)
    if is_regen:
        regen_count += 1
        custom_book_store.update_order(order_id, character_regen_count=regen_count)

    generation = regen_count + 1
    char_dir = order_dir(order_id) / "character" / f"gen_{generation}"
    char_dir.mkdir(parents=True, exist_ok=True)

    assets: list[tuple[str, str, int]] = []
    errors: list[str] = []
    for view, hint in CHARACTER_VIEWS:
        out = char_dir / f"{view.value}.png"
        try:
            await generate_character(
                character_prompt=prompt,
                view_hint=hint,
                out_path=out,
            )
            assets.append((view.value, str(out), generation))
        except Exception as exc:  # noqa: BLE001
            logger.exception("character view %s failed", view.value)
            errors.append(f"{view.value}: {exc}")

    if not assets:
        raise RuntimeError(
            "角色设计图全部失败：" + ("；".join(errors) if errors else "未知错误")
        )

    custom_book_store.replace_character_assets(profile["id"], assets)
    custom_book_store.upsert_character_profile(
        order_id,
        name=profile["name"],
        age=int(profile["age"]),
        face_shape=profile.get("face_shape") or "",
        hair=profile.get("hair") or "",
        eyes=profile.get("eyes") or "",
        skin=profile.get("skin") or "",
        special_features=profile.get("special_features") or "",
        clothing_style=profile.get("clothing_style") or "",
        character_prompt=prompt,
        status="pending_confirm",
    )
    warn = f"部分视角失败（已跳过）：{'；'.join(errors)}" if errors else None
    custom_book_store.update_order(
        order_id,
        status=OrderStatus.character_pending.value,
        error=warn,
    )
