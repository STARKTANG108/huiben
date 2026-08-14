from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class XhsJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class XhsCreate(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)
    notes: str = Field(default="", max_length=400)
    max_cards: int = Field(default=3, ge=1, le=3)
    style: str = Field(default="notion", max_length=32)
    layout: str = Field(default="balanced", max_length=32)


class XhsCard(BaseModel):
    index: int
    hook: str = ""  # 爆点短句，大字
    title: str
    points: list[str] = Field(default_factory=list)
    footer: str = ""
    image_asset_id: str | None = None


class XhsAsset(BaseModel):
    id: str
    kind: str = "image"
    filename: str
    mime_type: str
    url: str
    meta: dict[str, Any] = Field(default_factory=dict)


class XhsProject(BaseModel):
    id: str
    url: str
    notes: str
    max_cards: int
    style: str = "notion"
    layout: str = "balanced"
    created_at: datetime
    updated_at: datetime
    job_status: XhsJobStatus = XhsJobStatus.pending
    job_error: str | None = None
    source_title: str = ""
    source_excerpt: str = ""
    summary: str = ""
    post_title: str = ""  # 可发帖标题
    post_body: str = ""  # 可发帖正文
    cards: list[XhsCard] = Field(default_factory=list)
    assets: dict[str, XhsAsset] = Field(default_factory=dict)

    @classmethod
    def new(cls, project_id: str, data: XhsCreate) -> XhsProject:
        now = utcnow()
        return cls(
            id=project_id,
            url=data.url.strip(),
            notes=data.notes.strip(),
            max_cards=data.max_cards,
            style=(data.style or "notion").strip() or "notion",
            layout=(data.layout or "balanced").strip() or "balanced",
            created_at=now,
            updated_at=now,
        )
