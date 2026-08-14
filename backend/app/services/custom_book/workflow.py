from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from app.models.custom_book_schemas import (
    CharacterAssetOut,
    CharacterProfileOut,
    CustomBookOrderOut,
    OrderListItem,
    OrderStatus,
    PageOut,
    PageStatus,
    PhotoOut,
    StoryPageOut,
    StoryScript,
)
from app.services.custom_book.character import generate_character_sheet, order_dir
from app.services.custom_book.page_image import generate_all_pages, regenerate_page
from app.services.custom_book.pdf import create_pdf
from app.services.custom_book.photo_select import score_photo, select_best_photos
from app.services.custom_book.story import generate_character_profile, generate_story_script
from app.store.custom_book_db import custom_book_store

logger = logging.getLogger(__name__)

API_PREFIX = "/api/custom-book"


class CustomBookError(Exception):
    pass


def _photo_mime(path: Path) -> str:
    """按扩展名返回正确 MIME（HEIC 浏览器也能直接预览）。"""
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext in (".heic", ".heif"):
        return "image/heic"
    return "image/jpeg"


def _asset_url(order_id: str, kind: str, file_id: str) -> str:
    return f"{API_PREFIX}/orders/{order_id}/files/{kind}/{file_id}"


def serialize_order(order: dict) -> CustomBookOrderOut:
    order_id = order["id"]
    story = None
    if order.get("story_json"):
        try:
            raw = json.loads(order["story_json"])
            story = StoryScript(
                title=str(raw.get("title") or ""),
                character_description=str(raw.get("character_description") or ""),
                pages=[
                    StoryPageOut(
                        page=int(p["page"]),
                        text=str(p.get("text") or ""),
                        scene_prompt=str(p.get("scene_prompt") or ""),
                        emotion=str(p.get("emotion") or ""),
                    )
                    for p in (raw.get("pages") or [])
                ],
            )
        except Exception:  # noqa: BLE001
            story = None

    character = None
    if order.get("character"):
        c = order["character"]
        character = CharacterProfileOut(
            name=c["name"],
            age=int(c["age"]),
            face_shape=c.get("face_shape") or "",
            hair=c.get("hair") or "",
            eyes=c.get("eyes") or "",
            skin=c.get("skin") or "",
            special_features=c.get("special_features") or "",
            clothing_style=c.get("clothing_style") or "",
            character_prompt=c.get("character_prompt") or "",
            status=c.get("status") or "draft",
            confirmed_at=c.get("confirmed_at"),
        )

    # Latest generation only for display
    assets_raw = order.get("character_assets") or []
    max_gen = max((int(a.get("generation") or 1) for a in assets_raw), default=0)
    character_assets = [
        CharacterAssetOut(
            view_type=a["view_type"],
            url=_asset_url(order_id, "character", a["id"]),
            generation=int(a.get("generation") or 1),
        )
        for a in assets_raw
        if int(a.get("generation") or 1) == max_gen
    ]

    photos = [
        PhotoOut(
            id=p["id"],
            url=_asset_url(order_id, "photo", p["id"]),
            sort_order=int(p["sort_order"]),
            quality_score=float(p.get("quality_score") or 0),
        )
        for p in (order.get("photos") or [])
    ]

    pages = [
        PageOut(
            page_no=int(p["page_no"]),
            text=p.get("text") or "",
            scene_prompt=p.get("scene_prompt") or "",
            emotion=p.get("emotion") or "",
            image_url=_asset_url(order_id, "page", p["id"]) if p.get("image_path") else None,
            status=PageStatus(p.get("status") or "pending"),
            regen_count=int(p.get("regen_count") or 0),
            version=int(p.get("version") or 1),
        )
        for p in (order.get("pages") or [])
    ]

    pdf_url = None
    if order.get("pdf_path") and Path(order["pdf_path"]).exists():
        pdf_url = f"{API_PREFIX}/orders/{order_id}/pdf"

    return CustomBookOrderOut(
        id=order_id,
        child_name=order["child_name"],
        age=int(order["age"]),
        gender=order["gender"],
        theme=order["theme"],
        emotion_goal=order.get("emotion_goal") or "",
        parent_message=order.get("parent_message") or "",
        status=OrderStatus(order["status"]),
        title=order.get("title") or "",
        story=story,
        character=character,
        character_assets=character_assets,
        photos=photos,
        pages=pages,
        pdf_url=pdf_url,
        character_regen_count=int(order.get("character_regen_count") or 0),
        error=order.get("error"),
        created_at=order["created_at"],
        updated_at=order["updated_at"],
    )


def create_order_with_photos(
    *,
    child_name: str,
    age: int,
    gender: str,
    theme: str,
    emotion_goal: str,
    photo_paths: list[Path],
) -> CustomBookOrderOut:
    if len(photo_paths) < 3:
        raise CustomBookError("至少上传 3 张孩子照片")
    if len(photo_paths) > 5:
        photo_paths = select_best_photos(photo_paths, max_keep=5)

    order = custom_book_store.create_order(
        child_name=child_name.strip(),
        age=age,
        gender=gender,
        theme=theme.strip(),
        emotion_goal=(emotion_goal or "").strip(),
    )
    order_id = order["id"]
    dest = order_dir(order_id) / "photos"
    dest.mkdir(parents=True, exist_ok=True)

    saved: list[tuple[str, int, float]] = []
    for i, src in enumerate(photo_paths):
        target = dest / f"photo_{i + 1}{src.suffix.lower() or '.jpg'}"
        shutil.copy2(src, target)
        saved.append((str(target), i, score_photo(target)))
    custom_book_store.add_photos(order_id, saved)
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


async def prepare_character(order_id: str) -> CustomBookOrderOut:
    """Story → character profile → Flux character sheet (not story pages)."""
    from app.runtime_config import runtime_config

    order = custom_book_store.get_order(order_id)
    if not order:
        raise CustomBookError("订单不存在")
    if len(order.get("photos") or []) < 3:
        raise CustomBookError("照片不足 3 张")
    if runtime_config.get().text_preset == "mock":
        raise CustomBookError(
            "定制绘本需要真实文本模型。请先在「模型配置」（或本页上方 API Key 面板）"
            "填写 DeepSeek API Key 并保存，再重新生成。"
        )

    custom_book_store.update_order(
        order_id, status=OrderStatus.preparing.value, error=None
    )
    try:
        story = await generate_story_script(
            child_name=order["child_name"],
            age=int(order["age"]),
            gender=order["gender"],
            theme=order["theme"],
            emotion_goal=order.get("emotion_goal") or "",
        )
        custom_book_store.set_story(order_id, story["title"], story)
        custom_book_store.replace_pages(order_id, story["pages"])

        profile = await generate_character_profile(
            child_name=order["child_name"],
            age=int(order["age"]),
            gender=order["gender"],
            theme=order["theme"],
            character_description=story.get("character_description") or "",
        )
        custom_book_store.upsert_character_profile(
            order_id,
            name=profile["name"],
            age=int(profile["age"]),
            face_shape=profile["face_shape"],
            hair=profile["hair"],
            eyes=profile["eyes"],
            skin=profile["skin"],
            special_features=profile["special_features"],
            clothing_style=profile["clothing_style"],
            character_prompt=profile["character_prompt"],
            status="draft",
        )
        await generate_character_sheet(order_id, is_regen=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("prepare_character failed")
        custom_book_store.update_order(
            order_id, status=OrderStatus.failed.value, error=str(exc)
        )
        raise CustomBookError(str(exc)) from exc

    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


async def regen_character(order_id: str) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise CustomBookError("订单不存在")
    if not order.get("character"):
        raise CustomBookError("请先完成角色准备")
    if order["status"] not in (
        OrderStatus.character_pending.value,
        OrderStatus.failed.value,
    ):
        # Allow regen before confirm; after confirm block unless still pending
        char_status = (order.get("character") or {}).get("status")
        if char_status == "confirmed":
            raise CustomBookError("角色已确认，如需重做请新建订单")
    try:
        custom_book_store.update_order(
            order_id, status=OrderStatus.preparing.value, error=None
        )
        await generate_character_sheet(order_id, is_regen=True)
    except Exception as exc:  # noqa: BLE001
        custom_book_store.update_order(
            order_id, status=OrderStatus.failed.value, error=str(exc)
        )
        raise CustomBookError(str(exc)) from exc
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


def confirm_character(order_id: str) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise CustomBookError("订单不存在")
    if order["status"] != OrderStatus.character_pending.value:
        raise CustomBookError("当前状态不可确认角色")
    if not order.get("character_assets"):
        raise CustomBookError("尚无角色设计图")
    custom_book_store.confirm_character(order_id)
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


def admin_update_prompt(order_id: str, character_prompt: str) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order or not order.get("character"):
        raise CustomBookError("角色档案不存在")
    custom_book_store.update_character_prompt(order_id, character_prompt.strip())
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


async def run_pages(order_id: str) -> CustomBookOrderOut:
    try:
        await generate_all_pages(order_id)
    except Exception as exc:  # noqa: BLE001
        raise CustomBookError(str(exc)) from exc
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


async def run_regen_page(order_id: str, page_no: int) -> CustomBookOrderOut:
    try:
        await regenerate_page(order_id, page_no)
    except Exception as exc:  # noqa: BLE001
        raise CustomBookError(str(exc)) from exc
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


def update_page_text(order_id: str, page_no: int, text: str) -> CustomBookOrderOut:
    page = custom_book_store.get_page(order_id, page_no)
    if not page:
        raise CustomBookError("页面不存在")
    custom_book_store.update_page(order_id, page_no, text=text.strip())
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


def set_parent_message(order_id: str, message: str) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise CustomBookError("订单不存在")
    custom_book_store.update_order(order_id, parent_message=message.strip())
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


async def run_pdf(order_id: str) -> CustomBookOrderOut:
    try:
        await create_pdf(order_id)
    except Exception as exc:  # noqa: BLE001
        raise CustomBookError(str(exc)) from exc
    return serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


def list_orders() -> list[OrderListItem]:
    return [
        OrderListItem(
            id=r["id"],
            child_name=r["child_name"],
            age=int(r["age"]),
            theme=r["theme"],
            status=OrderStatus(r["status"]),
            title=r.get("title") or "",
            updated_at=r["updated_at"],
        )
        for r in custom_book_store.list_orders()
    ]


def resolve_file(order_id: str, kind: str, file_id: str) -> tuple[Path, str]:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise CustomBookError("订单不存在")
    if kind == "photo":
        for p in order.get("photos") or []:
            if p["id"] == file_id:
                path = Path(p["path"])
                mime = _photo_mime(path)
                return path, mime
    if kind == "character":
        for a in order.get("character_assets") or []:
            if a["id"] == file_id:
                return Path(a["path"]), "image/png"
    if kind == "page":
        for p in order.get("pages") or []:
            if p["id"] == file_id and p.get("image_path"):
                return Path(p["image_path"]), "image/png"
    raise CustomBookError("文件不存在")
