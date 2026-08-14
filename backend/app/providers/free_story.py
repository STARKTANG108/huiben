from __future__ import annotations

from app.models.schemas import Story, StoryParagraph
from app.providers.base import StoryRequest
from app.providers.llm_client import LLMError, chat_json


class FreeStoryProvider:
    """Free text via Pollinations (no key)."""

    name = "free"

    async def generate(self, req: StoryRequest) -> Story:
        data = await chat_json(
            system=(
                "你是儿童绘本作家。写温暖、积极、适合低龄儿童的短故事。"
                "输出 JSON：title, summary, mood, paragraphs(字符串数组，4段)。"
            ),
            user=(
                f"主题：{req.theme}\n适合年龄：{req.age_range}\n画风提示：{req.style}\n"
                "故事总长度适合约1分钟旁白，语言口语化。"
            ),
            temperature=0.7,
        )
        paragraphs_raw = data.get("paragraphs") or []
        if isinstance(paragraphs_raw, str):
            paragraphs_raw = [paragraphs_raw]
        paragraphs = [
            StoryParagraph(index=i, text=str(p).strip())
            for i, p in enumerate(paragraphs_raw)
            if str(p).strip()
        ]
        if not paragraphs:
            raise LLMError("免费故事模型未返回段落")
        return Story(
            title=str(data.get("title") or f"「{req.theme}」的故事"),
            summary=str(data.get("summary") or ""),
            age_range=req.age_range,
            paragraphs=paragraphs,
            mood=str(data.get("mood") or "warm"),
            provider=self.name,
        )


class OpenAICompatStoryProvider:
    name = "openai_compat"

    async def generate(self, req: StoryRequest) -> Story:
        # Same prompts; llm_client routes by runtime config mode=custom
        inner = FreeStoryProvider()
        story = await inner.generate(req)
        story.provider = self.name
        return story
