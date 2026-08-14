from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutfitJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# 十种高级时尚大片风格（id = 展示名）
STYLE_OPTIONS: dict[str, str] = {
    "芭莎封面大片": "Harper's Bazaar 封面级，冷艳气场，高级成衣，强编辑感",
    "Vogue 内页大片": "Vogue editorial，叙事性强，时装叙事与戏剧光影",
    "高定走秀风": "Haute couture runway，夸张廓形与面料雕塑感，T 台气场",
    "黑白艺术大片": "黑白艺术摄影，高对比光影，雕塑感面部与剪影",
    "摩登极简": "Modern minimal，极简色块与干净线条，建筑感构图",
    "法式优雅": "Parisian chic，柔光、丝绸与剪裁感，慵懒高级",
    "意式奢华": "Italian luxury，皮革、羊毛与金属配饰，地中海阳光质感",
    "日系清冷高级": "Japanese quiet luxury，留白、雾面质感、克制冷调",
    "轻奢晚宴": "Evening glamour，礼服、珠宝与夜景灯光，晚宴气场",
    "复古胶片大片": "Vintage film editorial，胶片颗粒、复古造型与暖调光影",
}

# 拍摄场景
SCENE_OPTIONS = (
    "多场景混搭",
    "都市街道",
    "酒店大堂",
    "玻璃幕墙写字楼",
    "美术馆",
    "屋顶天台",
    "海边度假",
    "黑棚棚拍",
    "咖啡馆",
    "老洋房庭院",
)


class OutfitCreate(BaseModel):
    season: str = Field(default="春秋", max_length=32)
    city: str = Field(default="上海", max_length=64)
    vibe: str = Field(default="芭莎封面大片", max_length=64)
    scene: str = Field(default="多场景混搭", max_length=64)
    notes: str = Field(default="", max_length=400)


class OutfitLook(BaseModel):
    index: int
    day_label: str
    title: str
    outfit_cn: str
    image_prompt: str
    image_asset_id: str | None = None


class OutfitAsset(BaseModel):
    id: str
    kind: str = "image"
    filename: str
    mime_type: str
    url: str
    meta: dict[str, Any] = Field(default_factory=dict)


class OutfitProject(BaseModel):
    id: str
    season: str
    city: str
    vibe: str
    scene: str = "多场景混搭"
    notes: str
    created_at: datetime
    updated_at: datetime
    job_status: OutfitJobStatus = OutfitJobStatus.pending
    job_error: str | None = None
    looks: list[OutfitLook] = Field(default_factory=list)
    assets: dict[str, OutfitAsset] = Field(default_factory=dict)

    @classmethod
    def new(cls, project_id: str, data: OutfitCreate) -> OutfitProject:
        now = utcnow()
        vibe = data.vibe.strip() or "芭莎封面大片"
        if vibe not in STYLE_OPTIONS:
            # 允许自定义，但默认落回封面大片
            pass
        scene = data.scene.strip() or "多场景混搭"
        return cls(
            id=project_id,
            season=data.season.strip() or "春秋",
            city=data.city.strip() or "上海",
            vibe=vibe,
            scene=scene,
            notes=data.notes.strip(),
            created_at=now,
            updated_at=now,
        )
