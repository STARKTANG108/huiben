from __future__ import annotations

import logging
import re

from app.models.xhs_schemas import XhsCard, XhsJobStatus, XhsProject, utcnow
from app.providers.openai_compat import chat_json
from app.providers.xhs_baoyu import generate_xhs_viz_via_baoyu
from app.providers.xhs_fetch import fetch_source_text
from app.store.xhs_memory import xhs_store
from pathlib import Path

logger = logging.getLogger(__name__)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？\n]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 8][:8]


async def distill_content(
    *,
    source_title: str,
    source_text: str,
    max_cards: int,
    notes: str,
) -> tuple[str, str, str, list[XhsCard]]:
    """Returns summary, post_title, post_body, cards."""
    data = await chat_json(
        system=(
            "你是小红书内容编辑兼信息图策划。阅读来源材料后输出严格 JSON："
            '{"summary":"客观总摘要",'
            '"post_title":"可直接发帖的标题≤28字",'
            '"post_body":"可直接发帖的正文200-450字",'
            '"cards":[{"hook":"爆点短句","title":"卡片标题","points":["要点"],"footer":"页脚"}]}。'
            f"cards 数量 1 到 {max_cards}，不要超过 {max_cards} 张。"
            "要求："
            "1) 事实必须来自原文，禁止编造数据/观点；"
            "2) hook≤12字，必须有爆点（数字/反差/结论），适合大字色块；"
            "3) title≤16字，与 hook 不重复；points 恰好 3-4 条，每条≤28字，一条一个信息点；"
            "4) post_title 有吸引力但不标题党造假；post_body 口语短句，可含清单，结尾轻引导收藏；"
            "5) 禁止 emoji 与特殊装饰符号；禁止赋能/综上所述等套话。"
        ),
        user=(
            f"来源标题：{source_title}\n"
            f"用户补充：{notes or '无'}\n"
            f"正文材料：\n{source_text[:9000]}\n\n"
            f"请提炼标题、正文，并拆成不超过 {max_cards} 张内容可视化卡片（文字会印在图上）。"
        ),
        temperature=0.45,
    )

    summary = str(data.get("summary") or "").strip()
    post_title = str(data.get("post_title") or "").strip()[:40]
    post_body = str(data.get("post_body") or "").strip()

    rows = data.get("cards") or []
    cards: list[XhsCard] = []
    for i, row in enumerate(rows[:max_cards]):
        points = [
            str(p).strip()
            for p in (row.get("points") or [])
            if str(p).strip()
        ][:6]
        if not points:
            continue
        cards.append(
            XhsCard(
                index=i,
                hook=str(row.get("hook") or "").strip()[:20],
                title=str(row.get("title") or f"要点 {i + 1}").strip()[:40],
                points=points,
                footer=str(row.get("footer") or "").strip()[:40],
            )
        )

    if not cards:
        snippet = _split_sentences(source_text)[:4] or [summary or "暂无摘要"]
        cards = [
            XhsCard(
                index=0,
                hook="核心结论",
                title=(source_title or "内容摘要")[:18],
                points=[s[:32] for s in snippet],
                footer="自动提炼",
            )
        ]

    if not summary:
        summary = "；".join(cards[0].points[:2])
    if not post_title:
        post_title = (cards[0].hook or cards[0].title or source_title or "内容分享")[:28]
    if not post_body:
        lines = [post_title, ""]
        for c in cards:
            lines.append(c.title)
            lines.extend(f"- {p}" for p in c.points)
            lines.append("")
        lines.append("原文提炼，收藏备用。")
        post_body = "\n".join(lines).strip()

    return summary, post_title, post_body, cards


async def run_xhs_pipeline(project_id: str) -> XhsProject:
    project = xhs_store.get(project_id)
    if not project:
        raise RuntimeError("XHS project not found")

    project.job_status = XhsJobStatus.running
    project.job_error = None
    project.updated_at = utcnow()
    xhs_store.save(project)

    try:
        title, body = await fetch_source_text(project.url)
        project.source_title = title
        project.source_excerpt = body[:500]
        project.updated_at = utcnow()
        xhs_store.save(project)

        summary, post_title, post_body, cards = await distill_content(
            source_title=title,
            source_text=body,
            max_cards=project.max_cards,
            notes=project.notes,
        )
        project.summary = summary
        project.post_title = post_title
        project.post_body = post_body
        project.cards = cards
        project.updated_at = utcnow()
        xhs_store.save(project)

        total = len(project.cards)
        anchor: Path | None = None
        for card in project.cards:
            asset = await generate_xhs_viz_via_baoyu(
                project_id=project.id,
                card=card,
                card_total=total,
                style=project.style,
                layout=project.layout,
                ref_image=anchor,
            )
            project.assets[asset.id] = asset
            card.image_asset_id = asset.id
            project.updated_at = utcnow()
            xhs_store.save(project)
            # baoyu-xhs-images: image-1 as visual anchor for the rest
            if anchor is None:
                anchor = Path(asset.meta["path"])

        project.job_status = XhsJobStatus.completed
        project.updated_at = utcnow()
        return xhs_store.save(project)
    except Exception as exc:  # noqa: BLE001
        logger.exception("XHS pipeline failed %s", project_id)
        project = xhs_store.get(project_id) or project
        project.job_status = XhsJobStatus.failed
        project.job_error = str(exc)
        project.updated_at = utcnow()
        xhs_store.save(project)
        raise
