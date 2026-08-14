from __future__ import annotations

"""Soft procedural BGM (no external API key)."""

import math
import random
import struct
import wave

from app.config import get_settings
from app.models.schemas import AssetRef, BGMResult
from app.providers.base import BGMRequest
from app.providers.media_utils import asset_url, new_asset_id, project_dir

# Children's lullaby motifs (Hz)
MOTIFS = {
    "warm": [392.00, 440.00, 493.88, 523.25, 493.88, 440.00, 392.00, 349.23],
    "calm": [261.63, 293.66, 329.63, 349.23, 329.63, 293.66, 261.63, 246.94],
    "playful": [523.25, 587.33, 659.25, 698.46, 659.25, 587.33, 523.25, 440.00],
    "adventure": [329.63, 392.00, 440.00, 493.88, 523.25, 493.88, 440.00, 392.00],
    "inspiring": [349.23, 392.00, 440.00, 523.25, 493.88, 440.00, 392.00, 349.23],
    "reflective": [246.94, 261.63, 293.66, 329.63, 293.66, 261.63, 246.94, 220.00],
}

# Melancholic minor piano motif (A minor-ish), slow
MELANCHOLIC_PIANO = [
    220.00,  # A3
    261.63,  # C4
    293.66,  # D4
    329.63,  # E4
    293.66,
    261.63,
    246.94,  # B3
    220.00,
    196.00,  # G3
    220.00,
    261.63,
    246.94,
]


def _clamp16(x: float) -> int:
    return max(-32767, min(32767, int(x)))


def _write_lullaby_wav(
    path,
    *,
    duration_sec: float,
    mood: str,
    sample_rate: int = 22050,
    volume: float = 0.11,
) -> float:
    duration_sec = max(8.0, duration_sec)
    motif = MOTIFS.get(mood, MOTIFS["warm"])
    note_len = 0.55
    n_frames = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            t = i / sample_rate
            note_idx = int(t / note_len) % len(motif)
            freq = motif[note_idx]
            local = t % note_len
            env_note = min(1.0, local * 8) * min(1.0, (note_len - local) * 6)
            env_global = min(1.0, t * 2) * min(1.0, (duration_sec - t) * 1.5)
            harm = 0.35 * math.sin(2 * math.pi * freq * 1.5 * t)
            sample = (
                volume
                * env_note
                * env_global
                * 32767
                * (math.sin(2 * math.pi * freq * t) + harm)
            )
            frames.extend(struct.pack("<h", _clamp16(sample)))
        wf.writeframes(frames)
    return duration_sec


def _write_melancholic_piano_rain(
    path,
    *,
    duration_sec: float,
    sample_rate: int = 22050,
) -> float:
    """Melancholic piano with soft rain bed — for 视频号说书."""
    duration_sec = max(12.0, duration_sec)
    note_len = 1.15
    n_frames = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    # Precompute sparse raindrop clicks
    drops: list[tuple[int, float]] = []
    t = 0.05
    while t < duration_sec:
        drops.append((int(t * sample_rate), 0.012 + rng.random() * 0.018))
        t += 0.04 + rng.random() * 0.12
    drop_i = 0

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            t = i / sample_rate
            # --- piano ---
            note_idx = int(t / note_len) % len(MELANCHOLIC_PIANO)
            freq = MELANCHOLIC_PIANO[note_idx]
            local = t % note_len
            # soft hammer: fast attack, long decay
            env = math.exp(-local * 2.4) * min(1.0, local * 40)
            # slight detune + soft upper partials for "piano-ish"
            tone = (
                0.72 * math.sin(2 * math.pi * freq * t)
                + 0.18 * math.sin(2 * math.pi * freq * 2.002 * t)
                + 0.08 * math.sin(2 * math.pi * freq * 3.01 * t)
                + 0.04 * math.sin(2 * math.pi * freq * 0.5 * t)
            )
            # pedal drone (very quiet fifth below)
            drone = 0.06 * math.sin(2 * math.pi * (freq * 0.5) * t) * (0.4 + 0.6 * env)
            piano = 0.13 * (tone * env + drone)

            # --- rain bed: filtered noise ---
            noise = (rng.random() * 2 - 1) * 0.028
            # soft high-shelf feel via differencing previous would need state;
            # approximate with quieter broadband hiss
            rain = noise

            # --- sparse drops ---
            while drop_i < len(drops) and drops[drop_i][0] < i:
                drop_i += 1
            drop = 0.0
            if drop_i < len(drops):
                di, amp = drops[drop_i]
                age = (i - di) / sample_rate
                if 0 <= age < 0.03:
                    drop = amp * math.exp(-age * 90) * (rng.random() * 2 - 1)

            env_global = min(1.0, t * 1.2) * min(1.0, (duration_sec - t) * 1.2)
            sample = (piano + rain + drop) * env_global * 32767
            frames.extend(struct.pack("<h", _clamp16(sample)))
        wf.writeframes(frames)
    return duration_sec


def _is_melancholic_rain(mood: str) -> bool:
    m = (mood or "").strip().lower().replace("-", " ").replace("_", " ")
    if "melancholic" in m and "piano" in m:
        return True
    if m in ("melancholic piano with rain", "piano rain", "rain piano"):
        return True
    return False


def _is_attractive_pulse(mood: str) -> bool:
    m = (mood or "").strip().lower().replace("-", " ").replace("_", " ")
    return any(
        k in m
        for k in (
            "attractive cinematic pulse",
            "cinematic pulse",
            "epic pulse",
            "hook beat",
            "attractive",
        )
    )


def _write_attractive_cinematic_pulse(
    path,
    *,
    duration_sec: float,
    sample_rate: int = 22050,
) -> float:
    """Punchy hook bed for 人生副本 — memorable pulse + rising motif."""
    duration_sec = max(12.0, duration_sec)
    n_frames = int(sample_rate * duration_sec)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Catchy minor-hook motif
    motif = [196.00, 233.08, 261.63, 311.13, 349.23, 311.13, 261.63, 233.08]
    note_len = 0.42
    rng = random.Random(7)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_frames):
            t = i / sample_rate
            note_idx = int(t / note_len) % len(motif)
            freq = motif[note_idx]
            local = t % note_len
            env = min(1.0, local * 25) * math.exp(-local * 3.2)

            lead = (
                0.55 * math.sin(2 * math.pi * freq * t)
                + 0.25 * math.sin(2 * math.pi * freq * 2.0 * t)
                + 0.12 * math.sin(2 * math.pi * freq * 3.0 * t)
            )
            # sidechain-ish pulse on downbeats
            beat = 0.5 + 0.5 * math.sin(2 * math.pi * (2.0 / note_len) * t)
            bass = 0.22 * math.sin(2 * math.pi * (freq * 0.5) * t) * beat
            # light noise riser every 4 notes
            riser = 0.0
            if note_idx % 4 == 3:
                riser = 0.04 * (local / note_len) * (rng.random() * 2 - 1)

            env_global = min(1.0, t * 2.0) * min(1.0, (duration_sec - t) * 1.5)
            sample = 0.16 * (lead * env + bass + riser) * env_global * 32767
            frames.extend(struct.pack("<h", _clamp16(sample)))
        wf.writeframes(frames)
    return duration_sec


class ProceduralBGMProvider:
    name = "procedural"

    async def generate(self, req: BGMRequest) -> BGMResult:
        settings = get_settings()
        asset_id = new_asset_id()
        filename = f"bgm_{asset_id}.wav"
        path = project_dir(settings, getattr(req, "storage_key", None) or req.project_id) / filename
        style = (req.mood or "").strip() or "warm"
        if _is_melancholic_rain(style):
            duration = _write_melancholic_piano_rain(
                path, duration_sec=req.duration_sec + 2.0
            )
            mood_label = "melancholic piano with rain"
        elif _is_attractive_pulse(style):
            duration = _write_attractive_cinematic_pulse(
                path, duration_sec=req.duration_sec + 2.0
            )
            mood_label = "attractive cinematic pulse"
        else:
            duration = _write_lullaby_wav(
                path, duration_sec=req.duration_sec + 2.0, mood=style
            )
            mood_label = style
        asset = AssetRef(
            id=asset_id,
            kind="audio",
            filename=filename,
            mime_type="audio/wav",
            url=asset_url(
                req.project_id,
                asset_id,
                api_prefix=getattr(req, "api_prefix", None) or "/api/projects",
            ),
            meta={
                "path": str(path),
                "mood": mood_label,
                "provider": self.name,
                "style": mood_label,
            },
        )
        return BGMResult(
            asset=asset,
            duration_sec=round(duration, 2),
            mood=mood_label,
            provider=self.name,
        )
