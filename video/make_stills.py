from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 2560, 1440
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
BUILD = ROOT / "build"
STILLS = BUILD / "stills"
STILLS.mkdir(parents=True, exist_ok=True)

BG = (8, 2, 3)
TEXT = (244, 236, 236)
MUTED = (169, 145, 148)
DIM = (117, 96, 99)
RED = (255, 59, 78)
RED_BRIGHT = (255, 113, 99)
RED_DEEP = (168, 7, 30)
LINE = (255, 82, 96)
CORE = PROJECT / "assets" / "turing-core.png"
PORTRAIT = PROJECT / "assets" / "turing-portrait.jpg"
PREVIEW = PROJECT / "preview.png"
PREVIEW_MOBILE = PROJECT / "preview-mobile.png"

FONT_MANROPE = ROOT / "fonts" / "Manrope.ttf"
FONT_UNBOUNDED = ROOT / "fonts" / "Unbounded.ttf"


def F(kind: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_MANROPE if kind == "manrope" else FONT_UNBOUNDED
    font = ImageFont.truetype(str(path), size)
    try:
        names = font.get_variation_names()
        wanted = weight.encode()
        if wanted in names:
            font.set_variation_by_name(weight)
    except Exception:
        pass
    return font


def tracked_width(draw: ImageDraw.ImageDraw, text: str, font, tracking: float) -> float:
    return sum(font.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


def tracked(
    draw: ImageDraw.ImageDraw,
    xy,
    text: str,
    font,
    fill,
    tracking: float = 0,
    center: bool = False,
    max_width: float | None = None,
):
    x, y = xy
    if center:
        width = tracked_width(draw, text, font, tracking)
        x -= width / 2
    if max_width and tracked_width(draw, text, font, tracking) > max_width:
        # Simple fallback for labels: reduce tracking.
        tracking = max(0, tracking - 1)
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking
    return x


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: float):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(
    draw: ImageDraw.ImageDraw,
    xy,
    text: str,
    font,
    fill,
    max_width: float,
    line_height: float | None = None,
    spacing: int = 10,
):
    x, y = xy
    lines = wrap(draw, text, font, max_width)
    if line_height is None:
        line_height = font.size * 1.35
    elif line_height < 3:
        line_height = font.size * line_height
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def background(focus=(0.72, 0.42), strength=1.0, grid=True, warm=1.0):
    y, x = np.mgrid[0:H, 0:W]
    xn = x / W
    yn = y / H
    base = np.zeros((H, W, 3), dtype=np.float32)
    base[..., 0] = 8
    base[..., 1] = 2
    base[..., 2] = 3

    # Main red atmosphere.
    for fx, fy, radius, intensity in [
        (focus[0], focus[1], 0.58, 0.42),
        (0.06, 0.12, 0.42, 0.20),
        (0.96, 0.92, 0.48, 0.16),
    ]:
        d = np.sqrt((xn - fx) ** 2 + (yn - fy) ** 2)
        glow = np.exp(-((d / radius) ** 2) * 2.2) * intensity * strength
        base[..., 0] += glow * 255 * warm
        base[..., 1] += glow * 33
        base[..., 2] += glow * 46

    # Faint horizontal falloff.
    base[..., 0] += np.clip(0.18 - yn * 0.16, 0, 0.18) * 20
    base = np.clip(base, 0, 255)

    # Vignette.
    vd = np.sqrt(((xn - 0.5) * 1.15) ** 2 + ((yn - 0.5) * 1.15) ** 2)
    vig = np.clip(1.12 - 0.82 * vd**1.8, 0.16, 1.0)
    base *= vig[..., None]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    if grid:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(overlay)
        for gx in range(0, W, 128):
            gd.line((gx, 0, gx, H), fill=(255, 90, 100, 4), width=1)
        for gy in range(0, H, 128):
            gd.line((0, gy, W, gy), fill=(255, 90, 100, 4), width=1)
        img = Image.alpha_composite(img, overlay)

    # Grain.
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 2.4, (H, W, 1))
    arr = np.array(img.convert("RGB"), dtype=np.float32) + noise
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return img


def glow(img: Image.Image, center, radius, color=(255, 40, 58), alpha=100, blur=70):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img, layer)


def circle_mask(size):
    mask = Image.new("L", (size * 4, size * 4), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def add_orb(img, center, size, rings=True, opacity=0.92, glow_alpha=82):
    cx, cy = center
    img = glow(img, (cx, cy), size * 0.7, alpha=glow_alpha, blur=int(size * 0.09))
    src = Image.open(CORE).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    orb = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    orb.paste(src, (0, 0), circle_mask(size))
    # Scan lines on the orb.
    scan = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scan)
    for y in range(0, size, 5):
        sd.line((0, y, size, y), fill=(0, 0, 0, 28), width=1)
    orb = Image.alpha_composite(orb, scan)
    if opacity < 1:
        alpha = orb.getchannel("A").point(lambda v: int(v * opacity))
        orb.putalpha(alpha)
    img.alpha_composite(orb, (cx - size // 2, cy - size // 2))

    if rings:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for rr, col, width in [
            (size * 0.52, (255, 80, 90, 50), 2),
            (size * 0.64, (255, 80, 90, 28), 1),
            (size * 0.78, (255, 80, 90, 18), 1),
        ]:
            d.ellipse((cx - rr, cy - rr * 0.46, cx + rr, cy + rr * 0.46), outline=col, width=width)
        img = Image.alpha_composite(img, layer)
    return img


def card(draw, box, fill=(19, 4, 7, 190), outline=(255, 82, 96, 62), radius=26, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def kicker(draw, x, y, number, label, color=RED):
    draw.ellipse((x, y + 3, x + 10, y + 13), fill=color)
    tracked(draw, (x + 24, y - 2), number, F("unbounded", "Medium", 18), (190, 160, 162), 3)
    tracked(draw, (x + 76, y - 2), label, F("unbounded", "Medium", 18), (190, 160, 162), 4)


def brand(draw, x, y, scale=1.0):
    color = (*RED, 255)
    r = 17 * scale
    cx, cy = x + r, y + r
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        draw.line(
            (cx + math.cos(rad) * 4 * scale, cy + math.sin(rad) * 4 * scale,
             cx + math.cos(rad) * r, cy + math.sin(rad) * r),
            fill=color,
            width=max(1, int(2 * scale)),
        )
    draw.ellipse((cx - 5 * scale, cy - 5 * scale, cx + 5 * scale, cy + 5 * scale), outline=color, width=max(1, int(2 * scale)))
    tracked(draw, (x + 52 * scale, y + 7 * scale), "TURING.", F("unbounded", "SemiBold", int(21 * scale)), TEXT, 3)


def footer(draw, text="ALAN TURING · 1912—1954", right="3'00\""):
    tracked(draw, (180, 1328), text, F("unbounded", "Medium", 16), (137, 111, 114), 4)
    tracked(draw, (W - 180 - tracked_width(draw, right, F("unbounded", "Medium", 16), 4), 1328), right, F("unbounded", "Medium", 16), (137, 111, 114), 4)


def add_corner_line(draw):
    draw.line((180, 112, 310, 112), fill=(255, 59, 78, 180), width=2)
    draw.line((W - 310, 112, W - 180, 112), fill=(255, 59, 78, 80), width=1)


def scene_title():
    img = background((0.72, 0.45), 1.15)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    brand(d, 180, 132, 1.2)
    tracked(d, (W - 700, 144), "ИСТОРИЯ ОДНОЙ ИДЕИ", F("unbounded", "Medium", 17), (196, 152, 154), 4)

    img = add_orb(img, (1890, 680), 980, opacity=0.82)
    d = ImageDraw.Draw(img)

    # Watermark
    tracked(d, (1560, 1040), "AI", F("unbounded", "Bold", 390), (255, 59, 78, 22), 0)

    kicker(d, 180, 360, "01", "НАЧАЛО", RED)
    d.text((180, 410), "АЛАН", font=F("manrope", "Bold", 210), fill=TEXT)
    d.text((180, 610), "ТЬЮРИНГ", font=F("manrope", "Bold", 210), fill=RED_BRIGHT)
    tracked(d, (186, 872), "ЧЕЛОВЕК, КОТОРЫЙ ПРИДУМАЛ ИИ", F("unbounded", "Medium", 40), TEXT, 2)
    d.line((186, 960, 1120, 960), fill=(255, 59, 78, 80), width=2)
    tracked(d, (186, 1000), "МАТЕМАТИК   ·   КРИПТОАНАЛИТИК   ·   ПИОНЕР ИИ", F("manrope", "SemiBold", 25), MUTED, 2)
    tracked(d, (186, 1160), "23.06.1912 — 07.06.1954", F("unbounded", "Medium", 22), RED_BRIGHT, 3)
    footer(d)
    return img


def scene_early():
    img = background((0.76, 0.38), 0.9)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "02", "ЛИЧНОСТЬ")
    tracked(d, (180, 210), "ОН ОПЕРЕДИЛ", F("manrope", "Bold", 122), TEXT, -1)
    tracked(d, (180, 338), "СВОЁ ВРЕМЯ", F("manrope", "Bold", 122), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 520),
        "Математик, логик и криптоаналитик. Его работа стала фундаментом информатики — задолго до первых электронных компьютеров.",
        F("manrope", "Medium", 34),
        MUTED,
        1080,
        1.55,
    )

    facts = [
        ("1912", "23 июня", "родился в Лондоне"),
        ("1931", "Кембридж", "Кингс-колледж, математика"),
        ("1938", "Принстон", "PhD под руководством Алонзо Чёрча"),
    ]
    y = 790
    for year, place, text in facts:
        d.line((186, y - 26, 1110, y - 26), fill=(255, 82, 96, 42), width=1)
        tracked(d, (186, y), year, F("unbounded", "SemiBold", 31), RED_BRIGHT, 1)
        tracked(d, (390, y + 6), place, F("unbounded", "Medium", 19), TEXT, 2)
        d.text((700, y + 4), text, font=F("manrope", "Medium", 29), fill=MUTED)
        y += 142

    # Portrait card.
    card(d, (1580, 260, 2380, 1190), fill=(14, 3, 5, 235), outline=(255, 82, 96, 90), radius=30, width=2)
    d.rounded_rectangle((1600, 280, 2360, 1110), radius=20, outline=(255, 177, 166, 45), width=2)
    photo = Image.open(PORTRAIT).convert("L")
    photo = ImageOps.fit(photo, (740, 820), method=Image.Resampling.LANCZOS, centering=(0.5, 0.18))
    photo = ImageEnhance.Contrast(photo).enhance(1.08)
    photo = ImageEnhance.Brightness(photo).enhance(0.72)
    photo = ImageOps.colorize(photo, black=(8, 2, 3), white=(236, 222, 220), mid=(118, 90, 92))
    img.paste(photo.convert("RGB"), (1610, 290))
    # Red wash + vignette.
    wash = Image.new("RGBA", (740, 820), (255, 30, 50, 22))
    img.alpha_composite(wash, (1610, 290))
    d = ImageDraw.Draw(img)
    tracked(d, (1610, 1140), "АЛАН ТЬЮРИНГ · 1930-Е ГОДЫ", F("unbounded", "Medium", 16), (158, 126, 129), 3)
    tracked(d, (1610, 1172), "WIKIMEDIA COMMONS · PUBLIC DOMAIN", F("unbounded", "Medium", 12), (107, 86, 89), 2)

    # Big background year.
    tracked(d, (1120, 1180), "1912", F("unbounded", "Bold", 130), (255, 59, 78, 14), 0)
    footer(d)
    return img


def scene_machine():
    img = background((0.68, 0.52), 1.0)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "03", "1936 · ТЕОРИЯ ВЫЧИСЛЕНИЙ")
    tracked(d, (180, 215), "МАШИНА", F("manrope", "Bold", 132), TEXT, -1)
    tracked(d, (180, 350), "ТЬЮРИНГА", F("manrope", "Bold", 132), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 540),
        "Абстрактное устройство, которое читает символы, меняет их по правилам и может выполнить любой алгоритм.",
        F("manrope", "Medium", 35),
        MUTED,
        1160,
        1.55,
    )
    tracked(d, (186, 700), "ОДНА МАШИНА → ЛЮБАЯ ПРОГРАММА", F("unbounded", "Medium", 20), RED_BRIGHT, 2)

    # Tape.
    tape_y = 875
    cell_w, cell_h = 115, 125
    start_x = 180
    symbols = ["0", "1", "·", "0", "1", "1", "0", "·", "1", "0", "0", "1", "0", "·", "1"]
    d.rounded_rectangle((start_x - 22, tape_y - 22, start_x + cell_w * len(symbols) + 18, tape_y + cell_h + 22), radius=16, fill=(18, 4, 6, 230), outline=(255, 82, 96, 70), width=2)
    highlight = 8
    for i, sym in enumerate(symbols):
        x = start_x + i * cell_w
        d.rectangle((x, tape_y, x + cell_w, tape_y + cell_h), outline=(255, 82, 96, 58), width=1)
        if i == highlight:
            d.rectangle((x + 2, tape_y + 2, x + cell_w - 2, tape_y + cell_h - 2), fill=(255, 59, 78, 48), outline=(255, 113, 99, 230), width=3)
        d.text((x + cell_w / 2, tape_y + cell_h / 2 - 6), sym, font=F("manrope", "SemiBold", 50), fill=TEXT if i != highlight else RED_BRIGHT, anchor="mm")

    # Head.
    hx = start_x + highlight * cell_w + cell_w / 2
    d.line((hx, tape_y - 38, hx, tape_y - 2), fill=RED_BRIGHT, width=3)
    d.polygon((hx - 17, tape_y - 55, hx + 17, tape_y - 55, hx, tape_y - 30), fill=RED_BRIGHT)
    d.rounded_rectangle((hx - 170, tape_y - 150, hx + 170, tape_y - 72), radius=14, fill=(30, 6, 10, 230), outline=(255, 82, 96, 100), width=2)
    tracked(d, (hx - 150, tape_y - 131), "ГОЛОВКА", F("unbounded", "Medium", 16), RED_BRIGHT, 4)

    # Rule cards.
    rules = [("01", "ПРОЧИТАЙ", "символ на ленте"), ("02", "ИЗМЕНИ", "состояние и символ"), ("03", "СДВИНЬСЯ", "влево или вправо")]
    for i, (n, title, sub) in enumerate(rules):
        x = 180 + i * 455
        card(d, (x, 1130, x + 415, 1270), fill=(20, 4, 7, 210), outline=(255, 82, 96, 55), radius=16, width=1)
        tracked(d, (x + 22, 1152), n, F("unbounded", "Medium", 14), RED_BRIGHT, 3)
        tracked(d, (x + 22, 1186), title, F("unbounded", "SemiBold", 21), TEXT, 2)
        d.text((x + 22, 1226), sub, font=F("manrope", "Medium", 21), fill=MUTED)

    # Formula.
    formula = "f : Q × Γ → Q × Γ × {L, R}"
    d.rounded_rectangle((1700, 235, 2350, 345), radius=16, fill=(18, 4, 6, 205), outline=(255, 82, 96, 60), width=1)
    tracked(d, (1730, 270), formula, F("manrope", "SemiBold", 27), (230, 201, 199), 0)
    tracked(d, (1730, 305), "ПРАВИЛО ВЫЧИСЛЕНИЯ", F("unbounded", "Medium", 13), (155, 119, 122), 3)

    tracked(d, (1740, 660), "1936", F("unbounded", "Bold", 210), (255, 59, 78, 16), 0)
    footer(d)
    return img


def rotor(draw, cx, cy, r, letters, offset=0):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(14, 3, 5, 215), outline=(255, 82, 96, 100), width=2)
    draw.ellipse((cx - r * 0.76, cy - r * 0.76, cx + r * 0.76, cy + r * 0.76), outline=(255, 82, 96, 48), width=1)
    draw.ellipse((cx - r * 0.23, cy - r * 0.23, cx + r * 0.23, cy + r * 0.23), fill=(255, 59, 78, 120), outline=(255, 113, 99, 210), width=2)
    for i in range(26):
        angle = math.radians(-90 + offset + i * (360 / 26))
        x = cx + math.cos(angle) * (r * 0.9)
        y = cy + math.sin(angle) * (r * 0.9)
        draw.text((x, y), letters[i], font=F("manrope", "SemiBold", max(12, int(r * 0.085))), fill=(232, 210, 208), anchor="mm")


def scene_enigma():
    img = background((0.74, 0.46), 1.1)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "04", "1939—1945 · БЛЕТЧЛИ-ПАРК")
    tracked(d, (180, 220), "ВОЙНА", F("manrope", "Bold", 138), TEXT, -1)
    tracked(d, (180, 360), "И ЭНИГМА", F("manrope", "Bold", 138), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 555),
        "Секретный центр британской разведки. Hut 8. Тьюринг и его команда ищут способ взломать немецкий шифр.",
        F("manrope", "Medium", 34),
        MUTED,
        1040,
        1.55,
    )

    # Rotor illustration.
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    rotor(d, 1850, 660, 310, letters, 0)
    rotor(d, 2130, 600, 210, letters, 17)
    rotor(d, 2110, 930, 175, letters, 8)
    d = ImageDraw.Draw(img)
    for i in range(14):
        y = 380 + i * 58
        d.line((1330, y, 1600, 520), fill=(255, 82, 96, 12 + i * 2), width=1)
    tracked(d, (1540, 1080), "ENIGMA", F("unbounded", "Bold", 130), (255, 59, 78, 28), 0)

    # Stats.
    stats = [("6", "ЛЕТ ВОЙНЫ"), ("10 000", "ЧЕЛОВЕК В БЛЕТЧЛИ"), ("СЕКРЕТ", "ДО 1970-Х")]
    for i, (num, label) in enumerate(stats):
        x = 186 + i * 380
        d.line((x, 1120, x + 300, 1120), fill=(255, 82, 96, 70), width=2)
        tracked(d, (x, 1150), num, F("unbounded", "SemiBold", 34), RED_BRIGHT, 1)
        tracked(d, (x, 1205), label, F("unbounded", "Medium", 13), (153, 121, 124), 2)

    footer(d)
    return img


def scene_bombe():
    img = background((0.25, 0.5), 0.8)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "05", "МАШИНА ПРОТИВ МАШИНЫ")
    tracked(d, (180, 220), "БОМБА", F("manrope", "Bold", 152), TEXT, -1)
    tracked(d, (180, 385), "ПРОТИВ ШИФРА", F("manrope", "Bold", 94), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 550),
        "Устройство перебирало возможные настройки «Энигмы» и находило ту, которая давала осмысленный текст.",
        F("manrope", "Medium", 34),
        MUTED,
        950,
        1.55,
    )

    # Rotor bank.
    bank_x, bank_y = 1370, 280
    d.rounded_rectangle((bank_x, bank_y, 2350, 1010), radius=22, fill=(14, 3, 5, 200), outline=(255, 82, 96, 60), width=2)
    for row in range(4):
        for col in range(7):
            x = bank_x + 50 + col * 132
            y = bank_y + 60 + row * 150
            d.rounded_rectangle((x, y, x + 92, y + 108), radius=11, fill=(28, 6, 10, 220), outline=(255, 82, 96, 70), width=1)
            d.ellipse((x + 27, y + 20, x + 65, y + 58), fill=(255, 59, 78, 130), outline=(255, 113, 99, 185), width=2)
            for k in range(3):
                d.line((x + 18, y + 72 + k * 9, x + 74, y + 72 + k * 9), fill=(255, 82, 96, 60), width=1)
    tracked(d, (1410, 1030), "BOMBE · ПЕРЕБОР НАСТРОЕК", F("unbounded", "Medium", 17), (179, 140, 143), 3)

    # Logic lines.
    for i in range(8):
        d.line((1200, 380 + i * 75, 1370, 420 + i * 68), fill=(255, 59, 78, 22 + i * 2), width=1)
    tracked(d, (180, 1110), "ENIGMA  →  BOMBE  →  РАЗВЕДКА", F("unbounded", "Medium", 22), RED_BRIGHT, 2)
    footer(d)
    return img


def scene_postwar():
    img = background((0.75, 0.42), 0.9)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "06", "1945—1948 · ПОСЛЕ ВОЙНЫ")
    tracked(d, (180, 220), "ОТ ИДЕИ", F("manrope", "Bold", 135), TEXT, -1)
    tracked(d, (180, 358), "К КОМПЬЮТЕРУ", F("manrope", "Bold", 112), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 540),
        "Проект ACE для Национальной физической лаборатории. Затем — Манчестер и программы для одного из первых компьютеров с хранимой программой.",
        F("manrope", "Medium", 33),
        MUTED,
        980,
        1.55,
    )

    # Computer cabinet.
    x, y, w, h = 1430, 225, 890, 900
    d.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=(13, 3, 5, 230), outline=(255, 82, 96, 80), width=2)
    d.rounded_rectangle((x + 26, y + 26, x + w - 26, y + 78), radius=10, fill=(255, 59, 78, 26), outline=(255, 82, 96, 45), width=1)
    tracked(d, (x + 50, y + 40), "ACE · PILOT MODEL", F("unbounded", "Medium", 15), (219, 181, 178), 3)
    for row in range(6):
        for col in range(9):
            lx = x + 60 + col * 88
            ly = y + 120 + row * 104
            d.rounded_rectangle((lx, ly, lx + 50, ly + 62), radius=7, fill=(28, 6, 10, 220), outline=(255, 82, 96, 55), width=1)
            d.ellipse((lx + 16, ly + 12, lx + 34, ly + 30), fill=(255, 59, 78, 35), outline=(255, 113, 99, 140), width=1)
            d.line((lx + 9, ly + 44, lx + 41, ly + 44), fill=(255, 82, 96, 85), width=1)
    d.line((x + 50, y + 800, x + w - 50, y + 800), fill=(255, 82, 96, 80), width=2)
    tracked(d, (x + 50, y + 830), "MANCHESTER MARK 1", F("unbounded", "Medium", 15), (179, 140, 143), 3)
    tracked(d, (180, 1110), "1945", F("unbounded", "SemiBold", 54), RED_BRIGHT, 1)
    d.line((330, 1140, 640, 1140), fill=(255, 82, 96, 100), width=2)
    tracked(d, (670, 1110), "1948", F("unbounded", "SemiBold", 54), RED_BRIGHT, 1)
    footer(d)
    return img


def scene_learning():
    img = background((0.78, 0.4), 0.85)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "07", "1948 · INTELLIGENT MACHINERY")
    tracked(d, (180, 220), "МАШИНА,", F("manrope", "Bold", 132), TEXT, -1)
    tracked(d, (180, 355), "КОТОРАЯ УЧИТСЯ", F("manrope", "Bold", 105), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 535),
        "Тьюринг предложил сети простых связанных элементов и идею «ребёнка-машины», которую нужно обучать, а не программировать целиком.",
        F("manrope", "Medium", 33),
        MUTED,
        1060,
        1.55,
    )
    tracked(d, (186, 760), "ПРЕДВИДЕНИЕ НЕЙРОСЕТЕЙ", F("unbounded", "Medium", 19), RED_BRIGHT, 2)

    # Neural network.
    layers = [(1500, [350, 560, 770, 980]), (1810, [300, 480, 660, 840, 1020]), (2120, [420, 650, 880])]
    for li in range(len(layers) - 1):
        x1, ys1 = layers[li]
        x2, ys2 = layers[li + 1]
        for y1 in ys1:
            for y2 in ys2:
                d.line((x1, y1, x2, y2), fill=(255, 59, 78, 30), width=1)
    for li, (x, ys) in enumerate(layers):
        for y in ys:
            d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=(255, 59, 78, 170), outline=(255, 177, 166, 200), width=2)
            d.ellipse((x - 42, y - 42, x + 42, y + 42), outline=(255, 82, 96, 45), width=1)
        tracked(d, (x - 48, 1090), ["ВХОД", "СКРЫТЫЙ СЛОЙ", "ВЫХОД"][li], F("unbounded", "Medium", 12), (154, 120, 123), 2)

    d.rounded_rectangle((1510, 1160, 2330, 1260), radius=14, fill=(18, 4, 6, 210), outline=(255, 82, 96, 55), width=1)
    tracked(d, (1535, 1188), "A-TYPE  /  B-TYPE  /  ОБУЧЕНИЕ", F("unbounded", "Medium", 16), (192, 151, 153), 3)
    footer(d)
    return img


def scene_question():
    img = background((0.72, 0.48), 1.25)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "08", "1950 · ЖУРНАЛ MIND")
    tracked(d, (180, 214), "МОЖЕТ ЛИ", F("manrope", "Bold", 132), TEXT, -1)
    tracked(d, (180, 350), "МАШИНА", F("manrope", "Bold", 132), TEXT, -1)
    tracked(d, (180, 486), "ДУМАТЬ?", F("manrope", "Bold", 152), RED_BRIGHT, -1)
    # Journal card.
    card(d, (1740, 290, 2350, 1040), fill=(18, 4, 7, 235), outline=(255, 82, 96, 90), radius=20, width=2)
    d.rectangle((1770, 320, 2320, 330), fill=(255, 59, 78, 180))
    tracked(d, (1800, 380), "MIND", F("unbounded", "Bold", 72), TEXT, 2)
    tracked(d, (1800, 470), "VOL. LIX · 1950", F("unbounded", "Medium", 17), (172, 136, 138), 3)
    d.line((1800, 530, 2280, 530), fill=(255, 82, 96, 65), width=1)
    d.text((1800, 575), "Computing", font=F("manrope", "SemiBold", 38), fill=TEXT)
    d.text((1800, 625), "Machinery and", font=F("manrope", "SemiBold", 38), fill=TEXT)
    d.text((1800, 675), "Intelligence", font=F("manrope", "SemiBold", 38), fill=RED_BRIGHT)
    tracked(d, (1800, 755), "A. M. TURING", F("unbounded", "Medium", 16), (186, 147, 149), 3)
    paragraph(
        d,
        (1800, 815),
        "Вопрос, который превратил философию в проверяемый эксперимент.",
        F("manrope", "Medium", 25),
        MUTED,
        480,
        1.45,
    )

    paragraph(
        d,
        (186, 760),
        "Тьюринг не стал спорить о сознании. Он предложил операциональный тест: судить машину по её ответам.",
        F("manrope", "Medium", 33),
        MUTED,
        1040,
        1.6,
    )
    tracked(d, (186, 1040), "«COMPUTING MACHINERY AND INTELLIGENCE»", F("unbounded", "Medium", 15), (183, 139, 142), 2)
    footer(d)
    return img


def chat_box(d, box, who, text, accent=False):
    fill = (32, 6, 11, 225) if accent else (18, 4, 6, 220)
    outline = (255, 82, 96, 110) if accent else (255, 255, 255, 28)
    card(d, box, fill=fill, outline=outline, radius=16, width=1)
    x1, y1, x2, y2 = box
    tracked(d, (x1 + 24, y1 + 20), who, F("unbounded", "Medium", 13), RED_BRIGHT if accent else (165, 131, 133), 3)
    paragraph(d, (x1 + 24, y1 + 55), text, F("manrope", "Medium", 23), (194, 171, 171), x2 - x1 - 48, 1.4)


def scene_imitation():
    img = background((0.32, 0.46), 0.9)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "09", "ИГРА В ИМИТАЦИЮ")
    tracked(d, (180, 220), "СУДЬЯ НЕ ВИДИТ,", F("manrope", "Bold", 90), TEXT, -1)
    tracked(d, (180, 320), "КТО ЕСТЬ КТО", F("manrope", "Bold", 120), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 500),
        "Только текст. Никаких лиц, голосов и подсказок. Если машину нельзя отличить от человека — она прошла тест.",
        F("manrope", "Medium", 33),
        MUTED,
        1000,
        1.55,
    )

    # Terminal.
    d.rounded_rectangle((1400, 180, 2380, 1170), radius=24, fill=(12, 3, 5, 235), outline=(255, 82, 96, 95), width=2)
    d.rounded_rectangle((1400, 180, 2380, 250), radius=24, fill=(25, 5, 9, 235), outline=(255, 82, 96, 55), width=1)
    for i, col in enumerate([(255, 59, 78), (110, 80, 82), (110, 80, 82)]):
        d.ellipse((1430 + i * 22, 207, 1442 + i * 22, 219), fill=col)
    tracked(d, (1510, 198), "IMITATION_GAME.EXE", F("unbounded", "Medium", 14), (160, 129, 131), 2)
    tracked(d, (2190, 198), "1950", F("unbounded", "Medium", 13), (137, 108, 110), 2)
    tracked(d, (1440, 292), "СУДЬЯ СПРАШИВАЕТ", F("unbounded", "Medium", 12), RED_BRIGHT, 3)
    d.text((1440, 328), "«Опиши, что ты чувствуешь, когда видишь закат».", font=F("manrope", "SemiBold", 28), fill=TEXT)
    chat_box(d, (1440, 405, 2340, 560), "СОБЕСЕДНИК A", "Тишину. Как будто день выдыхает. Я вспоминаю море и почему-то запах пыли.")
    chat_box(d, (1440, 585, 2340, 760), "СОБЕСЕДНИК B", "Я замечаю, как меняется свет. Не уверен, что это можно назвать чувством, но могу описать: небо становится медленнее.", True)
    tracked(d, (1440, 825), "КТО ИЗ НИХ МАШИНА?", F("unbounded", "Medium", 15), (196, 160, 162), 3)
    d.rounded_rectangle((1440, 875, 1880, 950), radius=12, fill=(255, 255, 255, 10), outline=(255, 255, 255, 35), width=1)
    d.rounded_rectangle((1900, 875, 2340, 950), radius=12, fill=(255, 59, 78, 30), outline=(255, 82, 96, 100), width=1)
    tracked(d, (1600, 900), "ЭТО A", F("unbounded", "Medium", 16), TEXT, 2)
    tracked(d, (2060, 900), "ЭТО B", F("unbounded", "Medium", 16), TEXT, 2)
    tracked(d, (1440, 1020), "5 МИНУТ", F("unbounded", "SemiBold", 24), RED_BRIGHT, 2)
    tracked(d, (1660, 1020), "30%", F("unbounded", "SemiBold", 24), RED_BRIGHT, 2)
    tracked(d, (1800, 1020), "К 2000 ГОДУ", F("unbounded", "Medium", 13), (148, 116, 119), 2)
    footer(d)
    return img


def make_pattern():
    path = BUILD / "pattern.png"
    if path.exists():
        return path
    size = 260
    steps = 5200
    feed, kill = 0.0545, 0.062
    du, dv = 0.16, 0.08
    rng = np.random.default_rng(7)
    u = np.ones((size, size), dtype=np.float32)
    v = np.zeros((size, size), dtype=np.float32)
    u += rng.normal(0, 0.01, (size, size)).astype(np.float32)
    v += rng.normal(0, 0.01, (size, size)).astype(np.float32)
    # Seed spots.
    for _ in range(28):
        cx, cy = rng.integers(20, size - 20, 2)
        u[cy - 7:cy + 7, cx - 7:cx + 7] = 0.5
        v[cy - 7:cy + 7, cx - 7:cx + 7] = 0.25
    for _ in range(steps):
        lap_u = (
            np.roll(u, 1, 0) + np.roll(u, -1, 0) + np.roll(u, 1, 1) + np.roll(u, -1, 1) - 4 * u
        )
        lap_v = (
            np.roll(v, 1, 0) + np.roll(v, -1, 0) + np.roll(v, 1, 1) + np.roll(v, -1, 1) - 4 * v
        )
        reaction = u * v * v
        u += (du * lap_u - reaction + feed * (1 - u))
        v += (dv * lap_v + reaction - (feed + kill) * v)
        np.clip(u, 0, 1, out=u)
        np.clip(v, 0, 1, out=v)
    arr = np.clip((v - v.min()) / (v.max() - v.min() + 1e-9), 0, 1)
    arr = arr**0.8
    rgb = np.zeros((size, size, 3), dtype=np.float32)
    rgb[..., 0] = 8 + arr * 247
    rgb[..., 1] = 2 + arr * 90
    rgb[..., 2] = 3 + arr * 102
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    img = img.resize((1100, 1100), Image.Resampling.LANCZOS)
    img.save(path)
    return path


def scene_morphogenesis():
    img = background((0.76, 0.5), 0.8)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "10", "1952 · МОРФОГЕНЕЗ")
    tracked(d, (180, 215), "УЗОРЫ,", F("manrope", "Bold", 132), TEXT, -1)
    tracked(d, (180, 350), "КОТОРЫЕ СОЗДАЁТ", F("manrope", "Bold", 84), TEXT, -1)
    tracked(d, (180, 458), "МАТЕМАТИКА", F("manrope", "Bold", 117), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 640),
        "Модель реакции-диффузии объясняет, как из простых химических процессов возникают пятна, полосы и биологические формы.",
        F("manrope", "Medium", 32),
        MUTED,
        1010,
        1.55,
    )
    tracked(d, (186, 880), "«THE CHEMICAL BASIS OF MORPHOGENESIS»", F("unbounded", "Medium", 14), (176, 135, 138), 2)

    # Pattern circle.
    pat = Image.open(make_pattern()).convert("RGB").resize((920, 920), Image.Resampling.LANCZOS)
    mask = circle_mask(920)
    circle = Image.new("RGBA", (920, 920), (0, 0, 0, 0))
    circle.paste(pat, (0, 0), mask)
    img = glow(img, (1990, 720), 560, alpha=55, blur=90)
    img.alpha_composite(circle, (1530, 260))
    d = ImageDraw.Draw(img)
    d.ellipse((1530, 260, 2450, 1180), outline=(255, 82, 96, 90), width=2)
    d.ellipse((1490, 220, 2490, 1220), outline=(255, 82, 96, 30), width=1)

    # Formula.
    d.rounded_rectangle((1500, 1180, 2380, 1270), radius=12, fill=(16, 3, 5, 210), outline=(255, 82, 96, 40), width=1)
    tracked(d, (1525, 1205), "∂u/∂t = Du·Δu − uv² + F(1−u)", F("manrope", "Medium", 22), (186, 151, 153), 0)
    footer(d)
    return img


def scene_tragedy():
    img = background((0.3, 0.55), 0.7, grid=False)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "11", "1952—1954 · ЦЕНА")
    tracked(d, (180, 230), "ЦЕНА", F("manrope", "Bold", 165), TEXT, -1)
    tracked(d, (180, 395), "ЧЕЛОВЕКА", F("manrope", "Bold", 165), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 610),
        "В 1952 году его судили за гомосексуальность. Приговор, гормональное «лечение», потеря допуска к секретным работам.",
        F("manrope", "Medium", 33),
        MUTED,
        1070,
        1.55,
    )
    d.line((186, 850, 1180, 850), fill=(255, 59, 78, 55), width=1)
    tracked(d, (186, 890), "7 ИЮНЯ 1954", F("unbounded", "SemiBold", 58), RED_BRIGHT, 2)
    tracked(d, (186, 980), "УИЛМСЛОУ · 41 ГОД", F("unbounded", "Medium", 22), (179, 140, 143), 3)
    tracked(d, (186, 1080), "ЕГО НАУЧНОЕ НАСЛЕДИЕ УЖЕ НЕВОЗМОЖНО БЫЛО ОТМЕНИТЬ.", F("unbounded", "Medium", 15), (165, 126, 129), 2)

    # Dark portrait.
    img = add_orb(img, (1930, 750), 740, opacity=0.24, glow_alpha=34)
    d = ImageDraw.Draw(img)
    d.ellipse((1540, 360, 2320, 1140), outline=(255, 82, 96, 35), width=1)
    footer(d)
    return img


def scene_legacy():
    img = background((0.7, 0.35), 1.0)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "12", "НАСЛЕДИЕ")
    tracked(d, (180, 215), "ОН НЕ УВИДЕЛ", F("manrope", "Bold", 98), TEXT, -1)
    tracked(d, (180, 330), "ЦИФРОВУЮ ЭПОХУ.", F("manrope", "Bold", 98), TEXT, -1)
    tracked(d, (180, 445), "НО ОН ЕЁ ЗАПУСТИЛ.", F("manrope", "Bold", 84), RED_BRIGHT, -1)

    facts = [
        ("1966", "ПРЕМИЯ ТЬЮРИНГА", "Главная награда в области информатики"),
        ("2013", "КОРОЛЕВСКОЕ ПОМИЛОВАНИЕ", "Спустя почти 60 лет после приговора"),
        ("2021", "БАНКНОТА £50", "Портрет Тьюринга в Британии"),
    ]
    for i, (year, title, text) in enumerate(facts):
        x = 180 + i * 750
        card(d, (x, 680, x + 690, 1010), fill=(19, 4, 7, 205), outline=(255, 82, 96, 60), radius=18, width=1)
        tracked(d, (x + 30, 715), year, F("unbounded", "SemiBold", 36), RED_BRIGHT, 1)
        tracked(d, (x + 30, 790), title, F("unbounded", "Medium", 15), TEXT, 2)
        paragraph(d, (x + 30, 840), text, F("manrope", "Medium", 24), MUTED, 620, 1.4)

    img = add_orb(img, (2300, 1190), 260, opacity=0.14)
    footer(d)
    return img


def scene_site():
    img = background((0.52, 0.45), 0.85)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    kicker(d, 180, 130, "13", "ПРОЕКТ · САЙТ-ЛОНГРИД")
    tracked(d, (180, 215), "ИСТОРИЯ", F("manrope", "Bold", 122), TEXT, -1)
    tracked(d, (180, 345), "В ОДНОМ МЕСТЕ", F("manrope", "Bold", 86), RED_BRIGHT, -1)
    paragraph(
        d,
        (186, 530),
        "Биография, хронология, идеи и интерактивный тест Тьюринга — в одном адаптивном сайте.",
        F("manrope", "Medium", 32),
        MUTED,
        760,
        1.55,
    )
    tracked(d, (186, 760), "АДАПТИВ · АНИМАЦИИ · ИНТЕРАКТИВ", F("unbounded", "Medium", 15), (175, 135, 138), 2)

    # Browser frame.
    frame = (940, 220, 2400, 1180)
    card(d, frame, fill=(12, 3, 5, 245), outline=(255, 82, 96, 90), radius=24, width=2)
    d.rounded_rectangle((940, 220, 2400, 292), radius=24, fill=(27, 5, 9, 245), outline=(255, 82, 96, 55), width=1)
    for i, col in enumerate([(255, 59, 78), (115, 82, 85), (115, 82, 85)]):
        d.ellipse((975 + i * 22, 248, 987 + i * 22, 260), fill=col)
    tracked(d, (1050, 241), "TURING. / ИСТОРИЯ", F("unbounded", "Medium", 13), (159, 126, 129), 2)
    preview = Image.open(PREVIEW).convert("RGB")
    preview = ImageOps.fit(preview, (1400, 820), method=Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    img.paste(preview, (970, 310))
    d.rectangle((970, 310, 2370, 1130), outline=(255, 82, 96, 55), width=1)

    # Mobile preview.
    mob = Image.open(PREVIEW_MOBILE).convert("RGB")
    mob = ImageOps.fit(mob, (235, 510), method=Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    d.rounded_rectangle((2180, 960, 2445, 1235), radius=20, fill=(10, 2, 4, 255), outline=(255, 113, 99, 120), width=2)
    img.paste(mob, (2192, 972))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2240, 972, 2390, 984), radius=6, fill=(12, 3, 5, 255))

    footer(d)
    return img


def scene_quote():
    img = background((0.3, 0.45), 0.8)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    img = add_orb(img, (2110, 720), 600, opacity=0.22)
    d = ImageDraw.Draw(img)
    d.text((160, 210), "“", font=F("manrope", "Bold", 260), fill=(255, 59, 78, 80))
    tracked(d, (180, 500), "МЫ МОЖЕМ ВИДЕТЬ", F("manrope", "SemiBold", 73), TEXT, -1)
    tracked(d, (180, 585), "ЛИШЬ НЕДАЛЕКО ВПЕРЕДИ,", F("manrope", "SemiBold", 73), TEXT, -1)
    tracked(d, (180, 670), "НО МОЖЕМ ВИДЕТЬ,", F("manrope", "SemiBold", 73), TEXT, -1)
    tracked(d, (180, 755), "ЧТО НУЖНО СДЕЛАТЬ.", F("manrope", "SemiBold", 73), RED_BRIGHT, -1)
    tracked(d, (186, 940), "АЛАН ТЬЮРИНГ · 1950", F("unbounded", "Medium", 18), (169, 134, 137), 3)
    footer(d)
    return img


def scene_outro():
    img = background((0.5, 0.42), 1.15)
    d = ImageDraw.Draw(img)
    add_corner_line(d)
    brand(d, W / 2 - 90, 215, 1.15)
    d.text((W / 2, 500), "СПАСИБО", font=F("manrope", "Bold", 188), fill=TEXT, anchor="mm")
    tracked(d, (W / 2, 650), "ЗА ВНИМАНИЕ", F("unbounded", "Medium", 38), RED_BRIGHT, 10, center=True)
    d.line((W / 2 - 330, 760, W / 2 + 330, 760), fill=(255, 59, 78, 80), width=2)
    tracked(d, (W / 2, 815), "ALAN TURING · 1912—1954", F("unbounded", "Medium", 19), (169, 134, 137), 5, center=True)
    tracked(d, (W / 2, 900), "ИСТОРИЯ, КОТОРАЯ ПРОДОЛЖАЕТСЯ", F("unbounded", "Medium", 14), (125, 96, 100), 4, center=True)
    img = add_orb(img, (2150, 1080), 380, opacity=0.1, glow_alpha=28)
    footer(d)
    return img


SCENES = [
    ("s01", scene_title, "seg01", 1.0),
    ("s02", scene_early, "seg02", 1.0),
    ("s03", scene_machine, "seg03", 1.0),
    ("s04", scene_enigma, "seg04", 0.58),
    ("s05", scene_bombe, "seg04", 0.42),
    ("s06", scene_postwar, "seg05", 0.55),
    ("s07", scene_learning, "seg05", 0.45),
    ("s08", scene_question, "seg06", 0.45),
    ("s09", scene_imitation, "seg06", 0.55),
    ("s10", scene_morphogenesis, "seg07", 0.52),
    ("s11", scene_tragedy, "seg07", 0.48),
    ("s12", scene_legacy, "seg08", 0.52),
    ("s13", scene_site, "seg08", 0.48),
    ("s14", scene_quote, "tail", 0.52),
    ("s15", scene_outro, "tail", 0.48),
]


def main():
    manifest = []
    for sid, func, segment, weight in SCENES:
        path = STILLS / f"{sid}.png"
        if not path.exists() or os.environ.get("REBUILD") == "1":
            print(f"Drawing {sid} ...")
            img = func()
            flat = Image.new("RGBA", img.size, (*BG, 255))
            flat.alpha_composite(img)
            flat.convert("RGB").save(path, optimize=True)
        manifest.append({"id": sid, "file": str(path), "segment": segment, "weight": weight})
    (ROOT / "scenes.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(manifest)} scenes")


if __name__ == "__main__":
    main()
