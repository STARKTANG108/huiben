from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.life_schemas import (
    LIFE_DEFAULT_BGM_TRACK_ID,
    LIFE_DEFAULT_TTS_VOICE,
    LifeCreate,
    LifeOptionsResponse,
    LifeProject,
    LifeRunRequest,
)
from app.models.schemas import JobStatus, StepName
from app.providers.life_bgm import available_life_bgm_tracks
from app.runtime_config import MINIMAX_VOICES
from app.services import life_pipeline
from app.store.life_memory import life_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/life", tags=["life"])

# 持有 create_task 的引用，防止任务被 GC 中断（进程重启前不丢）
_life_tasks: set[asyncio.Task] = set()


@router.get("/options", response_model=LifeOptionsResponse)
async def life_options() -> LifeOptionsResponse:
    tracks = [
        {"id": t["id"], "title": t["title"]}
        for t in available_life_bgm_tracks()
    ]
    # 推荐曲目置顶
    preferred = [t for t in tracks if t["id"] == LIFE_DEFAULT_BGM_TRACK_ID]
    others = [t for t in tracks if t["id"] != LIFE_DEFAULT_BGM_TRACK_ID]
    voices = [
        {"id": v["id"], "label": v.get("label") or v["id"], "group": v.get("group") or ""}
        for v in MINIMAX_VOICES
    ]
    # 默认温润男声置顶标注
    for v in voices:
        if v["id"] == LIFE_DEFAULT_TTS_VOICE and "推荐" not in v["label"]:
            v["label"] = f"{v['label']}（推荐）"
            break
    return LifeOptionsResponse(
        durations=[],
        bgm_tracks=preferred + others + [{"id": "", "title": "系统随机"}],
        voices=voices,
        defaults={
            "target_sec": 0,
            "tts_voice": LIFE_DEFAULT_TTS_VOICE,
            "bgm_track_id": LIFE_DEFAULT_BGM_TRACK_ID,
        },
    )


@router.post("", response_model=LifeProject)
async def create_life(body: LifeCreate) -> LifeProject:
    if not (body.story_text or "").strip():
        raise HTTPException(status_code=400, detail="请填写故事正文")
    project_id = uuid.uuid4().hex[:10]
    project = LifeProject.new(project_id, body)
    return life_store.create(project)


@router.get("/{project_id}", response_model=LifeProject)
async def get_life(project_id: str) -> LifeProject:
    project = life_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="人生副本项目不存在")
    return project


@router.post("/{project_id}/steps/{step}", response_model=LifeProject)
async def run_single_step(project_id: str, step: StepName) -> LifeProject:
    project = life_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="人生副本项目不存在")
    if project.job_status == JobStatus.running:
        raise HTTPException(status_code=409, detail="流水线正在运行")
    try:
        return await life_pipeline.run_step(project, step)
    except life_pipeline.LifePipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _bg_run(project_id: str, from_step: StepName | None) -> None:
    try:
        await life_pipeline.run_pipeline(project_id, from_step=from_step)
    except Exception as exc:  # noqa: BLE001
        logger.exception("life pipeline failed (project=%s): %s", project_id, exc)


@router.post("/{project_id}/run", response_model=LifeProject)
async def run_full(
    project_id: str,
    body: LifeRunRequest | None = None,
) -> LifeProject:
    project = life_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="人生副本项目不存在")
    if project.job_status == JobStatus.running:
        # 允许前端重复点：若已在跑，直接返回当前状态，避免卡住
        return project

    from_step = body.from_step if body else None
    project.job_status = JobStatus.running
    project.job_error = None
    life_store.save(project)
    # create_task：立刻返回，不堵接口；BackgroundTasks 在长任务时会拖死整站
    task = asyncio.create_task(_bg_run(project_id, from_step))
    _life_tasks.add(task)
    task.add_done_callback(_life_tasks.discard)
    refreshed = life_store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/{project_id}/assets/{asset_id}")
async def get_life_asset(project_id: str, asset_id: str) -> FileResponse:
    project = life_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="人生副本项目不存在")
    try:
        path, asset = life_pipeline.resolve_asset_path(project, asset_id)
    except life_pipeline.LifePipelineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.filename,
    )
