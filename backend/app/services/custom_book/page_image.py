from __future__ import annotations

import logging
from pathlib import Path

from app.models.custom_book_schemas import OrderStatus, PageStatus
from app.providers.flux_image import generate_page
from app.services.custom_book.character import order_dir
from app.store.custom_book_db import custom_book_store

logger = logging.getLogger(__name__)


async def generate_all_pages(order_id: str) -> None:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise RuntimeError("订单不存在")
    if order["status"] not in (
        OrderStatus.character_confirmed.value,
        OrderStatus.pages_generating.value,
        OrderStatus.pages_review.value,
    ):
        raise RuntimeError("请先确认角色后再生成绘本页")

    profile = order.get("character") or {}
    prompt = (profile.get("character_prompt") or "").strip()
    if not prompt:
        raise RuntimeError("缺少 character_prompt")
    if profile.get("status") != "confirmed":
        raise RuntimeError("角色尚未确认")

    pages = order.get("pages") or []
    if len(pages) != 8:
        raise RuntimeError("脚本页数异常，需要 8 页")

    custom_book_store.update_order(
        order_id, status=OrderStatus.pages_generating.value, error=None
    )
    pages_dir = order_dir(order_id) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    ok = 0
    for page in pages:
        page_no = int(page["page_no"])
        if page.get("status") in (
            PageStatus.ready.value,
            PageStatus.locked.value,
        ) and page.get("image_path"):
            ok += 1
            continue
        try:
            await _generate_one(order_id, page, prompt, pages_dir)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("page %s failed", page_no)
            custom_book_store.update_page(
                order_id, page_no, status=PageStatus.failed.value
            )
            errors.append(f"第{page_no}页: {exc}")

    summary = None
    if errors:
        summary = (
            f"已完成 {ok}/8 页；失败已跳过，可单页重试。"
            f"{'；'.join(errors[:4])}"
            + ("…" if len(errors) > 4 else "")
        )
    custom_book_store.update_order(
        order_id,
        status=OrderStatus.pages_review.value,
        error=summary,
    )
    if ok == 0:
        raise RuntimeError(summary or "全部绘本页生成失败")


async def regenerate_page(order_id: str, page_no: int) -> None:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise RuntimeError("订单不存在")
    page = custom_book_store.get_page(order_id, page_no)
    if not page:
        raise RuntimeError(f"第 {page_no} 页不存在")
    # failed / pending 可生成；ready 页最多重生 1 次
    if page.get("status") in (PageStatus.ready.value, PageStatus.locked.value) and int(
        page.get("regen_count") or 0
    ) >= 1:
        raise RuntimeError(f"第 {page_no} 页已达重生上限（每页最多 1 次）")

    profile = order.get("character") or {}
    prompt = (profile.get("character_prompt") or "").strip()
    if not prompt:
        raise RuntimeError("缺少 character_prompt")

    pages_dir = order_dir(order_id) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    is_regen = page.get("status") in (
        PageStatus.ready.value,
        PageStatus.locked.value,
    )
    await _generate_one(order_id, page, prompt, pages_dir, is_regen=is_regen)


async def _generate_one(
    order_id: str,
    page: dict,
    character_prompt: str,
    pages_dir: Path,
    *,
    is_regen: bool = False,
) -> None:
    page_no = int(page["page_no"])
    version = int(page.get("version") or 1) + (1 if is_regen else 0)
    if not is_regen:
        version = max(1, int(page.get("version") or 1))

    custom_book_store.update_page(
        order_id, page_no, status=PageStatus.generating.value
    )
    out = pages_dir / f"page_{page_no:02d}_v{version}.png"
    await generate_page(
        character_prompt=character_prompt,
        scene_prompt=page.get("scene_prompt") or "",
        emotion=page.get("emotion") or "warm",
        out_path=out,
    )
    regen_count = int(page.get("regen_count") or 0) + (1 if is_regen else 0)
    status = PageStatus.locked.value if regen_count >= 1 else PageStatus.ready.value
    custom_book_store.update_page(
        order_id,
        page_no,
        image_path=str(out),
        status=status,
        regen_count=regen_count,
        version=version,
    )
