from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.models.custom_book_schemas import (
    CharacterPromptIn,
    CustomBookOrderOut,
    OrderListItem,
    PageTextIn,
    ParentMessageIn,
)
from app.services.custom_book import workflow
from app.store.custom_book_db import custom_book_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/custom-book", tags=["custom-book"])


def _err(exc: Exception) -> HTTPException:
    if isinstance(exc, workflow.CustomBookError):
        return HTTPException(status_code=400, detail=str(exc))
    # 500 只透出脱敏文案，原始异常记日志，避免把第三方 API 报错原文泄露给前端
    logger.exception("custom-book unexpected error: %s", exc)
    return HTTPException(
        status_code=500,
        detail="生成过程中出现意外错误，请稍后重试；如持续失败请查看后端日志。",
    )


@router.get("/orders", response_model=list[OrderListItem])
async def list_orders() -> list[OrderListItem]:
    return workflow.list_orders()


@router.post("/orders", response_model=CustomBookOrderOut)
async def create_order(
    background_tasks: BackgroundTasks,
    child_name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    theme: str = Form(...),
    emotion_goal: str = Form(""),
    photos: list[UploadFile] = File(...),
    auto_prepare: bool = Form(True),
) -> CustomBookOrderOut:
    if age < 1 or age > 12:
        raise HTTPException(status_code=400, detail="年龄需在 1–12 岁")
    if gender not in ("boy", "girl"):
        raise HTTPException(status_code=400, detail="gender 应为 boy 或 girl")
    if len(photos) < 3:
        raise HTTPException(status_code=400, detail="至少上传 3 张孩子照片")

    tmp_dir = Path(tempfile.mkdtemp(prefix="cb_photos_"))
    saved: list[Path] = []
    try:
        for i, up in enumerate(photos):
            suffix = Path(up.filename or f"photo_{i}.jpg").suffix.lower() or ".jpg"
            if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
                suffix = ".jpg"
            dest = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
            content = await up.read()
            if len(content) < 1024:
                raise HTTPException(status_code=400, detail="照片文件过小或损坏")
            if len(content) > 20 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="单张照片不能超过 20MB")
            dest.write_bytes(content)
            saved.append(dest)

        order = workflow.create_order_with_photos(
            child_name=child_name,
            age=age,
            gender=gender,
            theme=theme,
            emotion_goal=emotion_goal,
            photo_paths=saved,
        )
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if auto_prepare:
        custom_book_store.update_order(order.id, status="preparing", error=None)
        background_tasks.add_task(_bg_prepare, order.id)
        refreshed = custom_book_store.get_order(order.id)
        assert refreshed
        return workflow.serialize_order(refreshed)
    return order


def _mark_failed(order_id: str, exc: Exception) -> None:
    """后台任务失败时把订单置为 failed 并记录错误，避免永远卡在生成中。"""
    logger.exception("custom-book background task failed (order=%s): %s", order_id, exc)
    custom_book_store.update_order(order_id, status="failed", error=str(exc))


async def _bg_prepare(order_id: str) -> None:
    try:
        await workflow.prepare_character(order_id)
    except Exception as exc:  # noqa: BLE001
        # prepare_character 内部已置 failed；这里兜底（如校验失败提前抛出）
        _mark_failed(order_id, exc)


def _ensure_can_generate_pages(order: dict) -> None:
    """生成绘本页前的同步校验：角色必须已确认且脚本为 8 页。

    在把状态置为 pages_generating 之前执行，避免前置校验失败后订单卡死。
    """
    profile = order.get("character") or {}
    if profile.get("status") != "confirmed":
        raise HTTPException(status_code=400, detail="请先确认角色后再生成绘本页")
    if len(order.get("pages") or []) != 8:
        raise HTTPException(status_code=400, detail="脚本页数异常，需要 8 页")


async def _bg_generate_pages(order_id: str) -> None:
    try:
        await workflow.run_pages(order_id)
    except Exception as exc:  # noqa: BLE001
        _mark_failed(order_id, exc)


@router.get("/orders/{order_id}", response_model=CustomBookOrderOut)
async def get_order(order_id: str) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return workflow.serialize_order(order)


@router.post("/orders/{order_id}/prepare", response_model=CustomBookOrderOut)
async def prepare(order_id: str, background_tasks: BackgroundTasks) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    background_tasks.add_task(_bg_prepare, order_id)
    await asyncio.sleep(0)
    refreshed = custom_book_store.get_order(order_id)
    assert refreshed
    custom_book_store.update_order(order_id, status="preparing", error=None)
    return workflow.serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


@router.post("/orders/{order_id}/character/regenerate", response_model=CustomBookOrderOut)
async def regenerate_character(
    order_id: str, background_tasks: BackgroundTasks
) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if not order.get("character"):
        raise HTTPException(status_code=400, detail="请先完成角色准备")

    async def _run() -> None:
        try:
            await workflow.regen_character(order_id)
        except Exception as exc:  # noqa: BLE001
            _mark_failed(order_id, exc)

    background_tasks.add_task(_run)
    custom_book_store.update_order(order_id, status="preparing", error=None)
    await asyncio.sleep(0)
    return workflow.serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


@router.post("/orders/{order_id}/character/confirm", response_model=CustomBookOrderOut)
async def confirm_character(order_id: str) -> CustomBookOrderOut:
    try:
        return workflow.confirm_character(order_id)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.patch("/orders/{order_id}/character/prompt", response_model=CustomBookOrderOut)
async def patch_character_prompt(
    order_id: str, body: CharacterPromptIn
) -> CustomBookOrderOut:
    try:
        return workflow.admin_update_prompt(order_id, body.character_prompt)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.post("/orders/{order_id}/pages/generate", response_model=CustomBookOrderOut)
async def generate_pages(
    order_id: str, background_tasks: BackgroundTasks
) -> CustomBookOrderOut:
    order = custom_book_store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    # 先同步校验再置状态，失败直接 400，不会出现订单永久卡在 pages_generating
    _ensure_can_generate_pages(order)

    background_tasks.add_task(_bg_generate_pages, order_id)
    custom_book_store.update_order(order_id, status="pages_generating", error=None)
    await asyncio.sleep(0)
    return workflow.serialize_order(custom_book_store.get_order(order_id))  # type: ignore[arg-type]


@router.post(
    "/orders/{order_id}/pages/{page_no}/regenerate",
    response_model=CustomBookOrderOut,
)
async def regenerate_page(order_id: str, page_no: int) -> CustomBookOrderOut:
    if page_no < 1 or page_no > 8:
        raise HTTPException(status_code=400, detail="页码需 1–8")
    try:
        return await workflow.run_regen_page(order_id, page_no)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.patch(
    "/orders/{order_id}/pages/{page_no}/text",
    response_model=CustomBookOrderOut,
)
async def patch_page_text(
    order_id: str, page_no: int, body: PageTextIn
) -> CustomBookOrderOut:
    try:
        return workflow.update_page_text(order_id, page_no, body.text)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.patch("/orders/{order_id}/parent-message", response_model=CustomBookOrderOut)
async def patch_parent_message(
    order_id: str, body: ParentMessageIn
) -> CustomBookOrderOut:
    try:
        return workflow.set_parent_message(order_id, body.parent_message)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.post("/orders/{order_id}/pdf", response_model=CustomBookOrderOut)
async def make_pdf(order_id: str) -> CustomBookOrderOut:
    try:
        return await workflow.run_pdf(order_id)
    except workflow.CustomBookError as exc:
        raise _err(exc) from exc


@router.get("/orders/{order_id}/pdf")
async def download_pdf(order_id: str) -> FileResponse:
    order = custom_book_store.get_order(order_id)
    if not order or not order.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF 尚未生成")
    path = Path(order["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF 文件缺失")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{order.get('title') or order_id}.pdf",
    )


@router.get("/orders/{order_id}/files/{kind}/{file_id}")
async def get_file(order_id: str, kind: str, file_id: str) -> FileResponse:
    try:
        path, mime = workflow.resolve_file(order_id, kind, file_id)
    except workflow.CustomBookError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type=mime)
