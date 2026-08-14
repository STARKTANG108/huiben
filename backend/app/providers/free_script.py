from __future__ import annotations

from app.models.schemas import Script, ScriptLine
from app.providers.base import ScriptRequest
from app.providers.llm_client import LLMError, chat_json


class FreeScriptProvider:
    name = "free"

    async def generate(self, req: ScriptRequest) -> Script:
        story_text = "\n".join(p.text for p in req.story.paragraphs)
        data = await chat_json(
            system=(
                "你是儿童绘本旁白编剧。把故事改成适合朗读的旁白脚本。"
                f"目标总时长约 {req.target_sec:.0f} 秒。"
                "输出 JSON：lines 数组，每项 {{text, estimated_sec}}。"
            ),
            user=(
                f"标题：{req.story.title}\n简介：{req.story.summary}\n正文：\n{story_text}"
            ),
            temperature=0.4,
        )
        lines_raw = data.get("lines") or []
        lines: list[ScriptLine] = []
        for i, item in enumerate(lines_raw):
            if isinstance(item, str):
                text = item.strip()
                sec = max(4.0, min(12.0, len(text) / 2.8))
            else:
                text = str(item.get("text") or "").strip()
                sec = float(item.get("estimated_sec") or max(4.0, len(text) / 2.8))
            if text:
                lines.append(
                    ScriptLine(index=i, text=text, estimated_sec=round(sec, 2))
                )
        if not lines:
            raise LLMError("免费脚本模型未返回句子")
        total = round(sum(l.estimated_sec for l in lines), 2)
        return Script(lines=lines, total_sec=total, provider=self.name)


class OpenAICompatScriptProvider:
    name = "openai_compat"

    async def generate(self, req: ScriptRequest) -> Script:
        script = await FreeScriptProvider().generate(req)
        script.provider = self.name
        return script
