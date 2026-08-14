from __future__ import annotations

"""MiniMax image (image-01) + TTS (speech-2.8) for pictale module 1."""

import base64
import logging
import re
from pathlib import Path

import asyncio
import httpx

from app.config import get_settings
from app.models.schemas import AssetRef, TTSResult
from app.providers.base import ImageRequest, TTSRequest
from app.providers.edge_tts_provider import _concat_mp3, _ffprobe_duration
from app.providers.media_utils import (
    asset_url,
    ensure_portrait_9_16,
    new_asset_id,
    project_dir,
)
from app.providers.style_lock import WATERCOLOR_STYLE_EN
from app.runtime_config import runtime_config

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.minimaxi.com"
DEFAULT_IMAGE_MODEL = "image-01"
DEFAULT_TTS_MODEL = "speech-2.8-hd"
DEFAULT_VOICE = "Chinese (Mandarin)_Warm_Girl"
# 说书/有声书：中气足的男声（仅书籍模块通过 TTSRequest.voice 指定）
BOOK_NARRATOR_VOICE = "Chinese (Mandarin)_Male_Announcer"
_PLACEHOLDER_VOICES = frozenset({"", "child_warm", "default"})

BOOK_ILLUSTRATION_STYLE_EN = (
    "cinematic narrative still matching the book story, warm film grade, "
    "strong composition and readable silhouette, vertical 9:16 full-bleed, "
    "no text, no watermark, no subtitle, no logo"
)


def _style_prefix(style: str) -> str:
    s = (style or "").strip()
    low = s.lower()
    if low.startswith("custom:"):
        return s[7:].strip() or BOOK_ILLUSTRATION_STYLE_EN
    if low in ("book", "book_illustration", "storybook"):
        return BOOK_ILLUSTRATION_STYLE_EN
    return WATERCOLOR_STYLE_EN


def _minimax_base() -> str:
    cfg = runtime_config.get()
    # 按 preset 显式取对应 base_url（自定义中转/代理域名也生效），不靠域名子串猜测
    if cfg.image_preset == "minimax":
        base = (cfg.image_base_url or "").strip().rstrip("/")
    elif cfg.tts_preset == "minimax":
        base = (cfg.tts_base_url or "").strip().rstrip("/")
    else:
        base = ""
    if not base:
        return DEFAULT_BASE
    return base[:-3] if base.endswith("/v1") else base


def _minimax_api_key() -> str:
    cfg = runtime_config.get()
    key = (cfg.minimax_api_key or cfg.tts_api_key or cfg.image_api_key or "").strip()
    if not key:
        raise RuntimeError(
            "请在模型配置填写 MiniMax API Key（平台 platform.minimaxi.com）"
        )
    return key


def _check_base_resp(data: dict) -> None:
    resp = data.get("base_resp") or {}
    code = resp.get("status_code")
    if code is not None and code != 0:
        msg = resp.get("status_msg") or f"status_code={code}"
        if "sensitive" in str(msg).lower() or code in (1026, 1027):
            raise RuntimeError(
                f"MiniMax 内容审核未通过（{msg}）。"
                "已尝试改写提示词；若仍失败请换更温和的讲述角度后重试。"
            )
        raise RuntimeError(f"MiniMax 错误：{msg}")


def _is_rate_limit_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return "rate limit" in text or "rpm" in text or "429" in text


async def _minimax_post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict,
    body: dict,
    retries: int = 4,
) -> dict:
    """POST with backoff on MiniMax RPM / rate limit."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            res = await client.post(url, headers=headers, json=body)
            if res.status_code == 429:
                raise RuntimeError(f"MiniMax 错误：rate limit exceeded(RPM) HTTP 429")
            if res.status_code >= 400:
                raise RuntimeError(
                    f"MiniMax 请求失败 ({res.status_code}): {res.text[:400]}"
                )
            data = res.json()
            _check_base_resp(data)
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt + 1 >= retries or not _is_rate_limit_error(exc):
                raise
            wait = 2.5 * (attempt + 1)
            logger.warning("MiniMax rate limit, retry in %.1fs (%s)", wait, exc)
            await asyncio.sleep(wait)
    assert last_err
    raise last_err


def _is_sensitive_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return (
        "new_sensitive" in text
        or "input sensitive" in text
        or "output new_sensitive" in text
        or "1026" in text
        or "涉敏" in str(exc)
    )


def _strip_cjk(text: str) -> str:
    """Remove Chinese/Japanese/Korean characters (MiniMax CN often flags CN narration)."""
    return re.sub(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+", " ", text or "")


_SENSITIVE_REPLACEMENTS = (
    (r"\b(kill|killed|killing|murder|suicide|blood|bloody|gore|gun|guns|revolver|"
     r"pistol|rifle|weapon|weapons|nude|naked|sex|erotic|porn|drug|cocaine|"
     r"heroin|terror|bomb|corpse|dead body)\b", "dramatic"),
    (r"(枪杀|杀人|自杀|死亡|尸体|鲜血|血腥|裸体|色情|毒品|枪支|手枪|步枪|炸弹|恐怖)", "戏剧张力"),
)


def sanitize_minimax_prompt(text: str, *, drop_cjk: bool = False) -> str:
    """Soften prompts that commonly trip MiniMax 1026 input new_sensitive."""
    s = (text or "").strip()
    if not s:
        return ""
    if drop_cjk:
        s = _strip_cjk(s)
    for pattern, repl in _SENSITIVE_REPLACEMENTS:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" .,;:")
    return s[:1500]


def _build_image_prompt(req: ImageRequest) -> str:
    # 不要把中文旁白塞进生图：极易触发 MiniMax input new_sensitive
    raw = (req.shot.visual_prompt or "").strip()
    scene = raw
    for marker in ("Scene:", "scene:", "Detailed scene:"):
        if marker in raw:
            scene = raw.split(marker, 1)[-1].strip()
            break
    # visual_prompt 里若夹带中文旁白，剥掉
    scene = sanitize_minimax_prompt(scene, drop_cjk=True)
    if len(scene) > 420:
        scene = scene[:420]

    lock = sanitize_minimax_prompt((req.characters_lock or "").strip(), drop_cjk=True)
    if lock.startswith("CHARACTER LOCK"):
        lock = lock.replace(
            "CHARACTER LOCK (must match exactly, do not invent humans unless listed): ",
            "characters: ",
        )
    if len(lock) > 320:
        lock = lock[:320]

    chars = ", ".join(req.shot.characters_in_shot) if req.shot.characters_in_shot else ""
    chars = sanitize_minimax_prompt(chars, drop_cjk=True)
    style = sanitize_minimax_prompt(_style_prefix(req.style), drop_cjk=False)
    parts = [
        style,
        f"draw only: {chars}" if chars else "",
        lock,
        f"scene: {scene}" if scene else "scene: wide atmospheric landscape, soft light",
        "artistic cinematic still, no violence, no weapons, no text",
    ]
    prompt = ". ".join(p for p in parts if p)
    prompt = re.sub(r"\s+", " ", prompt).strip()
    if not prompt:
        prompt = "cinematic atmospheric still, soft light, peaceful mood, vertical 9:16"
    return prompt[:1500]


def _safe_fallback_image_prompt(req: ImageRequest) -> str:
    style = sanitize_minimax_prompt(_style_prefix(req.style), drop_cjk=True)
    kind = (getattr(req.shot, "shot_kind", None) or "scenery").strip().lower()
    if kind == "metaphor":
        scene = "symbolic still life detail, soft light, peaceful metaphor object"
    elif kind == "character":
        scene = "distant silhouette of a traveler in landscape, gentle backlight, no face close-up"
    else:
        scene = "wide atmospheric landscape, golden hour, calm mood, empty foreground"
    return sanitize_minimax_prompt(
        f"{style}. {scene}. artistic cinematic still, no violence, no text, vertical 9:16",
        drop_cjk=True,
    )[:1200]


def _pictale_tts_voice_setting(shot, *, total: int) -> dict:
    """儿童绘本：慢速讲故事感，温柔稳定。"""
    idx = getattr(shot, "index", 0) or 0
    progress = idx / max(1, total - 1)
    mood = (getattr(shot, "mood", None) or "warm").strip().lower()
    # MiniMax speed：越小越慢；绘本整体偏慢
    speed = 0.86
    pitch = 0
    emotion: str | None = "happy"

    if idx == 0:
        speed = 0.84
        emotion = "calm"
    elif mood in ("calm", "reflective"):
        speed = 0.84
        emotion = "calm"
    elif mood in ("adventure", "playful") and progress < 0.7:
        speed = 0.88
        emotion = "happy"
    elif progress >= 0.82:
        speed = 0.85
        emotion = "happy"
        pitch = 0

    return {"speed": speed, "vol": 1.0, "pitch": pitch, "emotion": emotion}


def _encode_reference_image(path: Path) -> str:
    """Encode a small JPEG reference to keep MiniMax payloads light (avoids blocking)."""
    try:
        from PIL import Image
        import io

        img = Image.open(path).convert("RGB")
        img.thumbnail((512, 912), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:  # noqa: BLE001
        raw = path.read_bytes()
        # hard cap ~400KB raw to avoid freezing the API event loop
        if len(raw) > 400_000:
            raw = raw[:400_000]
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{b64}"


class MinimaxImageProvider:
    name = "minimax"

    async def generate(self, req: ImageRequest) -> AssetRef:
        cfg = runtime_config.get()
        api_key = _minimax_api_key()
        model = (cfg.image_model or DEFAULT_IMAGE_MODEL).strip() or DEFAULT_IMAGE_MODEL
        if not model.startswith("image-"):
            model = DEFAULT_IMAGE_MODEL
        base = _minimax_base()
        prompt = _build_image_prompt(req)
        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async def _post(client: httpx.AsyncClient, prompt_text: str, *, use_ref: bool) -> dict:
            body: dict = {
                "model": model,
                "prompt": prompt_text,
                "aspect_ratio": "9:16",
                "response_format": "base64",
                "n": 1,
                "prompt_optimizer": True,
            }
            if req.seed is not None:
                body["seed"] = int(req.seed)
            ref_path = (req.reference_image_path or "").strip()
            if use_ref and ref_path:
                ref = Path(ref_path)
                if ref.exists() and ref.stat().st_size > 500:
                    encoded = await asyncio.to_thread(_encode_reference_image, ref)
                    body["subject_reference"] = [
                        {"type": "character", "image_file": encoded}
                    ]
            return await _minimax_post_json(
                client,
                f"{base}/v1/image_generation",
                headers=headers,
                body=body,
            )

        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            try:
                data = await _post(client, prompt, use_ref=True)
            except Exception as exc:  # noqa: BLE001
                if not _is_sensitive_error(exc):
                    raise
                logger.warning(
                    "MiniMax image sensitive, retry safe prompt (shot=%s): %s",
                    getattr(req.shot, "index", "?"),
                    exc,
                )
                prompt = _safe_fallback_image_prompt(req)
                data = await _post(client, prompt, use_ref=False)

            payload = data.get("data") or {}
            asset_id = new_asset_id()
            filename = f"shot_{req.shot.index:02d}_{asset_id}.png"
            storage = req.storage_key or req.project_id
            path = project_dir(settings, storage) / filename

            b64_list = payload.get("image_base64") or []
            urls = payload.get("image_urls") or []
            if b64_list:
                raw_b64 = b64_list[0]
                if "," in raw_b64[:80]:
                    raw_b64 = raw_b64.split(",", 1)[1]
                path.write_bytes(base64.b64decode(raw_b64))
            elif urls:
                img = await client.get(urls[0])
                if img.status_code >= 400:
                    raise RuntimeError(f"下载 MiniMax 图片失败 ({img.status_code})")
                path.write_bytes(img.content)
            else:
                raise RuntimeError("MiniMax 生图返回中无图片数据")

        ensure_portrait_9_16(path)
        return AssetRef(
            id=asset_id,
            kind="image",
            filename=filename,
            mime_type="image/png",
            url=asset_url(
                req.project_id,
                asset_id,
                api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
            ),
            meta={
                "shot_index": req.shot.index,
                "path": str(path),
                "provider": self.name,
                "model": model,
                "aspect": "9:16",
            },
        )



class MinimaxTTSProvider:
    """Per-shot MiniMax T2A so narration length matches each image."""

    name = "minimax"

    async def _synthesize(
        self,
        client: httpx.AsyncClient,
        *,
        text: str,
        api_key: str,
        model: str,
        voice: str,
        base: str,
        voice_setting_extra: dict | None = None,
    ) -> tuple[bytes, float | None]:
        voice_setting = {
            "voice_id": voice,
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
        }
        if voice_setting_extra:
            voice_setting.update(voice_setting_extra)
        body = {
            "model": model,
            "text": text[:9000],
            "stream": False,
            "language_boost": "Chinese",
            "output_format": "hex",
            "voice_setting": voice_setting,
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        res = await client.post(
            f"{base}/v1/t2a_v2",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if res.status_code == 429 or (
            res.status_code < 400 and "rate limit" in (res.text or "").lower()
        ):
            raise RuntimeError("MiniMax 错误：rate limit exceeded(RPM)")
        if res.status_code >= 400:
            raise RuntimeError(f"MiniMax 配音失败 ({res.status_code}): {res.text[:400]}")
        data = res.json()
        _check_base_resp(data)
        audio_hex = ((data.get("data") or {}).get("audio")) or ""
        if not audio_hex:
            raise RuntimeError("MiniMax 配音返回中无音频数据")
        audio_bytes = bytes.fromhex(audio_hex)
        extra = data.get("extra_info") or {}
        # audio_length is milliseconds in MiniMax responses
        length_ms = extra.get("audio_length")
        duration = None
        if isinstance(length_ms, (int, float)) and length_ms > 0:
            duration = float(length_ms) / 1000.0
        return audio_bytes, duration

    async def generate(self, req: TTSRequest) -> TTSResult:
        cfg = runtime_config.get()
        api_key = _minimax_api_key()
        model = (cfg.tts_model or DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL
        if not model.startswith("speech-"):
            model = DEFAULT_TTS_MODEL
        req_voice = (req.voice or "").strip()
        cfg_voice = (cfg.tts_voice or "").strip()
        if req_voice and req_voice not in _PLACEHOLDER_VOICES:
            voice = req_voice
        else:
            voice = cfg_voice or DEFAULT_VOICE
        # Edge-style voices are invalid for MiniMax
        if voice.startswith("zh-CN-") or "Neural" in voice:
            voice = DEFAULT_VOICE
        base = _minimax_base()
        settings = get_settings()
        root = project_dir(settings, req.storage_key or req.project_id)
        part_paths: list[Path] = []
        is_book = (getattr(req, "api_prefix", None) or "").startswith("/api/book")
        is_pictale = not is_book
        total_shots = len(req.storyboard.shots)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            for i, shot in enumerate(req.storyboard.shots):
                if i > 0:
                    await asyncio.sleep(0.8)
                text = (shot.narration or "").strip() or "……"
                extra = (
                    _pictale_tts_voice_setting(shot, total=total_shots)
                    if is_pictale
                    else None
                )
                audio_bytes, api_dur = None, None
                last_err: Exception | None = None
                for attempt in range(4):
                    try:
                        audio_bytes, api_dur = await self._synthesize(
                            client,
                            text=text,
                            api_key=api_key,
                            model=model,
                            voice=voice,
                            base=base,
                            voice_setting_extra=extra,
                        )
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = exc
                        if attempt + 1 >= 4 or not _is_rate_limit_error(exc):
                            raise
                        wait = 2.5 * (attempt + 1)
                        logger.warning(
                            "MiniMax TTS rate limit, retry in %.1fs", wait
                        )
                        await asyncio.sleep(wait)
                if audio_bytes is None:
                    assert last_err
                    raise last_err
                part = root / f"tts_shot_{shot.index:02d}.mp3"
                part.write_bytes(audio_bytes)
                dur = api_dur or _ffprobe_duration(part)
                if dur and dur > 0.3:
                    shot.duration_sec = round(dur + 0.35, 2)  # 讲故事留一点气口
                else:
                    # 慢讲估算
                    shot.duration_sec = round(max(4.5, len(text) / 2.8), 2)
                part_paths.append(part)

        req.storyboard.total_sec = round(
            sum(s.duration_sec for s in req.storyboard.shots), 2
        )

        asset_id = new_asset_id()
        filename = f"tts_{asset_id}.mp3"
        path = root / filename
        if not _concat_mp3(part_paths, path):
            # fallback: single request with joined narration
            joined = "。".join(
                s.narration.strip() for s in req.storyboard.shots if s.narration.strip()
            ) or "……"
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                audio_bytes, _ = await self._synthesize(
                    client,
                    text=joined,
                    api_key=api_key,
                    model=model,
                    voice=voice,
                    base=base,
                )
            path.write_bytes(audio_bytes)

        duration = _ffprobe_duration(path) or req.storyboard.total_sec
        asset = AssetRef(
            id=asset_id,
            kind="audio",
            filename=filename,
            mime_type="audio/mpeg",
            url=asset_url(
                req.project_id,
                asset_id,
                api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
            ),
            meta={
                "path": str(path),
                "voice": voice,
                "provider": self.name,
                "model": model,
                "per_shot": True,
                "shot_durations": [s.duration_sec for s in req.storyboard.shots],
            },
        )
        return TTSResult(
            asset=asset, duration_sec=round(duration, 2), provider=self.name
        )
