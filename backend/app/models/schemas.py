from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StepName(str, Enum):
    story = "story"
    script = "script"
    storyboard = "storyboard"
    images = "images"
    tts = "tts"
    bgm = "bgm"
    video = "video"


PIPELINE_STEPS: list[StepName] = [
    StepName.story,
    StepName.script,
    StepName.storyboard,
    StepName.images,
    StepName.tts,
    StepName.bgm,
    StepName.video,
]


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class StoryParagraph(BaseModel):
    index: int
    text: str


class StoryCharacter(BaseModel):
    name: str
    appearance_en: str
    role: str = ""


class Story(BaseModel):
    title: str
    summary: str
    age_range: str
    paragraphs: list[StoryParagraph]
    characters: list[StoryCharacter] = Field(default_factory=list)
    mood: str = "warm"
    provider: str = "mock"
    # 视频号书籍剪辑：封面钩子 + 按书定调的画风（绘本可空）
    cover_hook: str = ""
    visual_style_en: str = ""
    cover_prompt_en: str = ""
    lessons: list[str] = Field(default_factory=list)


class ScriptLine(BaseModel):
    index: int
    text: str
    estimated_sec: float
    caption: str = ""


class Script(BaseModel):
    lines: list[ScriptLine]
    total_sec: float
    provider: str = "mock"


class Shot(BaseModel):
    index: int
    visual_prompt: str
    narration: str
    duration_sec: float
    camera: str = "slow_zoom"
    mood: str = "warm"
    image_asset_id: str | None = None
    characters_in_shot: list[str] = Field(default_factory=list)
    # character | scenery | metaphor — 视频号人景交替用
    shot_kind: str = "character"
    # 画面上大字（可短于旁白）
    on_screen_text: str = ""


class Storyboard(BaseModel):
    shots: list[Shot]
    total_sec: float
    provider: str = "mock"


class AssetRef(BaseModel):
    id: str
    kind: str  # image | audio | video
    filename: str
    mime_type: str
    url: str
    meta: dict[str, Any] = Field(default_factory=dict)


class TTSResult(BaseModel):
    asset: AssetRef
    duration_sec: float
    provider: str = "mock"


class BGMResult(BaseModel):
    asset: AssetRef
    duration_sec: float
    mood: str
    provider: str = "mock"


class VideoResult(BaseModel):
    asset: AssetRef
    duration_sec: float
    provider: str = "mock"


class StepState(BaseModel):
    name: StepName
    status: StepStatus = StepStatus.pending
    error: str | None = None
    updated_at: datetime | None = None


class ProjectCreate(BaseModel):
    theme: str = Field(..., min_length=1, max_length=200)
    age_range: str = Field(default="3-6", max_length=32)
    style: str = Field(default="watercolor", max_length=64)


class ProjectUpdateStory(BaseModel):
    title: str | None = None
    summary: str | None = None
    paragraphs: list[StoryParagraph] | None = None


class RunRequest(BaseModel):
    from_step: StepName | None = None


class Project(BaseModel):
    id: str
    theme: str
    age_range: str
    style: str
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

    @classmethod
    def new(cls, project_id: str, data: ProjectCreate) -> Project:
        now = utcnow()
        steps = {
            s.value: StepState(name=s, status=StepStatus.pending)
            for s in PIPELINE_STEPS
        }
        return cls(
            id=project_id,
            theme=data.theme.strip(),
            age_range=data.age_range,
            style=data.style,
            created_at=now,
            updated_at=now,
            steps=steps,
        )


class ProviderInfo(BaseModel):
    module: str
    current: str
    available: list[str]


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]
