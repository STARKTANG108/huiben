from __future__ import annotations

import asyncio
import re

from app.models.schemas import Script, ScriptLine
from app.providers.base import ScriptRequest


class MockScriptProvider:
    name = "mock"

    async def generate(self, req: ScriptRequest) -> Script:
        await asyncio.sleep(0.25)
        raw_parts: list[str] = []
        for p in req.story.paragraphs:
            # Split on Chinese/English sentence ends
            chunks = re.split(r"(?<=[。！？!?])", p.text)
            raw_parts.extend([c.strip() for c in chunks if c.strip()])

        if not raw_parts:
            raw_parts = [req.story.summary]

        # Aim ~60s narration: ~2.8 Chinese chars/sec for kids
        target = req.target_sec
        chars_per_sec = 2.8
        lines: list[ScriptLine] = []
        for i, text in enumerate(raw_parts):
            sec = max(4.0, min(12.0, len(text) / chars_per_sec))
            lines.append(ScriptLine(index=i, text=text, estimated_sec=round(sec, 2)))

        total = sum(l.estimated_sec for l in lines)
        # Scale to ~target if far off
        if total > 0 and abs(total - target) > 8:
            scale = target / total
            for line in lines:
                line.estimated_sec = round(max(3.5, line.estimated_sec * scale), 2)
            total = sum(l.estimated_sec for l in lines)

        return Script(lines=lines, total_sec=round(total, 2), provider=self.name)
