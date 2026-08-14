from __future__ import annotations

from app.models.schemas import Shot, Storyboard
from app.providers.base import StoryboardRequest
from app.providers.llm_client import LLMError, chat_json

CAMERAS = ["slow_zoom", "pan_left", "pan_right", "static", "gentle_rise"]


class FreeStoryboardProvider:
    name = "free"

    async def generate(self, req: StoryboardRequest) -> Storyboard:
        n = max(6, min(8, req.shot_count))
        script_blob = "\n".join(
            f"{i + 1}. {line.text}" for i, line in enumerate(req.script.lines)
        )
        data = await chat_json(
            system=(
                "你是儿童绘本分镜导演。输出 JSON：shots 数组。"
                "每项含 visual_prompt(英文画面描述), narration(中文旁白), "
                "duration_sec, camera, mood。"
                f"一共 {n} 个镜头，总时长约 {req.script.total_sec or 60} 秒。"
            ),
            user=(
                f"标题：{req.story.title}\n画风：{req.style}\n脚本：\n{script_blob}"
            ),
            temperature=0.5,
        )
        shots_raw = data.get("shots") or []
        shots: list[Shot] = []
        for i, item in enumerate(shots_raw[:n]):
            if not isinstance(item, dict):
                continue
            narration = str(item.get("narration") or "").strip()
            visual = str(item.get("visual_prompt") or "").strip()
            if not narration and not visual:
                continue
            if not visual:
                visual = (
                    f"{req.style} children's picture book, soft lighting, "
                    f"scene {i + 1}: {narration[:80]}"
                )
            shots.append(
                Shot(
                    index=i,
                    visual_prompt=visual,
                    narration=narration or req.story.summary,
                    duration_sec=float(item.get("duration_sec") or (60 / n)),
                    camera=str(item.get("camera") or CAMERAS[i % len(CAMERAS)]),
                    mood=str(item.get("mood") or req.story.mood),
                )
            )
        if len(shots) < 4:
            raise LLMError("免费分镜模型返回镜头过少")
        # reindex
        for i, s in enumerate(shots):
            s.index = i
        total = round(sum(s.duration_sec for s in shots), 2)
        return Storyboard(shots=shots, total_sec=total, provider=self.name)


class OpenAICompatStoryboardProvider:
    name = "openai_compat"

    async def generate(self, req: StoryboardRequest) -> Storyboard:
        board = await FreeStoryboardProvider().generate(req)
        board.provider = self.name
        return board
