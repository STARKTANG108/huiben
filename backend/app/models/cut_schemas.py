from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CutJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


WORKFLOWS = (
    "social-short",
    "stock-story",
    "person-profile",
    "explainer",
    "english-mix",
)


class CutCreate(BaseModel):
    brief: str = Field(..., min_length=4, max_length=800)
    workflow: str = Field(default="social-short", max_length=40)
    duration: int = Field(default=45, ge=10, le=180)
    format: str = Field(default="9:16", max_length=12)
    notes: str = Field(default="", max_length=400)


class CutScene(BaseModel):
    id: str
    purpose: str = ""
    visual: str = ""
    caption: str = ""
    image_prompt: str = ""
    duration_sec: float = 4.0
    image_asset_id: str | None = None


class CutClipSeekHit(BaseModel):
    id: str
    title: str = ""
    provider: str = ""
    source_page: str | None = None
    thumbnail: str | None = None
    media_type: str = "video"


class CutAsset(BaseModel):
    id: str
    kind: str = "image"
    filename: str
    mime_type: str
    url: str
    meta: dict[str, Any] = Field(default_factory=dict)


class CutProject(BaseModel):
    id: str
    brief: str
    workflow: str
    duration: int
    format: str
    notes: str
    created_at: datetime
    updated_at: datetime
    job_status: CutJobStatus = CutJobStatus.pending
    job_error: str | None = None
    stage: str = ""
    ir: dict[str, Any] = Field(default_factory=dict)
    scenes: list[CutScene] = Field(default_factory=list)
    clipseek: list[CutClipSeekHit] = Field(default_factory=list)
    video_asset_id: str | None = None
    render_engine: str = ""
    doctor_hint: str = ""
    assets: dict[str, CutAsset] = Field(default_factory=dict)

    @classmethod
    def new(cls, project_id: str, data: CutCreate) -> CutProject:
        now = utcnow()
        workflow = (data.workflow or "social-short").strip()
        if workflow not in WORKFLOWS:
            workflow = "social-short"
        fmt = (data.format or "9:16").strip()
        if fmt not in ("9:16", "16:9", "1:1"):
            fmt = "9:16"
        return cls(
            id=project_id,
            brief=data.brief.strip(),
            workflow=workflow,
            duration=int(data.duration),
            format=fmt,
            notes=data.notes.strip(),
            created_at=now,
            updated_at=now,
        )
