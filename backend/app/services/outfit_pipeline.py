from __future__ import annotations

import logging

from app.models.outfit_schemas import (
    SCENE_OPTIONS,
    STYLE_OPTIONS,
    OutfitJobStatus,
    OutfitLook,
    OutfitProject,
    utcnow,
)
from app.providers.fashion_image import build_fashion_prompt, generate_fashion_image
from app.providers.openai_compat import chat_json
from app.store.outfit_memory import outfit_store

logger = logging.getLogger(__name__)

LOOK_COUNT = 5

_MIX_SCENES = [
    "都市玻璃幕墙写字楼外",
    "五星酒店大理石大堂",
    "当代美术馆白色展厅",
    "城市屋顶天台黄昏",
    "精致咖啡馆与落地窗",
]


def _style_brief(vibe: str) -> str:
    return STYLE_OPTIONS.get(vibe, "高级时尚杂志编辑大片，有气场、可印刷")


def _look_from_row(index: int, row: dict, project: OutfitProject) -> OutfitLook:
    hairstyle = str(row.get("hairstyle") or row.get("appearance") or "").strip()
    outfit = str(row.get("outfit") or "").strip()
    accessories = str(row.get("accessories") or "").strip()
    scene = str(row.get("scene") or "").strip()
    lighting = str(row.get("lighting") or "").strip()
    outfit_cn = str(row.get("outfit_cn") or "").strip()
    if not outfit_cn and outfit:
        outfit_cn = outfit
    if not hairstyle:
        hairstyle = "精致发型，发丝有光泽，杂志大片妆发"
    if not outfit:
        outfit = f"{project.vibe}高级时装造型，廓形利落"
    if not accessories:
        accessories = "设计师手袋、金属耳饰与细项链"
    if not scene:
        if project.scene == "多场景混搭":
            scene = f"{project.city}{_MIX_SCENES[index % len(_MIX_SCENES)]}"
        else:
            scene = f"{project.city}{project.scene}"
    if not lighting:
        lighting = "时尚编辑大片侧光与轮廓光"

    return OutfitLook(
        index=index,
        day_label=str(row.get("day_label") or f"Look {index + 1}").strip(),
        title=str(row.get("title") or f"大片 {index + 1}").strip(),
        outfit_cn=outfit_cn or outfit,
        image_prompt=build_fashion_prompt(
            hairstyle=hairstyle,
            outfit=outfit,
            accessories=accessories,
            scene=scene,
            lighting=lighting,
            style_vibe=project.vibe,
            style_brief=_style_brief(project.vibe),
        ),
    )


def _scene_instruction(project: OutfitProject) -> str:
    scene = project.scene or "多场景混搭"
    if scene == "多场景混搭":
        return (
            f"场景要求：5 套必须覆盖不同拍摄地点，从以下类型中各选其一并写具体可拍描述，"
            f"地点落在「{project.city}」："
            + "、".join(_MIX_SCENES)
            + "。禁止 5 套都是同一类街道。"
        )
    if scene in SCENE_OPTIONS:
        return (
            f"场景要求：5 套都围绕「{scene}」展开，但每套的具体机位/时间段/背景细节要不同"
            f"（同城 {project.city}），保持时尚杂志大片感，不要写成日常街拍自拍。"
        )
    return f"场景要求：以「{scene}」为主，写具体可拍摄地点。"


async def generate_outfit_prompts(project: OutfitProject) -> list[OutfitLook]:
    style_hint = _style_brief(project.vibe)
    data = await chat_json(
        system=(
            "你是国际一线时尚杂志（Vogue / Harper's Bazaar）的高级时装造型总监与摄影策划。"
            "不限于职场通勤：面向高级时装、杂志封面与编辑大片。"
            "人物五官与皮肤特征已固化，你只需填写可变槽位。"
            "输出严格 JSON："
            '{"looks":[{"index":0,"day_label":"Look 1","title":"",'
            '"hairstyle":"发型样式","outfit":"上衣+下装+鞋子或完整时装造型",'
            '"accessories":"包、耳饰、项链等配饰","scene":"拍摄地点",'
            '"lighting":"时尚大片灯光","outfit_cn":"中文造型简述"}]}。'
            f"必须正好 {LOOK_COUNT} 套高级时尚大片造型。"
            f"本辑风格锁定：「{project.vibe}」——{style_hint}。"
            "气质目标：时尚杂志封面/内页编辑大片，高级、有气场、可印刷；"
            "可以是高定、成衣、晚宴、度假、艺术黑白等，但不要写成廉价网红自拍或日常 OOTD。"
            "各字段用中文、具体可拍摄："
            "hairstyle 只写发型发色与造型，不要改脸型五官；"
            "outfit 必须完整（含鞋或靴），偏向高级时装/成衣/高定廓形与面料；"
            "accessories 偏设计师质感；"
            "scene 写具体拍摄地点；lighting 写时尚摄影灯光（轮廓光、伦勃朗光、黄金时刻侧逆光等）；"
            "day_label 用 Look 1…Look 5；title 像杂志专题名。"
            "不要写二次元/插画；不要输出完整长提示词；不要描述脸型五官皮肤。"
            + _scene_instruction(project)
        ),
        user=(
            f"季节：{project.season}\n城市：{project.city}\n"
            f"大片风格：{project.vibe}（{style_hint}）\n"
            f"拍摄场景偏好：{project.scene}\n"
            f"补充：{project.notes or '无'}\n"
            f"请给出 {LOOK_COUNT} 套该风格的高级时尚大片造型方案。"
        ),
        temperature=0.75,
    )
    rows = data.get("looks") or []
    looks = [_look_from_row(i, row, project) for i, row in enumerate(rows[:LOOK_COUNT])]
    while len(looks) < LOOK_COUNT:
        i = len(looks)
        scene = (
            f"{project.city}{_MIX_SCENES[i % len(_MIX_SCENES)]}"
            if project.scene == "多场景混搭"
            else f"{project.city}{project.scene}"
        )
        looks.append(
            _look_from_row(
                i,
                {
                    "day_label": f"Look {i + 1}",
                    "title": f"{project.vibe} · Look {i + 1}",
                    "hairstyle": "精致杂志妆发，发丝有光泽",
                    "outfit": f"{project.vibe}高级时装造型，廓形利落，搭配高跟鞋或短靴",
                    "accessories": "设计师手袋、金属耳饰与细项链",
                    "scene": scene,
                    "lighting": "时尚编辑大片侧光与轮廓光",
                    "outfit_cn": f"{project.vibe}杂志大片造型，气场高级。",
                },
                project,
            )
        )
    return looks


async def run_outfit_pipeline(project_id: str) -> OutfitProject:
    project = outfit_store.get(project_id)
    if not project:
        raise RuntimeError("Outfit project not found")

    project.job_status = OutfitJobStatus.running
    project.job_error = None
    project.updated_at = utcnow()
    outfit_store.save(project)

    try:
        looks = await generate_outfit_prompts(project)
        project.looks = looks
        project.updated_at = utcnow()
        outfit_store.save(project)

        for look in project.looks:
            asset = await generate_fashion_image(
                project_id=project.id,
                index=look.index,
                image_prompt=look.image_prompt or look.outfit_cn,
                day_label=look.day_label,
            )
            project.assets[asset.id] = asset
            look.image_asset_id = asset.id
            project.updated_at = utcnow()
            outfit_store.save(project)

        project.job_status = OutfitJobStatus.completed
        project.updated_at = utcnow()
        return outfit_store.save(project)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Outfit pipeline failed %s", project_id)
        project = outfit_store.get(project_id) or project
        project.job_status = OutfitJobStatus.failed
        project.job_error = str(exc)
        project.updated_at = utcnow()
        outfit_store.save(project)
        raise
