from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "runtime_config.json"

TextPreset = Literal["mock", "gemini", "groq", "deepseek", "custom"]
ImagePreset = Literal["mock", "pollinations", "custom", "minimax", "flux"]
TTSPreset = Literal["mock", "edge", "custom", "minimax"]


class RuntimeConfig(BaseModel):
    """User-editable provider config (UI + file). Env defaults only seed first load."""

    text_preset: TextPreset = "mock"
    text_base_url: str = ""
    text_api_key: str = ""
    text_model: str = ""

    image_preset: ImagePreset = "minimax"
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""

    # custom-book Flux（Replicate）专用，不影响其他模块的 image_api_key / MiniMax
    replicate_api_token: str = ""

    tts_preset: TTSPreset = "minimax"
    tts_base_url: str = ""
    tts_api_key: str = ""
    tts_model: str = ""
    tts_voice: str = "Chinese (Mandarin)_Warm_Girl"
    # 书籍说书单独选声；空则回退 tts_voice
    book_tts_voice: str = "Chinese (Mandarin)_Male_Announcer"

    # Shared MiniMax key for pictale image + TTS (keeps suxi image_api_key for other modules)
    minimax_api_key: str = ""

    # ToAPIs（书籍开场视频 veo3.1-fast 首尾帧）
    toapis_api_key: str = ""
    toapis_base_url: str = "https://toapis.com"
    toapis_video_model: str = "veo3.1-fast"

    # Fixed for now
    bgm_preset: str = "mock"
    video_preset: str = "mock"


# Free / common presets — only need API key for gemini/groq/deepseek
TEXT_PRESETS: dict[str, dict[str, str]] = {
    "mock": {
        "label": "本地演示（无需 Key）",
        "base_url": "",
        "model": "",
        "hint": "不调用外部模型，用模板故事",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "hint": "故事 / 脚本 / 分镜 · platform.deepseek.com 申请 Key",
    },
    "gemini": {
        "label": "Google Gemini（免费额度）",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "hint": "到 Google AI Studio 免费申请 API Key",
    },
    "groq": {
        "label": "Groq（免费额度）",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "hint": "到 console.groq.com 免费申请 API Key",
    },
    "custom": {
        "label": "自定义（填 URL + Key）",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "hint": "任意 OpenAI 兼容接口（硅基流动 / 通义等）",
    },
}

IMAGE_PRESETS: dict[str, dict[str, str]] = {
    "mock": {
        "label": "本地占位图",
        "base_url": "",
        "model": "",
        "hint": "彩色占位图，不花钱",
    },
    "minimax": {
        "label": "MiniMax 生图（绘本）",
        "base_url": "https://api.minimaxi.com",
        "model": "image-01",
        "hint": "绘本画面 · platform.minimaxi.com · 填下方 MiniMax Key",
    },
    "pollinations": {
        "label": "Pollinations（免费生图）",
        "base_url": "https://image.pollinations.ai",
        "model": "flux",
        "hint": "无需 Key，联网即可生成",
    },
    "flux": {
        "label": "Flux（CatsAPI）",
        "base_url": "https://catsapi.com/api",
        "model": "flux2Pro",
        "hint": "儿童定制绘本 custom-book 专用 · catsapi.com · Token 形如 cats-…",
    },
    "custom": {
        "label": "自定义生图 API（suxi 等）",
        "base_url": "https://new.suxi.ai/v1",
        "model": "jimeng-3.0",
        "hint": "OpenAI Images 兼容接口；职场穿搭 / 小红绿书仍用此 Key",
    },
}

TTS_PRESETS: dict[str, dict[str, str]] = {
    "mock": {
        "label": "本地蜂鸣占位",
        "base_url": "",
        "model": "",
        "hint": "测试用，不是人声",
    },
    "minimax": {
        "label": "MiniMax 配音（绘本）",
        "base_url": "https://api.minimaxi.com",
        "model": "speech-2.8-hd",
        "hint": "绘本旁白 · 与生图共用 MiniMax Key",
    },
    "edge": {
        "label": "Edge TTS（免费真人声）",
        "base_url": "",
        "model": "",
        "hint": "微软 Edge 语音，无需 Key",
    },
    "custom": {
        "label": "自定义 TTS API",
        "base_url": "https://api.openai.com/v1",
        "model": "tts-1",
        "hint": "OpenAI TTS 兼容接口，需填 Key",
    },
}

# 系统内可选 MiniMax 音色（说书男声优先列出，绘本女声也保留）
MINIMAX_VOICES: list[dict[str, str]] = [
    {"id": "Chinese (Mandarin)_Male_Announcer", "label": "播报男声（说书推荐）", "group": "说书男声"},
    {"id": "Chinese (Mandarin)_Radio_Host", "label": "电台男主播", "group": "说书男声"},
    {"id": "Chinese (Mandarin)_Gentleman", "label": "温润男声", "group": "说书男声"},
    {"id": "Chinese (Mandarin)_Lyrical_Voice", "label": "抒情男声", "group": "说书男声"},
    {"id": "male-qn-jingying", "label": "精英青年", "group": "说书男声"},
    {"id": "male-qn-qingse", "label": "青涩青年", "group": "说书男声"},
    {"id": "male-qn-badao", "label": "霸道青年", "group": "说书男声"},
    {"id": "male-qn-daxuesheng", "label": "青年大学生", "group": "说书男声"},
    {"id": "Chinese (Mandarin)_Warm_Girl", "label": "温暖少女（绘本推荐）", "group": "女声"},
    {"id": "Chinese (Mandarin)_Sweet_Lady", "label": "甜美女声", "group": "女声"},
    {"id": "Chinese (Mandarin)_Gentle_Senior", "label": "温柔学姐", "group": "女声"},
    {"id": "female-yujie", "label": "御姐", "group": "女声"},
    {"id": "female-tianmei", "label": "甜美", "group": "女声"},
    {"id": "female-shaonv", "label": "少女", "group": "女声"},
]


def _looks_like_api_key(value: str) -> bool:
    """Reject error messages / Chinese pasted into the key field."""
    v = value.strip()
    if not v or not v.isascii():
        return False
    if any(bad in v.lower() for bad in ("error", "失败", "invalid", "{", "}", " ")):
        return False
    # MiniMax JWT keys are long; other vendors ~20–200
    if len(v) < 16 or len(v) > 4096:
        return False
    # Common vendor prefixes + MiniMax JWT (eyJ...)
    if v.startswith(("sk-", "key-", "api-", "tok-", "eyJ", "r8_", "cats-")):
        return True
    if v.count(".") >= 2 and len(v) > 40:
        return True
    return v.replace("-", "").replace("_", "").isalnum()


class RuntimeConfigStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._config = self._load()

    def _file_mtime(self) -> float | None:
        try:
            return CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None
        except OSError:
            return None

    def _load(self) -> RuntimeConfig:
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self._mtime = self._file_mtime()
                return RuntimeConfig.model_validate(data)
            except Exception:  # noqa: BLE001
                pass
        self._mtime = self._file_mtime()
        return RuntimeConfig()

    def _save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            self._config.model_dump_json(indent=2),
            encoding="utf-8",
        )
        self._mtime = self._file_mtime()

    def _reload_if_stale(self) -> None:
        """Pick up edits written by other processes / scripts."""
        current = self._file_mtime()
        if current is not None and current != self._mtime:
            self._config = self._load()

    def get(self) -> RuntimeConfig:
        with self._lock:
            self._reload_if_stale()
            return self._config.model_copy(deep=True)

    def update(self, patch: dict[str, Any]) -> RuntimeConfig:
        with self._lock:
            self._reload_if_stale()
            data = self._config.model_dump()
            for k, v in patch.items():
                if k in data and v is not None:
                    # Keep existing key if UI sends masked placeholder
                    if (k.endswith("_api_key") or k.endswith("_api_token") or k == "replicate_api_token") and isinstance(v, str):
                        cleaned = v.strip()
                        if not cleaned or cleaned.startswith("••••"):
                            continue
                        if not _looks_like_api_key(cleaned):
                            raise ValueError(
                                f"{k} 无效：请粘贴平台 API Key（sk- / cats- / r8_ / eyJ…），"
                                "不要把报错信息粘贴到 Key 栏"
                            )
                        data[k] = cleaned
                        continue
                    data[k] = v
            # Apply preset defaults when switching preset and fields empty
            data = self._apply_preset_defaults(data)
            self._config = RuntimeConfig.model_validate(data)
            self._save()
            return self._config.model_copy(deep=True)

    def _apply_preset_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        tp = data.get("text_preset", "mock")
        if tp in TEXT_PRESETS and tp != "custom":
            preset = TEXT_PRESETS[tp]
            if not data.get("text_base_url"):
                data["text_base_url"] = preset["base_url"]
            if not data.get("text_model"):
                data["text_model"] = preset["model"]
        elif tp == "custom":
            if not data.get("text_base_url"):
                data["text_base_url"] = TEXT_PRESETS["custom"]["base_url"]
            if not data.get("text_model"):
                data["text_model"] = TEXT_PRESETS["custom"]["model"]

        ip = data.get("image_preset", "minimax")
        if ip in IMAGE_PRESETS and ip != "custom":
            preset = IMAGE_PRESETS[ip]
            if ip in ("minimax", "flux") or not data.get("image_base_url"):
                data["image_base_url"] = preset["base_url"] or data.get("image_base_url", "")
            if ip in ("minimax", "flux") or not data.get("image_model"):
                data["image_model"] = preset["model"] or data.get("image_model", "")

        tp_tts = data.get("tts_preset", "minimax")
        if tp_tts in TTS_PRESETS and tp_tts == "minimax":
            preset = TTS_PRESETS["minimax"]
            data["tts_base_url"] = preset["base_url"]
            data["tts_model"] = preset["model"]
            voice = (data.get("tts_voice") or "").strip()
            if not voice or voice.startswith("zh-CN-") or "Neural" in voice:
                data["tts_voice"] = "Chinese (Mandarin)_Warm_Girl"
            book_voice = (data.get("book_tts_voice") or "").strip()
            if not book_voice or book_voice.startswith("zh-CN-") or "Neural" in book_voice:
                data["book_tts_voice"] = "Chinese (Mandarin)_Male_Announcer"

        return data

    def public_view(self) -> dict[str, Any]:
        """Safe for frontend — mask secrets."""
        c = self.get()
        data = c.model_dump()
        for key in (
            "text_api_key",
            "image_api_key",
            "tts_api_key",
            "minimax_api_key",
            "replicate_api_token",
            "toapis_api_key",
        ):
            val = data.get(key) or ""
            if val:
                data[key] = "••••" + val[-4:] if len(val) >= 4 else "••••"
                data[f"{key}_set"] = True
            else:
                data[key] = ""
                data[f"{key}_set"] = False
        data["presets"] = {
            "text": TEXT_PRESETS,
            "image": IMAGE_PRESETS,
            "tts": TTS_PRESETS,
        }
        data["minimax_voices"] = MINIMAX_VOICES
        return data


runtime_config = RuntimeConfigStore()
