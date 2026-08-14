from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.outfit_schemas import OutfitCreate, OutfitJobStatus, OutfitProject
from app.services import outfit_pipeline
from app.store.outfit_memory import outfit_store

router = APIRouter(prefix="/api/outfits", tags=["outfits"])


async def _bg_run(project_id: str) -> None:
    try:
        await outfit_pipeline.run_outfit_pipeline(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("outfit pipeline failed (project=%s): %s", project_id, exc)


@router.post("", response_model=OutfitProject)
async def create_outfit(
    body: OutfitCreate,
    background_tasks: BackgroundTasks,
) -> OutfitProject:
    project_id = uuid.uuid4().hex[:10]
    project = OutfitProject.new(project_id, body)
    project.job_status = OutfitJobStatus.running
    outfit_store.create(project)
    background_tasks.add_task(_bg_run, project_id)
    await asyncio.sleep(0)
    refreshed = outfit_store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/{project_id}", response_model=OutfitProject)
async def get_outfit(project_id: str) -> OutfitProject:
    project = outfit_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Outfit project not found")
    return project


@router.get("/{project_id}/assets/{asset_id}")
async def get_outfit_asset(project_id: str, asset_id: str) -> FileResponse:
    project = outfit_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Outfit project not found")
    asset = project.assets.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset file missing")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.filename)
