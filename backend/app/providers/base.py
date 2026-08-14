from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.schemas import (
    AssetRef,
    BGMResult,
    Script,
    Shot,
    Story,
    Storyboard,
    TTSResult,
    VideoResult,
)


@dataclass
class StoryRequest:
    theme: str
    age_range: str
    style: str


@dataclass
class ScriptRequest:
    story: Story
    target_sec: float = 60.0


@dataclass
class StoryboardRequest:
    story: Story
    script: Script
    style: str
    shot_count: int = 14


@dataclass
class ImageRequest:
    project_id: str
    shot: Shot
    style: str
    theme: str
    characters_lock: str = ""
    api_prefix: str = "/api/projects"
    storage_key: str | None = None
    reference_image_path: str | None = None
    seed: int | None = None


@dataclass
class TTSRequest:
    project_id: str
    script: Script
    storyboard: Storyboard
    voice: str = "child_warm"
    api_prefix: str = "/api/projects"
    storage_key: str | None = None


@dataclass
class BGMRequest:
    project_id: str
    mood: str
    duration_sec: float
    api_prefix: str = "/api/projects"
    storage_key: str | None = None
    track_id: str | None = None


@dataclass
class VideoRequest:
    project_id: str
    storyboard: Storyboard
    image_assets: list[AssetRef]
    tts: TTSResult
    bgm: BGMResult
    title: str
    api_prefix: str = "/api/projects"
    storage_key: str | None = None
    # 视频号：大字烧录 + 冲击力封面作片头
    burn_captions: bool = False
    cover_path: str | None = None
    cover_sec: float = 2.8
    bgm_volume: float = 0.16
    # 书籍模版：顶部书名（如《一生》）；字幕优先用 on_screen_text 双语金句
    caption_header: str | None = None
    prefer_on_screen_text: bool = False
    # 书籍开场动效：首尾帧生成的短视频（保留原声）
    motion_clip_path: str | None = None
    motion_sec: float = 8.0
    keep_motion_audio: bool = True
    motion_audio_volume: float = 0.42
    motion_skip_shot_count: int = 2


class StoryProvider(Protocol):
    name: str

    async def generate(self, req: StoryRequest) -> Story: ...


class ScriptProvider(Protocol):
    name: str

    async def generate(self, req: ScriptRequest) -> Script: ...


class StoryboardProvider(Protocol):
    name: str

    async def generate(self, req: StoryboardRequest) -> Storyboard: ...


class ImageProvider(Protocol):
    name: str

    async def generate(self, req: ImageRequest) -> AssetRef: ...


class TTSProvider(Protocol):
    name: str

    async def generate(self, req: TTSRequest) -> TTSResult: ...


class BGMProvider(Protocol):
    name: str

    async def generate(self, req: BGMRequest) -> BGMResult: ...


class VideoProvider(Protocol):
    name: str

    async def generate(self, req: VideoRequest) -> VideoResult: ...
