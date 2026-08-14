from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.schemas import (
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

# 人生副本顺序：先配音，再按配音时长出图，最后 BGM + 烧字幕成片
LIFE_PIPELINE_STEPS: list[StepName] = [
    StepName.story,
    StepName.script,
    StepName.storyboard,
    StepName.tts,
    StepName.images,
    StepName.bgm,
    StepName.video,
]

# 兼容旧常量（不再用作硬上限）
LIFE_DURATION_OPTIONS_SEC: tuple[int, ...] = (60, 120, 180, 240, 300)
LIFE_TARGET_SEC = 0.0  # 0 = 不限，成片跟配音走
LIFE_MIN_SEC = 0.0
LIFE_MAX_SEC = 0.0
LIFE_SHOT_MIN = 1
LIFE_SHOT_SOFT_MAX = 999
LIFE_API_PREFIX = "/api/life"
LIFE_BGM_MOOD = "attractive cinematic pulse"
LIFE_SERIES_PREFIX = "1000种平行人生之"
# 固定 BGM 曲库（文件放 backend/assets/bgm/life/）
LIFE_BGM_TRACKS: tuple[dict[str, str], ...] = (
    {"id": "illusionary_daytime", "title": "Illusionary Daytime", "filename": "illusionary_daytime.mp3"},
    {"id": "windy_hill", "title": "Windy Hill", "filename": "windy_hill.mp3"},
    {"id": "the_world_is_wide_open", "title": "The World Is Wide Open", "filename": "the_world_is_wide_open.mp3"},
)
# 背景垫乐约 20%，不抢口播
LIFE_BGM_VOLUME = 0.20
# 默认成片配方：县城安稳·治愈
LIFE_PRESET_ID = "county_calm"
LIFE_DEFAULT_TTS_VOICE = "Chinese (Mandarin)_Gentleman"
LIFE_DEFAULT_BGM_TRACK_ID = "illusionary_daytime"
# 日系治愈人物 + 写实县城 + 暖色胶片
LIFE_VISUAL_STYLE_EN = (
    "Japanese healing illustration style with cute round-faced East Asian character "
    "(big head, soft simplified features), Chinese small-town realistic environments "
    "(county streets, school, wet market, home courtyard), warm muted orange beige cream palette, "
    "soft film grain and gentle vintage look, slow cinematic still, cozy everyday details, "
    "vertical 9:16 full-bleed, no text no watermark no subtitle"
)
# 兼容旧名
LIFE_COMIC_STYLE_EN = LIFE_VISUAL_STYLE_EN
LIFE_COVER_PROMPT_EN = (
    "Japanese healing cute round-faced character in a warm Chinese county town scene, "
    "soft film grain, orange street lamp glow, room for title overlay, no text in image"
)
LIFE_NARRATIVE_LOCK_EN = (
    "first-person life-sim narrative frame; emphasize choice-consequence life nodes "
    "(gaokao, major, job, marriage, parenting); contrast big-city drift vs county calm; "
    "prefer concrete everyday props (e-bike, home-cooked food, old rattan chair, plane trees)"
)


def normalize_life_target_sec(value: float | int | None) -> float:
    """保留字段兼容；0 表示不限时长。"""
    try:
        sec = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, sec)


def life_duration_plan(target_sec: float | int | None) -> dict[str, float | int]:
    """软参考计划；不再裁切用户文案。"""
    target = normalize_life_target_sec(target_sec)
    return {
        "target_sec": target,
        "min_sec": 0.0,
        "max_sec": 0.0,
        "shot_min": 1,
        "shot_soft_max": 999,
        "paragraph_min": 1,
        "paragraph_max": 999,
    }


class LifeCreate(BaseModel):
    # 用户自写口播故事（必填）；不再用 DeepSeek 写脚本
    story_text: str = Field(default="", max_length=12000)
    title: str = Field(default="", max_length=80)  # 用于「1000种平行人生之…」
    premise: str = Field(default="", max_length=200)  # 兼容旧字段 / 可选钩子
    vibe: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=2000)  # 可选：角色外貌等提示
    target_sec: float = Field(default=0, ge=0, le=3600)
    tts_voice: str = Field(default="", max_length=120)
    bgm_track_id: str = Field(default="", max_length=80)  # empty = auto


class LifeProject(BaseModel):
    id: str
    premise: str
    vibe: str
    notes: str
    story_text: str = ""
    title: str = ""
    target_sec: float = 0.0
    tts_voice: str = ""
    bgm_track_id: str = ""
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
    def new(cls, project_id: str, data: LifeCreate) -> LifeProject:
        now = utcnow()
        steps = {
            s.value: StepState(name=s, status=StepStatus.pending)
            for s in LIFE_PIPELINE_STEPS
        }
        return cls(
            id=project_id,
            premise=(data.premise or "").strip(),
            vibe=(data.vibe or "").strip(),
            notes=(data.notes or "").strip(),
            story_text=(data.story_text or "").strip(),
            title=(data.title or "").strip(),
            target_sec=normalize_life_target_sec(data.target_sec),
            tts_voice=(data.tts_voice or "").strip() or LIFE_DEFAULT_TTS_VOICE,
            bgm_track_id=(data.bgm_track_id or "").strip() or LIFE_DEFAULT_BGM_TRACK_ID,
            created_at=now,
            updated_at=now,
            steps=steps,
        )


class LifeRunRequest(BaseModel):
    from_step: StepName | None = None


class LifeOptionsResponse(BaseModel):
    durations: list[dict[str, float | str]]
    bgm_tracks: list[dict[str, str]]
    voices: list[dict[str, str]]
    defaults: dict[str, float | str]
