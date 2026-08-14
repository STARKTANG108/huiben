from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import (
    PIPELINE_STEPS,
    AssetRef,
    BGMResult,
    JobStatus,
    Script,
    StepName,
    StepState,
    StepStatus,
    Story,
    Storyboard,
    TTSResult,
    VideoResult,
    utcnow,
)

BOOK_TARGET_SEC = 180.0  # 约 3 分钟成片，以口播讲故事为主
BOOK_MAX_SEC = 210.0
# 配图不必随时长等比增加：约 8–12 张，每镜挂更长旁白
BOOK_IMAGE_COUNT = 10
BOOK_IMAGE_COUNT_MIN = 8
BOOK_IMAGE_COUNT_MAX = 12
BOOK_API_PREFIX = "/api/book"
BOOK_TEMPLATE_ID = "lifetime_cinematic"
BOOK_BGM_MOOD = (
    "纯音乐 melancholic cinematic piano and soft strings, "
    "reflective book narration underscore, instrumental only"
)
BOOK_BGM_VOLUME = 0.13  # 背景纯音乐 13%，不抢旁白
BOOK_MOTION_SEC = 8.0  # 开场首尾帧动效时长
BOOK_MOTION_AUDIO_VOLUME = 0.42  # 保留开场视频原声，压在旁白下
BOOK_MOTION_SKIP_SHOTS = 2  # 前两张图作首/尾帧，后续静帧接续
# 默认画风（可被 LLM 按书内容覆盖）：《一生》式西部胶片电影感
BOOK_VISUAL_STYLE_EN = (
    "cinematic western road-movie still, warm sepia golden-hour grade, "
    "soft film grain, dramatic backlight and silhouettes, dusty desert plains "
    "or misty pine forests or mountain rivers, epic lonely traveler mood, "
    "shallow depth of field, vertical 9:16 full-bleed, "
    "no text no watermark no subtitle no logo"
)
BOOK_COVER_PROMPT_EN = (
    "cinematic golden-hour silhouette cover matching the story mood, "
    "strong focal subject, room for Chinese book title at top and quote at bottom, "
    "warm film grain, no text in image"
)
BOOK_SHOT_KIND_CYCLE = (
    "metaphor",
    "scenery",
    "character",
    "scenery",
    "metaphor",
    "scenery",
    "character",
    "scenery",
)


class BookCreate(BaseModel):
    book_title: str = Field(..., min_length=1, max_length=120)
    theme: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    # optional: user-provided key lessons / takeaways
    key_lessons: str = Field(default="", max_length=1200)


class BookProject(BaseModel):
    id: str
    book_title: str
    theme: str
    notes: str
    key_lessons: str
    target_sec: float = BOOK_TARGET_SEC
    # 兼容旧数据；成片角标不再使用「第 N 本」
    book_seq: int = 1
    created_at: datetime
    updated_at: datetime
    job_status: JobStatus = JobStatus.pending
    job_error: str | None = None
    current_step: StepName | None = None
    steps: dict[str, StepState] = Field(default_factory=dict)

    story: Story | None = None
    script: Script | None = None
    storyboard: Storyboard | None = None
    tts: TTSResult | None = None
    bgm: BGMResult | None = None
    video: VideoResult | None = None
    assets: dict[str, AssetRef] = Field(default_factory=dict)
    cover_asset_id: str | None = None

    @classmethod
    def new(cls, project_id: str, data: BookCreate, *, book_seq: int = 1) -> BookProject:
        now = utcnow()
        steps = {
            s.value: StepState(name=s, status=StepStatus.pending)
            for s in PIPELINE_STEPS
        }
        theme = (data.theme or "").strip() or f"读懂《{data.book_title.strip()}》的核心启示"
        return cls(
            id=project_id,
            book_title=data.book_title.strip(),
            theme=theme,
            notes=(data.notes or "").strip(),
            key_lessons=(data.key_lessons or "").strip(),
            target_sec=BOOK_TARGET_SEC,
            book_seq=max(1, int(book_seq)),
            created_at=now,
            updated_at=now,
            steps=steps,
        )


class BookRunRequest(BaseModel):
    from_step: StepName | None = None
