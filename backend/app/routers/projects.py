from __future__ import annotations

import asyncio
import logging
import uuid

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import (
    JobStatus,
    Project,
    ProjectCreate,
    ProjectUpdateStory,
    ProvidersResponse,
    RunRequest,
    StepName,
    utcnow,
)
from app.providers.registry import list_providers
from app.services import pipeline
from app.store.memory import store

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pictale"}


@router.get("/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    return list_providers()


@router.post("/projects", response_model=Project)
async def create_project(body: ProjectCreate) -> Project:
    project_id = uuid.uuid4().hex[:10]
    project = Project.new(project_id, body)
    return store.create(project)


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}/story", response_model=Project)
async def update_story(project_id: str, body: ProjectUpdateStory) -> Project:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.story:
        raise HTTPException(status_code=400, detail="Story not generated yet")
    if body.title is not None:
        project.story.title = body.title
    if body.summary is not None:
        project.story.summary = body.summary
    if body.paragraphs is not None:
        project.story.paragraphs = body.paragraphs
    project.updated_at = utcnow()
    return store.save(project)


@router.post("/projects/{project_id}/steps/{step}", response_model=Project)
async def run_single_step(project_id: str, step: StepName) -> Project:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.job_status == JobStatus.running:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    try:
        return await pipeline.run_step(project, step)
    except pipeline.PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _bg_run(project_id: str, from_step: StepName | None) -> None:
    try:
        await pipeline.run_pipeline(project_id, from_step=from_step)
    except Exception as exc:  # noqa: BLE001
        # Errors persisted on project by pipeline; 仍记录日志便于排查
        logger.exception("pictale pipeline failed (project=%s): %s", project_id, exc)


@router.post("/projects/{project_id}/run", response_model=Project)
async def run_full(
    project_id: str,
    background_tasks: BackgroundTasks,
    body: RunRequest | None = None,
) -> Project:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.job_status == JobStatus.running:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    from_step = body.from_step if body else None
    project.job_status = JobStatus.running
    project.job_error = None
    store.save(project)
    background_tasks.add_task(_bg_run, project_id, from_step)
    # Yield so client gets running state immediately
    await asyncio.sleep(0)
    refreshed = store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/projects/{project_id}/assets/{asset_id}")
async def get_asset(project_id: str, asset_id: str) -> FileResponse:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        path, asset = pipeline.resolve_asset_path(project, asset_id)
    except pipeline.PipelineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.filename,
    )
