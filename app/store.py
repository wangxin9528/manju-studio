"""Tiny JSON project store. No database, no cloud."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import RLock

from .seed import now_iso, sample_project

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "data" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
_LOCK = RLock()


def project_dir(pid: str) -> Path:
    return PROJECTS_DIR / pid


def project_file(pid: str) -> Path:
    return project_dir(pid) / "project.json"


def ensure_sample() -> dict:
    sample = sample_project()
    path = project_file(sample["id"])
    if path.exists():
        return load_project(sample["id"])
    project_dir(sample["id"]).mkdir(parents=True, exist_ok=True)
    _hydrate_media(sample)
    save_project(sample)
    return sample


def _hydrate_media(project: dict) -> None:
    pid = project["id"]
    for episode in project.get("episodes", []):
        base = project_dir(pid) / f"ep{episode['index']:02d}"
        mp4 = base / "final.mp4"
        cover = base / "cover.jpg"
        srt = base / "subtitles.srt"
        timeline = base / "timeline.json"
        if mp4.exists():
            episode["video"] = f"/media/{pid}/ep{episode['index']:02d}/final.mp4"
            episode["status"] = "ready"
        if cover.exists():
            episode["cover"] = f"/media/{pid}/ep{episode['index']:02d}/cover.jpg"
            project["cover"] = episode["cover"]
        if srt.exists():
            episode["srt"] = f"/media/{pid}/ep{episode['index']:02d}/subtitles.srt"
        if timeline.exists():
            try:
                episode["timeline"] = json.loads(timeline.read_text(encoding="utf-8"))
                episode["duration"] = episode["timeline"].get("duration")
            except Exception:
                pass


def save_project(project: dict) -> dict:
    with _LOCK:
        project["updated_at"] = now_iso()
        d = project_dir(project["id"])
        d.mkdir(parents=True, exist_ok=True)
        path = d / "project.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    return project


def load_project(pid: str) -> dict:
    path = project_file(pid)
    if not path.exists():
        raise FileNotFoundError(pid)
    return json.loads(path.read_text(encoding="utf-8"))


def list_projects() -> list[dict]:
    items = []
    for p in PROJECTS_DIR.glob("*/project.json"):
        try:
            project = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        episodes = project.get("episodes", [])
        items.append(
            {
                "id": project.get("id"),
                "title": project.get("title"),
                "genre": project.get("genre"),
                "style": project.get("style"),
                "style_name": project.get("style_name"),
                "logline": project.get("logline"),
                "cover": project.get("cover"),
                "sample": project.get("sample", False),
                "episode_count": len(episodes),
                "duration": sum(float(e.get("duration") or 0) for e in episodes),
                "updated_at": project.get("updated_at"),
                "status": "ready" if any(e.get("video") for e in episodes) else "draft",
            }
        )
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items


def delete_project(pid: str) -> None:
    target = project_dir(pid).resolve()
    root = PROJECTS_DIR.resolve()
    if root not in target.parents:
        raise ValueError("invalid project path")
    if target.exists():
        shutil.rmtree(target)
