"""Voice generation: free Edge TTS by default, macOS `say` as the offline fallback."""
from __future__ import annotations

import asyncio
import hashlib
import subprocess
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from .config import load_config

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "tts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

EMOTION = {
    "冷淡": ("-8%", "-3Hz"),
    "冷静": ("-5%", "-2Hz"),
    "低沉": ("-12%", "-7Hz"),
    "轻快": ("+8%", "+5Hz"),
    "失真": ("+2%", "+14Hz"),
    "颤抖": ("+12%", "+7Hz"),
    "动摇": ("+2%", "+1Hz"),
    "克制": ("-6%", "-2Hz"),
    "决绝": ("-2%", "-1Hz"),
    "逼近": ("-4%", "-4Hz"),
    "低语": ("-14%", "-8Hz"),
    "neutral": ("+0%", "+0Hz"),
}

LOCAL_VOICE_FALLBACK = "Tingting"


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _to_wav(src: Path, dst: Path, pitch_hz: float = 0.0) -> None:
    cmd = [ffmpeg_exe(), "-y", "-v", "error", "-i", str(src)]
    if abs(pitch_hz) > 0.5:
        # Resample first so the pitch ratio is relative to a known 48k stream.
        ratio = 2 ** (pitch_hz / 12.0)
        cmd += ["-af", f"aresample=48000,asetrate=48000*{ratio:.5f},aresample=48000,atempo={1/ratio:.5f}"]
    cmd += ["-ac", "1", "-ar", "48000", "-sample_fmt", "s16", str(dst)]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] or "ffmpeg conversion failed")


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / float(f.getframerate())


def _cache_key(text: str, voice: str, rate: str, pitch: str, engine: str, male: bool) -> str:
    raw = f"{engine}|{voice}|{rate}|{pitch}|{male}|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def _local_synthesize(text: str, out_wav: Path, male: bool) -> None:
    raw = CACHE_DIR / f"{out_wav.stem}.aiff"
    voice = LOCAL_VOICE_FALLBACK
    cmd = ["say", "-v", voice, "-r", "172" if not male else "160", "-o", str(raw), text]
    result = _run(cmd)
    if result.returncode != 0 or not raw.exists():
        raise RuntimeError(f"macOS say failed: {result.stderr[-300:]}")
    _to_wav(raw, out_wav, pitch_hz=-3.2 if male else 0.0)
    try:
        raw.unlink()
    except OSError:
        pass


async def _edge_save(text: str, voice: str, rate: str, pitch: str, mp3: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(mp3))


def synthesize(
    text: str,
    voice: str,
    emotion: str = "neutral",
    *,
    male: bool = False,
    engine: str | None = None,
) -> tuple[Path, float]:
    """Return (wav_path, seconds). Tries Edge TTS then local macOS speech."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    cfg = load_config()
    engine = engine or cfg["tts"].get("engine", "edge")
    rate, pitch = EMOTION.get(emotion, EMOTION["neutral"])
    key = _cache_key(text, voice, rate, pitch, engine, male)
    wav = CACHE_DIR / f"{key}.wav"
    if wav.exists():
        return wav, _duration(wav)

    errors = []
    if engine == "edge":
        mp3 = CACHE_DIR / f"{key}.mp3"
        try:
            asyncio.run(_edge_save(text, voice, rate, pitch, mp3))
            _to_wav(mp3, wav)
            if wav.exists() and _duration(wav) > 0.2:
                try:
                    mp3.unlink()
                except OSError:
                    pass
                return wav, _duration(wav)
            errors.append("edge returned an empty clip")
        except Exception as exc:  # noqa: BLE001 - fall back to local voice
            errors.append(f"edge: {exc}")
            try:
                mp3.unlink()
            except OSError:
                pass

    if cfg["tts"].get("fallback_local", True):
        try:
            _local_synthesize(text, wav, male)
            if wav.exists() and _duration(wav) > 0.2:
                return wav, _duration(wav)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"local: {exc}")

    raise RuntimeError("配音失败：" + " | ".join(errors))


def choose_voice(project: dict, speaker: str, cfg: dict | None = None) -> tuple[str, bool]:
    cfg = cfg or load_config()
    if speaker in ("", "旁白", "VO", "画外"):
        return cfg["tts"].get("narrator_voice", "zh-CN-YunyangNeural"), True
    for char in project.get("characters", []):
        if char.get("name") == speaker or char.get("id") == speaker:
            voice = char.get("voice") or cfg["tts"].get("narrator_voice", "zh-CN-YunyangNeural")
            male = any(token in voice for token in ("Yunjian", "Yunyang", "Yunfeng", "male"))
            return voice, male
    return cfg["tts"].get("narrator_voice", "zh-CN-YunyangNeural"), True
