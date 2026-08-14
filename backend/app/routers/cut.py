from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.cut_schemas import WORKFLOWS, CutCreate, CutJobStatus, CutProject
from app.services import cut_pipeline
from app.store.cut_memory import cut_store

router = APIRouter(prefix="/api/cut", tags=["hunjian"])


async def _bg_run(project_id: str) -> None:
    try:
        await cut_pipeline.run_cut_pipeline(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("cut pipeline failed (project=%s): %s", project_id, exc)


@router.get("/workflows")
async def list_workflows() -> dict:
    return {
        "workflows": [
            {"id": "social-short", "title": "短视频强节奏", "bestFor": "抖音 / 小红书 / Reels"},
            {"id": "stock-story", "title": "免费素材故事", "bestFor": "科普 / 概念 / B-roll"},
            {"id": "person-profile", "title": "人物档案", "bestFor": "介绍 / 创始人 / 历史人物"},
            {"id": "explainer", "title": "知识科普", "bestFor": "机制解释 / 抽象概念"},
            {"id": "english-mix", "title": "影视英语混剪", "bestFor": "台词学习（需本地片源）"},
        ]
    }


@router.post("", response_model=CutProject)
async def create_cut(
    body: CutCreate,
    background_tasks: BackgroundTasks,
) -> CutProject:
    if body.workflow not in WORKFLOWS:
        raise HTTPException(status_code=400, detail=f"不支持的 workflow：{body.workflow}")
    project_id = uuid.uuid4().hex[:10]
    project = CutProject.new(project_id, body)
    project.job_status = CutJobStatus.running
    cut_store.create(project)
    background_tasks.add_task(_bg_run, project_id)
    await asyncio.sleep(0)
    refreshed = cut_store.get(project_id)
    assert refreshed
    return refreshed


@router.get("/{project_id}", response_model=CutProject)
async def get_cut(project_id: str) -> CutProject:
    project = cut_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="混剪项目不存在")
    return project


@router.get("/{project_id}/assets/{asset_id}")
async def get_cut_asset(project_id: str, asset_id: str) -> FileResponse:
    project = cut_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="混剪项目不存在")
    asset = project.assets.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资源不存在")
    path = Path(asset.meta.get("path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件缺失")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.filename)
