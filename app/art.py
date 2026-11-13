"""The local motion-comic art engine.

Everything is drawn procedurally with Pillow + NumPy: no model downloads, no
API keys, no network. The visual language is a deliberately limited one:
silhouettes, duotone neon, halftone, rain, paper grain and comic typography.
"""
from __future__ import annotations

import math
import os
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_SANS_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_SANS_BOLD_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_DISPLAY_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_FALLBACK_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"

PALETTES = {
    "neo_noir": {
        "name": "霓虹黑",
        "sky": ["#05070D", "#0E1B2B", "#253346", "#3A2638"],
        "ink": "#05060A",
        "paper": "#F2E9D8",
        "accent": "#FF4D3D",
        "accent2": "#63F2DE",
        "halo": "#37C9CF",
        "fog": "#132435",
        "warm": "#FFB05C",
        "window": ["#FFD9A0", "#73F6E7", "#FF5A66", "#9BA8FF"],
    },
    "dusk_anime": {
        "name": "晚霞日漫",
        "sky": ["#14162B", "#43305B", "#B9587A", "#F4A26B"],
        "ink": "#0B0C16",
        "paper": "#FFF3DE",
        "accent": "#FF6B5E",
        "accent2": "#FFD36E",
        "halo": "#FF9F87",
        "fog": "#3B2B4C",
        "warm": "#FFD9A0",
        "window": ["#FFE4B5", "#FF8B7A", "#9FE7E1", "#FFD36E"],
    },
    "ink_wuxia": {
        "name": "水墨朱砂",
        "sky": ["#0C0C0B", "#1C1A17", "#3A342A", "#6E5C42"],
        "ink": "#080807",
        "paper": "#EDE3CE",
        "accent": "#C7352B",
        "accent2": "#D9B56B",
        "halo": "#B44A35",
        "fog": "#2A241D",
        "warm": "#D8B06A",
        "window": ["#E8C17C", "#C7352B", "#F0E3C5"],
    },
    "warm_slice": {
        "name": "暖调都市",
        "sky": ["#141019", "#2C1C2B", "#633B3C", "#B86E4C"],
        "ink": "#120D0F",
        "paper": "#F8EDDC",
        "accent": "#E4553F",
        "accent2": "#F4C26B",
        "halo": "#E9A36D",
        "fog": "#302027",
        "warm": "#FFD4A3",
        "window": ["#FFE0A8", "#FF9A6A", "#B9D7D0"],
    },
    "cyber_pop": {
        "name": "赛博波普",
        "sky": ["#07040F", "#1B0B3A", "#3A0F5E", "#801D6B"],
        "ink": "#06030B",
        "paper": "#F5E9FF",
        "accent": "#FF2E88",
        "accent2": "#43F9FF",
        "halo": "#8A5CFF",
        "fog": "#23113A",
        "warm": "#FFE86E",
        "window": ["#43F9FF", "#FF2E88", "#FFE86E", "#A78BFA"],
    },
}

SCENE_ALIASES = {
    "establish": "rooftop",
    "confront": "rooftop",
    "detail": "prop",
    "interior": "apartment",
    "close": "close",
    "memory": "memory",
    "lab_door": "lab_door",
    "void": "void",
    "chip": "chip",
    "prop": "prop",
}


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t: float):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


@lru_cache(maxsize=64)
def font(size: int, kind: str = "sans") -> ImageFont.FreeTypeFont:
    size = max(8, int(size))
    if kind == "display":
        path, index = FONT_DISPLAY_PATH, 0
    elif kind == "bold":
        path, index = FONT_SANS_BOLD_PATH, 2
    elif kind == "light":
        path, index = FONT_SANS_PATH, 0
    else:
        path, index = FONT_SANS_PATH, 2
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.truetype(FONT_FALLBACK_PATH, size, index=1)


class Canvas:
    def __init__(self, width: int, palette: dict):
        self.w = width
        self.h = round(width * 16 / 9)
        self.s = width / 1080.0
        self.p = palette
        self.img = Image.new("RGB", (self.w, self.h), _hex(palette["sky"][0]))
        self.draw = ImageDraw.Draw(self.img, "RGBA")

    def sx(self, value: float) -> float:
        return value * self.s

    def box(self, x: float, y: float, w: float, h: float):
        s = self.s
        return [x * s, y * s, (x + w) * s, (y + h) * s]

    def glow(self, center, radius, color, strength=1.0, rect=None):
        add_radial_glow(self.img, center, radius, color, strength, self.s, rect=rect)

    def text(
        self,
        xy,
        text: str,
        size: int,
        fill,
        kind="sans",
        anchor="la",
        spacing=8,
        align="left",
        stroke_width=0,
        stroke_fill=None,
    ):
        f = font(self.sx(size), kind)
        self.draw.multiline_text(
            (xy[0] * self.s, xy[1] * self.s),
            text,
            font=f,
            fill=fill,
            anchor=anchor,
            spacing=self.sx(spacing),
            align=align,
            stroke_width=int(stroke_width * self.s),
            stroke_fill=stroke_fill,
        )

    def line(self, pts, fill, width=2, joint="curve"):
        self.draw.line(
            [(x * self.s, y * self.s) for x, y in pts],
            fill=fill,
            width=max(1, int(width * self.s)),
            joint=joint,
        )

    def polygon(self, pts, fill):
        self.draw.polygon([(x * self.s, y * self.s) for x, y in pts], fill=fill)

    def rect(self, box, fill, radius=0):
        x, y, w, h = box
        b = [x * self.s, y * self.s, (x + w) * self.s, (y + h) * self.s]
        if radius:
            self.draw.rounded_rectangle(b, radius=self.sx(radius), fill=fill)
        else:
            self.draw.rectangle(b, fill=fill)


def add_radial_glow(img, center, radius, color, strength=1.0, s=1.0, rect=None):
    """Screen-add a cheap radial glow, rendered at half resolution."""
    w, h = img.size
    cx, cy = center[0] * s, center[1] * s
    r = max(2.0, radius * s)
    if rect:
        x0, y0, x1, y1 = [int(v * s) for v in rect]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        if x1 <= x0 or y1 <= y0:
            return
    else:
        x0, y0, x1, y1 = 0, 0, w, h
    scale = 0.5
    lw, lh = max(2, int((x1 - x0) * scale)), max(2, int((y1 - y0) * scale))
    yy, xx = np.mgrid[0:lh, 0:lw]
    dx = (xx + x0 * scale) - cx * scale
    dy = (yy + y0 * scale) - cy * scale
    dist = np.sqrt(dx * dx + dy * dy) / max(1.0, r * scale)
    mask = np.clip(1.0 - dist, 0, 1) ** 2.2 * float(strength)
    mask = (mask * 255).astype(np.uint8)
    glow = Image.new("RGB", (lw, lh), color)
    glow.putalpha(Image.fromarray(mask, "L"))
    glow = glow.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR)
    region = img.crop((x0, y0, x1, y1)).convert("RGBA")
    region.alpha_composite(glow)
    img.paste(region.convert("RGB"), (x0, y0))


def vertical_gradient(w, h, stops, positions=None):
    n = len(stops)
    if positions is None:
        positions = np.linspace(0, 1, n)
    ys = np.linspace(0, 1, h)
    cols = np.array([_hex(c) for c in stops], dtype=np.float32)
    out = np.zeros((h, 3), dtype=np.float32)
    for ch in range(3):
        out[:, ch] = np.interp(ys, positions, cols[:, ch])
    arr = np.repeat(out[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def add_noise(img, amount=8, seed=1):
    rng = np.random.default_rng(seed)
    w, h = img.size
    noise = rng.normal(0, amount, (h // 2, w // 2, 1)).repeat(3, axis=2)
    noise = np.clip(noise + 128, 0, 255).astype(np.uint8)
    layer = Image.fromarray(noise, "RGB").resize((w, h), Image.Resampling.BILINEAR)
    return Image.blend(img, ImageChops.add(img, ImageChops.subtract(layer, Image.new("RGB", (w, h), (128, 128, 128)))), 0.22)


def add_grain(img, seed=1, amount=14):
    rng = np.random.default_rng(seed)
    arr = np.array(img).astype(np.int16)
    noise = rng.normal(0, amount, (img.height, img.width, 1)).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def vignette(img, strength=0.55):
    w, h = img.size
    scale = 0.25
    lw, lh = max(8, int(w * scale)), max(8, int(h * scale))
    yy, xx = np.mgrid[0:lh, 0:lw]
    dx = (xx / lw - 0.5) * 2
    dy = (yy / lh - 0.5) * 2
    d = np.sqrt(dx * dx + dy * dy)
    mask = np.clip((d - 0.35) / 0.9, 0, 1) ** 1.6 * strength
    mask = Image.fromarray((mask * 255).astype(np.uint8), "L").resize((w, h), Image.Resampling.BILINEAR)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, mask)


def bloom(img, radius=12, amount=0.34):
    blur = img.filter(ImageFilter.GaussianBlur(radius))
    return ImageChops.screen(img, Image.eval(blur, lambda v: int(v * amount)))


def halftone_overlay(img, accent=(255, 255, 255), alpha=18, spacing=7, dot=2.1, seed=3):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx % max(2, spacing)) - spacing / 2
    dy = (yy % max(2, spacing)) - spacing / 2
    mask = ((dx * dx + dy * dy) <= (dot * dot)).astype(np.uint8) * int(alpha)
    layer = Image.new("RGBA", (w, h), (*accent, 0))
    layer.putalpha(Image.fromarray(mask, "L"))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def scanlines(img, alpha=10, gap=4):
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(0, h, gap):
        d.line([(0, y), (w, y)], fill=(0, 0, 0, alpha), width=1)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


# ---------------------------------------------------------------------------
# Backgrounds


def _rain(c: Canvas, rng, amount=210, alpha=70, color=(196, 230, 238)):
    for _ in range(amount):
        x = rng.uniform(-100, 1080)
        y = rng.uniform(0, 1750)
        length = rng.uniform(18, 90)
        slant = rng.uniform(5, 22)
        a = int(rng.uniform(alpha * 0.25, alpha))
        c.line([(x, y), (x + slant, y + length)], (*color, a), width=rng.choice([1, 1, 2]))


def _skyline(c: Canvas, rng, base_y, min_h, max_h, color, alpha=255, windows=True, layer_blur=0, density=0.9):
    layer = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = -20
    while x < 1100:
        bw = rng.uniform(28, 92)
        bh = rng.uniform(min_h, max_h)
        top = base_y - bh
        d.rectangle(
            [x * c.s, top * c.s, (x + bw) * c.s, base_y * c.s],
            fill=(*color, alpha),
        )
        if rng.random() < 0.35:
            d.rectangle(
                [(x + bw * 0.45) * c.s, (top - rng.uniform(18, 60)) * c.s, (x + bw * 0.5) * c.s, top * c.s],
                fill=(*color, alpha),
            )
        if windows:
            cols = max(2, int(bw / 13))
            rows = max(3, int(bh / 22))
            for cx in range(cols):
                for cy in range(rows):
                    if rng.random() < 0.35:
                        wx = x + 5 + cx * (bw - 8) / cols
                        wy = top + 7 + cy * (bh - 10) / rows
                        wc = _hex(rng.choice(c.p["window"]))
                        a = int(rng.uniform(70, 210))
                        d.rectangle(
                            [wx * c.s, wy * c.s, (wx + 2.5) * c.s, (wy + 3.5) * c.s],
                            fill=(*wc, a),
                        )
        x += bw + rng.uniform(4, 20)
    if layer_blur:
        layer = layer.filter(ImageFilter.GaussianBlur(layer_blur * c.s))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), layer).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")


def _neon_sign(c: Canvas, x, y, text, color, size=46, vertical=True, glow=18):
    layer = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(int(size * c.s), "bold")
    if vertical:
        yy = y
        for ch in text:
            d.text((x * c.s, yy * c.s), ch, font=f, fill=(*color, 255), anchor="ma")
            yy += size * 1.06
    else:
        d.text((x * c.s, y * c.s), text, font=f, fill=(*color, 255), anchor="ma")
    blurred = layer.filter(ImageFilter.GaussianBlur(glow * c.s))
    c.img = ImageChops.screen(c.img, blurred.convert("RGB"))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), layer).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")


def scene_rooftop(c: Canvas, rng):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, p["sky"], [0, 0.34, 0.72, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    c.glow((780, 360), 520, _hex(p["halo"]), 0.30)
    c.glow((220, 1100), 700, _hex(p["accent"]), 0.22)
    # moon
    mx, my, mr = 792, 300, 86
    c.glow((mx, my), 250, (226, 240, 226), 0.55)
    c.draw.ellipse(c.box(mx - mr, my - mr, mr * 2, mr * 2), fill=(228, 237, 221, 235))
    c.draw.ellipse(c.box(mx - mr + 22, my - mr + 8, mr * 2 - 8, mr * 2 - 8), fill=(198, 214, 201, 80))
    # clouds
    for i in range(5):
        x, y = rng.uniform(-100, 900), rng.uniform(380, 760)
        w, h = rng.uniform(280, 720), rng.uniform(24, 64)
        c.draw.ellipse(c.box(x, y, w, h), fill=(*_hex(p["fog"]), rng.randint(60, 120)))
    _skyline(c, rng, 1120, 120, 360, _hex(p["fog"]), 210, windows=True, layer_blur=3)
    _skyline(c, rng, 1240, 160, 500, _hex(p["sky"][1]), 245, windows=True, layer_blur=1)
    _skyline(c, rng, 1380, 200, 620, (4, 7, 12), 255, windows=True)
    # neon billboards
    _neon_sign(c, 160, 900, "雾", _hex(p["accent"]), 72, True, 16)
    _neon_sign(c, 910, 1030, "梦", _hex(p["accent2"]), 54, True, 12)
    c.draw.rectangle(c.box(858, 995, 104, 8), fill=(*_hex(p["accent2"]), 175))
    # distant rain haze
    haze = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    hd.rectangle(c.box(0, 1150, 1080, 500), fill=(*_hex(p["fog"]), 50))
    haze = haze.filter(ImageFilter.GaussianBlur(28 * c.s))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), haze).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    # rooftop
    roof = _hex(p["ink"])
    c.polygon([(0, 1500), (1080, 1410), (1080, 1920), (0, 1920)], (*roof, 255))
    c.draw.polygon(
        [(0, 1500 * c.s), (1080 * c.s, 1410 * c.s), (1080 * c.s, 1920 * c.s), (0, 1920 * c.s)],
        fill=(*roof, 255),
    )
    for i in range(7):
        y = 1510 + i * 58
        c.line([(0, y), (1080, y - 85)], (*_hex(p["sky"][2]), 45), 2)
    for i in range(6):
        x = 80 + i * 210
        c.line([(x, 1500), (x * 1.3 - 110, 1920)], (*_hex(p["sky"][2]), 26), 2)
    # railing
    c.line([(0, 1440), (1080, 1355)], (*_hex(p["sky"][2]), 210), 8)
    c.line([(0, 1492), (1080, 1407)], (*_hex(p["sky"][2]), 150), 3)
    for x in range(40, 1100, 92):
        c.line([(x, 1440 - x * 0.078), (x, 1580 - x * 0.078)], (*_hex(p["sky"][2]), 170), 4)
    # puddles / reflections
    c.draw.ellipse(c.box(530, 1620, 500, 66), fill=(14, 25, 34, 190))
    c.draw.ellipse(c.box(640, 1630, 260, 30), fill=(*_hex(p["accent"]), 55))
    c.draw.ellipse(c.box(80, 1740, 280, 36), fill=(*_hex(p["accent2"]), 30))
    # a faint ring framing the confrontation
    c.draw.ellipse(c.box(480, 780, 520, 520), outline=(*_hex(p["accent"]), 26), width=max(1, int(2 * c.s)))
    c.draw.ellipse(c.box(515, 815, 450, 450), outline=(*_hex(p["accent2"]), 18), width=max(1, int(1.4 * c.s)))
    # signage glow spill
    c.glow((160, 960), 400, _hex(p["accent"]), 0.20)
    c.glow((930, 1080), 360, _hex(p["accent2"]), 0.16)
    _rain(c, rng, 240, 90)
    # foreground vignette shapes
    c.draw.polygon(
        [(0, 1830 * c.s), (250 * c.s, 1760 * c.s), (0, 1920 * c.s)],
        fill=(0, 0, 0, 170),
    )
    return c


def scene_alley(c: Canvas, rng):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, [p["sky"][1], p["sky"][0], p["ink"]], [0, 0.45, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    vx, vy = 520, 930
    # walls
    c.polygon([(0, 0), (vx, vy), (vx, 1920), (0, 1920)], _hex(p["ink"]))
    c.polygon([(1080, 0), (vx, vy), (vx, 1920), (1080, 1920)], _hex(p["sky"][1]))
    c.glow((vx, vy), 500, _hex(p["halo"]), 0.32)
    # perspective panels and pipes
    for i in range(1, 9):
        t = i / 9
        lx = vx * (1 - t)
        c.line([(0, 80 + i * 180), (vx, vy + i * 20)], (*_hex(p["sky"][2]), 45), 2)
        c.line([(1080, 120 + i * 170), (vx, vy + i * 20)], (*_hex(p["sky"][2]), 40), 2)
    for i in range(4):
        y = 200 + i * 330
        c.line([(vx - 30 - i * 30, y), (vx - 260 - i * 70, y + 90 + i * 60)], (*_hex(p["sky"][2]), 100), 7)
    # neon strips
    for x, y, w, h, col in [
        (90, 280, 12, 520, p["accent"]),
        (980, 360, 10, 460, p["accent2"]),
        (760, 660, 180, 8, p["accent"]),
    ]:
        c.rect((x, y, w, h), (*_hex(col), 215))
        c.glow((x + w / 2, y + h / 2), 200, _hex(col), 0.35)
    _neon_sign(c, 860, 740, "記", _hex(p["accent"]), 64, True, 16)
    _neon_sign(c, 180, 880, "忆", _hex(p["accent2"]), 48, True, 14)
    # air conditioners / boxes
    for x, y, w, h in [(70, 1030, 150, 100), (900, 980, 128, 90), (230, 1160, 90, 70)]:
        c.rect((x, y, w, h), (*_hex(p["ink"]), 255))
        c.draw.rectangle(c.box(x, y, w, h), outline=(*_hex(p["sky"][2]), 160), width=max(1, int(2 * c.s)))
        for k in range(4):
            c.line([(x + 12, y + 18 + k * 15), (x + w - 12, y + 18 + k * 15)], (*_hex(p["sky"][2]), 90), 2)
    # wet ground
    c.polygon([(0, 1470), (vx, 1160), (1080, 1440), (1080, 1920), (0, 1920)], (3, 5, 9, 255))
    for i in range(5):
        y = 1530 + i * 80
        c.line([(0, y), (1080, y + 160)], (*_hex(p["sky"][2]), 35), 2)
    c.draw.ellipse(c.box(250, 1610, 560, 100), fill=(*_hex(p["accent"]), 42))
    c.draw.ellipse(c.box(570, 1710, 380, 70), fill=(*_hex(p["accent2"]), 36))
    c.glow((540, 1500), 500, _hex(p["halo"]), 0.18)
    _rain(c, rng, 260, 95)
    return c


def scene_lab(c: Canvas, rng, door=False):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, [p["sky"][0], "#07141C", "#020609"], [0, 0.5, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    cx, cy = 610, 760
    c.glow((cx, cy), 760, _hex(p["accent2"]), 0.26)
    c.glow((cx, cy), 340, (220, 255, 250), 0.30)
    # wall grid
    for x in range(0, 1081, 60):
        c.line([(x, 0), (x, 1450)], (*_hex(p["accent2"]), 12), 1)
    for y in range(0, 1451, 60):
        c.line([(0, y), (1080, y)], (*_hex(p["accent2"]), 10), 1)
    # server racks
    for side in (0, 1):
        x0 = 0 if side == 0 else 930
        w = 170
        c.rect((x0, 230, w, 1180), (7, 12, 17, 245))
        for y in range(260, 1380, 44):
            c.line([(x0 + 14, y), (x0 + w - 14, y)], (*_hex(p["accent2"]), 55), 2)
            for k in range(3):
                if rng.random() < 0.65:
                    col = _hex(rng.choice([p["accent2"], p["accent"], p["warm"]]))
                    c.draw.ellipse(c.box(x0 + 18 + k * 18, y - 9, 5, 5), fill=(*col, 210))
        c.line([(x0 + 12, 230), (x0 + 12, 1410)], (*_hex(p["accent2"]), 90), 3)
    # core rings
    for i, r in enumerate([260, 212, 170, 132]):
        c.draw.ellipse(
            c.box(cx - r, cy - r, r * 2, r * 2),
            outline=(*_hex(p["accent2"]), 80 if i % 2 == 0 else 150),
            width=max(1, int((2 if i % 2 else 5) * c.s)),
        )
    for i in range(28):
        a = rng.uniform(0, math.tau)
        r1, r2 = rng.uniform(150, 240), rng.uniform(260, 300)
        c.line(
            [
                (cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                (cx + math.cos(a) * r2, cy + math.sin(a) * r2),
            ],
            (*_hex(p["accent2"]), 60),
            2,
        )
    c.draw.ellipse(c.box(cx - 92, cy - 92, 184, 184), fill=(*_hex(p["accent2"]), 25))
    c.draw.ellipse(c.box(cx - 30, cy - 30, 60, 60), fill=(225, 255, 252, 230))
    c.glow((cx, cy), 120, (210, 255, 250), 0.75)
    # cables
    for i in range(5):
        sx = 140 + i * 35
        c.line(
            [(sx, 1340), (sx + 80, 1180 + i * 10), (cx - 100, 1030), (cx - 40, cy + 80)],
            (*_hex(p["accent2"]), 70),
            4,
        )
    # desk / holographic panel
    c.polygon([(0, 1390), (1080, 1340), (1080, 1920), (0, 1920)], (4, 8, 12, 255))
    c.line([(0, 1390), (1080, 1340)], (*_hex(p["accent2"]), 130), 4)
    c.polygon([(170, 1450), (500, 1415), (560, 1630), (190, 1680)], (13, 33, 40, 210))
    c.polygon([(620, 1410), (900, 1385), (950, 1580), (650, 1620)], (13, 33, 40, 180))
    for i in range(12):
        y = 1460 + i * 14
        c.line([(210, y), (210 + rng.randint(60, 260), y - 3)], (*_hex(p["accent2"]), rng.randint(40, 150)), 2)
    # door light
    if door:
        c.rect((390, 330, 300, 1010), (2, 3, 5, 255))
        c.rect((414, 354, 252, 986), (*_hex(p["fog"]), 240))
        c.glow((540, 840), 420, _hex(p["accent"]), 0.42)
        c.draw.rectangle(c.box(414, 354, 252, 986), outline=(*_hex(p["accent"]), 160), width=max(1, int(3 * c.s)))
    c.glow((540, 1740), 520, _hex(p["accent2"]), 0.10)
    c.img = scanlines(c.img, alpha=5, gap=4)
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    return c


def scene_memory(c: Canvas, rng):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, ["#E8E2D4", "#C9CDCA", "#8C9A9E", "#2E3C42"], [0, 0.35, 0.7, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    vx, vy = 540, 930
    # corridor perspective
    c.polygon([(0, 0), (vx, vy), (vx, 1920), (0, 1920)], (214, 216, 207, 255))
    c.polygon([(1080, 0), (vx, vy), (vx, 1920), (1080, 1920)], (181, 190, 187, 255))
    c.polygon([(0, 0), (1080, 0), (vx, vy)], (244, 241, 230, 255))
    c.polygon([(0, 1920), (vx, vy), (1080, 1920)], (58, 71, 75, 255))
    # wall panels / doors
    for i in range(1, 7):
        t = i / 7
        x = vx - 540 * t
        y_top = vy - 930 * t
        y_bot = vy + 990 * t
        c.line([(x, y_top), (x, y_bot)], (40, 56, 60, 90), 2)
        c.line([(vx + (1080 - vx) * t, y_top), (vx + (1080 - vx) * t, y_bot)], (40, 56, 60, 70), 2)
    for side in (0, 1):
        for i in range(1, 5):
            t = i / 5.4
            x0 = 0 + (vx - 120) * t if side == 0 else 1080 - (1080 - vx - 120) * t
            c.rect(
                c.box(x0 - 50, 300 + i * 120 - t * 80, 100, 300 + t * 100),
                fill=(52, 66, 69, 40),
            )
    # floor reflection / lines
    for i in range(12):
        x = rng.uniform(0, 1080)
        c.line([(x, 1920), (vx + rng.uniform(-70, 70), vy)], (219, 225, 215, 20), 2)
    # red alarm
    c.glow((150, 380), 360, (255, 44, 44), 0.55)
    c.glow((960, 540), 300, (255, 44, 44), 0.35)
    c.rect((0, 210, 1080, 10), (255, 57, 48, 190))
    c.rect((0, 1880, 1080, 8), (255, 57, 48, 130))
    # glitch bands
    for i in range(6):
        y = rng.uniform(200, 1700)
        h = rng.uniform(6, 26)
        c.rect((0, y, 1080, h), (*_hex(p["accent2"]), rng.randint(12, 42)))
    # particles
    for _ in range(90):
        x, y = rng.uniform(0, 1080), rng.uniform(0, 1800)
        c.draw.ellipse(c.box(x, y, 2, 2), fill=(255, 255, 244, rng.randint(60, 200)))
    return c


def scene_chip(c: Canvas, rng, prop=False):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, ["#030407", "#071018", "#030407"], [0, 0.5, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    for i in range(12):
        c.glow((rng.uniform(0, 1080), rng.uniform(200, 1700)), rng.uniform(40, 220), _hex(rng.choice([p["accent"], p["accent2"]])), rng.uniform(0.05, 0.16))
    # giant chip, slight perspective
    layer = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = 540, 900
    pts = [(cx - 260, cy - 390), (cx + 290, cy - 320), (cx + 220, cy + 390), (cx - 330, cy + 310)]
    d.polygon([(x * c.s, y * c.s) for x, y in pts], fill=(10, 20, 25, 245), outline=(*_hex(p["accent2"]), 255))
    d.line([(x * c.s, y * c.s) for x, y in pts + [pts[0]]], fill=(*_hex(p["accent2"]), 220), width=max(2, int(4 * c.s)))
    inner = [(cx - 205, cy - 315), (cx + 220, cy - 260), (cx + 165, cy + 300), (cx - 255, cy + 240)]
    d.polygon([(x * c.s, y * c.s) for x, y in inner], fill=(8, 32, 39, 255), outline=(*_hex(p["accent2"]), 100))
    for i in range(8):
        y = cy - 240 + i * 70
        d.line([(cx - 180) * c.s, y * c.s, (cx + 120) * c.s, (y - 12) * c.s], fill=(*_hex(p["accent2"]), 45), width=max(1, int(2 * c.s)))
    # contact pads
    for i in range(7):
        x = cx - 330 + i * 95
        d.rectangle([(x) * c.s, (cy + 310) * c.s, (x + 55) * c.s, (cy + 390 + i * 4) * c.s], fill=(*_hex(p["warm"]), 180))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), layer).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    c.glow((540, 860), 560, _hex(p["accent2"]), 0.18)
    c.glow((540, 1030), 320, _hex(p["accent"]), 0.24)
    # red countdown
    c.text((540, 730), "00:07", 132, (*_hex(p["accent"]), 235), "display", "mm", 0, "center")
    c.text((540, 800), "MEMORY  /  UNKNOWN", 17, (220, 235, 230, 150), "light", "mm", 0, "center")
    # hand silhouette bottom right
    hand = [(720, 1920), (770, 1460), (840, 1370), (910, 1420), (880, 1530), (970, 1640), (1080, 1700), (1080, 1920)]
    c.polygon(hand, (2, 3, 5, 255))
    c.line([(770, 1460), (840, 1370), (910, 1420), (880, 1530)], (*_hex(p["accent2"]), 75), 3)
    _rain(c, rng, 80, 50)
    return c


def scene_apartment(c: Canvas, rng):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, ["#0B0D13", "#131C27", "#090B10"], [0, 0.45, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    # window with city bokeh
    c.rect((80, 240, 650, 830), (2, 4, 8, 255))
    c.rect((100, 260, 610, 790), (23, 39, 57, 255))
    for i in range(26):
        x, y = rng.uniform(110, 690), rng.uniform(300, 1010)
        r = rng.uniform(4, 26)
        col = _hex(rng.choice(p["window"]))
        c.draw.ellipse(c.box(x, y, r, r), fill=(*col, rng.randint(30, 130)))
    _skyline(c, rng, 1050, 80, 220, (8, 14, 21), 220, True, 4)
    c.glow((390, 620), 360, _hex(p["warm"]), 0.12)
    # blinds / frame
    c.rect((70, 230, 18, 850), (0, 0, 0, 255))
    c.rect((730, 230, 18, 850), (0, 0, 0, 255))
    c.rect((70, 230, 680, 18), (0, 0, 0, 255))
    c.line([(80, 260), (80, 1080)], (*_hex(p["sky"][2]), 90), 2)
    for i in range(8):
        c.line([(80, 280 + i * 92), (730, 250 + i * 92)], (*_hex(p["sky"][2]), 18), 2)
    # lamp glow
    c.glow((830, 1120), 300, _hex(p["warm"]), 0.38)
    c.line([(830, 1150), (830, 1470)], (16, 18, 22, 255), 10)
    c.draw.polygon([(760, 1090), (900, 1090), (860, 1160), (800, 1160)], (235, 198, 138, 245))
    # desk
    c.polygon([(0, 1440), (1080, 1390), (1080, 1920), (0, 1920)], (10, 13, 18, 255))
    c.line([(0, 1440), (1080, 1390)], (*_hex(p["sky"][2]), 100), 3)
    for i in range(4):
        c.draw.ellipse(c.box(420 + i * 45, 1560 + i * 8, 20, 20), fill=(*_hex(p["accent"]), 120))
    c.rect((150, 1480, 200, 110), (16, 22, 28, 255))
    c.text((250, 1490), "03:17", 46, (*_hex(p["accent2"]), 180), "light", "la")
    return c


def scene_void(c: Canvas, rng):
    p = c.p
    c.img = vertical_gradient(c.w, c.h, ["#020308", "#070C14", "#020308"], [0, 0.6, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    cx, cy = 540, 840
    c.glow((cx, cy), 760, _hex(p["halo"]), 0.18)
    for i in range(9):
        r = 120 + i * 80
        c.draw.ellipse(
            c.box(cx - r, cy - r * 0.62, r * 2, r * 1.24),
            outline=(*_hex(p["accent2"] if i % 2 else p["accent"]), max(12, 70 - i * 6)),
            width=2,
        )
    # floating shards
    for i in range(18):
        x, y = rng.uniform(100, 980), rng.uniform(180, 1700)
        size = rng.uniform(14, 80)
        pts = [
            (x, y),
            (x + size, y - size * 0.3),
            (x + size * 0.7, y + size * 0.8),
            (x - size * 0.2, y + size * 0.5),
        ]
        c.polygon(pts, (*_hex(p["accent2"] if i % 3 else p["paper"]), rng.randint(20, 75)))
        c.line(pts + [pts[0]], (*_hex(p["accent2"]), 90), 2)
    for i in range(80):
        x, y = rng.uniform(0, 1080), rng.uniform(0, 1800)
        c.draw.ellipse(c.box(x, y, 2, 2), fill=(220, 240, 235, rng.randint(40, 160)))
    c.text((540, 1560), "00:07", 90, (*_hex(p["accent"]), 160), "display", "mm")
    return c


# ---------------------------------------------------------------------------
# Characters


def _find_character(project, name_or_id):
    for char in project.get("characters", []):
        if char.get("id") == name_or_id or char.get("name") == name_or_id:
            return char
    return {
        "id": name_or_id,
        "name": name_or_id,
        "accent": "#63F2DE",
        "color": "#1A1D24",
    }


def _figure_mask(c: Canvas, mask, x, ground, height, pose, facing, hair="bob", back=False):
    """Draw one graphic-novel silhouette in normalized body units."""
    md = ImageDraw.Draw(mask)
    s = c.s
    h = height
    lean = 0.0
    if pose == "run":
        lean = 0.055 * facing
    elif pose == "reach":
        lean = 0.02 * facing
    cx = x + lean * h
    head_r = h * 0.080
    head_y = ground - h * 0.862

    def pt(px, py):
        return ((cx + px * h) * s, (ground + py * h) * s)

    def ellipse(px, py, rx, ry, fill=255):
        md.ellipse(
            ((cx + (px - rx) * h) * s, (ground + (py - ry) * h) * s,
             (cx + (px + rx) * h) * s, (ground + (py + ry) * h) * s),
            fill=fill,
        )

    def line(points, width, fill=255):
        md.line([pt(px, py) for px, py in points], fill=fill, width=max(1, int(width * h * s)), joint="curve")

    # Legs and boots -------------------------------------------------------
    if pose != "sit":
        if pose == "run":
            line([(-0.045, -0.46), (-0.15, -0.245), (-0.30, -0.10)], 0.055)
            line([(0.04, -0.46), (0.17, -0.30), (0.27, -0.055)], 0.052)
            # boot tips
            md.polygon([pt(-0.31, -0.10), pt(-0.24, -0.10), pt(-0.25, 0.005), pt(-0.35, 0.005)], fill=255)
            md.polygon([pt(0.26, -0.055), pt(0.33, -0.055), pt(0.34, 0.005), pt(0.25, 0.005)], fill=255)
        else:
            # contrapposto: one leg carries the weight
            line([(-0.038, -0.46), (-0.055, -0.25), (-0.075, -0.035)], 0.052)
            line([(0.045, -0.46), (0.085, -0.24), (0.105, -0.028)], 0.050)
            md.ellipse([*pt(-0.105, -0.055), *pt(-0.015, 0.012)], fill=255)
            md.ellipse([*pt(0.075, -0.048), *pt(0.165, 0.012)], fill=255)

    # Coat / torso ---------------------------------------------------------
    shoulder_y = -0.735
    hem_y = -0.185
    torso = [
        (-0.115, shoulder_y),
        (-0.145, -0.62),
        (-0.125, -0.47),
        (-0.175, hem_y + 0.02),
        (-0.10, hem_y - 0.015),
        (-0.02, hem_y + 0.035),
        (0.07, hem_y - 0.005),
        (0.16, hem_y + 0.025),
        (0.125, -0.47),
        (0.145, -0.62),
        (0.112, shoulder_y),
    ]
    md.polygon([pt(px, py) for px, py in torso], fill=255)
    # high collar
    md.polygon([pt(-0.078, -0.79), pt(-0.115, -0.71), pt(-0.018, -0.665), pt(0.0, -0.79)], fill=255)
    md.polygon([pt(0.078, -0.79), pt(0.115, -0.71), pt(0.018, -0.665), pt(0.0, -0.79)], fill=255)

    # Run coat tails -------------------------------------------------------
    if pose == "run":
        md.polygon(
            [pt(-0.13, -0.44), pt(-0.40, -0.28), pt(-0.24, -0.20), pt(-0.06, -0.30)],
            fill=255,
        )
        md.polygon(
            [pt(0.12, -0.43), pt(0.32, -0.25), pt(0.23, -0.16), pt(0.05, -0.28)],
            fill=255,
        )

    # Arms -----------------------------------------------------------------
    if pose == "reach":
        line([(-0.095, -0.71), (-0.15, -0.54), (-0.13, -0.38)], 0.044)
        line([(0.09, -0.71), (0.18, -0.64), (0.37, -0.66)], 0.046)
        ellipse(0.395, -0.66, 0.032, 0.030)
    elif pose == "run":
        line([(-0.10, -0.71), (-0.23, -0.60), (-0.17, -0.50)], 0.044)
        line([(0.10, -0.71), (0.24, -0.61), (0.17, -0.49)], 0.044)
    elif pose != "sit":
        line([(-0.10, -0.70), (-0.155, -0.55), (-0.125, -0.40)], 0.043)
        line([(0.10, -0.70), (0.155, -0.55), (0.125, -0.40)], 0.043)

    # Neck / head ----------------------------------------------------------
    if pose != "sit":
        md.rectangle([*pt(-0.035, -0.80), *pt(0.035, -0.75)], fill=255)
    ellipse(0, -0.862, 0.080, 0.090)

    # Hair silhouette ------------------------------------------------------
    if hair in ("long", "male"):
        if back:
            md.ellipse([*pt(-0.092, -0.955), *pt(0.092, -0.765)], fill=255)
        md.polygon(
            [
                pt(-0.095, -0.81), pt(-0.115, -0.90), pt(-0.08, -0.985),
                pt(0.02, -1.005), pt(0.095, -0.95), pt(0.118, -0.87),
                pt(0.09, -0.80), pt(0.075, -0.88), pt(0.02, -0.925),
                pt(-0.06, -0.90),
            ],
            fill=255,
        )
        # swept fringe
        md.polygon(
            [pt(-0.08, -0.93), pt(0.01, -0.995), pt(0.10, -0.94), pt(0.07, -0.89), pt(-0.01, -0.925)],
            fill=255,
        )
        # side strand
        line([(-0.09, -0.94), (-0.12, -0.82), (-0.10, -0.72)], 0.018)
    else:
        # asymmetric bob with jagged ends
        md.polygon(
            [
                pt(-0.10, -0.83), pt(-0.118, -0.93), pt(-0.085, -1.0),
                pt(0.015, -1.015), pt(0.10, -0.97), pt(0.118, -0.88),
                pt(0.10, -0.80), pt(0.082, -0.84), pt(0.085, -0.77),
                pt(0.045, -0.81), pt(0.015, -0.76), pt(-0.02, -0.81),
                pt(-0.06, -0.76), pt(-0.075, -0.82), pt(-0.10, -0.78),
            ],
            fill=255,
        )
        if back:
            md.ellipse([*pt(-0.09, -0.955), *pt(0.09, -0.77)], fill=255)
        # long side pieces
        md.polygon([pt(-0.10, -0.90), pt(-0.125, -0.80), pt(-0.095, -0.68), pt(-0.065, -0.82)], fill=255)
        md.polygon([pt(0.09, -0.91), pt(0.12, -0.82), pt(0.095, -0.70), pt(0.06, -0.82)], fill=255)
        # stray strands
        line([(0.08, -0.98), (0.15, -0.90), (0.14, -0.82)], 0.008)
        line([(-0.08, -0.97), (-0.14, -0.89), (-0.13, -0.83)], 0.007)

    # a noir fedora for Shen Yan
    if hair == "male" and not back:
        brim_y = -0.948
        md.ellipse([*pt(-0.145, brim_y - 0.012), *pt(0.145, brim_y + 0.022)], fill=255)
        md.polygon([pt(-0.095, brim_y + 0.006), pt(-0.072, -1.035), pt(0.055, -1.04), pt(0.09, brim_y + 0.004)], fill=255)
        md.line([*pt(-0.07, -1.0), *pt(0.06, -1.003)], fill=255, width=max(1, int(0.012 * h * s)))

    # Child proportion tweak: bigger head, shorter coat
    if hair == "child":
        md.ellipse([*pt(-0.085, -0.94), *pt(0.085, -0.77)], fill=255)
        md.polygon(
            [
                pt(-0.12, -0.76), pt(0.12, -0.76), pt(0.15, -0.42),
                pt(0.08, -0.35), pt(-0.08, -0.35), pt(-0.15, -0.42),
            ],
            fill=255,
        )


def draw_figure(c: Canvas, char, x, ground, height, pose="stand", facing=1, back=False, ghost=False):
    p = c.p
    accent = _hex(char.get("accent", p["accent2"]))
    body = _mix(_hex(char.get("color", "#14171E")), _hex(p["ink"]), 0.945)
    if ghost:
        body = _mix(body, _hex(p["accent2"]), 0.25)
    mask = Image.new("L", (c.w, c.h), 0)
    hair = "bob"
    cid = str(char.get("id", ""))
    name = str(char.get("name", ""))
    if cid in ("shenyan", "stranger") or name in ("沈砚", "陌生人"):
        hair = "male"
    if cid == "girl" or name in ("小女孩", "女孩"):
        hair = "child"
    _figure_mask(c, mask, x, ground, height, pose, facing, hair, back)

    # contact shadow
    sh = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(
        c.box(x - height * 0.20, ground - height * 0.018, height * 0.40, height * 0.042),
        fill=(0, 0, 0, 175),
    )
    sh = sh.filter(ImageFilter.GaussianBlur(7 * c.s))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), sh).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")

    # directional rim: edge pixels weighted toward the lit side
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.1 * c.s))
    arr = np.asarray(edge, dtype=np.float32) / 255.0
    w = c.w
    if facing >= 0:
        grad = np.linspace(0.10, 1.0, w, dtype=np.float32)[None, :]
    else:
        grad = np.linspace(1.0, 0.10, w, dtype=np.float32)[None, :]
    yy = np.linspace(0.55, 1.0, c.h, dtype=np.float32)[:, None]
    rim_alpha = np.clip(arr * grad * yy * 1.15, 0, 1)
    rim_layer = Image.new("RGBA", (c.w, c.h), (*accent, 0))
    rim_layer.putalpha(Image.fromarray((rim_alpha * 255).astype(np.uint8), "L"))
    # soft outer glow
    broad_alpha = mask.filter(ImageFilter.GaussianBlur(20 * c.s)).point(lambda v: int(v * 0.07))
    broad = Image.new("RGBA", (c.w, c.h), (*accent, 0))
    broad.putalpha(broad_alpha)
    c.img = Image.alpha_composite(c.img.convert("RGBA"), broad).convert("RGB")
    c.img = Image.alpha_composite(c.img.convert("RGBA"), rim_layer).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")

    # body fill
    fill = Image.new("RGBA", (c.w, c.h), (*body, 255))
    fill.putalpha(mask.point(lambda v: int(v * (0.55 if ghost else 1.0))))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), fill).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")

    # interior / clothing details, clipped to the silhouette
    detail = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(detail)

    def dp(px, py):
        return ((x + px * height) * c.s, (ground + py * height) * c.s)

    def dline(points, color, width=2):
        dd.line([dp(px, py) for px, py in points], fill=color, width=max(1, int(width * c.s)), joint="curve")

    paper = _hex(p["paper"])
    paper = _hex(p["paper"])
    # only two tiny light sources break the silhouette
    if cid == "linwu" or name == "林雾":
        dd.ellipse([*dp(-0.079, -0.888), *dp(-0.050, -0.858)], fill=(4, 6, 8, 255))
        dd.ellipse([*dp(-0.071, -0.882), *dp(-0.056, -0.863)], fill=(*accent, 255))
        dd.ellipse([*dp(-0.078, -0.89), *dp(-0.048, -0.855)], fill=(*accent, 35))
    if hair == "male":
        # the chip in his hand, and one red catchlight under the brim
        c.glow((x + facing * height * 0.135, ground - height * 0.40), 60 * c.s, accent, 0.75)
        dd.ellipse([*dp(0.115, -0.425), *dp(0.155, -0.385)], fill=(*accent, 220))
        dd.ellipse([*dp(0.028, -0.872), *dp(0.068, -0.858)], fill=(*accent, 235))
    detail.putalpha(ImageChops.multiply(detail.getchannel("A"), mask))
    c.img = Image.alpha_composite(c.img.convert("RGBA"), detail).convert("RGB")
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    # wet shoulder glint
    c.line(
        [(x - height * 0.10, ground - height * 0.72), (x - height * 0.02, ground - height * 0.74)],
        (*accent, 70),
        2,
    )


def draw_eye_macro(c: Canvas, char, rng):
    """Tight, graphic eye insert. The pupil reflects the memory corridor."""
    p = c.p
    accent = _hex(char.get("accent", p["accent2"]))
    paper = _hex(p["paper"])
    c.img = vertical_gradient(c.w, c.h, ["#08090A", "#1A1A1B", "#0B0B0C"], [0, 0.3, 1])
    c.draw = ImageDraw.Draw(c.img, "RGBA")
    c.glow((540, 920), 780, accent, 0.09)
    # full-frame skin
    c.draw.rectangle(c.box(0, 0, 1080, 1920), fill=(31, 30, 30, 255))
    c.draw.ellipse(c.box(-160, 80, 1400, 1500), fill=(36, 34, 33, 255))
    # cheek and jaw shaping
    c.polygon([(0, 1330), (300, 1220), (720, 1260), (1080, 1540), (1080, 1920), (0, 1920)], (24, 23, 23, 255))
    c.polygon([(0, 0), (1080, 0), (1080, 520), (850, 620), (640, 480), (380, 590), (120, 480), (0, 570)], (6, 7, 9, 255))
    # hair strands crossing top
    for i in range(9):
        sx = 20 + i * 128 + rng.uniform(-30, 30)
        ex = sx + 80
        c.line([(sx, -30), (sx + 100, 260), (ex, 500 + rng.uniform(-70, 130))], (6, 7, 9, 255), rng.choice([22, 28, 34]))
    # eye socket
    c.draw.ellipse(c.box(-80, 610, 1240, 840), fill=(13, 14, 15, 235))
    # huge eye opening, cropped by the frame
    upper = [(-40, 1000), (150, 810), (400, 700), (680, 690), (920, 780), (1120, 980)]
    lower = [(1120, 980), (930, 1190), (680, 1300), (400, 1290), (150, 1160), (-40, 1000)]
    c.polygon(upper + lower, (4, 5, 7, 255))
    c.polygon([(80, 1000), (220, 860), (440, 770), (690, 775), (900, 860), (1010, 1000), (870, 1130), (660, 1210), (410, 1200), (210, 1100)], (105, 109, 105, 255))
    c.polygon([(80, 1000), (240, 870), (460, 790), (690, 800), (880, 875), (970, 1000), (830, 1010), (620, 940), (400, 950), (220, 1030)], (141, 142, 134, 255))
    # iris
    ix, iy, ir = 560, 960, 300
    c.draw.ellipse(c.box(ix - ir, iy - ir, ir * 2, ir * 2), fill=(13, 45, 49, 255))
    for k in range(64):
        a = k / 64 * math.tau
        c.line(
            [(ix + math.cos(a) * 86, iy + math.sin(a) * 86), (ix + math.cos(a) * (ir - 8), iy + math.sin(a) * (ir - 8))],
            (*accent, 40 if k % 2 else 100),
            2 if k % 2 else 3,
        )
    c.draw.ellipse(c.box(ix - ir + 8, iy - ir + 8, ir * 2 - 16, ir * 2 - 16), outline=(*accent, 210), width=max(2, int(5 * c.s)))
    c.draw.ellipse(c.box(ix - ir + 38, iy - ir + 38, ir * 2 - 76, ir * 2 - 76), outline=(*paper, 24), width=max(1, int(2 * c.s)))
    c.draw.ellipse(c.box(ix - 126, iy - 126, 252, 252), fill=(1, 3, 4, 255))
    c.draw.ellipse(c.box(ix - 112, iy - 112, 224, 224), outline=(*accent, 65), width=max(1, int(3 * c.s)))
    # corridor reflected in the iris
    c.draw.rectangle(c.box(ix - 245, iy - 230, 250, 110), fill=(*paper, 45))
    c.draw.rectangle(c.box(ix - 120, iy - 230, 12, 110), fill=(*_hex(p["accent"]), 210))
    c.draw.rectangle(c.box(ix + 25, iy - 230, 6, 110), fill=(*paper, 100))
    c.draw.ellipse(c.box(ix - 220, iy - 244, 110, 110), fill=(250, 248, 236, 235))
    c.draw.ellipse(c.box(ix + 95, iy + 92, 48, 48), fill=(*accent, 190))
    c.draw.arc(c.box(ix - ir + 60, iy - ir + 60, ir * 2 - 120, ir * 2 - 120), 200, 340, fill=(*paper, 60), width=max(1, int(5 * c.s)))
    # eyelids / lashes
    c.line(upper, (4, 5, 7, 255), 42)
    c.line([(60, 990), (230, 840), (450, 760), (680, 760), (900, 840), (1040, 980)], (*paper, 55), 4)
    c.line(lower, (4, 5, 7, 255), 24)
    c.line([(90, 1080), (320, 1200), (620, 1230), (880, 1110)], (*accent, 55), 3)
    for i in range(24):
        t = i / 23
        bx = -20 + t * 1130
        by = 1000 - math.sin(t * math.pi) * 280
        length = 30 + math.sin(t * math.pi) * 50
        c.line([(bx, by), (bx + 12, by - length * 0.6), (bx + 28, by - length)], (3, 4, 5, 235), rng.choice([5, 6, 7]))
    # brow
    c.line([(-40, 650), (190, 550), (450, 520), (730, 560), (1010, 690)], (4, 5, 6, 255), 66)
    c.line([(60, 625), (280, 550), (520, 540)], (*paper, 30), 3)
    # tears and skin texture
    c.draw.ellipse(c.box(900, 1110, 78, 104), fill=(*accent, 50))
    c.draw.ellipse(c.box(928, 1126, 18, 28), fill=(245, 255, 250, 190))
    for _ in range(22):
        x, y = rng.uniform(40, 1040), rng.uniform(600, 1400)
        r = rng.uniform(1, 3.5)
        c.draw.ellipse(c.box(x, y, r, r * 1.7), fill=(225, 240, 235, rng.randint(25, 90)))
    # HUD
    return c


# ---------------------------------------------------------------------------
# Finishing and public API


def _comic_marks(c: Canvas, shot, rng):
    p = c.p
    # corner marks
    edge = _hex(p["paper"])
    for x, y, dx, dy in [(34, 34, 1, 1), (1046, 34, -1, 1), (34, 1886, 1, -1), (1046, 1886, -1, -1)]:
        c.line([(x, y), (x + dx * 34, y)], (*edge, 110), 2)
        c.line([(x, y), (x, y + dy * 34)], (*edge, 110), 2)
    # index
    c.text((1028, 1848), f"{shot.get('index', 1):02d}", 34, (*edge, 90), "light", "ra")
    c.text((50, 1848), "MANJU / LOCAL ENGINE", 13, (*edge, 70), "light", "la")
    # caption on the image, very small
    caption = shot.get("caption", "")
    if caption:
        c.text((50, 56), caption, 18, (*edge, 120), "light", "la")
    # halftone
    c.img = halftone_overlay(c.img, _hex(p["paper"]), alpha=10, spacing=max(5, int(6 * c.s)), dot=1.4 * c.s, seed=shot.get("index", 1))
    c.img = add_grain(c.img, seed=shot.get("index", 1), amount=3.5)


def render_panel(project: dict, episode: dict, shot: dict, out_path: str | Path, width: int = 1080) -> str:
    style = project.get("style", "neo_noir")
    palette = PALETTES.get(style, PALETTES["neo_noir"])
    import hashlib
    seed = int(hashlib.sha1(f"{project.get('id')}-{episode.get('id')}-{shot.get('id')}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    np.random.seed(seed % (2**32 - 1))
    c = Canvas(width, palette)
    scene = SCENE_ALIASES.get(shot.get("scene"), shot.get("scene", "rooftop"))
    if scene == "lab_door":
        scene_lab(c, rng, door=True)
    elif scene == "rooftop":
        scene_rooftop(c, rng)
    elif scene == "alley":
        scene_alley(c, rng)
    elif scene == "lab":
        scene_lab(c, rng)
    elif scene == "memory":
        scene_memory(c, rng)
    elif scene == "apartment":
        scene_apartment(c, rng)
    elif scene == "void":
        scene_void(c, rng)
    elif scene in ("chip", "prop"):
        scene_chip(c, rng)
    elif scene == "close":
        c.img = vertical_gradient(c.w, c.h, ["#020306", "#081018", "#020306"], [0, 0.5, 1])
        c.draw = ImageDraw.Draw(c.img, "RGBA")
    else:
        scene_rooftop(c, rng)

    chars = [_find_character(project, name) for name in shot.get("characters", [])]
    shot_type = shot.get("shot_type", "medium")
    focus = shot.get("focus", "")
    pose = shot.get("pose", "stand")

    if scene not in ("chip", "prop", "void") and shot_type == "close" and chars:
        draw_eye_macro(c, chars[0], rng)
    elif scene not in ("chip", "prop", "void") and chars:
        if shot_type == "wide":
            height = 430 if len(chars) == 1 else 610
            ground = 1745
            positions = [365, 705] if len(chars) > 1 else [805]
            if shot.get("scene") == "memory":
                height = 280
                ground = 1600
                positions = [560]
            for i, char in enumerate(chars[:2]):
                x = positions[i] if len(positions) > i else 500 + i * 190
                if len(chars) > 1 and focus == char.get("name"):
                    x = 690
                    height = 650
                draw_figure(
                    c, char, x, ground, height,
                    pose=pose, facing=-1 if i == 0 else 1, back=(pose == "stand_back"),
                )
        elif shot_type == "detail":
            draw_figure(c, chars[0], 660, 1860, 760, pose="reach", facing=-1)
        else:
            if len(chars) > 1:
                draw_figure(c, chars[0], 355, 1790, 680, pose=pose, facing=1, back=(pose == "stand_back"), ghost=False)
                draw_figure(c, chars[1], 735, 1780, 700, pose="stand", facing=-1, back=False)
            else:
                x = 540 if focus != "left" else 420
                draw_figure(c, chars[0], x, 1790, 760, pose=pose, facing=-1 if position_is_left(shot) else 1, back=(pose == "stand_back"))
    # foreground atmospheric particles
    for _ in range(18):
        x, y = rng.uniform(0, 1080), rng.uniform(0, 1800)
        r = rng.uniform(1, 4)
        c.draw.ellipse(c.box(x, y, r, r), fill=(230, 245, 240, rng.randint(20, 70)))
    if scene in ("lab", "lab_door") and shot.get("pose") == "sit":
        # a foreground console hides the seated body and adds depth
        c.polygon([(0, 1510), (240, 1435), (680, 1415), (1080, 1480), (1080, 1920), (0, 1920)], (3, 6, 9, 255))
        c.line([(0, 1510), (240, 1435), (680, 1415), (1080, 1480)], (*_hex(palette["accent2"]), 75), 3)
        c.line([(0, 1540), (1080, 1510)], (0, 0, 0, 180), 2)
        for i in range(3):
            c.draw.ellipse(c.box(840 + i * 34, 1560, 13, 13), fill=(*_hex(palette["accent"]), 80))
    c.img = bloom(c.img, radius=4 * c.s, amount=0.16)
    c.img = vignette(c.img, 0.48)
    _comic_marks(c, shot, rng)
    if shot.get("index") == 1 and shot.get("scene") != "chip":
        title = project.get("title", "")
        yy = 250
        for ch in title:
            c.text((64, yy), ch, 66, (*_hex(palette["paper"]), 92), "display", "la")
            yy += 76
        c.text((64, 212), f"EP.{episode.get('index', 1):02d}", 16, (*_hex(palette["accent"]), 190), "light", "la")
        c.line([(64, 244), (64, 244 + 76 * len(title))], (*_hex(palette["accent"]), 70), 1)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c.img.save(out_path, quality=94, subsampling=1)
    return str(out_path)


def position_is_left(shot) -> bool:
    return shot.get("focus") in ("left", "linwu") and shot.get("shot_type") == "medium"
