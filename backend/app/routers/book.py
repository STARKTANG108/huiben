from __future__ import annotations

import asyncio
import logging
import uuid

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.book_schemas import BookCreate, BookProject, BookRunRequest
from app.models.schemas import JobStatus, StepName
from app.services import book_pipeline
from app.store.book_memory import book_store

router = APIRouter(prefix="/api/book", tags=["book"])


@router.post("", response_model=BookProject)
async def create_book(body: BookCreate) -> BookProject:
    project_id = uuid.uuid4().hex[:10]
    project = BookProject.new(project_id, body, book_seq=book_store.next_book_seq())
    return book_store.create(project)


@router.get("/{project_id}", response_model=BookProject)
async def get_book(project_id: str) -> BookProject:
    project = book_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="书籍项目不存在")
    return project


@router.post("/{project_id}/steps/{step}", response_model=BookProject)
async def run_single_step(project_id: str, step: StepName) -> BookProject:
    project = book_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="书籍项目不存在")
    if project.job_status == JobStatus.running:
        raise HTTPException(status_code=409, detail="流水线正在运行")
    try:
        return await book_pipeline.run_step(project, step)
    except book_pipeline.BookPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _bg_run(project_id: str, from_step: StepName | None) -> None:
    try:
        await book_pipeline.run_pipeline(project_id, from_step=from_step)
    except Exception as exc:  # noqa: BLE001
        logger.exception("book pipeline failed (project=%s): %s", project_id, exc)


@router.post("/{project_id}/run", response_model=BookProject)
async def run_full(
    project_id: str,
    background_tasks: BackgroundTasks,
    body: BookRunRequest | None = None,
) -> BookProject:
    project = book_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="书籍项目不存在")
    if project.job_status == JobStatus.running:
        raise HTTPException(status_code=409, detail="流水线正在运行")

    from_step = body.from_step if body else None
    project.job_status = JobStatus.running
    project.job_error = None
    book_store.save(project)
    background_tasks.add_task(_bg_run, project_id, from_step)
    await asyncio.sleep(0)
    refreshed = book_store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/{project_id}/assets/{asset_id}")
async def get_book_asset(project_id: str, asset_id: str) -> FileResponse:
    project = book_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="书籍项目不存在")
    try:
        path, asset = book_pipeline.resolve_asset_path(project, asset_id)
    except book_pipeline.BookPipelineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.filename,
    )
