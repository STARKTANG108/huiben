from __future__ import annotations

from typing import Any

from app.providers.openai_compat import chat_json
from app.services.custom_book.prompt_safety import (
    SAFE_CONTENT_RULES_CN,
    sanitize_prompt_text,
    with_safe_scene,
)


async def generate_story_script(
    *,
    child_name: str,
    age: int,
    gender: str,
    theme: str,
    emotion_goal: str,
) -> dict[str, Any]:
    gender_cn = {"boy": "男孩", "girl": "女孩"}.get(gender, gender)
    data = await chat_json(
        system=(
            "你是儿童成长绘本编剧。只输出合法 JSON：\n"
            "{"
            '"title":"",'
            '"character_description":"中文外貌与气质描述，供后续视觉锁定",'
            '"pages":[{"page":1,"text":"页文案，适合朗读","scene_prompt":"英文场景视觉描述",'
            '"emotion":"情绪词"}]'
            "}\n"
            "硬性要求：\n"
            "1) pages 必须恰好 8 页，page 为 1..8。\n"
            "2) 主角是给定的孩子，名字贯穿全书，不引入其他同龄主角。\n"
            "3) 主题与情绪目标贯穿起承转合，温暖正向。\n"
            "4) text 用中文短句；scene_prompt 用英文、具体可画。\n"
            "5) character_description 必须写死发型/发色/发长/刘海、脸型、眼神、肤色、服装；"
            "后续插画禁止改发型。\n"
            "6) 安全克制：" + SAFE_CONTENT_RULES_CN + "\n"
            "7) scene_prompt 与 text 禁止敏感词：裸露、暴力血腥、恐怖、成人向、政治敏感；"
            "哭闹分离焦虑用温和表达（sad but cute, missing mom, brave hug）。\n"
            "8) 每条 scene_prompt 末尾隐含儿童安全绘本风格，不要写负面成人词。"
        ),
        user=(
            f"孩子昵称：{child_name}\n年龄：{age}\n性别：{gender_cn}\n"
            f"主题：{theme}\n希望解决的问题/情绪目标：{emotion_goal or '成长与安心'}\n"
            "请生成 8 页成长绘本脚本（务必安全克制、适合幼儿）。"
        ),
        temperature=0.55,
    )
    pages = data.get("pages") or []
    if len(pages) != 8:
        normalized = []
        for i in range(1, 9):
            src = next((p for p in pages if int(p.get("page", 0)) == i), None)
            if src is None and i - 1 < len(pages):
                src = pages[i - 1]
            src = src or {}
            normalized.append(
                {
                    "page": i,
                    "text": sanitize_prompt_text(
                        str(src.get("text") or f"{child_name}的故事第{i}页")
                    ),
                    "scene_prompt": with_safe_scene(
                        str(
                            src.get("scene_prompt")
                            or f"warm children's book scene {i} with {child_name}"
                        )
                    ),
                    "emotion": sanitize_prompt_text(
                        str(src.get("emotion") or "warm")
                    ),
                }
            )
        data["pages"] = normalized
    else:
        data["pages"] = [
            {
                "page": int(p.get("page", i + 1)),
                "text": sanitize_prompt_text(str(p.get("text") or "")),
                "scene_prompt": with_safe_scene(str(p.get("scene_prompt") or "")),
                "emotion": sanitize_prompt_text(str(p.get("emotion") or "warm")),
            }
            for i, p in enumerate(pages)
        ]
    data["title"] = sanitize_prompt_text(
        str(data.get("title") or f"{child_name}的成长绘本")
    )
    data["character_description"] = sanitize_prompt_text(
        str(data.get("character_description") or "")
    )
    return data


async def generate_character_profile(
    *,
    child_name: str,
    age: int,
    gender: str,
    theme: str,
    character_description: str,
) -> dict[str, Any]:
    gender_cn = {"boy": "男孩", "girl": "女孩"}.get(gender, gender)
    data = await chat_json(
        system=(
            "你是儿童角色视觉设定师。只输出合法 JSON：\n"
            "{"
            '"name":"",'
            '"age":0,'
            '"face_shape":"",'
            '"hair":"必须含发色+发长+发型+刘海，后续禁止改动",'
            '"eyes":"",'
            '"skin":"",'
            '"special_features":"",'
            '"clothing_style":"",'
            '"character_prompt":"英文锁定提示词"'
            "}\n"
            "character_prompt 用英文，必须包含："
            "age, gender, face shape, EXACT hairstyle/length/color/bangs, eyes, skin, outfit colors。"
            "并写明：same hairstyle every page。"
            "禁止：innocent、pajama、裸露、性感、成人向；服装写成 daytime T-shirt / sweater 等日常装。"
            "只写适合儿童绘本的可爱造型，短句即可。"
        ),
        user=(
            f"昵称：{child_name}\n年龄：{age}\n性别：{gender_cn}\n主题：{theme}\n"
            f"故事中的角色描述：{character_description}\n"
            "请生成 Character Profile；发型必须写死并锁定。"
        ),
        temperature=0.35,
    )
    name = str(data.get("name") or child_name).strip()
    hair = sanitize_prompt_text(str(data.get("hair") or "").strip())
    prompt = sanitize_prompt_text(str(data.get("character_prompt") or "").strip())
    if not prompt:
        prompt = (
            f"a cute {age}-year-old Chinese {gender} child named {name}, "
            f"exact hair: {hair or 'natural soft hair'}, "
            f"{data.get('eyes', '')}, {data.get('skin', '')}, "
            f"wearing {data.get('clothing_style', 'simple soft fully-clothed outfit')}, "
            "same hairstyle every page, do not change hair, "
            "consistent character for a children's picture book, wholesome"
        )
    if "hairstyle" not in prompt.lower() and "hair" not in prompt.lower():
        prompt = f"{prompt}, exact locked hairstyle: {hair or 'keep identical hair'}"
    if "do not change hair" not in prompt.lower():
        prompt = f"{prompt}, do not change hair or hairstyle"
    return {
        "name": name,
        "age": int(data.get("age") or age),
        "face_shape": sanitize_prompt_text(str(data.get("face_shape") or "")),
        "hair": hair,
        "eyes": sanitize_prompt_text(str(data.get("eyes") or "")),
        "skin": sanitize_prompt_text(str(data.get("skin") or "")),
        "special_features": sanitize_prompt_text(
            str(data.get("special_features") or "")
        ),
        "clothing_style": sanitize_prompt_text(str(data.get("clothing_style") or "")),
        "character_prompt": prompt,
    }
