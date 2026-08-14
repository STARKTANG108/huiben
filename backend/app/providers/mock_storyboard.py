from __future__ import annotations

import asyncio

from app.models.schemas import Shot, Storyboard
from app.providers.base import StoryboardRequest

CAMERAS = ["slow_zoom", "pan_left", "pan_right", "static", "gentle_rise"]


class MockStoryboardProvider:
    name = "mock"

    async def generate(self, req: StoryboardRequest) -> Storyboard:
        await asyncio.sleep(0.3)
        n = max(6, min(8, req.shot_count))
        lines = req.script.lines
        shots: list[Shot] = []

        for i in range(n):
            line = lines[i % len(lines)] if lines else None
            narration = line.text if line else req.story.summary
            duration = (
                round(req.script.total_sec / n, 2)
                if req.script.total_sec
                else 8.0
            )
            visual = (
                f"{req.style} children's picture book illustration, soft lighting, "
                f"scene {i + 1} of story '{req.story.title}': {narration[:80]}"
            )
            shots.append(
                Shot(
                    index=i,
                    visual_prompt=visual,
                    narration=narration,
                    duration_sec=duration,
                    camera=CAMERAS[i % len(CAMERAS)],
                    mood=req.story.mood,
                )
            )

        total = round(sum(s.duration_sec for s in shots), 2)
        return Storyboard(shots=shots, total_sec=total, provider=self.name)
