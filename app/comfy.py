"""Minimal ComfyUI HTTP client and workflow templates.

The illustrator talks to a running ComfyUI instance. If it is unavailable the
renderer falls back to the built-in panel engine, so the studio never stops
working because of a model server.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, base_url: str, timeout: float = 240.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.client_id = uuid.uuid4().hex

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def test_connection(self, quick: bool = True) -> dict:
        try:
            with httpx.Client(timeout=4.0 if quick else 12.0) as c:
                r = c.get(self._url("/system_stats"))
                r.raise_for_status()
                stats = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ComfyError(f"无法连接 ComfyUI：{exc}") from exc
        system = stats.get("system") or {}
        nodes = {}
        for name in ("CheckpointLoaderSimple", "KSampler", "IPAdapterUnifiedLoader", "IPAdapter"):
            try:
                with httpx.Client(timeout=4.0) as c:
                    r = c.get(self._url(f"/object_info/{name}"))
                    nodes[name] = r.status_code == 200
            except Exception:
                nodes[name] = False
        checkpoints = self.list_checkpoints()
        return {
            "ok": True,
            "base_url": self.base_url,
            "comfyui": system.get("comfyui_version") or system.get("python_version") or "connected",
            "nodes": nodes,
            "ipadapter_ready": bool(nodes.get("IPAdapter") and nodes.get("IPAdapterUnifiedLoader")),
            "checkpoints": checkpoints,
        }

    def list_checkpoints(self) -> list[str]:
        try:
            with httpx.Client(timeout=5.0) as c:
                r = c.get(self._url("/object_info/CheckpointLoaderSimple"))
                r.raise_for_status()
                info = r.json()
            required = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
            values = required[0] if isinstance(required, list) else required
            return [str(x) for x in values] if isinstance(values, list) else []
        except Exception:
            return []

    def upload_image(self, path: Path) -> str:
        content = path.read_bytes()
        digest = hashlib.sha1(content).hexdigest()[:10]
        name = f"manju_ref_{digest}{path.suffix.lower() if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp') else '.png'}"
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(
                    self._url("/upload/image"),
                    files={"image": (name, content, "image/png" if name.endswith(".png") else "image/jpeg")},
                    data={"type": "input", "overwrite": "true"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ComfyError(f"参考图上传失败：{exc}") from exc
        return str(data.get("name") or name)

    def queue(self, workflow: dict) -> str:
        payload = {"prompt": workflow, "client_id": self.client_id}
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(self._url("/prompt"), json=payload)
                if r.status_code >= 400:
                    raise ComfyError(f"ComfyUI 拒绝了工作流（HTTP {r.status_code}）：{r.text[:700]}")
                data = r.json()
        except ComfyError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ComfyError(f"提交 ComfyUI 任务失败：{exc}") from exc
        if data.get("node_errors"):
            raise ComfyError("工作流节点错误：" + json.dumps(data["node_errors"], ensure_ascii=False)[:700])
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"ComfyUI 未返回 prompt_id：{data}")
        return str(prompt_id)

    def wait(self, prompt_id: str, on_poll=None) -> list[dict]:
        deadline = time.time() + self.timeout
        last = None
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=20.0) as c:
                    r = c.get(self._url(f"/history/{prompt_id}"))
                    if r.status_code == 200:
                        history = r.json()
                        item = history.get(prompt_id)
                        if item:
                            outputs = item.get("outputs") or {}
                            images = []
                            for node in outputs.values():
                                for img in node.get("images") or []:
                                    if img.get("filename"):
                                        images.append(img)
                            if images:
                                return images
                            status = item.get("status") or {}
                            if status.get("status_str") == "error":
                                raise ComfyError(f"ComfyUI 执行失败：{status.get('messages')}")
            except ComfyError:
                raise
            except Exception as exc:  # noqa: BLE001
                last = exc
            if on_poll:
                on_poll()
            time.sleep(0.9)
        suffix = f"（最后一次错误：{last}）" if last else ""
        raise ComfyError(f"ComfyUI 生成超时{suffix}")

    def download(self, image: dict) -> bytes:
        params = {
            "filename": image.get("filename", ""),
            "subfolder": image.get("subfolder", ""),
            "type": image.get("type", "output"),
        }
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.get(self._url("/view"), params=params)
                r.raise_for_status()
                return r.content
        except Exception as exc:  # noqa: BLE001
            raise ComfyError(f"下载 ComfyUI 图片失败：{exc}") from exc

    def generate(self, workflow: dict, on_poll=None) -> bytes:
        prompt_id = self.queue(workflow)
        images = self.wait(prompt_id, on_poll=on_poll)
        return self.download(images[0])


# ---------------------------------------------------------------------------
# Workflow templates


def txt2img_workflow(cfg: dict, prompt: str, negative: str, seed: int, width: int, height: int) -> dict:
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": cfg.get("checkpoint") or ""},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": int(width), "height": int(height), "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(seed),
                "steps": int(cfg.get("steps", 24)),
                "cfg": float(cfg.get("cfg", 7.0)),
                "sampler_name": cfg.get("sampler", "euler_ancestral"),
                "scheduler": cfg.get("scheduler", "normal"),
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "manju_ref"}},
    }


def ipadapter_workflow(
    cfg: dict,
    prompt: str,
    negative: str,
    seed: int,
    width: int,
    height: int,
    image_name: str,
    weight: float | None = None,
    weight_type: str | None = None,
) -> dict:
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": cfg.get("checkpoint") or ""},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": int(width), "height": int(height), "batch_size": 1},
        },
        "5": {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {"model": ["1", 0], "preset": cfg.get("preset", "PLUS (high strength)")},
        },
        "6": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        },
        "7": {
            "class_type": "IPAdapter",
            "inputs": {
                "model": ["5", 0],
                "ipadapter": ["5", 1],
                "image": ["6", 0],
                "weight": float(weight if weight is not None else cfg.get("ipadapter_weight", 0.62)),
                "start_at": 0.0,
                "end_at": 1.0,
                "weight_type": weight_type or cfg.get("ipadapter_weight_type", "prompt is more important"),
            },
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(seed),
                "steps": int(cfg.get("steps", 24)),
                "cfg": float(cfg.get("cfg", 7.0)),
                "sampler_name": cfg.get("sampler", "euler_ancestral"),
                "scheduler": cfg.get("scheduler", "normal"),
                "denoise": 1.0,
                "model": ["7", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "manju_shot"}},
    }


def load_workflow(path: str, values: dict) -> dict:
    """Optional custom API workflow with {{placeholders}}.

    Values may be scalars or strings. A full-string placeholder preserves its
    type (int/float/list); embedded placeholders are string-substituted.
    """
    p = Path(path)
    if not p.exists():
        raise ComfyError(f"找不到工作流文件：{p}")
    raw = json.loads(p.read_text(encoding="utf-8"))

    def replace(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: replace(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [replace(v) for v in obj]
        if isinstance(obj, str):
            stripped = obj.strip()
            if stripped.startswith("{{") and stripped.endswith("}}"):
                key = stripped[2:-2].strip()
                if key in values:
                    return copy.deepcopy(values[key])
            for key, value in values.items():
                obj = obj.replace("{{" + key + "}}", str(value))
        return obj

    return replace(raw)
