from __future__ import annotations

import random
import uuid

from app.models.life_schemas import (
    LIFE_TARGET_SEC,
    LIFE_VISUAL_STYLE_EN,
    life_duration_plan,
)
from app.models.schemas import Script, ScriptLine, Story, StoryCharacter, StoryParagraph
from app.providers.base import ScriptRequest, StoryRequest
from app.providers.openai_compat import chat_json
from app.runtime_config import runtime_config

_HOOK_SEEDS = [
    "假如留在县城没有去大城市",
    "假如高考那年选了另一所大学",
    "假如没辞职继续熬大厂",
    "假如当时接受了那份相亲",
    "假如没有卖掉乡下的老屋",
    "假如退学去学一门手艺",
    "假如跟父母回小城开店",
    "假如错过那班去远方的火车",
]


class LifeStoryProvider:
    """人生副本：按用户选择的 1–5 分钟写完整故事骨架。"""

    name = "llm_life"

    async def generate(
        self,
        req: StoryRequest,
        *,
        premise: str,
        vibe: str,
        notes: str,
        target_sec: float | None = None,
    ) -> Story:
        cfg = runtime_config.get()
        plan = life_duration_plan(target_sec)
        target = int(plan["target_sec"])
        p_min = int(plan["paragraph_min"])
        p_max = int(plan["paragraph_max"])
        seed = random.choice(_HOOK_SEEDS)
        nonce = uuid.uuid4().hex[:8]
        minutes = max(1, round(target / 60))
        data = await chat_json(
            system=(
                "你是短视频「人生副本」导演。写一条平行人生的完整故事骨架，"
                f"竖屏口播约 {minutes} 分钟（目标 {target} 秒）：完整、有爽点、有情绪起伏。"
                "输出严格 JSON：\n"
                "{"
                '"title":"成片标题",'
                '"cover_hook":"封面大字8–14字",'
                '"summary":"一句话梗概",'
                '"mood":"tense|inspiring|fierce|triumphant",'
                '"visual_style_en":"modern cinematic contemporary East Asian urban realism, '
                'natural light, film color grade, vertical 9:16, no text",'
                '"cover_prompt_en":"modern cinematic cover still, strong focal subject, '
                'contemporary look, room for title overlay, no text in image",'
                '"lessons":["核心爽点1","爽点2"],'
                '"characters":[{"name":"中文名","appearance_en":"modern realistic look lock","role":"主角/对手"}],'
                '"paragraphs":[{"index":0,"text":""}]'
                "}\n"
                "硬性要求：\n"
                "1) 完整故事：岔路口→发展→冲突升级→清晰爽点/反转→收束。\n"
                "2) lessons 至少 1–2 个爽点，并在段落里演出来。\n"
                f"3) 共 {p_min}–{p_max} 段口语骨架，适合约 {target} 秒旁白。\n"
                "4) 角色 1–2 个；画风必须是现代写实电影感，不要漫画描边。\n"
                "5) 禁止空洞鸡汤、禁止半截子烂尾。"
            ),
            user=(
                f"随机种子：{seed} / {nonce}\n"
                f"假如设定：{premise or '无，请原创一条「假如另一条路」'}\n"
                f"味道：{vibe or '不限'}\n"
                f"补充：{notes or '无'}\n"
                f"主题：{req.theme or '人生副本'}\n"
                f"写约 {minutes} 分钟（{target} 秒）能讲完的完整故事。"
            ),
            temperature=0.9,
        )

        paragraphs_raw = data.get("paragraphs") or []
        paragraphs = [
            StoryParagraph(index=i, text=str(p.get("text", "")).strip())
            for i, p in enumerate(paragraphs_raw)
            if str(p.get("text", "")).strip()
        ]
        if not paragraphs:
            paragraphs = [
                StoryParagraph(index=0, text=f"假如：{seed}。"),
                StoryParagraph(index=1, text="这一次，结果不一样。"),
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
        if not characters:
            characters = [
                StoryCharacter(
                    name="主角",
                    appearance_en=(
                        "young East Asian adult, contemporary casual clothes, "
                        "natural look, consistent across frames"
                    ),
                    role="主角",
                )
            ]

        lessons = [str(x).strip() for x in (data.get("lessons") or []) if str(x).strip()]
        summary = str(data.get("summary") or "").strip() or "；".join(lessons[:2])
        title = str(data.get("title") or "").strip() or f"人生副本：{seed}"
        cover_hook = str(data.get("cover_hook") or "").strip() or (
            summary[:14] or "假如另一条路"
        )
        visual_style = str(data.get("visual_style_en") or "").strip() or LIFE_VISUAL_STYLE_EN
        if "manhua" in visual_style.lower() or "comic" in visual_style.lower():
            visual_style = LIFE_VISUAL_STYLE_EN
        cover_prompt = str(data.get("cover_prompt_en") or "").strip() or (
            "modern cinematic cover, contemporary East Asian scene, strong focal, no text"
        )

        return Story(
            title=title,
            summary=summary,
            age_range="general",
            paragraphs=paragraphs,
            characters=characters,
            mood=str(data.get("mood") or "inspiring"),
            provider=f"llm_life:{cfg.text_preset}",
            cover_hook=cover_hook,
            visual_style_en=visual_style,
            cover_prompt_en=cover_prompt,
            lessons=lessons,
        )


class LifeScriptProvider:
    name = "llm_life"

    async def generate(self, req: ScriptRequest) -> Script:
        cfg = runtime_config.get()
        story_text = "\n".join(p.text for p in req.story.paragraphs)
        cast = "、".join(c.name for c in req.story.characters) or "主角"
        plan = life_duration_plan(req.target_sec or LIFE_TARGET_SEC)
        target = float(plan["target_sec"])
        min_sec = float(plan["min_sec"])
        max_sec = float(plan["max_sec"])
        shot_min = int(plan["shot_min"])
        shot_soft_max = int(plan["shot_soft_max"])
        minutes = max(1, round(target / 60))

        data = await chat_json(
            system=(
                f"你是人生副本短视频编剧（约 {minutes} 分钟）。输出严格 JSON：\n"
                '{"lines":[{"index":0,"text":"","caption":"","estimated_sec":4.5}],'
                f'"total_sec":{int(target)}}}\n'
                "要求：\n"
                f"1) 旁白 {shot_min}–{shot_soft_max} 句（一张图一句），讲完完整故事。\n"
                "2) text 每句 12–28 字；estimated_sec 约 3.8–5.2。\n"
                "3) caption 必须与 text 完全一致（字幕=配音）。\n"
                f"4) 总时长约 {int(min_sec)}–{int(max_sec)} 秒（不含片头，片头由系统追加）。\n"
                "5) 钩子→设定→冲突升级→爽点/反转→收束；禁止空洞鸡汤。"
            ),
            user=(
                f"标题：{req.story.title}\n钩子：{req.story.cover_hook}\n"
                f"爽点：{'；'.join(req.story.lessons) or '反转'}\n"
                f"角色：{cast}\n骨架：\n{story_text}\n"
                f"目标：{int(target)} 秒（约 {minutes} 分钟）。"
            ),
            temperature=0.55,
        )

        lines: list[ScriptLine] = []
        for i, row in enumerate(data.get("lines") or []):
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            sec = float(
                row.get("estimated_sec") or max(3.8, min(5.2, len(text) / 3.5))
            )
            lines.append(
                ScriptLine(
                    index=i,
                    text=text,
                    estimated_sec=round(sec, 2),
                    caption=text,
                )
            )

        if len(lines) > shot_soft_max:
            lines = lines[:shot_soft_max]
            for i, line in enumerate(lines):
                line.index = i

        while len(lines) < shot_min and req.story.paragraphs:
            for p in req.story.paragraphs:
                if len(lines) >= shot_min:
                    break
                chunk = (p.text or "").strip()
                if not chunk:
                    continue
                if len(chunk) > 28:
                    chunk = chunk[:28]
                lines.append(
                    ScriptLine(
                        index=len(lines),
                        text=chunk,
                        estimated_sec=4.5,
                        caption=chunk,
                    )
                )
            if len(lines) < shot_min:
                lines.append(
                    ScriptLine(
                        index=len(lines),
                        text=req.story.cover_hook or "这一次，路不同了。",
                        estimated_sec=4.0,
                        caption=req.story.cover_hook or "这一次，路不同了。",
                    )
                )

        total = sum(l.estimated_sec for l in lines)
        while lines and total > max_sec and len(lines) > shot_min:
            lines.pop()
            for i, line in enumerate(lines):
                line.index = i
            total = sum(l.estimated_sec for l in lines)

        if not lines:
            seed = req.story.summary or req.story.title
            lines = [
                ScriptLine(
                    index=0,
                    text=seed,
                    estimated_sec=5.0,
                    caption=seed,
                )
            ]

        total = sum(l.estimated_sec for l in lines)
        return Script(
            lines=lines,
            total_sec=round(min(total, max_sec), 2),
            provider=f"llm_life:{cfg.text_preset}",
        )
