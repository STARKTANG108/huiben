from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    draft = "draft"
    preparing = "preparing"
    story_ready = "story_ready"
    character_pending = "character_pending"
    character_confirmed = "character_confirmed"
    pages_generating = "pages_generating"
    pages_review = "pages_review"
    pdf_ready = "pdf_ready"
    done = "done"
    failed = "failed"


class PageStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    ready = "ready"
    locked = "locked"
    failed = "failed"


class CharacterViewType(str, Enum):
    front = "front"
    side = "side"
    full = "full"
    happy = "happy"
    crying = "crying"


CHARACTER_VIEWS: list[tuple[CharacterViewType, str]] = [
    (CharacterViewType.front, "front portrait, gentle smile"),
    (CharacterViewType.side, "side profile portrait, calm"),
    (CharacterViewType.full, "full body standing pose, cheerful"),
    (CharacterViewType.happy, "close-up bright happy smile"),
    (CharacterViewType.crying, "close-up soft sad eyes, wholesome"),
]


class StoryPageOut(BaseModel):
    page: int
    text: str
    scene_prompt: str
    emotion: str


class StoryScript(BaseModel):
    title: str
    character_description: str
    pages: list[StoryPageOut]


class CharacterProfileOut(BaseModel):
    name: str
    age: int
    face_shape: str = ""
    hair: str = ""
    eyes: str = ""
    skin: str = ""
    special_features: str = ""
    clothing_style: str = ""
    character_prompt: str = ""
    status: str = "draft"
    confirmed_at: str | None = None


class CharacterAssetOut(BaseModel):
    view_type: str
    url: str
    generation: int


class PhotoOut(BaseModel):
    id: str
    url: str
    sort_order: int
    quality_score: float = 0.0


class PageOut(BaseModel):
    page_no: int
    text: str
    scene_prompt: str
    emotion: str
    image_url: str | None = None
    status: PageStatus
    regen_count: int = 0
    version: int = 1


class CustomBookOrderOut(BaseModel):
    id: str
    child_name: str
    age: int
    gender: str
    theme: str
    emotion_goal: str
    parent_message: str = ""
    status: OrderStatus
    title: str = ""
    story: StoryScript | None = None
    character: CharacterProfileOut | None = None
    character_assets: list[CharacterAssetOut] = Field(default_factory=list)
    photos: list[PhotoOut] = Field(default_factory=list)
    pages: list[PageOut] = Field(default_factory=list)
    pdf_url: str | None = None
    character_regen_count: int = 0
    error: str | None = None
    created_at: str
    updated_at: str


class ParentMessageIn(BaseModel):
    parent_message: str = Field(..., min_length=1, max_length=800)


class PageTextIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class CharacterPromptIn(BaseModel):
    character_prompt: str = Field(..., min_length=20, max_length=2000)


class OrderListItem(BaseModel):
    id: str
    child_name: str
    age: int
    theme: str
    status: OrderStatus
    title: str = ""
    updated_at: str


# Internal row helpers (dict-shaped)
OrderRow = dict[str, Any]
