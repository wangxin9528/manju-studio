"""Frame compositor and FFmpeg encoder for vertical motion comics."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import art, audio, illustrator, tts
from .config import load_config

ROOT = Path(__file__).resolve().parent.parent
FONT_SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_DISPLAY = "/System/Library/Fonts/Supplemental/Songti.ttc"


def _font(size, kind="sans"):
    if kind == "display":
        return ImageFont.truetype(FONT_DISPLAY, int(size), index=1)
    if kind == "bold":
        return ImageFont.truetype(FONT_SANS, int(size), index=2)
    if kind == "light":
        return ImageFont.truetype(FONT_SANS, int(size), index=0)
    return ImageFont.truetype(FONT_SANS, int(size), index=2)


def _hex(v):
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        trial = current + ch
        if font.getlength(trial) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines[:4]


def _round_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_bubble(cue: dict, project: dict, width: int) -> tuple[Image.Image, int, int]:
    k = width / 1080
    characters = {c["name"]: c for c in project.get("characters", [])}
    char = characters.get(cue.get("speaker", ""), {})
    accent = _hex(char.get("accent", "#FF4D3D"))
    ink = (10, 11, 14, 255)
    paper = (247, 239, 226, 248)
    max_text = 590 * k
    text_font = _font(30 * k, "sans")
    name_font = _font(21 * k, "bold")
    lines = _wrap(cue["text"], text_font, max_text)
    line_h = 47 * k
    pad_x = 28 * k
    pad_y = 20 * k
    name_h = 38 * k
    text_w = max((text_font.getlength(line) for line in lines), default=0)
    bw = min(660 * k, max(340 * k, text_w + pad_x * 2 + 8 * k))
    bh = pad_y * 2 + name_h + len(lines) * line_h - 4 * k
    tail = 22 * k
    canvas = Image.new("RGBA", (int(bw + 18 * k), int(bh + tail + 16 * k)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    _round_rect(sd, (9 * k, 12 * k, bw - 1 * k, bh + 10 * k), 18 * k, (0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10 * k)))
    d = ImageDraw.Draw(canvas)
    _round_rect(d, (0, 0, bw, bh), 18 * k, paper, ink, max(2, int(3 * k)))
    # paper fold / inner edge
    d.line([(18 * k, 1.5 * k), (bw - 18 * k, 1.5 * k)], fill=(255, 255, 255, 90), width=max(1, int(1 * k)))
    # speaker tab inside the bubble
    d.rectangle((pad_x, pad_y + 2 * k, pad_x + 5 * k, pad_y + 20 * k), fill=accent)
    d.text((pad_x + 15 * k, pad_y - 2 * k), cue.get("speaker", ""), font=name_font, fill=accent)
    # tail
    tail_x = min(bw - 95 * k, max(60 * k, bw * 0.30))
    tail_pts = [(tail_x, bh - 2 * k), (tail_x + 34 * k, bh - 2 * k), (tail_x + 9 * k, bh + tail)]
    d.polygon(tail_pts, fill=paper, outline=ink)
    d.line([(tail_x + 2 * k, bh), (tail_x + 31 * k, bh)], fill=paper, width=max(2, int(4 * k)))
    for i, line in enumerate(lines):
        d.text((pad_x, pad_y + name_h + i * line_h), line, font=text_font, fill=(12, 13, 16, 255))
    return canvas, int(bw), int(bh + tail)


def make_caption(cue: dict, project: dict, width: int) -> Image.Image:
    k = width / 1080
    font = _font(27 * k, "sans")
    max_text = width - 160 * k
    lines = _wrap(cue["text"], font, max_text)
    line_h = 42 * k
    pad = 18 * k
    text_w = max((font.getlength(line) for line in lines), default=0)
    bw = min(width - 100 * k, text_w + pad * 2 + 16 * k)
    bh = len(lines) * line_h + pad * 2
    canvas = Image.new("RGBA", (int(bw + 10 * k), int(bh + 10 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    _round_rect(d, (0, 0, bw, bh), 8 * k, (8, 10, 13, 208))
    d.rectangle((0, 0, 5 * k, bh), fill=(255, 77, 61, 255))
    for i, line in enumerate(lines):
        d.text((22 * k, pad + i * line_h), line, font=font, fill=(242, 237, 225, 250))
    return canvas


def _ease(t):
    return t * t * (3 - 2 * t)


def camera_crop(size, zoom, panx, pany):
    w, h = size
    cw = w / zoom
    ch = h / zoom
    cx = w / 2 + panx
    cy = h / 2 + pany
    x0 = max(0, min(w - cw, cx - cw / 2))
    y0 = max(0, min(h - ch, cy - ch / 2))
    return int(x0), int(y0), int(x0 + cw), int(y0 + ch)


def _hud(frame: Image.Image, project: dict, episode: dict, t: float, duration: float):
    w, h = frame.size
    k = w / 1080
    # legibility gradients for the tiny HUD and bottom captions
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(120):
        a = int(125 * (1 - i / 120) ** 1.7)
        sd.line([(0, i * k), (w, i * k)], fill=(3, 4, 7, a))
    for i in range(200):
        a = int(190 * (i / 200) ** 1.8)
        sd.line([(0, h - (200 - i) * k), (w, h - (200 - i) * k)], fill=(3, 4, 7, a))
    frame.alpha_composite(shade)
    d = ImageDraw.Draw(frame, "RGBA")
    paper = (242, 235, 222, 205)
    muted = (242, 235, 222, 95)
    accent = (255, 77, 61, 230)
    d.rectangle((0, 0, w, 2 * k), fill=(255, 77, 61, 140))
    title_font = _font(20 * k, "bold")
    small = _font(14 * k, "light")
    d.text((54 * k, 46 * k), project.get("title", ""), font=title_font, fill=paper)
    d.text((54 * k, 78 * k), f"EP.{episode.get('index', 1):02d}  /  {episode.get('title', '')}", font=small, fill=muted)
    label = "MANJU · LOCAL ENGINE"
    lw = small.getlength(label)
    d.text((w - 54 * k - lw, 48 * k), label, font=small, fill=(255, 77, 61, 150))
    d.line([(w - 54 * k - lw, 72 * k), (w - 54 * k, 72 * k)], fill=(255, 77, 61, 100), width=max(1, int(1 * k)))
    # progress
    d.rectangle((0, h - 5 * k, w, h), fill=(8, 9, 11, 150))
    d.rectangle((0, h - 5 * k, w * min(1, t / max(duration, 0.1)), h), fill=accent)


def _end_card(frame: Image.Image, project: dict, episode: dict, alpha: float, t: float):
    w, h = frame.size
    k = w / 1080
    overlay = Image.new("RGBA", (w, h), (4, 5, 8, int(235 * alpha)))
    frame.alpha_composite(overlay)
    d = ImageDraw.Draw(frame, "RGBA")
    title_font = _font(86 * k, "display")
    sub_font = _font(22 * k, "light")
    small = _font(15 * k, "light")
    accent = (255, 77, 61, int(240 * alpha))
    paper = (242, 234, 220, int(245 * alpha))
    d.text((w / 2, h * 0.33), "MANJU ORIGINAL", font=small, fill=(255, 77, 61, int(180 * alpha)), anchor="mm")
    d.text((w / 2, h * 0.42), project.get("title", ""), font=title_font, fill=paper, anchor="mm")
    d.line([(w / 2 - 120 * k, h * 0.47), (w / 2 + 120 * k, h * 0.47)], fill=accent, width=max(1, int(2 * k)))
    d.text((w / 2, h * 0.52), f"第 {episode.get('index', 1):02d} 集 · {episode.get('title', '')} · 完", font=sub_font, fill=(230, 225, 214, int(220 * alpha)), anchor="mm")
    hook = episode.get("hook", "")
    if hook:
        lines = _wrap(hook, _font(24 * k, "sans"), w - 220 * k)[:2]
        for i, line in enumerate(lines):
            d.text((w / 2, h * 0.61 + i * 40 * k), line, font=_font(24 * k, "sans"), fill=(244, 237, 225, int(220 * alpha)), anchor="mm")
    d.text((w / 2, h * 0.75), "下一集，继续。", font=_font(20 * k, "bold"), fill=accent, anchor="mm")
    d.text((w / 2, h * 0.93), "MANJU / AI MOTION COMIC STUDIO", font=small, fill=(170, 170, 165, int(120 * alpha)), anchor="mm")


def render_video(project: dict, episode: dict, episode_dir: Path, timeline: dict, resolution="720p", on_progress=None) -> Path:
    W, H = (1080, 1920) if resolution == "1080p" else (720, 1280)
    fps = int(load_config().get("video", {}).get("fps", 24))
    total = float(timeline["duration"])
    frames = int(total * fps)
    art_dir = episode_dir / "art"
    shot_art = {}
    for shot in episode["shots"]:
        p = art_dir / f"shot_{shot['index']:02d}.jpg"
        if p.exists():
            img = Image.open(p).convert("RGB")
            if img.size != (W, H):
                # keep overscan; downscale for speed
                pass
            shot_art[shot["index"]] = img
    if not shot_art:
        raise RuntimeError("没有可用的漫画面板")

    bubble_cache = {}
    caption_cache = {}
    # Pre-render each cue overlay once
    for ci, cue in enumerate(timeline["cues"]):
        if cue["kind"] == "dialogue":
            bubble_cache[ci] = make_bubble(cue, project, W)
        else:
            caption_cache[ci] = make_caption(cue, project, W)

    out = episode_dir / "final.mp4"
    ffmpeg = tts.ffmpeg_exe()
    mix = episode_dir / "mix.wav"
    cmd = [
        ffmpeg, "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
        "-i", str(mix),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def shot_at(t):
        for s in timeline["shots"]:
            if s["start"] <= t < s["end"]:
                return s
        return timeline["shots"][-1]

    speech_end = float(timeline["speech_end"])
    grain = np.random.default_rng(21)
    try:
        for fi in range(frames):
            t = fi / fps
            frame = Image.new("RGBA", (W, H), (4, 5, 8, 255))
            if t >= speech_end:
                # end card, built from last panel
                last = timeline["shots"][-1]
                base = shot_art.get(last["index"])
                if base is not None:
                    bg = base.resize((W, H), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(16 * (W / 1080)))
                    frame = bg.convert("RGBA")
                p = min(1.0, (t - speech_end) / 0.6)
                _end_card(frame, project, episode, _ease(p), t)
            else:
                s = shot_at(t)
                base = shot_art.get(s["index"])
                if base is None:
                    base = next(iter(shot_art.values()))
                local = (t - s["start"]) / max(0.1, s["end"] - s["start"])
                shot = next(sh for sh in episode["shots"] if sh["index"] == s["index"])
                camera = shot.get("camera", "")
                push = "推" in camera or "微距" in camera or "跟" in camera
                pan = "横移" in camera or "环绕" in camera
                zoom = 1.015 + (0.125 if push else 0.065) * _ease(min(1, local))
                px = (local - 0.5) * (34 * (W / 1080)) if pan else 0
                py = (local - 0.5) * (18 * (W / 1080)) if pan else 0
                if "impact" in shot.get("sfx", []) and local < 0.12:
                    px += math.sin(fi * 2.7) * 7 * (W / 1080)
                    py += math.cos(fi * 3.1) * 5 * (W / 1080)
                box = camera_crop(base.size, zoom, px, py)
                frame = base.crop(box).resize((W, H), Image.Resampling.BILINEAR).convert("RGBA")
                # fade in from black at each cut
                cut_in = max(0.0, 1.0 - (t - s["start"]) / 0.22)
                if cut_in > 0:
                    frame = Image.blend(Image.new("RGBA", (W, H), (3, 4, 6, 255)), frame, 1 - cut_in)
                if fi < int(0.6 * fps):
                    frame = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), frame, fi / max(1, int(0.6 * fps)))
                # active cue overlay
                for ci, cue in enumerate(timeline["cues"]):
                    if not (cue["start"] <= t <= cue["end"] + 0.12):
                        continue
                    alpha = 1.0
                    if t < cue["start"] + 0.16:
                        alpha = (t - cue["start"]) / 0.16
                    if t > cue["end"]:
                        alpha = max(0.0, 1 - (t - cue["end"]) / 0.14)
                    alpha = max(0.0, min(1.0, alpha))
                    if cue["kind"] == "dialogue" and ci in bubble_cache:
                        bub, bw, bh = bubble_cache[ci]
                        bub = bub.copy()
                        if alpha < 1:
                            bub.putalpha(bub.getchannel("A").point(lambda v: int(v * alpha)))
                        shot_info = next((x for x in timeline["shots"] if x["index"] == cue["shot"]), None)
                        shot_def = next(sh for sh in episode["shots"] if sh["index"] == cue["shot"])
                        if shot_def.get("shot_type") in ("close", "detail"):
                            y = int(H - bh - 175 * (W / 1080))
                        else:
                            y = int(188 * (W / 1080))
                        y += int((1 - alpha) * 12 * (W / 1080))
                        x = int((W - bw) / 2 + (10 * (W / 1080) if cue.get("speaker") == "沈砚" else -10 * (W / 1080)))
                        frame.alpha_composite(bub, (max(0, min(W - bw, x)), max(0, min(H - bh, y))))
                    elif cue["kind"] == "narration" and ci in caption_cache:
                        cap = caption_cache[ci].copy()
                        if alpha < 1:
                            cap.putalpha(cap.getchannel("A").point(lambda v: int(v * alpha)))
                        x = int(58 * (W / 1080))
                        y = int(H - cap.height - 92 * (W / 1080))
                        frame.alpha_composite(cap, (x, y))
            _hud(frame, project, episode, t, total)
            # light animated grain
            if fi % 3 == 0:
                noise = grain.normal(0, 5.5, (H // 3, W // 3, 1)).repeat(3, axis=2) + 128
                noise_img = Image.fromarray(np.clip(noise, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.Resampling.BILINEAR)
                frame = Image.blend(frame.convert("RGB"), Image.blend(frame.convert("RGB"), noise_img, 0.10), 0.9)
            proc.stdin.write(frame.convert("RGB").tobytes())
            if on_progress and fi % 6 == 0:
                pct = 65 + (fi / max(1, frames)) * 30
                on_progress("frames", pct, f"合成画面 {fi}/{frames}")
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", "ignore")
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"FFmpeg 合成失败: {stderr[-1200:]}")
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
    if on_progress:
        on_progress("encode", 98, "写入 MP4")
    return out


def render_cover(project: dict, episode: dict, episode_dir: Path) -> Path:
    W, H = 1080, 1920
    art_path = episode_dir / "art" / "shot_02.jpg"
    if not art_path.exists():
        art_path = episode_dir / "art" / "shot_01.jpg"
    base = Image.open(art_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(int(H * 0.40), H):
        a = int(235 * ((y - H * 0.40) / (H * 0.60)) ** 1.15)
        d.line([(0, y), (W, y)], fill=(4, 5, 8, a))
    base = Image.alpha_composite(base.convert("RGBA"), overlay)
    d = ImageDraw.Draw(base)
    d.text((58, 58), "MANJU ORIGINAL", font=_font(15, "light"), fill=(255, 77, 61, 200))
    d.text((58, 84), f"EP.{episode.get('index', 1):02d} / LOCAL ENGINE", font=_font(11, "light"), fill=(242, 234, 220, 100))
    d.line([(58, 112), (148, 112)], fill=(255, 77, 61, 120), width=2)
    d.text((1022, 1830), "9:16", font=_font(15, "bold"), fill=(242, 234, 220, 110), anchor="ra")
    out = episode_dir / "cover.jpg"
    base.convert("RGB").save(out, quality=92)
    return out




def render_episode(project: dict, episode: dict, on_progress=None, resolution=None) -> dict:
    pid = project["id"]
    episode_dir = ROOT / "data" / "projects" / pid / f"ep{episode['index']:02d}"
    art_dir = episode_dir / "art"
    art_dir.mkdir(parents=True, exist_ok=True)
    resolution = resolution or project.get("resolution", "720p")
    art_width = 1440 if resolution == "1080p" else 1080

    def progress(stage, pct, message):
        if on_progress:
            on_progress(stage, pct, message)

    art_cfg = load_config().get("art", {})
    art_engine = art_cfg.get("engine", "builtin")
    art_meta = {"engine": "builtin"}
    if art_engine == "comfyui":
        progress("art", 3, "连接 ComfyUI · 准备 IP-Adapter")
        try:
            result = illustrator.generate_episode_art(
                project,
                episode,
                art_dir,
                on_progress=lambda frac, msg: progress("art", 4 + frac * 26, msg),
            )
            art_meta = result
            project.setdefault("meta", {})["art"] = {k: v for k, v in result.items() if k != "warnings"}
            project["meta"]["art"]["warnings_count"] = len(result.get("warnings", []))
            if result.get("warnings"):
                progress("art", 29, "部分 AI 插画回退到本地剪影")
        except Exception as exc:  # noqa: BLE001
            art_meta = {"engine": "builtin", "fallback_reason": str(exc)[:300]}
            progress("art", 6, f"ComfyUI 不可用，回退本地剪影：{str(exc)[:60]}")
            for i, shot in enumerate(episode["shots"]):
                art.render_panel(project, episode, shot, art_dir / f"shot_{shot['index']:02d}.jpg", width=art_width)
                shot["ai_art"] = False
                progress("art", 7 + (i + 1) / len(episode["shots"]) * 23, f"绘制第 {shot['index']} 镜")
    else:
        progress("art", 4, "铺设漫画面板")
        for i, shot in enumerate(episode["shots"]):
            art.render_panel(project, episode, shot, art_dir / f"shot_{shot['index']:02d}.jpg", width=art_width)
            progress("art", 5 + (i + 1) / len(episode["shots"]) * 25, f"绘制第 {shot['index']} 镜")

    progress("voice", 32, "生成角色配音")
    timeline = audio.build_timeline(
        project,
        episode,
        episode_dir,
        progress=lambda i, n, t: progress("voice", 32 + (i / max(1, n)) * 22, f"配音 {i}/{n}"),
    )
    progress("music", 56, "编写配乐与音效")
    audio.build_mix(project, episode, timeline, episode_dir)
    progress("music", 64, "混音完成")

    video = render_video(project, episode, episode_dir, timeline, resolution=resolution, on_progress=progress)
    audio.write_srt(timeline, episode_dir / "subtitles.srt")
    render_cover(project, episode, episode_dir)
    progress("finalize", 99, "整理封面与字幕")

    base = f"/media/{pid}/ep{episode['index']:02d}"
    episode.update(
        {
            "video": f"{base}/final.mp4",
            "srt": f"{base}/subtitles.srt",
            "cover": f"{base}/cover.jpg",
            "duration": timeline["duration"],
            "status": "ready",
            "timeline": timeline,
        }
    )
    project["cover"] = episode["cover"]
    from .seed import now_iso
    project["updated_at"] = now_iso()
    progress("done", 100, "成片已就绪")
    project.setdefault("meta", {})["art_last_run"] = art_meta
    return {
        "video": video,
        "cover": episode_dir / "cover.jpg",
        "srt": episode_dir / "subtitles.srt",
        "timeline": timeline,
        "art": art_meta,
    }
