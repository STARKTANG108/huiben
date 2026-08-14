from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.xhs_schemas import XhsCreate, XhsJobStatus, XhsProject
from app.services import xhs_pipeline
from app.store.xhs_memory import xhs_store

router = APIRouter(prefix="/api/xhs", tags=["xiaohonglvshu"])


async def _bg_run(project_id: str) -> None:
    try:
        await xhs_pipeline.run_xhs_pipeline(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("xhs pipeline failed (project=%s): %s", project_id, exc)


@router.post("", response_model=XhsProject)
async def create_xhs(
    body: XhsCreate,
    background_tasks: BackgroundTasks,
) -> XhsProject:
    project_id = uuid.uuid4().hex[:10]
    project = XhsProject.new(project_id, body)
    project.job_status = XhsJobStatus.running
    xhs_store.create(project)
    background_tasks.add_task(_bg_run, project_id)
    await asyncio.sleep(0)
    refreshed = xhs_store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/{project_id}", response_model=XhsProject)
async def get_xhs(project_id: str) -> XhsProject:
    project = xhs_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="XHS project not found")
    return project


@router.get("/{project_id}/assets/{asset_id}")
async def get_xhs_asset(project_id: str, asset_id: str) -> FileResponse:
    project = xhs_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="XHS project not found")
    asset = project.assets.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.filename)
