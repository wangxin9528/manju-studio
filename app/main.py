"""FastAPI application: local studio API, render jobs and the web console."""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import director, render, store
from .config import load_config, public_config, save_config
from .seed import now_iso

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
VERSION = "0.1.0"

app = FastAPI(title="漫构 MANJU STUDIO", version=VERSION)
app.mount("/media", StaticFiles(directory=str(store.PROJECTS_DIR)), name="media")

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="manju-render")


@app.on_event("startup")
def _startup():
    store.ensure_sample()


def _job_update(job_id: str, **fields):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = now_iso()
        msg = fields.get("message")
        if msg and (not job["log"] or job["log"][-1] != msg):
            job["log"].append(msg)
            job["log"] = job["log"][-24:]


def _run_job(job_id: str, pid: str, ep_index: int, resolution: str):
    try:
        project = store.load_project(pid)
        episode = next((e for e in project.get("episodes", []) if e["index"] == ep_index), None)
        if not episode:
            raise ValueError("找不到这一集")
        _job_update(job_id, status="running", stage="art", progress=1, message="开始制作")
        result = render.render_episode(
            project,
            episode,
            resolution=resolution,
            on_progress=lambda stage, pct, message: _job_update(
                job_id, stage=stage, progress=round(max(1, min(99, pct)), 1), message=message
            ),
        )
        project.setdefault("meta", {})["last_engine"] = "local"
        store.save_project(project)
        base = f"/media/{pid}/ep{ep_index:02d}"
        _job_update(
            job_id,
            status="done",
            stage="done",
            progress=100,
            message="成片已就绪",
            result={
                "video": f"{base}/final.mp4",
                "cover": f"{base}/cover.jpg",
                "srt": f"{base}/subtitles.srt",
                "duration": result["timeline"]["duration"],
            },
        )
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _job_update(job_id, status="failed", message="制作失败", error=str(exc)[-1000:])


def _hydrate_paths(project: dict, pid: str) -> dict:
    for char in project.get("characters", []):
        ref = char.get("ref_image")
        if ref:
            char["ref_url"] = f"/media/{pid}/{ref}"
    for ep in project.get("episodes", []):
        base_fs = store.project_dir(pid) / f"ep{ep['index']:02d}"
        for i, shot in enumerate(ep.get("shots", [])):
            art = base_fs / "art" / f"shot_{shot['index']:02d}.jpg"
            shot["image_url"] = f"/media/{pid}/ep{ep['index']:02d}/art/shot_{shot['index']:02d}.jpg" if art.exists() else None
        video = base_fs / "final.mp4"
        if video.exists() and not ep.get("video"):
            ep["video"] = f"/media/{pid}/ep{ep['index']:02d}/final.mp4"
        cover = base_fs / "cover.jpg"
        if cover.exists():
            ep["cover"] = f"/media/{pid}/ep{ep['index']:02d}/cover.jpg"
            project["cover"] = ep["cover"]
    return project


@app.get("/api/health")
def health():
    cfg = load_config()
    ffmpeg_ok = True
    try:
        from .tts import ffmpeg_exe
        ffmpeg_ok = Path(ffmpeg_exe()).exists()
    except Exception:
        ffmpeg_ok = False
    local_say = Path("/usr/bin/say").exists()
    return {
        "ok": True,
        "version": VERSION,
        "engine": "local",
        "ffmpeg": ffmpeg_ok,
        "edge_tts": True,
        "macos_say": local_say,
        "llm_enabled": bool(cfg.get("llm", {}).get("enabled")),
        "tts_engine": cfg.get("tts", {}).get("engine"),
        "art_engine": cfg.get("art", {}).get("engine"),
        "llm_model": cfg.get("llm", {}).get("model"),
        "projects": len(store.list_projects()),
    }


@app.get("/api/projects")
def projects():
    return {"projects": store.list_projects()}


@app.post("/api/projects")
async def create_project(request: Request):
    body = await request.json()
    premise = (body.get("premise") or "").strip()
    if len(premise) < 4:
        raise HTTPException(400, "请至少写一句故事创意")
    project, engine = director.create_project(
        premise=premise,
        genre=body.get("genre") or "都市悬疑",
        style=body.get("style") or "neo_noir",
        protagonist=(body.get("protagonist") or "").strip(),
        title=(body.get("title") or "").strip(),
        use_llm=bool(body.get("use_llm")),
    )
    store.save_project(project)
    return {"project": _hydrate_paths(project, project["id"]), "engine": engine}


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    try:
        project = store.load_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "项目不存在")
    return {"project": _hydrate_paths(project, pid)}


@app.patch("/api/projects/{pid}")
async def patch_project(pid: str, request: Request):
    project = store.load_project(pid)
    body = await request.json()
    for key in ("title", "logline", "resolution"):
        if key in body and body[key] is not None:
            project[key] = body[key]
    store.save_project(project)
    return {"project": _hydrate_paths(project, pid)}


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    try:
        store.delete_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "项目不存在")
    return {"ok": True}


@app.patch("/api/projects/{pid}/episodes/{ep_index}/shots/{shot_id}")
async def patch_shot(pid: str, ep_index: int, shot_id: str, request: Request):
    project = store.load_project(pid)
    body = await request.json()
    episode = next((e for e in project.get("episodes", []) if e["index"] == ep_index), None)
    if not episode:
        raise HTTPException(404, "集数不存在")
    shot = next((s for s in episode.get("shots", []) if s["id"] == shot_id), None)
    if not shot:
        raise HTTPException(404, "分镜不存在")
    for key in ("narration", "narration_speaker", "camera", "shot_type", "caption", "time", "location", "image_prompt"):
        if key in body:
            shot[key] = body[key]
    if "dialogues" in body and isinstance(body["dialogues"], list):
        shot["dialogues"] = [
            {
                "speaker": str(d.get("speaker") or ""),
                "text": str(d.get("text") or "")[:90],
                "emotion": str(d.get("emotion") or "neutral"),
            }
            for d in body["dialogues"]
            if str(d.get("text") or "").strip()
        ]
    episode["status"] = "edited"
    store.save_project(project)
    return {"project": _hydrate_paths(project, pid), "shot": shot}


@app.post("/api/projects/{pid}/episodes/generate")
def generate_episode(pid: str):
    project = store.load_project(pid)
    if len(project.get("episodes", [])) >= 12:
        raise HTTPException(400, "一季最多 12 集")
    episode = director.compose_next_episode(project)
    project["episodes"].append(episode)
    store.save_project(project)
    return {"project": _hydrate_paths(project, pid), "episode": episode}


@app.post("/api/projects/{pid}/episodes/{ep_index}/render")
async def start_render(pid: str, ep_index: int, request: Request):
    project = store.load_project(pid)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    resolution = body.get("resolution") or project.get("resolution") or "720p"
    if resolution not in ("720p", "1080p"):
        raise HTTPException(400, "分辨率只支持 720p 或 1080p")
    episode = next((e for e in project.get("episodes", []) if e["index"] == ep_index), None)
    if not episode:
        raise HTTPException(404, "集数不存在")
    project["resolution"] = resolution
    store.save_project(project)
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "project_id": pid,
            "episode_index": ep_index,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "message": "排队准备",
            "log": [],
            "resolution": resolution,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "result": None,
            "error": None,
        }
    _EXECUTOR.submit(_run_job, job_id, pid, ep_index, resolution)
    return {"job": _JOBS[job_id]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "任务不存在")
        return {"job": dict(job)}


@app.get("/api/settings")
def get_settings():
    return {"config": public_config()}


@app.put("/api/settings")
async def put_settings(request: Request):
    patch = await request.json()
    if "llm" in patch and isinstance(patch["llm"], dict):
        key = str(patch["llm"].get("api_key") or "")
        if "•" in key:
            patch["llm"].pop("api_key", None)
        patch["llm"].pop("has_key", None)
    cfg = save_config(patch)
    return {"config": public_config(), "saved": True}


@app.post("/api/settings/test-llm")
async def test_llm(request: Request):
    cfg = dict(load_config()["llm"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        for key in ("base_url", "model", "api_key"):
            value = body.get(key)
            if value is not None:
                if key == "api_key" and ("•" in str(value) or not str(value).strip()):
                    continue
                cfg[key] = str(value).strip()
    base = str(cfg.get("base_url") or "").rstrip("/")
    headers = {}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    started = time.time()
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(f"{base}/models", headers=headers)
            if r.status_code < 500:
                return {"ok": True, "message": f"连接成功 · {round(time.time() - started, 1)}s · HTTP {r.status_code}"}
        with httpx.Client(timeout=45) as client:
            r = client.post(
                f"{base}/chat/completions",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": cfg.get("model"),
                    "messages": [{"role": "user", "content": "只回复：好"}],
                    "max_tokens": 8,
                },
            )
            if r.status_code < 400:
                return {"ok": True, "message": f"模型可用 · {round(time.time() - started, 1)}s"}
            return {"ok": False, "message": f"HTTP {r.status_code}: {r.text[:160]}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败：{exc}"}


@app.get("/api/comfy/status")
def comfy_status(url: str | None = None):
    cfg = load_config().get("art", {})
    base_url = url or cfg.get("comfyui_url", "http://127.0.0.1:8188")
    from .comfy import ComfyClient
    try:
        info = ComfyClient(base_url, 10).test_connection(quick=False)
        info["checkpoint"] = cfg.get("checkpoint") or (info.get("checkpoints") or [None])[0]
        return {"ok": True, **info}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc), "base_url": base_url}


@app.get("/api/llm/models")
def llm_models(base_url: str | None = None, api_key: str | None = None):
    cfg = load_config().get("llm", {})
    base = str(base_url or cfg.get("base_url") or "").rstrip("/")
    key = api_key or cfg.get("api_key") or ""
    headers = {}
    if key and "•" not in key:
        headers["Authorization"] = f"Bearer {key}"
    models: list[str] = []
    source = ""
    for url, source_name in ((f"{base}/models", "openai"), (f"{base.removesuffix('/v1')}/api/tags", "ollama")):
        try:
            with httpx.Client(timeout=6.0) as client:
                r = client.get(url, headers=headers)
                if r.status_code >= 400:
                    continue
                data = r.json()
                if isinstance(data, dict) and isinstance(data.get("data"), list):
                    models = [str(m.get("id")) for m in data["data"] if m.get("id")]
                elif isinstance(data, dict) and isinstance(data.get("models"), list):
                    models = [str(m.get("name") or m.get("model")) for m in data["models"] if m.get("name") or m.get("model")]
                if models:
                    source = source_name
                    break
        except Exception:
            continue
    return {"ok": bool(models), "models": models, "source": source, "base_url": base}


@app.get("/api/voices")
def voices():
    return {
        "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "style": "清冷 / 少女"},
            {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "style": "明亮 / 少女"},
            {"id": "zh-CN-YunjianNeural", "name": "云健", "style": "低沉 / 旁白"},
            {"id": "zh-CN-YunxiNeural", "name": "云希", "style": "轻快 / 少年"},
            {"id": "zh-CN-YunyangNeural", "name": "云扬", "style": "新闻 / 旁白"},
            {"id": "zh-CN-YunxiaNeural", "name": "云夏", "style": "少年"},
            {"id": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北", "style": "东北话"},
            {"id": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮", "style": "陕西话"},
        ]
    }


@app.get("/assets/{path:path}")
def assets(path: str):
    target = (WEB / path).resolve()
    if WEB.resolve() not in target.parents and target != WEB.resolve():
        raise HTTPException(404)
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(404)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/studio/{pid}")
def studio(pid: str):
    return FileResponse(WEB / "index.html")


@app.get("/settings")
def settings_page():
    return FileResponse(WEB / "index.html")


@app.exception_handler(404)
async def _404(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "接口不存在"}, status_code=404)
    if request.url.path.startswith("/assets/") or request.url.path.startswith("/media/"):
        return JSONResponse({"detail": "文件不存在"}, status_code=404)
    return FileResponse(WEB / "index.html")
