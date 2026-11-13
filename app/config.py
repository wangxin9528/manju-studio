"""Persistent local configuration. Everything defaults to a zero-key setup."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import Lock

DATA_DIR = Path(os.environ.get("MANJU_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
_LOCK = Lock()

DEFAULT_CONFIG = {
    "llm": {
        "enabled": False,
        "provider": "ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "",
        "model": "qwen2.5:3b",
        "timeout": 90,
    },
    "tts": {
        "engine": "edge",
        "fallback_local": True,
        "narrator_voice": "zh-CN-YunyangNeural",
        "local_voice": "Tingting",
    },
    "art": {
        "engine": "builtin",
        "comfyui_url": "http://127.0.0.1:8188",
        "checkpoint": "",
        "preset": "PLUS (high strength)",
        "width": 512,
        "height": 896,
        "ref_width": 512,
        "ref_height": 768,
        "steps": 24,
        "cfg": 7.0,
        "sampler": "euler_ancestral",
        "scheduler": "normal",
        "ipadapter_weight": 0.62,
        "ipadapter_weight_type": "prompt is more important",
        "timeout": 240,
        "fallback": True,
        "negative": "text, watermark, logo, speech bubble, letters, signature, lowres, worst quality, bad anatomy, extra fingers, deformed hands, duplicate character, cropped face",
    },
    "video": {
        "fps": 24,
        "resolution": "720p",
    },
}


def _merge(default, override):
    out = deepcopy(default)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        return _merge(DEFAULT_CONFIG, json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        return deepcopy(DEFAULT_CONFIG)


def save_config(patch: dict) -> dict:
    with _LOCK:
        cfg = _merge(load_config(), patch)
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return cfg


def public_config() -> dict:
    cfg = load_config()
    out = deepcopy(cfg)
    key = out.get("llm", {}).get("api_key", "")
    out["llm"]["api_key"] = ("•" * 8 + key[-4:]) if key else ""
    out["llm"]["has_key"] = bool(key)
    return out
