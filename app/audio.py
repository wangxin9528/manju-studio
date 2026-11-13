"""Timeline, free procedural score / sound design, and final audio mix."""
from __future__ import annotations

import json
import math
import wave
from pathlib import Path

import numpy as np

from . import tts
from .config import load_config

SR = 48000


# ---------------------------------------------------------------------------
# Timeline


def build_timeline(project: dict, episode: dict, episode_dir: Path, progress=None) -> dict:
    cfg = load_config()
    voice_dir = episode_dir / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    cursor = 0.35
    cues: list[dict] = []
    for shot in episode["shots"]:
        shot_start = cursor
        local = 0.30
        shot_cues = []

        narration = (shot.get("narration") or "").strip()
        if narration:
            speaker = shot.get("narration_speaker", "旁白")
            voice, male = tts.choose_voice(project, speaker, cfg)
            out = voice_dir / f"s{shot['index']:02d}_n.wav"
            try:
                audio, length = tts.synthesize(narration, voice, "冷淡", male=male)
                if audio != out:
                    out.write_bytes(audio.read_bytes())
            except Exception as exc:  # noqa: BLE001
                print("TTS narration failed:", exc)
                length = max(1.2, len(narration) * 0.22)
                _write_silence(out, length)
            cue = {
                "kind": "narration",
                "speaker": speaker,
                "text": narration,
                "shot": shot["index"],
                "start": round(shot_start + local, 3),
                "end": round(shot_start + local + length, 3),
                "audio": out.name,
            }
            shot_cues.append(cue)
            local += length + 0.26

        for i, dialogue in enumerate(shot.get("dialogues", [])):
            text = (dialogue.get("text") or "").strip()
            if not text:
                continue
            speaker = dialogue.get("speaker", "")
            voice, male = tts.choose_voice(project, speaker, cfg)
            out = voice_dir / f"s{shot['index']:02d}_d{i + 1}.wav"
            try:
                audio, length = tts.synthesize(text, voice, dialogue.get("emotion", "neutral"), male=male)
                if audio != out:
                    out.write_bytes(audio.read_bytes())
            except Exception as exc:  # noqa: BLE001
                print("TTS dialogue failed:", exc)
                length = max(1.0, len(text) * 0.22)
                _write_silence(out, length)
            cue = {
                "kind": "dialogue",
                "speaker": speaker,
                "text": text,
                "shot": shot["index"],
                "start": round(shot_start + local, 3),
                "end": round(shot_start + local + length, 3),
                "audio": out.name,
            }
            shot_cues.append(cue)
            local += length + 0.22

        duration = max(3.1, min(11.0, local + 0.55))
        for cue in shot_cues:
            cue["shot_start"] = round(shot_start, 3)
            cue["shot_end"] = round(shot_start + duration, 3)
            cues.append(cue)
        shots.append(
            {
                "index": shot["index"],
                "start": round(shot_start, 3),
                "end": round(shot_start + duration, 3),
                "duration": round(duration, 3),
                "cues": shot_cues,
            }
        )
        cursor += duration
        if progress:
            progress(shot["index"], len(episode["shots"]), cursor)

    outro = 2.6
    timeline = {
        "duration": round(cursor + outro, 3),
        "speech_end": round(cursor, 3),
        "outro": outro,
        "shots": shots,
        "cues": cues,
    }
    (episode_dir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return timeline


def _write_silence(path: Path, seconds: float) -> None:
    n = int(max(0.2, seconds) * SR)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(b"\x00\x00" * n)


# ---------------------------------------------------------------------------
# Music and sound design


def _note(freq: float, dur: float, kind="pad", fade=0.02) -> np.ndarray:
    n = max(1, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    if kind == "pad":
        sig = (
            np.sin(2 * np.pi * freq * t)
            + 0.36 * np.sin(2 * np.pi * freq * 2.002 * t)
            + 0.16 * np.sin(2 * np.pi * freq * 0.501 * t)
            + 0.08 * np.sin(2 * np.pi * freq * 3.01 * t)
        )
        env = np.sin(np.pi * np.clip(t / max(dur, 0.01), 0, 1)) ** 0.7
        sig *= env * 0.18
    elif kind == "pluck":
        sig = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
        sig *= np.exp(-t * 5.5) * 0.16
    elif kind == "bass":
        sig = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(4 * np.pi * freq * t)
        sig *= np.exp(-t * 1.6) * 0.28
    else:
        sig = np.sin(2 * np.pi * freq * t) * 0.1
    if fade and kind != "pad":
        a = min(n, int(fade * SR))
        if a:
            sig[:a] *= np.linspace(0, 1, a)
            sig[-a:] *= np.linspace(1, 0, a)
    return sig.astype(np.float32)


def _add(buf: np.ndarray, sig: np.ndarray, at: float, gain=1.0, pan=0.0):
    start = max(0, int(at * SR))
    end = min(buf.shape[0], start + sig.shape[0])
    if end <= start:
        return
    chunk = sig[: end - start] * gain
    left = math.sqrt((1 - max(-0.9, min(0.9, pan))) / 2)
    right = math.sqrt((1 + max(-0.9, min(0.9, pan))) / 2)
    buf[start:end, 0] += chunk * left
    buf[start:end, 1] += chunk * right


def _kick(dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 95 * np.exp(-t * 18) + 38
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    return (sig * 0.5).astype(np.float32)


def _noise(dur, color="white", rng=None):
    rng = rng or np.random.default_rng(2)
    n = int(dur * SR)
    x = rng.normal(0, 1, n).astype(np.float32)
    if color == "pink":
        # cheap pink-ish filtering
        b = np.cumsum(x)
        b -= np.convolve(b, np.ones(64) / 64, mode="same")
        x = b / (np.max(np.abs(b)) + 1e-6)
    return x


def _rain(seconds, rng, intensity=0.5):
    n = int(seconds * SR)
    x = rng.normal(0, 1, n).astype(np.float32)
    # high-pass by subtracting a slow moving average
    kernel = np.ones(48) / 48
    low = np.convolve(x, kernel, mode="same")
    x = x - low
    mod = 0.75 + 0.25 * np.sin(np.linspace(0, 18, n))
    return (x * mod * 0.10 * intensity).astype(np.float32)


def _heartbeat(dur=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n, dtype=np.float32)
    for at, amp in ((0.02, 1.0), (0.22, 0.65)):
        tt = t - at
        env = np.exp(-np.clip(tt, 0, None) * 18) * (tt >= 0)
        sig += np.sin(2 * np.pi * 58 * tt) * env * amp
    return sig * 0.35


def _alarm(dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = (np.sin(2 * np.pi * 3.2 * t) > 0).astype(np.float32)
    sig = np.sin(2 * np.pi * 680 * t) * mod * 0.06
    return sig


def _impact(dur=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 22) + 32
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
    crack = np.random.default_rng(4).normal(0, 1, n) * np.exp(-t * 20) * 0.12
    return (boom * 0.55 + crack).astype(np.float32)


def _glitch(dur=0.7, seed=3):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    sig = rng.normal(0, 1, n).astype(np.float32)
    # digital stair-step / sample hold
    hold = rng.integers(1, 9)
    sig = np.repeat(sig[::hold], hold)[:n]
    sig *= (np.sin(np.linspace(0, 40, n)) > -0.2).astype(np.float32)
    return (np.clip(sig, -1, 1) * 0.09).astype(np.float32)


def _siren(dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 440 + 80 * np.sin(2 * np.pi * 0.7 * t)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.035).astype(np.float32)


def make_bgm(total: float, style: str, seed=7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(total * SR)
    buf = np.zeros((n, 2), dtype=np.float32)
    bpm = 72 if style in ("neo_noir", "ink_wuxia") else 84
    beat = 60.0 / bpm
    bar = beat * 4
    # D minor-ish, with a different mode for warm stories
    if style in ("dusk_anime", "warm_slice"):
        roots = [146.83, 174.61, 130.81, 196.00]  # D, F, C, G
        chords = [(0, 3, 7), (3, 7, 10), (0, 3, 7), (4, 7, 11)]
    else:
        roots = [73.42, 58.27, 87.31, 65.41]  # D2, Bb1, F2, C2
        chords = [(0, 3, 7), (0, 4, 7), (0, 4, 7), (0, 4, 7)]
    bars = int(math.ceil(total / bar)) + 1
    for b in range(bars):
        at = b * bar
        root = roots[b % 4]
        chord = chords[b % 4]
        # pad
        for interval in chord:
            f = root * 2 ** (interval / 12) * 2
            _add(buf, _note(f, bar * 1.15, "pad"), at, 0.90, (-0.25 if interval % 2 else 0.25))
        # sub
        _add(buf, _note(root, bar * 0.9, "bass"), at, 0.85)
        # sparse arpeggio
        for step in (0, 1.5, 2.5, 3.25):
            f = root * 4 * 2 ** (chord[int(step) % len(chord)] / 12)
            _add(buf, _note(f, beat * 1.2, "pluck"), at + step * beat, 0.55, 0.15 if step % 2 else -0.15)
        if style not in ("warm_slice", "dusk_anime"):
            _add(buf, _kick(), at + 0 * beat, 0.55)
            _add(buf, _kick(), at + 2.5 * beat, 0.40)
        # brushed hat
        hat = _noise(0.055, rng=rng) * 0.035
        for k in range(8):
            _add(buf, hat, at + k * beat / 2, 0.55 if k % 2 == 0 else 0.3, 0.2)
    # vinyl / air
    air = _noise(total, "pink", rng) * 0.012
    buf[:, 0] += air
    buf[:, 1] += air
    # slow filter / fade
    fade = int(min(2.5, total / 4) * SR)
    if fade > 1:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
        buf[:fade] *= ramp
        buf[-fade:] *= ramp[::-1]
    peak = float(np.max(np.abs(buf))) or 1.0
    return (buf / peak * 0.55).astype(np.float32)


def load_wav_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as f:
        n = f.getnframes()
        data = f.readframes(n)
        sr = f.getframerate()
        channels = f.getnchannels()
        width = f.getsampwidth()
    if width != 2:
        raise ValueError(f"unsupported wav width {width}")
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    if sr != SR:
        # simple linear resample
        t = np.linspace(0, len(arr) / sr, int(len(arr) * SR / sr), endpoint=False)
        arr = np.interp(t, np.arange(len(arr)) / sr, arr).astype(np.float32)
    return arr


def _normalize_voice(x: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(x * x))) or 1e-6
    x = x * min(5.0, 0.105 / rms)
    return np.tanh(x * 1.15) * 0.9


def _smooth_duck(activity: np.ndarray, window=0.4) -> np.ndarray:
    w = max(1, int(window * SR))
    kernel = np.ones(w, dtype=np.float32) / w
    smooth = np.convolve(activity, kernel, mode="same")
    return np.clip(smooth * 4.0, 0, 1)


def build_mix(project: dict, episode: dict, timeline: dict, episode_dir: Path, progress=None) -> Path:
    cfg = load_config()
    total = float(timeline["duration"])
    n = int(total * SR)
    voice = np.zeros(n, dtype=np.float32)
    voice_activity = np.zeros(n, dtype=np.float32)
    sfx = np.zeros((n, 2), dtype=np.float32)
    style = project.get("style", "neo_noir")
    rng = np.random.default_rng(11)

    for cue in timeline["cues"]:
        path = episode_dir / "voice" / cue["audio"]
        if not path.exists():
            continue
        audio = _normalize_voice(load_wav_mono(path))
        start = int(float(cue["start"]) * SR)
        end = min(n, start + len(audio))
        if end > start:
            voice[start:end] += audio[: end - start]
            voice_activity[start:end] = 1.0
        cue["peak"] = round(float(np.max(np.abs(audio))) if len(audio) else 0.0, 3)

    for shot in episode["shots"]:
        info = next((x for x in timeline["shots"] if x["index"] == shot["index"]), None)
        if not info:
            continue
        at = info["start"]
        for effect in shot.get("sfx", []):
            if effect == "rain":
                _add(sfx, _rain(min(4.0, info["duration"] + 1.0), rng), at, 0.55, -0.2)
                _add(sfx, _rain(min(4.0, info["duration"] + 1.0), rng), at + 0.7, 0.28, 0.4)
            elif effect == "heartbeat":
                for k in range(int(info["duration"] / 1.05)):
                    _add(sfx, _heartbeat(), at + 0.35 + k * 1.05, 0.5, 0.0)
            elif effect == "alarm":
                _add(sfx, _alarm(min(2.0, info["duration"])), at + 0.1, 0.7, 0.35)
            elif effect == "glitch":
                _add(sfx, _glitch(min(0.8, info["duration"]), seed=shot["index"]), at + 0.25, 0.6, 0.0)
            elif effect == "impact":
                _add(sfx, _impact(), at + 0.05, 0.7, 0.0)
            elif effect == "spark":
                _add(sfx, _noise(0.18, rng=rng) * np.exp(-np.linspace(0, 8, int(0.18 * SR))), at + 0.4, 0.3, 0.3)
            elif effect == "city":
                _add(sfx, _siren(min(3.0, info["duration"])), at + 0.2, 0.55, 0.4)
            elif effect == "wind":
                _add(sfx, _rain(min(3.0, info["duration"]), rng, 0.5), at, 0.35, -0.1)
            elif effect == "hum":
                t = np.arange(int(min(2.0, info["duration"]) * SR)) / SR
                _add(sfx, (np.sin(2 * np.pi * 58 * t) * 0.04).astype(np.float32), at, 0.7)
        # a soft transition whoosh at every cut
        _add(sfx, _noise(0.45, rng=rng) * np.linspace(0.0, 1.0, int(0.45 * SR)) ** 2, at, 0.035, -0.3)

    bgm = make_bgm(total, style)
    duck = _smooth_duck(voice_activity, 0.45)
    bgm *= (1.0 - 0.62 * duck)[:, None]

    mix = np.zeros((n, 2), dtype=np.float32)
    mix[:, 0] += voice * 0.92
    mix[:, 1] += voice * 0.92
    mix += bgm * 0.60
    mix += sfx * 0.60
    # gentle limiter / fades
    fade = int(0.5 * SR)
    mix[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    mix[-int(1.2 * SR):] *= np.linspace(1, 0, int(1.2 * SR), dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = np.tanh(mix * 1.15) * min(1.0, 0.94 / max(peak, 0.94))
    out = episode_dir / "mix.wav"
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    if progress:
        progress(total)
    return out


def write_srt(timeline: dict, path: Path) -> Path:
    def ts(v):
        ms = int(round(v * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, cue in enumerate(timeline["cues"], 1):
        text = cue["text"]
        if cue["kind"] == "dialogue" and cue.get("speaker"):
            text = f"{cue['speaker']}：{text}"
        lines.extend([str(i), f"{ts(cue['start'])} --> {ts(cue['end'])}", text, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
