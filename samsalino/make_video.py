#!/usr/bin/env python3
"""Samsalino Tandirino - a 60 s vertical brainrot nursery-rhyme Short.

    python make_video.py                  # -> output/samsalino.mp4
    python make_video.py --preview 5 30   # PNG stills at 5 s and 30 s
"""
import argparse
import bisect
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import audio
import characters as ch

W, H, FPS, DUR = 1080, 1920, 30, 60.0
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "LuckiestGuy-Regular.ttf")
SYMBOL_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OUT = (28, 18, 32, 255)

# ------------------------------------------------------------------ timeline
SECTIONS = [0, 3, 13, 23, 33, 43, 53]


def build_beats():
    beats, t = [], 0.0
    for end, bpm in ((43, 120), (53, 132), (59, 140)):
        while t < end - 1e-6:
            beats.append(round(t, 4))
            t += 60.0 / bpm
        t = float(end)
    beats += [59.0, 60.0, 61.0]
    return beats


BEATS = build_beats()


def L(t0, t1, sub, tts=None, pause=0.0, gain=1.0, echo=False, sub_t1=None):
    return dict(t0=t0, t1=t1, sub=sub, tts=tts or sub, pause=pause, gain=gain,
                echo=echo, sub_t1=sub_t1 or t1)


NAME_PAUSE = 0.38   # dramatic beat of silence before every character name


def stanza(start, rows):
    out = []
    for i, (sub, tts, is_name) in enumerate(rows):
        out.append(L(start + i * 2.5, start + (i + 1) * 2.5, sub, tts,
                     pause=NAME_PAUSE if is_name else 0.05))
    return out


# Each song: (subtitle, tts text or None, starts-with-a-name) per line.
SONGS = {
    "en": dict(
        title=("Samsalino... Tandirino!", None),
        chorus=[
            ("Boom-boom-tandir, boom-boom-tandir!", "Boom boom tandeer! Boom boom tandeer!", False),
            ("Samsalino's finally here!", "Samsalino's... finally here!", True),
            ("Little feet go stomp, sesame on top,", "Little feet go stomp! Sesame on top!", False),
            ("Dance with him and never stop!", None, False)],
        verse1=[
            ("Plovolino Kazanino,", "Plovolino... Kazanino!", True),
            ("A flying pot, a rice machino!", "A flying pot! A rice ma-keeno!", False),
            ("Whoosh-whoosh over rooftops high,", "Whoosh whoosh, over rooftops high!", False),
            ("Raining carrots from the sky!", None, False)],
        verse2=[
            ("Dutarini Crocodini", "Dutarini... Crocodini!", True),
            ("Wears a doppi, blue and teeny!", "Wears a doppy, blue and teeny!", False),
            ("Tail goes clack, teeth go snap,", "Tail goes clack! Teeth go snap!", False),
            ("Even wolves begin to clap!", None, False)],
        verse3=[
            ("Chaynikoni Pialoni,", "Chai-nee-koni... Pee-ah-loni!", True),
            ("A teapot riding on a pony!", None, False),
            ('Glug-glug-glug, it shouts "Salom!"', "Glug glug glug! It shouts, Sah-lom!", False),
            ("Pouring tea in every home!", None, False)],
        names=[("Samsalino!", None), ("Plovolino!", None), ("Dutarini!", None),
               ("Chaynikoni!", "Chai-nee-koni!")],
        together=("All together, one-two-three...", "All together! One, two, three!"),
        boom=("BOOM-BOOM-TANDIR!", "Boom boom tandeer!"),
        screen=dict(chorus2="BOOM-BOOM\nTANDIR!", together="ALL TOGETHER!",
                    boom="BOOM-BOOM-\nTANDIR!", salom="SALOM!",
                    croc="DUTARINI\nCROCODINI"),
    ),
    "uz": dict(
        title=("Samsalino... Tandirino!", None),
        chorus=[
            ("Bum-bum-tandir, bum-bum-tandir!", "Bum bum tandir! Bum bum tandir!", False),
            ("Samsalino keldi, qarang!", "Samsalino... keldi, qarang!", True),
            ("Oyoqchasi tup-tup-tup,", "Oyoqchasi tup, tup, tup!", False),
            ("Boshda kunjut, raqsga tush, hop!", "Boshda kunjut! Raqsga tush, hop!", False)],
        verse1=[
            ("Plovolino Kazanino,", "Plovolino... Kazanino!", True),
            ("Uchar qozon, guruch-mashino!", "Uchar qozon, guruch mashino!", False),
            ("Vush-vush, tomlar uzra uchar,", "Vush vush! Tomlar uzra uchar!", False),
            ("Osmondan sabzi yog'ar!", None, False)],
        verse2=[
            ("Dutarini Krokodini", "Dutarini... Krokodini!", True),
            ("Boshida ko'k do'ppi, mini!", None, False),
            ("Dumi taq-taq, tishi shaq,", "Dumi taq taq! Tishi shaq!", False),
            ("Bo'ri ham chalar qarsak!", None, False)],
        verse3=[
            ("Chaynikoni Pialoni,", "Chaynikoni... Pialoni!", True),
            ("Choynak minar toychoqni!", None, False),
            ('Bul-bul-bul, der: "Salom!"', "Bul bul bul! Der: Salom!", False),
            ("Har uyga choy quyar, davom!", "Har uyga choy quyar! Davom!", False)],
        names=[("Samsalino!", None), ("Plovolino!", None), ("Dutarini!", None),
               ("Chaynikoni!", None)],
        together=("Birga! Bir-ikki-uch...", "Birga! Bir, ikki, uch!"),
        boom=("BUM-BUM-TANDIR!", "Bum bum tandir!"),
        screen=dict(chorus2="BUM-BUM\nTANDIR!", together="HAMMA BIRGA!",
                    boom="BUM-BUM-\nTANDIR!", salom="SALOM!",
                    croc="DUTARINI\nKROKODINI"),
    ),
}


def build_lyrics(song):
    n = song["names"]
    return (
        [L(0.2, 2.2, song["title"][0], song["title"][1], echo=True, sub_t1=3.0)]
        + stanza(3, song["chorus"])
        + stanza(13, song["verse1"])
        + stanza(23, song["verse2"])
        + stanza(33, song["verse3"])
        + stanza(43, song["chorus"])
        + [L(53.0, 54.3, *n[0], pause=0.15),
           L(54.3, 55.5, *n[1], pause=0.12),
           L(55.5, 56.5, *n[2], pause=0.1),
           L(56.5, 57.4, *n[3], pause=0.08),
           L(57.4, 59.0, *song["together"]),
           L(59.0, 60.0, *song["boom"], echo=True)]
    )


SONG = SONGS["en"]
LYRICS = build_lyrics(SONG)

FINALE_SLOTS = [(53.0, 54.3, "samsa", "SAMSALINO!"), (54.3, 55.5, "kazan", "PLOVOLINO!"),
                (55.5, 56.5, "croc", "DUTARINI!"), (56.5, 57.4, "tea", "CHAYNIKONI!")]


# ------------------------------------------------------------------ helpers
def beat_at(t):
    i = max(0, bisect.bisect_right(BEATS, t) - 1)
    p = (t - BEATS[i]) / (BEATS[i + 1] - BEATS[i])
    return i, min(max(p, 0.0), 1.0)


def pulse(t, k=6.0):
    return math.exp(-beat_at(t)[1] * k)


def hop(t):
    return 4 * beat_at(t)[1] * (1 - beat_at(t)[1])


def squash(t, amt=0.09):
    p = beat_at(t)[1]
    q = math.cos(2 * math.pi * p)
    return 1 + amt * q, 1 - amt * q


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def paste(frame, img, cx, cy, sx=1.0, sy=1.0, angle=0.0, alpha=1.0):
    w, h = max(1, int(img.width * sx)), max(1, int(img.height * sy))
    im = img if (w, h) == img.size else img.resize((w, h), Image.BILINEAR)
    if abs(angle) > 0.2:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    composite_clipped(frame, im, x, y)


def composite_clipped(frame, im, x, y):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame.width, x + im.width), min(frame.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    frame.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def paste_bottom(frame, img, cx, by, sx=1.0, sy=1.0, angle=0.0, alpha=1.0):
    paste(frame, img, cx, by - img.height * sy / 2, sx, sy, angle, alpha)


@lru_cache(maxsize=4096)
def font(size, path=FONT):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=512)
def text_img(text, size, fill=(255, 255, 255, 255), stroke=None,
             stroke_fill=OUT, shadow=True, path=FONT):
    stroke = stroke if stroke is not None else max(4, size // 11)
    f = font(size, path)
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = d.multiline_textbbox((0, 0), text, font=f, stroke_width=stroke,
                               align="center", spacing=size // 8)
    box = [math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3])]
    pad = stroke + 16
    im = Image.new("RGBA", (box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad))
    dd = ImageDraw.Draw(im)
    org = (pad - box[0], pad - box[1])
    if shadow:
        dd.multiline_text((org[0] + size // 16, org[1] + size // 12), text, font=f,
                          fill=(0, 0, 0, 150), stroke_width=stroke,
                          stroke_fill=(0, 0, 0, 150), align="center",
                          spacing=size // 8)
    dd.multiline_text(org, text, font=f, fill=fill, stroke_width=stroke,
                      stroke_fill=stroke_fill, align="center", spacing=size // 8)
    return im


def wrap(text, size, max_w):
    f = font(size)
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if f.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    return "\n".join(lines)


# ------------------------------------------------------------------ layers
S = None  # sprites, built once before forking workers


def tea_combo():
    pony = S["pony"][0].copy()
    canvas = Image.new("RGBA", (pony.width, pony.height + 300))
    canvas.alpha_composite(pony, (0, 300))
    tp = S["teapot"].resize((int(S["teapot"].width * 0.82),
                             int(S["teapot"].height * 0.82)), Image.LANCZOS)
    canvas.alpha_composite(tp, (385 - tp.width // 2, 300 + 195 - tp.height))
    return canvas


def background(frame, t, kind):
    frame.alpha_composite(S[kind])
    # sun and drifting clouds over the sky 
    sun_ang = -t * 25
    paste(frame, S["sun"], 880, 590 if kind == "courtyard" else 330,
          1 + 0.04 * pulse(t), 1 + 0.04 * pulse(t), sun_ang)
    speed = 160 if kind == "rooftops" else 25
    for k, (y, sc, off) in enumerate(((560, 0.8, 0), (700, 0.6, 520), (420, 0.5, 900))):
        x = (off - t * speed * (1 + 0.3 * k)) % (W + 500) - 250
        paste(frame, S["cloud"], x, y, sc, sc)


def name_card(frame, t, t0, text, color, y=340, size=130):
    k = (t - t0) / 0.45
    if k < 0:
        return
    s = ease_out_back(k) * (1 + 0.06 * pulse(t))
    ang = 4 * math.sin(math.pi * (beat_at(t)[0] + beat_at(t)[1]))
    paste(frame, text_img(text, size, color, stroke=14), W / 2, y, s, s, ang)


def subtitles(frame, t):
    for ln in LYRICS:
        if ln["t0"] <= t < ln["sub_t1"]:
            size = 78
            txt = wrap(ln["sub"].upper(), size, 940)
            while txt.count("\n") > 1 and size > 54:
                size -= 6
                txt = wrap(ln["sub"].upper(), size, 940)
            im = text_img(txt, size, (255, 255, 255, 255), stroke=9, shadow=False)
            k = min(1.0, (t - ln["t0"]) / 0.14)
            s = 0.8 + 0.2 * ease_out_back(k)
            bar = Image.new("RGBA", (W - 60, im.height + 30))
            ImageDraw.Draw(bar).rounded_rectangle(
                [0, 0, bar.width - 1, bar.height - 1], 40, fill=(20, 10, 40, 150))
            paste(frame, bar, W / 2, 1690)
            paste(frame, im, W / 2, 1690, s, s)
            # highlight colour pulse on the beat: thin yellow underline
            return


def flash(frame, t):
    a = 0.0
    for s in SECTIONS[1:]:
        if s <= t < s + 0.18:
            a = max(a, 0.75 * (1 - (t - s) / 0.18))
    if 59.0 <= t:
        a = max(a, 1.0 - (t - 59.0) / 0.4)
    if t >= DUR - 0.17:
        a = max(a, (t - (DUR - 0.17)) / 0.17)
    if a > 0:
        frame.alpha_composite(Image.new("RGBA", frame.size,
                                        (255, 255, 240, int(255 * min(a, 1)))))


def burst(frame, t, key, speed=40):
    b = S["burst"][key].rotate(t * speed, resample=Image.BILINEAR)
    x0, y0 = (b.width - W) // 2, (b.height - H) // 2
    frame.alpha_composite(b.crop((x0, y0, x0 + W, y0 + H)))


def flames(img, nozzles, t, length=130):
    """Return a copy of img extended downward with flickering booster flames."""
    out = Image.new("RGBA", (img.width, img.height + length + 40))
    d = ImageDraw.Draw(out)
    rnd = random.Random(int(t * FPS))
    for nx, ny, nw in nozzles:
        ln = length * (0.75 + 0.35 * rnd.random())
        for col, sc in (((255, 90, 20, 255), 1.0), ((255, 200, 40, 255), 0.65),
                        ((255, 255, 210, 255), 0.3)):
            hw = nw / 2 * sc
            pts = [(nx - hw, ny)]
            for k in range(1, 6):
                yy = ny + ln * sc * k / 6
                pts.append((nx - hw * (1 - k / 6) + rnd.uniform(-6, 6), yy))
            pts.append((nx + rnd.uniform(-8, 8), ny + ln * sc + 10))
            for k in range(5, 0, -1):
                yy = ny + ln * sc * k / 6
                pts.append((nx + hw * (1 - k / 6) + rnd.uniform(-6, 6), yy))
            pts.append((nx + hw, ny))
            d.polygon(pts, fill=col)
    out.alpha_composite(img, (0, 0))
    return out


KAZAN_NOZZLES = [(80, 555, 110), (700, 555, 110)]


def kazan_with_flames(t, length=130):
    return flames(S["kazan"], KAZAN_NOZZLES, t, length)


# ------------------------------------------------------------------ scenes
def scene_title(fr, t):
    burst(fr, t, "title", 30)
    for i, (word, t0) in enumerate((("SAMSALINO", 0.2), ("TANDIRINO", 1.15))):
        if t < t0:
            continue
        k = (t - t0)
        y = 700 + i * 230
        img = text_img(word, 168, (255, 238, 60, 255) if i == 0 else
                       (255, 120, 40, 255), stroke=16)
        for g in range(3, 0, -1):  # echo ghosts expanding outward
            gk = k - g * 0.12
            if 0 < gk < 0.9:
                gs = 1 + gk * 0.5
                paste(fr, img, W / 2, y, gs, gs, 0, max(0, 0.45 * (1 - gk / 0.9)))
        s = ease_out_back(k / 0.35) * (1 + 0.07 * pulse(t))
        paste(fr, img, W / 2, y, s, s, 3 * math.sin(t * 7 + i))
    if t > 1.5:
        k = ease_out_back((t - 1.5) / 0.6)
        sx, sy = squash(t, 0.06)
        paste_bottom(fr, S["samsa"][beat_at(t)[0] % 2], W / 2, 1560 + (1 - k) * 700,
                     0.75 * sx, 0.75 * sy, 6 * math.sin(t * 6))


def draw_samsa_on_tandir(fr, t, cx=W / 2, base=1500, scale=1.0, t_emerge=3.0):
    tandir = S["tandir"]
    tw, th = tandir.width * scale, tandir.height * scale
    paste_bottom(fr, tandir, cx, base + 6 * pulse(t), scale, scale)
    rim = base - th + 112 * scale
    i, p = beat_at(t)
    sx, sy = squash(t)
    lift = hop(t) * 250 * scale
    e = (t - t_emerge) / 0.55
    if e < 1:  # rising out of the oven, clipped at the rim
        lift = -(1 - ease_out_back(e)) * 520 * scale
        sx = sy = 1.0
    spr = S["samsa"][i % 2]
    sw, sh = int(spr.width * scale * sx), int(spr.height * scale * sy)
    im = spr.resize((sw, sh), Image.BILINEAR)
    ang = 8 * math.sin(math.pi * (i + p))
    if e >= 1:
        im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
    bottom = rim + 25 * scale - lift
    top = bottom - im.height
    if e < 1:
        visible = int(rim - top)
        if visible <= 0:
            return
        im = im.crop((0, 0, im.width, min(im.height, visible)))
    composite_clipped(fr, im, int(cx - im.width / 2), int(top))
    # steam puffs
    for k in range(3):
        ph = (t * 0.8 + k / 3) % 1
        r = 25 + 40 * ph
        x = cx + 160 * scale + 30 * math.sin(t * 2 + k)
        y = rim - 40 - ph * 260
        puff = Image.new("RGBA", (int(2 * r), int(2 * r)))
        ImageDraw.Draw(puff).ellipse([0, 0, 2 * r - 1, 2 * r - 1],
                                     fill=(255, 255, 255, int(150 * (1 - ph))))
        composite_clipped(fr, puff, int(x - r), int(y - r))


def scene_chorus(fr, t, s0):
    background(fr, t, "courtyard")
    draw_samsa_on_tandir(fr, t, t_emerge=s0)
    name_card(fr, t, s0, "SAMSALINO\nTANDIRINO", (255, 175, 40, 255))


def kazan_x(t, t0=13.0):
    u = max(-1.0, min(1.0, (t - (t0 + 5)) / 5))
    return W / 2 + 980 * math.copysign(abs(u) ** 1.7, u)


def kazan_y(t):
    return 760 + 70 * math.sin(t * 2.4) - 50 * hop(t)


def scene_verse1(fr, t):
    background(fr, t, "rooftops")
    # carrots raining from the flying kazan
    rng = random.Random(42)
    spawn = 13.6
    while spawn < 22.6:
        vx, spin, sc = rng.uniform(-120, 120), rng.uniform(-400, 400), rng.uniform(1.3, 1.9)
        dt = t - spawn
        if 0 <= dt < 2.2:
            x = kazan_x(spawn) + rng.uniform(-150, 150) + vx * dt
            y = kazan_y(spawn) + 200 + 250 * dt + 0.5 * 1500 * dt * dt
            if y < H + 100:
                paste(fr, S["carrot"], x, y, sc, sc, spin * dt)
        spawn += 0.22
    x, y = kazan_x(t), kazan_y(t)
    # speed lines
    d = ImageDraw.Draw(fr)
    for k in range(5):
        yy = y - 160 + k * 80
        ln = 160 + 80 * ((k * 37 + int(t * 20)) % 3)
        x1 = x - 420 - (k % 2) * 60
        d.rounded_rectangle([x1 - ln, yy - 7, x1, yy + 7], 7, fill=(255, 255, 255, 200))
    sx, sy = squash(t, 0.05)
    img = kazan_with_flames(t)
    paste(fr, img, x, y + 60, 0.95 * sx, 0.95 * sy, -6 + 5 * math.sin(t * 3))
    name_card(fr, t, 13.0, "PLOVOLINO\nKAZANINO", (255, 95, 60, 255))


def scene_verse2(fr, t):
    background(fr, t, "courtyard")
    i, p = beat_at(t)
    # wolf
    if t < 30.5:
        pose = "dance" if i % 2 == 0 else "dance_m"
        wx = 270 + 40 * math.sin(math.pi * (i + p))
        lift = hop(t) * 90
    else:
        pose = "clap" if p < 0.35 else "open"
        wx, lift = 270, hop(t) * 40
    sx, sy = squash(t, 0.07)
    paste_bottom(fr, S["wolf"][pose], wx, 1520 - lift, 0.74 * sx, 0.74 * sy,
                 6 * math.sin(math.pi * (i + p)))
    # croc
    strum = int(t * 4) % 2 == 0
    snap = 28.0 <= t < 30.5
    mouth_open = (i % 2 == 0) if snap else (p < 0.3 and i % 4 == 0)
    sx, sy = squash(t, 0.06)
    cx = 720
    paste_bottom(fr, S["croc"][(strum, mouth_open)], cx, 1530 - hop(t) * 45,
                 0.86 * sx, 0.86 * sy, 4 * math.sin(math.pi * (i + p) + 1))
    # music notes rising from the dutar
    rng = random.Random(9)
    for k in range(int((t - 23) * 4) + 1):
        st = 23 + k * 0.25
        dt = t - st
        sym = rng.choice(["♪", "♫"])
        col = rng.choice([(255, 80, 120, 255), (255, 210, 40, 255),
                          (80, 140, 255, 255), (170, 80, 220, 255)])
        off = rng.uniform(-80, 80)
        if 0 <= dt < 1.6:
            img = text_img(sym, 90, col, stroke=6, shadow=False, path=SYMBOL_FONT)
            paste(fr, img, cx - 60 + off + 40 * math.sin(dt * 5 + k), 1080 - dt * 330,
                  1, 1, 15 * math.sin(dt * 4), max(0, 1 - dt / 1.6))
    name_card(fr, t, 23.0, SONG["screen"]["croc"], (90, 215, 90, 255))


PONY_SC = 0.85
TEA_SC = 0.7


def teapot_angle(t):
    if t < 38.6:
        return 6 * math.sin(math.pi * (beat_at(t)[0] + beat_at(t)[1]))
    return 38 * ease_in_out((t - 38.6) / 0.7) + 3 * math.sin(t * 9)


def scene_verse3(fr, t):
    background(fr, t, "courtyard")
    i, p = beat_at(t)
    k = ease_in_out((t - 33.0) / 2.6)
    px = 1500 + (700 - 1500) * k
    moving = t < 35.6
    step = int(t * 8) % 2 if moving else i % 2
    lift = (abs(math.sin(t * 12)) * 30) if moving else hop(t) * 50
    base = 1520 - lift
    pony = S["pony"][step]
    pw, ph = pony.width * PONY_SC, pony.height * PONY_SC
    pang = (-4 + 4 * math.sin(t * 12)) if moving else 3 * math.sin(math.pi * (i + p))
    paste_bottom(fr, pony, px, base, PONY_SC, PONY_SC, pang)
    # piala on the ground
    pour_k = max(0.0, min(1.0, (t - 39.2) / 3.3))
    pia_x, pia_by = 210, 1500
    pia = S["piala"][int(round(pour_k * 8))]
    paste_bottom(fr, pia, pia_x, pia_by + 4 * pulse(t), 1, 1)
    # teapot on the saddle
    tp = S["teapot"]
    tcx = px - pw / 2 + 385 * PONY_SC
    tby = base - ph + 195 * PONY_SC
    tcy = tby - tp.height * TEA_SC / 2 - hop(t) * 25
    ang = teapot_angle(t)
    paste(fr, tp, tcx, tcy, TEA_SC, TEA_SC, ang)
    # tea stream from the rotated spout tip
    if t >= 39.2:
        ox = (ch.TEAPOT_SPOUT[0] - tp.width / 2) * TEA_SC
        oy = (ch.TEAPOT_SPOUT[1] - tp.height / 2) * TEA_SC
        a = math.radians(ang)
        sx = tcx + ox * math.cos(a) + oy * math.sin(a)
        sy = tcy - ox * math.sin(a) + oy * math.cos(a)
        ex, ey = pia_x, pia_by - 95
        pts = []
        for n in range(26):
            u = n / 25
            pts.append((sx + (ex - sx) * u, sy + (ey - sy) * u * u - 120 * u * (1 - u)))
        d = ImageDraw.Draw(fr)
        d.line(pts, fill=OUT, width=26, joint="curve")
        d.line(pts, fill=(160, 195, 50, 255), width=14, joint="curve")
        for n in range(6):
            u = ((t * 2.5 + n / 6) % 1)
            x = sx + (ex - sx) * u + 10 * math.sin(n)
            y = sy + (ey - sy) * u * u - 120 * u * (1 - u)
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(200, 230, 90, 255))
    # "SALOM!" speech bubble
    if 38.0 <= t < 40.7:
        kk = ease_out_back((t - 38.0) / 0.3)
        bub = speech_bubble(SONG["screen"]["salom"])
        paste(fr, bub, min(tcx + 230, W - 230), tcy - 260, kk * (1 + 0.06 * pulse(t)),
              kk * (1 + 0.06 * pulse(t)), -5)
    name_card(fr, t, 33.0, "CHAYNIKONI\nPIALONI", (80, 160, 255, 255))


@lru_cache(maxsize=4)
def speech_bubble(text):
    txt = text_img(text, 96, (230, 40, 60, 255), stroke=8, shadow=False)
    w, h = txt.width + 80, txt.height + 70
    im = Image.new("RGBA", (w, h + 70))
    d = ImageDraw.Draw(im)
    d.polygon([(70, h - 20), (40, h + 60), (150, h - 20)], fill=OUT)
    d.ellipse([4, 4, w - 4, h - 4], fill=OUT)
    d.ellipse([14, 14, w - 14, h - 14], fill=(255, 255, 255, 255))
    d.polygon([(82, h - 30), (52, h + 40), (138, h - 30)], fill=(255, 255, 255, 255))
    im.alpha_composite(txt, ((w - txt.width) // 2, (h - txt.height) // 2))
    return im


def confetti(fr, t, t0, rate=8, seed=5):
    rng = random.Random(seed)
    n = int((t - t0 + 2) * rate)
    for k in range(n):
        st = t0 - 2 + k / rate
        x0 = rng.uniform(0, W)
        kind = rng.randint(0, 2)
        spin = rng.uniform(-300, 300)
        dt = t - st
        if 0 <= dt < 2.5:
            y = -80 + dt * 800
            x = x0 + 60 * math.sin(dt * 3 + k)
            if kind == 0:
                paste(fr, S["carrot"], x, y, 0.8, 0.8, spin * dt)
            else:
                col = (255, 245, 210, 255) if kind == 1 else (130, 50, 150, 255)
                r = 12 if kind == 1 else 18
                d = ImageDraw.Draw(fr)
                d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=col,
                          outline=OUT, width=4)


def scene_chorus2(fr, t):
    background(fr, t, "courtyard")
    i, p = beat_at(t)
    confetti(fr, t, 43.0)
    # flying kazan overhead
    paste(fr, kazan_with_flames(t, 90), W / 2 + 120 * math.sin(t * 1.5),
          720 + 40 * math.sin(t * 3) - 40 * hop(t), 0.58, 0.58, 6 * math.sin(t * 2))
    sx, sy = squash(t, 0.09)
    # samsa (left)
    paste_bottom(fr, S["samsa"][i % 2], 175, 1530 - hop(t) * 140, 0.56 * sx, 0.56 * sy,
                 9 * math.sin(math.pi * (i + p)))
    # croc (middle)
    paste_bottom(fr, S["croc"][(int(t * 4) % 2 == 0, i % 2 == 0)], 485,
                 1530 - hop(t) * 70, 0.56 * sy, 0.56 * sx, -6 * math.sin(math.pi * (i + p)))
    # teapot on pony (right)
    paste_bottom(fr, S["tea_combo"], 850, 1530 - hop(t) * 90, 0.56 * sx, 0.56 * sy,
                 6 * math.sin(math.pi * (i + p) + 0.7))
    name_card(fr, t, 43.0, SONG["screen"]["chorus2"], (255, 220, 50, 255))


def finale_sprite(key, t):
    if key == "samsa":
        return S["samsa"][beat_at(t)[0] % 2]
    if key == "kazan":
        return kazan_with_flames(t, 110)
    if key == "croc":
        return S["croc"][(int(t * 6) % 2 == 0, beat_at(t)[0] % 2 == 0)]
    return S["tea_combo"]


def scene_finale(fr, t):
    for t0, t1, key, name in FINALE_SLOTS:
        if t0 <= t < t1:
            k = (t - t0) / (t1 - t0)
            burst(fr, t, key, 90)
            spr = finale_sprite(key, t)
            fit = 820 / max(spr.width, spr.height)
            z = fit * (0.65 + 0.6 * k)
            paste(fr, spr, W / 2, 1050, z, z, 8 * math.sin(t * 14))
            nimg = text_img(name, 150, (255, 255, 255, 255), stroke=16)
            zz = 0.7 + 0.55 * ease_out_back(min(1, k * 2.5)) + 0.25 * k
            zz = min(zz, W * 0.94 / nimg.width)
            paste(fr, nimg, W / 2, 380, zz, zz, 5 * math.sin(t * 11))
            return
    burst(fr, t, "final", 120 if t < 59 else 220)
    if t >= 59.0:
        k = (t - 59.0)
        shake = 55 * math.exp(-k * 2.5)
        rng = random.Random(int(t * FPS))
        ox, oy = rng.uniform(-shake, shake), rng.uniform(-shake, shake)
    else:
        ox = oy = 0
    i, p = beat_at(t)
    sx, sy = squash(t, 0.1)
    row = [("samsa", 190, 0.48), ("croc", 420, 0.45), ("tea", 680, 0.46), ("kazan", 920, 0.36)]
    for n, (key, x, sc) in enumerate(row):
        spr = finale_sprite(key, t)
        lift = hop(t) * (110 if (i + n) % 2 else 50)
        paste_bottom(fr, spr, x + ox, 1500 - lift + oy, sc * sx, sc * sy,
                     10 * math.sin(math.pi * (i + p) + n))
    if t < 59.0:
        paste(fr, text_img(SONG["screen"]["together"], 120, (255, 255, 255, 255), stroke=14),
              W / 2 + ox, 330, 1 + 0.08 * pulse(t), 1 + 0.08 * pulse(t),
              4 * math.sin(t * 9))
        for num, nt in (("1", 58.0), ("2", 58.35), ("3", 58.7)):
            if nt <= t < nt + 0.33 or (num == "3" and nt <= t < 59.0):
                kk = ease_out_back((t - nt) / 0.15)
                paste(fr, text_img(num, 380, (255, 230, 40, 255), stroke=22),
                      W / 2, 720, kk, kk, -8 + 16 * (num == "2"))
    else:
        k = t - 59.0
        bimg = text_img(SONG["screen"]["boom"], 150, (255, 235, 50, 255), stroke=18)
        z = 0.6 + 0.9 * ease_out_back(min(1, k / 0.25)) + 0.15 * k
        z = min(z, W * 0.96 / bimg.width)
        paste(fr, bimg, W / 2 + ox, 560 + oy, z, z, 6 * math.sin(t * 25))


def render(t):
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if t < 3:
        scene_title(fr, t)
    elif t < 13:
        scene_chorus(fr, t, 3.0)
    elif t < 23:
        scene_verse1(fr, t)
    elif t < 33:
        scene_verse2(fr, t)
    elif t < 43:
        scene_verse3(fr, t)
    elif t < 53:
        scene_chorus2(fr, t)
    else:
        scene_finale(fr, t)
    # camera punch on every kick
    z = 1 + 0.018 * pulse(t, 9) + (0.05 * math.exp(-(t - 59) * 3) if t >= 59 else 0)
    if z > 1.001:
        big = fr.resize((int(W * z), int(H * z)), Image.BILINEAR)
        x0, y0 = (big.width - W) // 2, (big.height - H) // 2
        fr = big.crop((x0, y0, x0 + W, y0 + H))
    subtitles(fr, t)
    flash(fr, t)
    return fr.convert("RGB")


# ------------------------------------------------------------------ encode
def encode_segment(args):
    f0, f1, path = args
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
           "-preset", "medium", "-crf", "21", "-tune", "animation", "-pix_fmt", "yuv420p", "-r", str(FPS),
           path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(render(f / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for segment {path}")
    return f1 - f0


def build_assets(assets_dir):
    global S
    S = ch.build_sprites(assets_dir, W, H)
    S["tea_combo"] = tea_combo()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tts", default="auto", choices=["auto", "edge", "kokoro", "espeak"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--lang", default="en", choices=sorted(SONGS),
                    help="song language: en (English) or uz (Uzbek)")
    ap.add_argument("--out", default=None,
                    help="default: output/samsalino.mp4 (en), output/samsalino_uz.mp4 (uz)")
    ap.add_argument("--assets", default=os.path.join(HERE, "assets"))
    ap.add_argument("--preview", type=float, nargs="*",
                    help="only write PNG stills at these times (seconds)")
    a = ap.parse_args()

    global SONG, LYRICS
    SONG, LYRICS = SONGS[a.lang], build_lyrics(SONGS[a.lang])
    audio.LANG = a.lang
    a.out = a.out or os.path.join(
        HERE, "output", "samsalino.mp4" if a.lang == "en" else f"samsalino_{a.lang}.mp4")
    t_start = time.time()
    assets = a.assets if os.path.isdir(a.assets) else None
    print(f"Drawing characters{' (using PNGs from ' + assets + ')' if assets else ''} ...")
    build_assets(assets)

    if a.preview is not None:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        for t in a.preview:
            p = os.path.join(os.path.dirname(a.out), f"preview_{t:05.2f}.png")
            render(t).save(p)
            print("  wrote", p)
        return

    print("Narration ...")
    narrator = audio.Narrator(a.tts)
    voice, _ = audio.render_voice(LYRICS, narrator, DUR)
    print("Drum beat ...")
    drums = audio.make_drums(BEATS, DUR, start=3.0, roll=(57.4, 59.0), boom=59.0)
    stereo = audio.mix(voice, drums)

    tmp = tempfile.mkdtemp(prefix="samsalino_")
    wav = os.path.join(tmp, "mix.wav")
    audio.write_wav(wav, stereo)

    total = int(DUR * FPS)
    n = max(1, a.workers)
    bounds = [round(total * k / n) for k in range(n + 1)]
    segs = [(bounds[k], bounds[k + 1], os.path.join(tmp, f"seg{k:02d}.mp4"))
            for k in range(n)]
    print(f"Rendering {total} frames with {n} workers ...")
    ctx = mp.get_context("fork")
    with ctx.Pool(n) as pool:
        done = 0
        for c in pool.imap_unordered(encode_segment, segs):
            done += c
            print(f"  {done}/{total} frames")
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for _, _, p in segs:
            f.write(f"file '{p}'\n")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", lst, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-t", str(DUR),
                    "-movflags", "+faststart", a.out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Done: {a.out}  ({time.time() - t_start:.0f}s, voice: {narrator.backend})")


if __name__ == "__main__":
    sys.exit(main())
