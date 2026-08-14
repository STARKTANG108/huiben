from __future__ import annotations

from app.models.book_schemas import (
    BOOK_COVER_PROMPT_EN,
    BOOK_IMAGE_COUNT,
    BOOK_IMAGE_COUNT_MAX,
    BOOK_IMAGE_COUNT_MIN,
    BOOK_MAX_SEC,
    BOOK_TARGET_SEC,
    BOOK_VISUAL_STYLE_EN,
)
from app.models.schemas import Script, ScriptLine, Story, StoryCharacter, StoryParagraph
from app.providers.base import ScriptRequest, StoryRequest
from app.providers.openai_compat import chat_json
from app.runtime_config import runtime_config


class BookStoryProvider:
    """《一生》式金句说书：双语字幕布局 + 按书内容定制画面风格。"""

    name = "llm_book"

    async def generate(
        self, req: StoryRequest, *, book_title: str, notes: str, key_lessons: str
    ) -> Story:
        cfg = runtime_config.get()
        data = await chat_json(
            system=(
                "你是视频号「书籍金句说书」导演。模版对标电影感短片《一生》："
                "竖屏 9:16、约 3 分钟、顶部书名、底部中英对照金句；"
                "画面必须贴合本书故事，不要固定成某一种题材（可西部、现代、古风、都市等）。"
                "输出严格 JSON：\n"
                "{"
                '"title":"成片标题（含好奇心）",'
                '"cover_hook":"封面大字8–18汉字，痛点/觉悟，禁止堆砌书名",'
                '"summary":"一句话点题",'
                '"mood":"reflective",'
                '"visual_style_en":"English cinematic still style matching THIS book, '
                'vertical 9:16, no text no watermark",'
                '"cover_prompt_en":"English cover scene matching the story, no text",'
                '"lessons":["核心觉悟1","觉悟2"],'
                '"characters":[{"name":"角色名","appearance_en":'
                '"consistent English appearance lock","role":"象征/主角"}],'
                '"paragraphs":[{"index":0,"text":""}]'
                "}\n"
                "硬性要求：\n"
                "1) 开场钩子：反常识提问或痛点。\n"
                "2) paragraphs 写口语讲故事骨架 10–14 段，适合约 3 分钟口播，"
                "以叙述、人物经历、对照为主。\n"
                "3) visual_style_en / cover_prompt_en 必须根据书名与情节定制，"
                "禁止千篇一律的国风雨夜；也不要写字进画面。\n"
                "4) 结构：钩子→故事展开→顿悟→升华收束。\n"
                "5) 禁止论文腔、「本章」「综上所述」。"
            ),
            user=(
                f"书名：《{book_title}》\n"
                f"主题/角度：{req.theme}\n"
                f"用户补充：{notes or '无'}\n"
                f"已知要点：{key_lessons or '无，请按书名合理提炼金句与画面风格'}\n"
                "请写成《一生》式金句说书骨架，并给出贴合本书的英文画风。"
            ),
            temperature=0.65,
        )
        paragraphs_raw = data.get("paragraphs") or []
        paragraphs = [
            StoryParagraph(index=i, text=str(p.get("text", "")).strip())
            for i, p in enumerate(paragraphs_raw)
            if str(p.get("text", "")).strip()
        ]
        if not paragraphs:
            lessons = data.get("lessons") or [req.theme]
            paragraphs = [
                StoryParagraph(index=i, text=str(x))
                for i, x in enumerate(lessons)
                if str(x).strip()
            ] or [StoryParagraph(index=0, text=f"今天我们一起读懂《{book_title}》。")]

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
                    name="旅人",
                    appearance_en=(
                        "lone traveler silhouette, consistent coat and silhouette, "
                        "distant figure in environment"
                    ),
                    role="象征",
                )
            ]

        lessons = [str(x).strip() for x in (data.get("lessons") or []) if str(x).strip()]
        summary = str(data.get("summary") or "").strip()
        if lessons and not summary:
            summary = "；".join(lessons[:2])
        title = str(data.get("title") or "").strip() or f"《{book_title}》里最值得带走的觉悟"
        cover_hook = str(data.get("cover_hook") or "").strip() or (summary or title)[:18]

        visual_style = str(data.get("visual_style_en") or "").strip() or BOOK_VISUAL_STYLE_EN
        # 去掉 LLM 可能塞进画风的文字指令冲突，并强制竖屏无字
        low = visual_style.lower()
        if "text" not in low:
            visual_style = (
                visual_style.rstrip(".")
                + ", vertical 9:16 full-bleed, no text no watermark no subtitle no logo"
            )
        cover_prompt = str(data.get("cover_prompt_en") or "").strip() or BOOK_COVER_PROMPT_EN

        return Story(
            title=title,
            summary=summary,
            age_range="general",
            paragraphs=paragraphs,
            characters=characters,
            mood=str(data.get("mood") or "reflective").strip() or "reflective",
            provider=f"llm_book:{cfg.text_preset}",
            cover_hook=cover_hook,
            visual_style_en=visual_style[:500],
            cover_prompt_en=cover_prompt[:500],
            lessons=lessons,
        )


class BookScriptProvider:
    name = "llm_book"

    async def generate(self, req: ScriptRequest) -> Script:
        cfg = runtime_config.get()
        story_text = "\n".join(p.text for p in req.story.paragraphs)
        cast = "、".join(c.name for c in req.story.characters) or "旅人"
        target = max(150.0, min(BOOK_MAX_SEC, float(req.target_sec or BOOK_TARGET_SEC)))
        n_shots = BOOK_IMAGE_COUNT

        data = await chat_json(
            system=(
                "你是《一生》式书籍说书编剧。成片约 3 分钟，以叙述讲故事为主；"
                "配图约 8–12 张，每段旁白挂一张图。输出严格 JSON：\n"
                '{"lines":[{"index":0,"text":"","visual_hint_en":"","estimated_sec":16}],'
                f'"total_sec":{int(target)}}}\n'
                "要求：\n"
                f"1) 正好拆成 {BOOK_IMAGE_COUNT_MIN}–{BOOK_IMAGE_COUNT_MAX} 段口播"
                f"（目标 {n_shots} 段）。\n"
                "2) text 每段 55–110 汉字，口语讲故事，有人物/情节/对照；"
                "text 即配音稿，也是画面逐字字幕，必须可直接朗读。\n"
                "3) visual_hint_en：本镜英文画面提示，必须贴合旁白情节，具体可拍，"
                "禁止千篇一律空镜头。\n"
                "4) estimated_sec 单段约 14–22 秒；"
                f"总时长约 {int(target - 20)}–{int(target)} 秒，不超过 {int(BOOK_MAX_SEC)}。\n"
                "5) 结构：钩子→故事→顿悟→升华。禁止「大家好我是」、禁止另写与口播不同的金句字幕。"
            ),
            user=(
                f"标题：{req.story.title}\n封面钩子：{req.story.cover_hook}\n"
                f"画风：{req.story.visual_style_en}\n角色：{cast}\n"
                f"讲述骨架：\n{story_text}\n"
                f"目标时长：{target} 秒；配图约 {n_shots} 张。"
            ),
            temperature=0.45,
        )
        lines: list[ScriptLine] = []
        for i, row in enumerate(data.get("lines") or []):
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            sec = float(
                row.get("estimated_sec") or max(12.0, min(24.0, len(text) / 3.4))
            )
            sec = max(12.0, min(24.0, sec))
            hint = str(row.get("visual_hint_en") or "").strip()
            # caption：逐字稿=text；可选附带画面提示供分镜拆解
            caption = text if not hint else f"{text}\x1e{hint}"
            lines.append(
                ScriptLine(
                    index=i,
                    text=text,
                    estimated_sec=round(sec, 2),
                    caption=caption,
                )
            )

        while len(lines) > BOOK_IMAGE_COUNT_MAX:
            last = lines.pop()
            lines[-1].text = f"{lines[-1].text}{last.text}"
            lines[-1].estimated_sec = round(
                min(28.0, lines[-1].estimated_sec + last.estimated_sec), 2
            )
        for i, line in enumerate(lines):
            line.index = i

        total = sum(l.estimated_sec for l in lines)
        while lines and total > BOOK_MAX_SEC and len(lines) > BOOK_IMAGE_COUNT_MIN:
            lines.pop()
            for i, line in enumerate(lines):
                line.index = i
            total = sum(l.estimated_sec for l in lines)

        if len(lines) < BOOK_IMAGE_COUNT_MIN and req.story.paragraphs:
            lines = []
            for p in req.story.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                chunk = text if len(text) <= 110 else text[:110]
                lines.append(
                    ScriptLine(
                        index=len(lines),
                        text=chunk,
                        estimated_sec=round(max(14.0, min(22.0, len(chunk) / 3.4)), 2),
                        caption=chunk,
                    )
                )
                if len(lines) >= n_shots or sum(l.estimated_sec for l in lines) >= target:
                    break

        if not lines:
            seed = (req.story.summary or req.story.title or "").strip()
            lines = [
                ScriptLine(
                    index=0,
                    text=seed,
                    estimated_sec=18.0,
                    caption=seed,
                )
            ]

        total = sum(l.estimated_sec for l in lines)
        return Script(
            lines=lines,
            total_sec=round(min(total, BOOK_MAX_SEC), 2),
            provider=f"llm_book:{cfg.text_preset}",
        )