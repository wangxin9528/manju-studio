"""Development-only mock ComfyUI server.

It implements just enough of the ComfyUI HTTP API to exercise the MANJU
illustration pipeline without downloading Stable Diffusion models. The images
it returns are graphic placeholders, not real AI art.

    .venv/bin/uvicorn scripts.mock_comfyui:app --port 8188

Then set the art engine to ComfyUI in MANJU settings for an end-to-end test.
"""
from __future__ import annotations

import hashlib
import io
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "data" / "cache" / "mock_comfy"
WORK.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Mock ComfyUI")
_JOBS: dict[str, dict] = {}
_FILES: dict[str, Path] = {}


def _font(size):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", size, index=2)
    except Exception:
        return ImageFont.load_default()


def _make_image(prompt: str, reference: Path | None, width=512, height=896) -> Path:
    h = int(hashlib.sha1(prompt.encode()).hexdigest()[:6], 16)
    a = ((h >> 8) % 100 + 30, (h >> 4) % 90 + 20, (h) % 120 + 40)
    b = (20 + (h % 40), 18 + (h % 24), 30 + (h % 30))
    img = Image.new("RGB", (width, height), b)
    d = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(1, height - 1)
        c = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))
        d.line([(0, y), (width, y)], fill=c)
    if reference and reference.exists():
        try:
            ref = Image.open(reference).convert("RGB")
            ref.thumbnail((width // 2, height // 2))
            img.paste(ref, (width - ref.width - 20, 30))
        except Exception:
            pass
    # simple graphic figure
    d.ellipse((width // 2 - 80, height // 2 - 180, width // 2 + 80, height // 2 - 20), fill=(13, 16, 22))
    d.polygon(
        [(width // 2 - 110, height // 2 + 20), (width // 2 + 110, height // 2 + 20),
         (width // 2 + 150, height - 110), (width // 2 - 150, height - 110)],
        fill=(13, 16, 22),
    )
    d.rectangle((0, height - 70, width, height), fill=(9, 10, 14))
    d.text((24, 22), "MOCK COMFYUI", font=_font(18), fill=(255, 255, 255))
    snippet = prompt.replace("\n", " ")[:64]
    d.text((24, height - 52), snippet, font=_font(13), fill=(180, 240, 230))
    d.text((24, height - 30), f"{width}x{height} · placeholder", font=_font(11), fill=(255, 80, 64))
    out = WORK / f"{uuid.uuid4().hex}.jpg"
    img.save(out, quality=88)
    return out


@app.get("/system_stats")
def system_stats():
    return {"system": {"comfyui_version": "mock-0.0", "python_version": "3.12"}, "devices": []}


@app.get("/object_info/CheckpointLoaderSimple")
def checkpoints():
    return {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["mock_anime.safetensors"]]}}}}


@app.get("/object_info/IPAdapterUnifiedLoader")
def ipa_loader():
    return {"IPAdapterUnifiedLoader": {"input": {"required": {"preset": [["PLUS (high strength)"]]}}}}


@app.get("/object_info/IPAdapter")
def ipa():
    return {"IPAdapter": {"input": {"required": {}}}}


@app.get("/object_info/KSampler")
def sampler():
    return {"KSampler": {"input": {"required": {}}}}


@app.post("/upload/image")
async def upload(image: UploadFile = File(...), type: str = Form("input"), overwrite: str = Form("true")):
    suffix = Path(image.filename or "ref.png").suffix or ".png"
    name = f"upload_{uuid.uuid4().hex[:10]}{suffix}"
    path = WORK / name
    path.write_bytes(await image.read())
    _FILES[name] = path
    return {"name": name, "subfolder": "", "type": "input"}


@app.post("/prompt")
async def prompt(payload: dict):
    prompt_id = uuid.uuid4().hex
    workflow = payload.get("prompt") or {}
    prompt_text = ""
    reference = None
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type")
        inputs = node.get("inputs") or {}
        if cls == "CLIPTextEncode":
            prompt_text = str(inputs.get("text") or "")
        if cls == "LoadImage":
            name = str(inputs.get("image") or "")
            reference = _FILES.get(name)
    width, height = 512, 896
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "EmptyLatentImage":
            width = int(node.get("inputs", {}).get("width") or width)
            height = int(node.get("inputs", {}).get("height") or height)
    path = _make_image(prompt_text, reference, width, height)
    _JOBS[prompt_id] = {"path": path, "created": time.time(), "prompt": prompt_text[:200]}
    return {"prompt_id": prompt_id, "number": 1, "node_errors": {}}


@app.get("/history/{prompt_id}")
def history(prompt_id: str):
    job = _JOBS.get(prompt_id)
    if not job or time.time() - job["created"] < 0.6:
        return {}
    path: Path = job["path"]
    return {
        prompt_id: {
            "prompt": [],
            "outputs": {"10": {"images": [{"filename": path.name, "subfolder": "", "type": "output"}]}},
            "status": {"status_str": "success", "completed": True, "messages": []},
        }
    }


@app.get("/view")
def view(filename: str, subfolder: str = "", type: str = "output"):
    path = WORK / filename
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path)
