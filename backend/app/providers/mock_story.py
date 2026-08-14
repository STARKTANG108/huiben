from __future__ import annotations

import asyncio

from app.models.schemas import Story, StoryParagraph
from app.providers.base import StoryRequest


class MockStoryProvider:
    name = "mock"

    async def generate(self, req: StoryRequest) -> Story:
        await asyncio.sleep(0.35)
        theme = req.theme.strip()
        short = theme if len(theme) <= 12 else theme[:12] + "…"
        title = f"「{short}」的奇妙一天"
        paragraphs = [
            StoryParagraph(
                index=0,
                text=f"从前，有一个好奇的小朋友，听说了「{theme}」的故事，决定出发去看看。",
            ),
            StoryParagraph(
                index=1,
                text="路上遇见会说话的小动物，它们一起穿过彩色的树林，发现了许多闪闪发光的小秘密。",
            ),
            StoryParagraph(
                index=2,
                text="忽然起了一阵温柔的风，把大家带到了一片金黄的草地上，那里藏着勇气和友谊。",
            ),
            StoryParagraph(
                index=3,
                text=f"最后，小朋友明白了：关于「{theme}」，最重要的是善良、分享，还有回家的拥抱。",
            ),
        ]
        return Story(
            title=title,
            summary=f"一个适合 {req.age_range} 岁的温暖绘本故事，围绕「{theme}」展开冒险。",
            age_range=req.age_range,
            paragraphs=paragraphs,
            mood="warm",
            provider=self.name,
        )
