from __future__ import annotations

from app.models.schemas import Story, StoryCharacter, StoryParagraph
from app.providers.base import StoryRequest
from app.providers.openai_compat import chat_json
from app.runtime_config import runtime_config


class LLMStoryProvider:
    name = "llm"

    async def generate(self, req: StoryRequest) -> Story:
        cfg = runtime_config.get()
        data = await chat_json(
            system=(
                "你是资深儿童绘本作家与口语故事老师。输出严格 JSON：\n"
                "{"
                '"title":"",'
                '"summary":"一两句梗概",'
                '"mood":"warm|adventure|calm|playful",'
                '"characters":[{"name":"中文名","appearance_en":"detailed English visual lock: species/colors/body/signature prop, must stay identical every page","role":"主角/配角"}],'
                '"paragraphs":[{"index":0,"text":""}]'
                "}\n"
                "硬性要求：\n"
                "1) 有清晰起承转合：开头建立角色与愿望→遇到小问题→努力解决→温暖收束；"
                "要有具体情节小事件，不要空泛抒情。\n"
                "2) 句子口语化、适合慢慢讲给孩子听；3–6 岁也能听懂；少用抽象词。\n"
                "3) 角色 2–3 个即可；每个角色必须有可复现的角色卡 appearance_en"
                "（颜色、体型、耳朵/毛色、标志物如围巾/蝴蝶结），禁止中途换设定。\n"
                "4) 不要出现与主题无关的人类小孩，除非主题明确要求。\n"
                "5) 正能量，无惊吓、无暴力。\n"
                "6) 共 5–7 段，整体适合约 70–90 秒慢速旁白（讲故事感）。"
            ),
            user=(
                f"主题：{req.theme}\n年龄：{req.age_range}\n"
                "画风固定：水彩绘本（watercolor）。\n"
                "请写出故事性强、好听好记的短篇。"
            ),
            temperature=0.75,
        )
        paragraphs_raw = data.get("paragraphs") or []
        paragraphs = [
            StoryParagraph(index=i, text=str(p.get("text", "")).strip())
            for i, p in enumerate(paragraphs_raw)
            if str(p.get("text", "")).strip()
        ]
        if not paragraphs:
            paragraphs = [
                StoryParagraph(index=0, text=str(data.get("summary") or req.theme))
            ]
        characters: list[StoryCharacter] = []
        for row in data.get("characters") or []:
            name = str(row.get("name", "")).strip()
            appearance = str(row.get("appearance_en", "")).strip()
            if name and appearance:
                characters.append(
                    StoryCharacter(
                        name=name,
                        appearance_en=appearance,
                        role=str(row.get("role", "")).strip(),
                    )
                )
        title = str(data.get("title") or "").strip() or f"「{req.theme}」"
        return Story(
            title=title,
            summary=str(data.get("summary") or ""),
            age_range=req.age_range,
            paragraphs=paragraphs,
            characters=characters,
            mood=str(data.get("mood") or "warm"),
            provider=f"llm:{cfg.text_preset}",
        )
