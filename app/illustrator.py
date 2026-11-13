"""ComfyUI illustration provider with IP-Adapter character anchoring.

The first time an episode is rendered with the AI art engine, one portrait
reference is generated per character. Every shot then uses the matching
reference through IP-Adapter. If ComfyUI is down, the caller falls back to the
built-in panel engine instead of failing the episode.
"""
from __future__ import annotations

import hashlib
import io
import re
import time
from pathlib import Path

from PIL import Image, ImageOps

from . import art, comfy
from .config import load_config, save_config

ROOT = Path(__file__).resolve().parent.parent

STYLE_PROMPTS = {
    "neo_noir": (
        "cinematic Chinese manhua noir illustration, rain-soaked neon megacity, "
        "teal and crimson palette, strong rim light, deep shadows, graphic novel ink texture, "
        "dramatic film still, high contrast, highly detailed, vertical 9:16 composition"
    ),
    "dusk_anime": (
        "cinematic anime key visual, warm dusk palette, orange and violet sky, soft rim light, "
        "detailed urban background, emotional atmosphere, high quality anime film still, vertical 9:16"
    ),
    "ink_wuxia": (
        "Chinese ink wash manhua illustration, sumi-e brush texture, cinnabar red accents, "
        "misty mountains, cinematic wuxia atmosphere, elegant negative space, vertical 9:16"
    ),
    "warm_slice": (
        "warm cinematic anime still, cozy urban night, amber and coral palette, soft focus, "
        "nostalgic emotional atmosphere, detailed background, film still, vertical 9:16"
    ),
    "cyber_pop": (
        "bold cyberpunk pop art anime illustration, saturated magenta and cyan, halftone texture, "
        "dynamic graphic composition, neon glow, high energy, vertical 9:16"
    ),
}

SCENE_PROMPTS = {
    "rooftop": "rainy rooftop at night, wet concrete, neon city skyline, full moon, cables and puddles, cinematic atmosphere",
    "alley": "narrow neon alley at night, wet pavement, glowing signs, cables, steam, deep perspective",
    "lab": "futuristic memory repair laboratory, circular glowing memory core, server racks, holographic displays, teal light",
    "lab_door": "laboratory doorway backlit by red light, long shadows, cinematic threshold",
    "memory": "overexposed white hospital corridor, red emergency light, long perspective, dreamlike memory, film grain",
    "apartment": "small apartment at night, rain on window, city bokeh, warm lamp, lived-in details",
    "void": "abstract memory void, floating glass shards, concentric rings, particles, dark space",
    "chip": "macro shot of a glowing cyberpunk memory chip, circuitry, red countdown, rain droplets, shallow depth of field",
    "prop": "macro shot of a mysterious cyberpunk object on wet metal, glowing edges, shallow depth of field",
    "close": "extreme close-up portrait, rain and neon reflections, cinematic eye highlight",
}

SHOT_PROMPTS = {
    "wide": "wide establishing shot, full environment visible, strong sense of scale",
    "medium": "medium shot, waist-up composition, cinematic framing",
    "close": "extreme close-up, face and eyes, shallow depth of field",
    "detail": "macro detail shot, object in sharp focus, cinematic bokeh",
}

POSE_PROMPTS = {
    "stand": "standing still, three-quarter view, natural pose",
    "stand_back": "seen from behind, looking out at the city, quiet posture",
    "run": "running, motion, dynamic pose",
    "reach": "reaching out toward the camera, hand in foreground",
    "sit": "seated, leaning forward, thoughtful",
    "closeup": "close-up face, intense expression",
    "static": "no people in frame",
}

SKIP_REFERENCE_IDS = {"bainao", "白噪"}


def _safe(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fa5]", "", str(value))
    return value[:40] or hashlib.sha1(str(value).encode()).hexdigest()[:8]


def _seed(project: dict, shot: dict, suffix: str = "") -> int:
    raw = f"{project.get('id')}|{shot.get('id')}|{suffix}"
    return int(hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8], 16)


def find_character(project: dict, name: str) -> dict | None:
    for char in project.get("characters", []):
        if char.get("id") == name or char.get("name") == name:
            return char
    return None


def _character_en(char: dict) -> str:
    return str(char.get("appearance_en") or char.get("appearance") or char.get("persona") or "").strip()


def build_shot_prompt(project: dict, shot: dict) -> str:
    style = project.get("style", "neo_noir")
    parts = [STYLE_PROMPTS.get(style, STYLE_PROMPTS["neo_noir"])]
    scene = art.SCENE_ALIASES.get(shot.get("scene"), shot.get("scene", "rooftop"))
    parts.append(SCENE_PROMPTS.get(scene, scene))
    shot_type = SHOT_PROMPTS.get(shot.get("shot_type", "medium"), SHOT_PROMPTS["medium"])
    parts.append(shot_type)
    parts.append(POSE_PROMPTS.get(shot.get("pose", "stand"), POSE_PROMPTS["stand"]))
    chars = [find_character(project, name) for name in shot.get("characters", [])]
    descriptions = []
    for char in chars:
        if not char:
            continue
        descriptions.append(f"{char.get('name')}: {_character_en(char)}")
    if descriptions:
        parts.append("characters in frame — " + "; ".join(descriptions))
        parts.append("keep the exact same face, hairstyle and outfit as the reference portrait")
    location = str(shot.get("location") or "").strip()
    when = str(shot.get("time") or "").strip()
    if location or when:
        parts.append(f"scene context: {location} {when}")
    extra = str(shot.get("image_prompt") or "").strip()
    if extra:
        parts.append(extra)
    parts.append("no text, no letters, no speech bubbles, no watermark, no logo, no subtitles, clean illustration")
    return ", ".join(p for p in parts if p)


def _reference_prompt(project: dict, char: dict) -> str:
    style = project.get("style", "neo_noir")
    base = STYLE_PROMPTS.get(style, STYLE_PROMPTS["neo_noir"])
    return (
        f"{base}, character design portrait of {char.get('name')}, {_character_en(char)}, "
        "upper body, facing camera, neutral expression, plain dark studio background, soft rim light, "
        "clear face, consistent character reference, no text, no watermark"
    )


def _image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _fit_vertical(img: Image.Image, width=1080, height=1920) -> Image.Image:
    return ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.44))


def _make_group_reference(paths: list[Path], out: Path) -> Path:
    images = []
    for path in paths:
        try:
            im = Image.open(path).convert("RGB")
            im.thumbnail((512, 768), Image.Resampling.LANCZOS)
            images.append(im)
        except Exception:
            continue
    if not images:
        raise RuntimeError("没有可用的角色参考图")
    gap = 24
    w = sum(im.width for im in images) + gap * (len(images) - 1)
    h = max(im.height for im in images)
    canvas = Image.new("RGB", (max(w, 512), h), (12, 13, 17))
    x = (canvas.width - w) // 2
    for im in images:
        canvas.paste(im, (x, (h - im.height) // 2))
        x += im.width + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=94)
    return out


def _check_ready(client: comfy.ComfyClient, cfg: dict) -> dict:
    info = client.test_connection(quick=False)
    if not info.get("ipadapter_ready"):
        raise comfy.ComfyError(
            "ComfyUI 缺少 IPAdapter 节点。请安装 ComfyUI_IPAdapter_plus，"
            "或在设置里切回「内置剪影」。"
        )
    checkpoint = cfg.get("checkpoint") or (info.get("checkpoints") or [""])[0]
    if not checkpoint:
        raise comfy.ComfyError("ComfyUI 没有可用 checkpoint，请先在设置里选择模型。")
    if not cfg.get("checkpoint"):
        cfg = {**cfg, "checkpoint": checkpoint}
        try:
            save_config({"art": {"checkpoint": checkpoint}})
        except Exception:
            pass
    info["checkpoint"] = checkpoint
    return info


def _set_ref(project: dict, char: dict, path: Path) -> None:
    try:
        rel = path.relative_to(ROOT / "data" / "projects" / project["id"])
        char["ref_image"] = str(rel).replace("\\", "/")
    except Exception:
        char["ref_image"] = path.name


def generate_episode_art(project: dict, episode: dict, art_dir: Path, on_progress=None) -> dict:
    """Generate refs + all shots. Raises ComfyError before touching art if setup fails."""
    cfg = load_config().get("art", {})
    client = comfy.ComfyClient(cfg.get("comfyui_url", "http://127.0.0.1:8188"), cfg.get("timeout", 240))
    info = _check_ready(client, cfg)
    cfg = {**cfg, "checkpoint": info["checkpoint"]}
    refs_dir = ROOT / "data" / "projects" / project["id"] / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    t0 = time.time()

    # character anchors ----------------------------------------------------
    needed = []
    for shot in episode.get("shots", []):
        for name in shot.get("characters", []):
            char = find_character(project, name)
            if char and char not in needed:
                needed.append(char)
    refs: dict[str, Path] = {}
    for i, char in enumerate(needed):
        if str(char.get("id")) in SKIP_REFERENCE_IDS or "no physical body" in _character_en(char).lower():
            continue
        path = refs_dir / f"{_safe(char.get('id') or char.get('name'))}.png"
        if path.exists() and path.stat().st_size > 1000:
            refs[char.get("name", "")] = path
            continue
        if on_progress:
            on_progress(0.03 + (i / max(1, len(needed))) * 0.13, f"生成角色参考 · {char.get('name')}")
        prompt = _reference_prompt(project, char)
        seed = _seed(project, {"id": f"ref-{char.get('id')}"}, "ref")
        wf = comfy.txt2img_workflow(
            cfg,
            prompt,
            cfg.get("negative", ""),
            seed,
            int(cfg.get("ref_width", 512)),
            int(cfg.get("ref_height", 768)),
        )
        try:
            data = client.generate(wf)
            path.write_bytes(data)
            _set_ref(project, char, path)
            refs[char.get("name", "")] = path
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{char.get('name')} 参考图失败：{exc}")

    # shots -----------------------------------------------------------------
    uploaded: dict[str, str] = {}
    group_cache: dict[tuple, Path] = {}
    shots = episode.get("shots", [])
    for i, shot in enumerate(shots):
        name = f"AI 插画 {i + 1}/{len(shots)}"
        if on_progress:
            on_progress(0.18 + (i / max(1, len(shots))) * 0.78, f"{name} · {shot.get('location', '')}")
        ref_path = None
        chars = [find_character(project, n) for n in shot.get("characters", [])]
        chars = [c for c in chars if c and c.get("name") in refs]
        if len(chars) >= 2:
            key = tuple(sorted(c["name"] for c in chars[:2]))
            if key not in group_cache:
                group_file = refs_dir / ("group_" + "_".join(_safe(k) for k in key) + ".png")
                group_cache[key] = _make_group_reference([refs[k] for k in key], group_file)
            ref_path = group_cache[key]
        elif len(chars) == 1:
            ref_path = refs[chars[0]["name"]]

        prompt = build_shot_prompt(project, shot)
        negative = cfg.get("negative", "")
        seed = _seed(project, shot, cfg.get("checkpoint", ""))
        try:
            if ref_path is not None:
                if str(ref_path) not in uploaded:
                    uploaded[str(ref_path)] = client.upload_image(ref_path)
                shot_weight = float(cfg.get("ipadapter_weight", 0.62))
                shot_type = shot.get("shot_type", "medium")
                if shot_type == "wide":
                    shot_weight *= 0.52
                elif shot_type == "close":
                    shot_weight = min(0.85, shot_weight * 1.08)
                if len(chars) >= 2:
                    shot_weight *= 0.82
                wf = comfy.ipadapter_workflow(
                    cfg,
                    prompt,
                    negative,
                    seed,
                    int(cfg.get("width", 512)),
                    int(cfg.get("height", 896)),
                    uploaded[str(ref_path)],
                    weight=round(shot_weight, 3),
                )
            else:
                wf = comfy.txt2img_workflow(
                    cfg,
                    prompt,
                    negative,
                    seed,
                    int(cfg.get("width", 512)),
                    int(cfg.get("height", 896)),
                )
            data = client.generate(wf)
            img = _fit_vertical(_image_from_bytes(data))
            out = art_dir / f"shot_{shot['index']:02d}.jpg"
            img.save(out, quality=94, subsampling=1)
            shot["ai_art"] = True
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"第 {shot['index']} 镜 AI 插画失败：{exc}")
            if not cfg.get("fallback", True):
                raise
            art.render_panel(project, episode, shot, art_dir / f"shot_{shot['index']:02d}.jpg", width=1080)
            shot["ai_art"] = False

    elapsed = round(time.time() - t0, 1)
    return {
        "engine": "comfyui",
        "reference_count": len(refs),
        "warnings": warnings,
        "elapsed": elapsed,
        "checkpoint": cfg.get("checkpoint"),
    }
