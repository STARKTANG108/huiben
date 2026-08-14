from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.models.cut_schemas import (
    CutAsset,
    CutClipSeekHit,
    CutJobStatus,
    CutProject,
    CutScene,
    utcnow,
)
from app.providers.cut_image import generate_cut_still
from app.providers.media_utils import (
    new_asset_id,
    project_dir,
    try_ffmpeg_slideshow,
)
from app.providers.openai_compat import chat_json
from app.providers import qcut as qcut_provider
from app.store.cut_memory import cut_store

logger = logging.getLogger(__name__)

MAX_SCENES = 8
FORMAT_SIZE = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


def _touch(project: CutProject, *, stage: str | None = None) -> CutProject:
    project.updated_at = utcnow()
    if stage is not None:
        project.stage = stage
    return cut_store.save(project)


def _qiaocut_dir(project_id: str) -> Path:
    return project_dir(get_settings(), f"cut/{project_id}") / "qiaocut"


def _load_ir(root: Path) -> dict:
    path = root / "qiaocut-ir.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _overlay_caption(image_path: Path, caption: str, size: tuple[int, int]) -> None:
    if not caption.strip():
        return
    img = Image.open(image_path).convert("RGB")
    if img.size != size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = size
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 42
        )
    except OSError:
        font = ImageFont.load_default()

    text = caption.strip()[:48]
    # bottom safe-area band
    band_top = int(h * 0.78)
    draw.rectangle((0, band_top, w, h), fill=(0, 0, 0, 140))
    # simple wrap
    lines: list[str] = []
    cur = ""
    for ch in text:
        trial = cur + ch
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > w - 80 and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    y = band_top + 28
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y), line, fill=(255, 255, 255), font=font)
        y += 52
    img.save(image_path, format="PNG", optimize=True)


async def _enrich_scenes(
    project: CutProject, ir_scenes: list[dict]
) -> list[CutScene]:
    # Split duration across scenes
    n = max(1, min(MAX_SCENES, len(ir_scenes) or 5))
    per = max(2.5, round(project.duration / n, 2))

    raw_rows = []
    for i, row in enumerate(ir_scenes[:n]):
        text = ""
        if isinstance(row.get("text"), dict):
            text = str(row["text"].get("content") or "")
        raw_rows.append(
            {
                "id": str(row.get("id") or f"s{i+1:02d}"),
                "purpose": str(row.get("purpose") or ""),
                "visual": str(row.get("visual") or ""),
                "caption": text,
            }
        )

    data = await chat_json(
        system=(
            "你是竖屏短视频混剪导演。根据分镜写出可拍摄的英文画面提示词，以及中文节奏字幕。"
            "输出严格 JSON："
            '{"scenes":[{"id":"s01","caption":"中文字幕≤16字","image_prompt":"English cinematic still, vertical 9:16, no text overlay"}]}。'
            "image_prompt 必须英文、具体、无文字水印；caption 短、有钩子。"
            f"场景数必须正好 {len(raw_rows)} 个，id 与输入一致。"
        ),
        user=(
            f"Brief：{project.brief}\n"
            f"Workflow：{project.workflow}\n"
            f"补充：{project.notes or '无'}\n"
            f"分镜：{json.dumps(raw_rows, ensure_ascii=False)}"
        ),
        temperature=0.6,
    )
    by_id = {str(r.get("id")): r for r in (data.get("scenes") or []) if isinstance(r, dict)}

    scenes: list[CutScene] = []
    for row in raw_rows:
        enriched = by_id.get(row["id"]) or {}
        caption = str(enriched.get("caption") or row["caption"] or "").strip()
        prompt = str(enriched.get("image_prompt") or "").strip()
        if not prompt:
            prompt = (
                f"Cinematic vertical still for: {row['visual'] or project.brief}. "
                "Photoreal editorial, bold focal subject, caption-safe lower third empty, no text."
            )
        if not caption:
            caption = row["purpose"] or "看这里"
        scenes.append(
            CutScene(
                id=row["id"],
                purpose=row["purpose"],
                visual=row["visual"],
                caption=caption[:40],
                image_prompt=prompt[:1200],
                duration_sec=per,
            )
        )
    return scenes


def _write_timeline(
    root: Path,
    project: CutProject,
    scenes: list[CutScene],
    rel_shots: list[dict],
) -> Path:
    width, height = FORMAT_SIZE.get(project.format, (1080, 1920))
    total = sum(float(s["duration"]) for s in rel_shots) or float(project.duration)
    timeline = {
        "schema": "qiaocut.timeline.v1",
        "title": project.brief[:80],
        "output": {
            "width": width,
            "height": height,
            "fps": 30,
            "duration": round(total, 2),
            "file": "renders/final.mp4",
        },
        "music": {
            "mode": "procedural",
            "bpm": 96,
            "energy": 0.55,
            "seed": int(hashlib.md5(project.id.encode()).hexdigest(), 16) % 10_000,
        },
        "shots": rel_shots,
        "reports": {"contactSheet": False, "renderReport": "reports/render-report.json"},
    }
    path = root / "timeline.json"
    path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


async def run_cut_pipeline(project_id: str) -> None:
    project = cut_store.get(project_id)
    if not project:
        return

    project.job_status = CutJobStatus.running
    project.job_error = None
    _touch(project, stage="scaffold")

    try:
        if not qcut_provider.which_node():
            raise RuntimeError("需要 Node.js 才能运行 qiaomu-cut（qcut）")

        root = _qiaocut_dir(project_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)

        project.doctor_hint = await asyncio.to_thread(qcut_provider.doctor_summary)
        _touch(project, stage="scaffold")

        await asyncio.to_thread(
            qcut_provider.scaffold_project,
            root,
            brief=project.brief,
            workflow=project.workflow,
            duration=project.duration,
            fmt=project.format,
        )
        ir = _load_ir(root)
        project.ir = {
            "workflow": (ir.get("workflow") or {}).get("id") or project.workflow,
            "style": ir.get("style") or {},
            "output": ir.get("output") or {},
            "scene_count": len(ir.get("scenes") or []),
        }
        _touch(project, stage="plan")

        ir_scenes = list(ir.get("scenes") or [])
        if not ir_scenes:
            # minimal fallback scenes
            ir_scenes = [
                {"id": "s01", "purpose": "hook", "visual": project.brief, "text": {"content": "先停一下"}},
                {"id": "s02", "purpose": "point", "visual": project.brief, "text": {"content": "重点来了"}},
                {"id": "s03", "purpose": "cta", "visual": project.brief, "text": {"content": "收藏起来"}},
            ]

        scenes = await _enrich_scenes(project, ir_scenes)
        project.scenes = scenes
        _touch(project, stage="clipseek")

        # ClipSeek discovery (links only; license verify on provider page)
        query = project.brief[:80]
        hits = await asyncio.to_thread(qcut_provider.clipseek_search, query, limit=5)
        project.clipseek = [
            CutClipSeekHit(
                id=str(h.get("id") or f"cs-{i}"),
                title=str(h.get("title") or ""),
                provider=str(h.get("provider") or ""),
                source_page=h.get("sourcePage") or h.get("source_page"),
                thumbnail=h.get("thumbnail"),
                media_type=str(h.get("mediaType") or h.get("media_type") or "video"),
            )
            for i, h in enumerate(hits)
        ]
        _touch(project, stage="images")

        width, height = FORMAT_SIZE.get(project.format, (1080, 1920))
        rel_shots: list[dict] = []
        image_paths: list[Path] = []
        durations: list[float] = []

        for i, scene in enumerate(project.scenes):
            asset = await generate_cut_still(
                project_id=project_id,
                index=i,
                image_prompt=scene.image_prompt,
                scene_id=scene.id,
            )
            project.assets[asset.id] = asset
            scene.image_asset_id = asset.id
            img_path = Path(asset.meta["path"])
            # copy into qiaocut assets for timeline-relative paths
            dest_name = f"assets/{scene.id}.png"
            dest = root / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, dest)
            _overlay_caption(dest, scene.caption, (width, height))
            # also overlay on served asset for preview consistency
            _overlay_caption(img_path, scene.caption, (width, height))

            rel_shots.append(
                {
                    "id": scene.id,
                    "kind": "image",
                    "path": dest_name,
                    "duration": float(scene.duration_sec),
                    "fit": "cover",
                    "motion": "pushIn" if i % 2 == 0 else "none",
                    "sourceAudio": False,
                }
            )
            image_paths.append(dest)
            durations.append(float(scene.duration_sec))
            _touch(project, stage=f"images:{i+1}/{len(project.scenes)}")

        project.scenes = list(project.scenes)
        _touch(project, stage="timeline")
        _write_timeline(root, project, project.scenes, rel_shots)

        _touch(project, stage="render")
        render_meta = await asyncio.to_thread(
            qcut_provider.try_qcut_render, root, profile="preview"
        )
        final_path = root / "renders" / "final.mp4"
        engine = "qcut"

        if not (final_path.exists() and final_path.stat().st_size > 1000):
            engine = "ffmpeg-slideshow"
            out = project_dir(get_settings(), f"cut/{project_id}") / "preview.mp4"
            ok = await asyncio.to_thread(
                try_ffmpeg_slideshow,
                image_paths,
                None,
                out,
                durations,
                bgm_path=None,
                width=width,
                height=height,
            )
            if not ok or not out.exists():
                raise RuntimeError(
                    "成片失败：qcut 需要 ffmpeg-full；本机回退 slideshow 也失败。"
                    "请安装 ffmpeg（brew install ffmpeg）后重试。"
                )
            final_path = out
            if render_meta is None and project.doctor_hint:
                pass  # keep hint

        asset_id = new_asset_id()
        video_name = f"cut_video_{asset_id}.mp4"
        served = project_dir(get_settings(), f"cut/{project_id}") / video_name
        if final_path.resolve() != served.resolve():
            shutil.copy2(final_path, served)
        video_asset = CutAsset(
            id=asset_id,
            kind="video",
            filename=video_name,
            mime_type="video/mp4",
            url=f"/api/cut/{project_id}/assets/{asset_id}",
            meta={
                "path": str(served),
                "engine": engine,
                "duration": sum(durations),
            },
        )
        project.assets[asset_id] = video_asset
        project.video_asset_id = asset_id
        project.render_engine = engine
        project.job_status = CutJobStatus.completed
        project.stage = "done"
        _touch(project)
    except Exception as exc:  # noqa: BLE001
        logger.exception("cut pipeline failed for %s", project_id)
        project = cut_store.get(project_id) or project
        project.job_status = CutJobStatus.failed
        project.job_error = str(exc)[:800]
        project.stage = "failed"
        _touch(project)
