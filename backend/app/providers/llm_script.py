from __future__ import annotations

from app.models.schemas import Script, ScriptLine
from app.providers.base import ScriptRequest
from app.providers.openai_compat import chat_json
from app.runtime_config import runtime_config


class LLMScriptProvider:
    name = "llm"

    async def generate(self, req: ScriptRequest) -> Script:
        cfg = runtime_config.get()
        story_text = "\n".join(p.text for p in req.story.paragraphs)
        cast = "、".join(c.name for c in req.story.characters) or "（故事角色）"
        target = float(req.target_sec or 60.0)
        data = await chat_json(
            system=(
                "你是儿童绘本「讲故事」旁白编剧，语气像睡前给孩子慢慢讲故事。"
                "输出严格 JSON：\n"
                '{"lines":[{"index":0,"text":"","estimated_sec":5.5}],"total_sec":65}\n'
                "硬性要求：\n"
                "1) 拆成 10–14 句旁白，保持完整故事弧："
                "开场点题→认识角色与愿望→遇到小麻烦→努力尝试→转折→温暖收束。\n"
                "2) 每句 16–32 个汉字：有一点情节推进与情绪，不要只有干巴巴的画面指令；"
                "可偶尔用「你听」「这时候」「原来」等讲故事连接词。\n"
                "3) 口语自然、温柔，适合慢速朗读；禁止书面腔、禁止说教口号。\n"
                "4) 尽量点名正在出场的角色（用故事里的角色名），避免含糊「他们」。\n"
                "5) estimated_sec 按慢讲估算，约 4.5–7.0 秒/句；"
                f"总时长约 {int(target - 5)}–{int(target + 15)} 秒。\n"
                "6) 顺序严格跟随故事，不要跳跃，结尾要有余韵。"
            ),
            user=(
                f"标题：{req.story.title}\n角色：{cast}\n情绪：{req.story.mood}\n"
                f"故事：\n{story_text}\n"
                f"目标时长：{target} 秒（慢速讲故事）。"
            ),
            temperature=0.55,
        )
        lines_raw = data.get("lines") or []
        lines: list[ScriptLine] = []
        for i, row in enumerate(lines_raw):
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            # 慢讲：按字数估时偏宽松
            sec = float(
                row.get("estimated_sec") or max(4.5, min(7.0, len(text) / 2.8))
            )
            sec = max(4.5, min(7.5, sec))
            lines.append(ScriptLine(index=i, text=text, estimated_sec=round(sec, 2)))

        if len(lines) < 8 and req.story.paragraphs:
            lines = []
            for p in req.story.paragraphs:
                text = (p.text or "").strip()
                if not text:
                    continue
                # 按句号切成叙事句，保留故事感
                chunks: list[str] = []
                buf = ""
                for ch in text:
                    buf += ch
                    if ch in "。！？；" and len(buf.strip()) >= 10:
                        chunks.append(buf.strip())
                        buf = ""
                if buf.strip():
                    chunks.append(buf.strip())
                if not chunks:
                    chunks = [text]
                for part in chunks:
                    if len(part) > 36:
                        # 在逗号处再拆，避免一句太长
                        cut = part.find("，", 14)
                        if cut > 0:
                            parts = [part[: cut + 1], part[cut + 1 :]]
                        else:
                            parts = [part]
                    else:
                        parts = [part]
                    for piece in parts:
                        piece = piece.strip()
                        if not piece:
                            continue
                        lines.append(
                            ScriptLine(
                                index=len(lines),
                                text=piece,
                                estimated_sec=round(max(4.5, len(piece) / 2.8), 2),
                            )
                        )

        if not lines:
            lines = [
                ScriptLine(
                    index=0,
                    text=req.story.summary or req.story.title,
                    estimated_sec=6.0,
                )
            ]

        for i, line in enumerate(lines):
            line.index = i
        total = sum(l.estimated_sec for l in lines)
        return Script(
            lines=lines,
            total_sec=round(total, 2),
            provider=f"llm:{cfg.text_preset}",
        )
