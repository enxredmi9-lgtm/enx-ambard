"""Bold flat cartoon characters and backgrounds drawn with Pillow.

Everything is drawn supersampled (SS x) and downscaled for smooth edges.
Coordinates passed to the Canvas helpers are in final-pixel units.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageOps

SS = 3                      # supersampling factor
OUT = (28, 18, 32, 255)     # outline colour
OW = 9                      # default outline width (final px)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def P(pts):
        return [(x * SS, y * SS) for x, y in pts]

    @staticmethod
    def B(box):
        return [v * SS for v in box]

    def poly(self, pts, fill, ow=OW, outline=OUT):
        self.d.polygon(self.P(pts), fill=fill, outline=outline if ow else None,
                       width=int(ow * SS) if ow else 1)

    def ell(self, box, fill, ow=OW, outline=OUT):
        self.d.ellipse(self.B(box), fill=fill, outline=outline if ow else None,
                       width=int(ow * SS) if ow else 1)

    def rrect(self, box, r, fill, ow=OW, outline=OUT):
        self.d.rounded_rectangle(self.B(box), radius=r * SS, fill=fill,
                                 outline=outline if ow else None,
                                 width=int(ow * SS) if ow else 1)

    def line(self, pts, fill=OUT, w=OW, caps=True):
        self.d.line(self.P(pts), fill=fill, width=int(w * SS), joint="curve")
        if caps:
            r = w / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse(self.B((x - r, y - r, x + r, y + r)), fill=fill)

    def thick_line(self, pts, fill, w, ow=OW):
        """Line with an outline: draw outline-coloured wide line, then fill."""
        self.line(pts, OUT, w + 2 * ow)
        self.line(pts, fill, w)

    def arc(self, box, start, end, fill=OUT, w=OW):
        self.d.arc(self.B(box), start, end, fill=fill, width=int(w * SS))

    def pie(self, box, start, end, fill, ow=OW):
        self.d.pieslice(self.B(box), start, end, fill=fill, outline=OUT,
                        width=int(ow * SS))

    def chord(self, box, start, end, fill, ow=OW):
        self.d.chord(self.B(box), start, end, fill=fill, outline=OUT,
                     width=int(ow * SS))

    def done(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


# ---------------------------------------------------------------- helpers
def rounded_poly(pts, r, steps=10):
    """Polygon with rounded corners (radius r) as a dense point list."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        a = (p1[0] + v1[0] / l1 * r, p1[1] + v1[1] / l1 * r)
        b = (p1[0] + v2[0] / l2 * r, p1[1] + v2[1] / l2 * r)
        for k in range(steps + 1):  # quadratic bezier a -> p1 -> b
            t = k / steps
            x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * b[0]
            y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * b[1]
            out.append((x, y))
    return out


def eye(c, cx, cy, r, look=(0.15, 0.1), lid=False):
    c.ell((cx - r, cy - r * 1.1, cx + r, cy + r * 1.1), (255, 255, 255, 255))
    pr = r * 0.52
    px, py = cx + look[0] * r, cy + look[1] * r
    c.ell((px - pr, py - pr, px + pr, py + pr), (20, 15, 25, 255), ow=0)
    hr = pr * 0.38
    c.ell((px - pr * 0.45 - hr, py - pr * 0.45 - hr, px - pr * 0.45 + hr,
           py - pr * 0.45 + hr), (255, 255, 255, 255), ow=0)
    if lid:
        c.chord((cx - r, cy - r * 1.1, cx + r, cy + r * 1.1), 180, 360,
                lid if isinstance(lid, tuple) else (0, 0, 0, 255))


def mouth(c, cx, cy, w, h, tongue=True):
    c.chord((cx - w / 2, cy - h, cx + w / 2, cy + h), 0, 180, (120, 20, 40, 255))
    if tongue:
        c.chord((cx - w / 4, cy + h * 0.2, cx + w / 4, cy + h * 0.95), 180, 360,
                (240, 90, 110, 255), ow=0)
    c.line([(cx - w / 2, cy), (cx + w / 2, cy)], OUT, OW * 0.8)


def cheeks(c, pts, r):
    for x, y in pts:
        c.ell((x - r, y - r * 0.6, x + r, y + r * 0.6), (255, 120, 140, 140), ow=0)


# ---------------------------------------------------------------- 1. samsa
def draw_samsa(arms_up=False):
    c = Canvas(560, 660)
    # arms behind body
    if arms_up:
        c.thick_line([(130, 330), (60, 220), (40, 160)], (205, 130, 40, 255), 18)
        c.thick_line([(430, 330), (500, 220), (520, 160)], (205, 130, 40, 255), 18)
    else:
        c.thick_line([(130, 360), (60, 400), (30, 470)], (205, 130, 40, 255), 18)
        c.thick_line([(430, 360), (500, 400), (530, 470)], (205, 130, 40, 255), 18)
    # legs + sneakers
    for lx in (205, 355):
        c.thick_line([(lx, 470), (lx - 5 if lx < 280 else lx + 5, 575)],
                     (205, 130, 40, 255), 20)
    for sx, flip in ((190, -1), (370, 1)):
        x0 = sx - 70 if flip < 0 else sx - 40
        c.rrect((x0, 560, x0 + 110, 615), 26, (230, 40, 50, 255))
        c.rrect((x0, 595, x0 + 110, 622), 12, (255, 255, 255, 255), ow=6)
        c.line([(x0 + 30, 572), (x0 + 55, 582)], (255, 255, 255, 255), 6)
    body = rounded_poly([(280, 30), (35, 480), (525, 480)], 60)
    c.poly(body, (243, 172, 50, 255), ow=11)
    hl = rounded_poly([(270, 95), (110, 400), (330, 300)], 40)
    c.poly(hl, (255, 205, 100, 255), ow=0)
    # crimped crust edge
    for i in range(9):
        x = 85 + i * 49
        c.arc((x, 445, x + 45, 490), 200, 340, (190, 115, 30, 255), 6)
    # sesame seeds
    rnd = random.Random(7)
    for _ in range(16):
        y = rnd.uniform(90, 250)
        half = (y - 30) * 0.5
        x = rnd.uniform(280 - half + 25, 280 + half - 25)
        a = rnd.uniform(0, math.pi)
        dx, dy = math.cos(a) * 9, math.sin(a) * 5
        c.ell((x - 9, y - 5, x + 9, y + 5), (255, 245, 210, 255), ow=3)
    eye(c, 210, 315, 46)
    eye(c, 350, 315, 46)
    c.line([(165, 250), (240, 262)], OUT, 10)
    c.line([(320, 262), (395, 250)], OUT, 10)
    mouth(c, 280, 385, 120, 55)
    cheeks(c, [(150, 380), (410, 380)], 28)
    return c.done()


def draw_tandir():
    c = Canvas(640, 560)
    c.rrect((10, 470, 630, 550), 18, (176, 84, 52, 255))       # brick base
    for x in range(10, 630, 78):
        c.line([(x, 470), (x, 550)], (120, 50, 30, 255), 5, caps=False)
    c.line([(10, 510), (630, 510)], (120, 50, 30, 255), 5, caps=False)
    dome = [(320 + 280 * math.cos(a), 480 - 390 * math.sin(a))
            for a in [math.pi * i / 60 for i in range(61)]]
    c.poly(dome, (205, 120, 66, 255), ow=11)
    for k, ry in enumerate((330, 260, 190)):  # clay rings
        pts = [(320 + 280 * math.cos(a) * (ry / 390) ** 0.3, 480 - ry * math.sin(a))
               for a in [math.pi * (0.12 + 0.76 * i / 30) for i in range(31)]]
        c.line(pts, (165, 85, 45, 255), 6)
    c.ell((180, 75, 460, 150), (60, 22, 12, 255), ow=10)       # top opening
    c.ell((215, 92, 425, 140), (255, 120, 30, 255), ow=0)
    c.ell((255, 102, 385, 132), (255, 210, 80, 255), ow=0)
    c.chord((250, 360, 390, 500), 180, 360, (60, 22, 12, 255))  # ash hole
    return c.done()


# ---------------------------------------------------------------- 2. kazan
def draw_kazan():
    c = Canvas(780, 640)
    # boosters behind
    for x0 in (20, 640):
        c.rrect((x0, 300, x0 + 120, 520), 30, (190, 196, 210, 255))
        c.rrect((x0, 380, x0 + 120, 420), 0, (230, 50, 50, 255), ow=6)
        c.poly([(x0 + 15, 515), (x0 + 105, 515), (x0 + 120, 560), (x0, 560)],
               (90, 95, 110, 255))
    # plov mound
    mound = [(390 + 250 * math.cos(a), 300 - 170 * math.sin(a))
             for a in [math.pi * i / 50 for i in range(51)]]
    c.poly(mound, (242, 190, 80, 255), ow=10)
    rnd = random.Random(3)
    for _ in range(170):
        a = rnd.uniform(0.05, math.pi - 0.05)
        rr = rnd.uniform(0, 0.92)
        x = 390 + 240 * rr * math.cos(a)
        y = 300 - 160 * rr * math.sin(a)
        ang = rnd.uniform(0, math.pi)
        dx, dy = 7 * math.cos(ang), 7 * math.sin(ang)
        c.line([(x - dx, y - dy), (x + dx, y + dy)], (255, 238, 175, 255), 5)
    for _ in range(20):  # carrot sticks
        a = rnd.uniform(0.15, math.pi - 0.15)
        rr = rnd.uniform(0.2, 0.85)
        x = 390 + 240 * rr * math.cos(a)
        y = 300 - 160 * rr * math.sin(a)
        ang = rnd.uniform(0, math.pi)
        dx, dy = 22 * math.cos(ang), 22 * math.sin(ang)
        c.line([(x - dx, y - dy), (x + dx, y + dy)], (90, 30, 10, 255), 15)
        c.line([(x - dx, y - dy), (x + dx, y + dy)], (245, 120, 25, 255), 9)
    for _ in range(9):  # meat
        a = rnd.uniform(0.3, math.pi - 0.3)
        rr = rnd.uniform(0.2, 0.75)
        x = 390 + 240 * rr * math.cos(a)
        y = 300 - 160 * rr * math.sin(a)
        c.rrect((x - 20, y - 15, x + 20, y + 15), 8, (130, 70, 40, 255), ow=5)
    for x, y in ((300, 230), (470, 250), (390, 200)):  # chickpeas
        c.ell((x - 10, y - 10, x + 10, y + 10), (230, 200, 120, 255), ow=4)
    # whole garlic on top
    c.ell((355, 115, 425, 185), (250, 245, 235, 255))
    c.line([(390, 125), (390, 180)], (200, 190, 180, 255), 4)
    c.line([(390, 117), (395, 95)], (120, 150, 60, 255), 8)
    # pot body
    pot = [(390 + 280 * math.cos(a), 330 + 260 * math.sin(a))
           for a in [math.pi * i / 50 for i in range(51)]]
    c.poly(pot, (38, 38, 46, 255), ow=11)
    c.arc((160, 360, 620, 570), 110, 160, (110, 110, 125, 255), 14)
    c.rrect((90, 295, 690, 350), 25, (78, 78, 90, 255), ow=10)  # rim
    for hx in (55, 725):  # handles
        c.ell((hx - 40, 300, hx + 40, 360), None, ow=14)
    eye(c, 315, 430, 46)
    eye(c, 465, 430, 46)
    c.line([(265, 365), (345, 380)], (255, 255, 255, 255), 10)
    c.line([(435, 380), (515, 365)], (255, 255, 255, 255), 10)
    mouth(c, 390, 505, 120, 40)
    return c.done()


def draw_carrot():
    c = Canvas(70, 130)
    c.poly([(15, 40), (55, 40), (35, 125)], (245, 120, 25, 255), ow=6)
    for x in (22, 35, 48):
        c.poly([(35, 42), (x - 9, 5), (x + 3, 8)], (60, 170, 60, 255), ow=5)
    c.line([(25, 65), (38, 68)], (190, 80, 10, 255), 4)
    c.line([(30, 90), (40, 92)], (190, 80, 10, 255), 4)
    return c.done()


# ---------------------------------------------------------------- 3. croc
GREEN = (78, 178, 72, 255)
GREEN_D = (50, 130, 50, 255)
BELLY = (190, 230, 130, 255)


def draw_dutar():
    c = Canvas(200, 560)
    c.rrect((88, 20, 112, 400), 10, (120, 65, 30, 255), ow=7)   # neck
    for y in range(70, 390, 40):
        c.line([(90, y), (110, y)], (230, 200, 140, 255), 4, caps=False)
    c.rrect((80, 0, 120, 45), 10, (90, 45, 20, 255), ow=6)      # head
    for y in (12, 30):
        c.line([(60, y), (80, y)], (90, 45, 20, 255), 9)
        c.line([(120, y + 6), (140, y + 6)], (90, 45, 20, 255), 9)
    c.ell((15, 330, 185, 555), (190, 115, 55, 255), ow=9)       # pear body
    c.ell((40, 360, 120, 480), (215, 150, 85, 255), ow=0)
    c.rrect((80, 495, 120, 510), 4, (60, 30, 15, 255), ow=0)     # bridge
    c.line([(96, 30), (96, 505)], (245, 240, 220, 255), 3, caps=False)
    c.line([(104, 30), (104, 505)], (245, 240, 220, 255), 3, caps=False)
    return c.done()


def draw_croc(strum_up=False, mouth_open=False):
    W, H = 640, 1010
    c = Canvas(W, H)
    # tail
    tail = [(210, 760), (60, 820), (5, 930), (60, 900), (150, 870), (250, 850)]
    c.poly(rounded_poly(tail, 25), GREEN, ow=10)
    for x, y in ((70, 845), (35, 885)):
        c.poly([(x, y), (x + 18, y - 30), (x + 30, y + 5)], GREEN_D, ow=6)
    # legs
    for lx in (245, 395):
        c.rrect((lx - 40, 820, lx + 40, 955), 30, GREEN, ow=10)
        c.rrect((lx - 60, 930, lx + 60, 980), 22, GREEN_D, ow=9)
    # torso
    c.ell((165, 400, 475, 880), GREEN, ow=11)
    c.ell((215, 470, 425, 860), BELLY, ow=8)
    for y in range(520, 840, 55):
        c.arc((230, y - 30, 410, y + 30), 20, 160, (150, 195, 95, 255), 6)
    # head + jaws
    c.ell((180, 170, 440, 420), GREEN, ow=11)
    if mouth_open:
        c.poly(rounded_poly([(380, 300), (620, 365), (600, 410), (380, 400)], 20),
               (200, 50, 70, 255), ow=9)
        c.poly(rounded_poly([(370, 340), (620, 410), (610, 445), (380, 425)], 18),
               GREEN, ow=10)
        for x in range(410, 600, 34):
            c.poly([(x, 404 - (x - 380) * 0.12), (x + 14, 380 - (x - 380) * 0.12),
                    (x + 26, 404 - (x - 380) * 0.12)], (255, 255, 255, 255), ow=4)
        top = [(360, 220), (615, 285), (625, 345), (380, 330)]
    else:
        top = [(360, 220), (615, 300), (620, 375), (380, 395)]
        for x in range(400, 600, 34):
            c.poly([(x, 385 - (x - 380) * 0.1), (x + 14, 410 - (x - 380) * 0.1),
                    (x + 26, 385 - (x - 380) * 0.1)], (255, 255, 255, 255), ow=4)
    c.poly(rounded_poly(top, 30), GREEN, ow=11)
    c.ell((585, 290, 600, 305), OUT, ow=0)
    for x, y in ((460, 280), (520, 300), (440, 330)):
        c.ell((x - 6, y - 6, x + 6, y + 6), GREEN_D, ow=0)
    # eye bumps + eyes
    for ex in (265, 365):
        c.ell((ex - 60, 165, ex + 60, 275), GREEN, ow=10)
        eye(c, ex, 215, 44, look=(0.25, 0.05))
    cheeks(c, [(250, 330)], 26)
    if not mouth_open:
        c.arc((330, 300, 470, 400), 20, 90, OUT, 8)
    # blue doppi (Uzbek skullcap)
    dop = rounded_poly([(195, 160), (215, 80), (405, 80), (425, 160)], 18)
    c.poly(dop, (35, 85, 205, 255), ow=10)
    c.rrect((185, 140, 435, 172), 10, (20, 50, 140, 255), ow=8)
    for x in (245, 310, 375):  # pepper motifs
        c.ell((x - 16, 96, x + 16, 128), (255, 255, 255, 255), ow=0)
        c.poly([(x + 10, 98), (x + 30, 82), (x + 16, 110)], (255, 255, 255, 255), ow=0)
        c.ell((x - 6, 106, x + 6, 118), (35, 85, 205, 255), ow=0)
    # dutar across the body + arms
    dutar = draw_dutar().rotate(-38, expand=True, resample=Image.BICUBIC)
    big = dutar.resize((dutar.width * SS, dutar.height * SS), Image.BICUBIC)
    c.im.alpha_composite(big, (110 * SS, 330 * SS))
    c.thick_line([(205, 500), (175, 600), (215, 645)], GREEN, 30)   # neck arm
    c.ell((195, 620, 245, 670), GREEN, ow=9)
    hand_y = 690 if strum_up else 760
    c.thick_line([(430, 520), (470, 640), (400, hand_y)], GREEN, 30)  # strum arm
    c.ell((375, hand_y - 25, 425, hand_y + 25), GREEN, ow=9)
    return c.done()


def draw_wolf(pose="dance"):
    """pose: dance | open | clap"""
    c = Canvas(480, 840)
    GREY, GREY_D, LIGHT = (150, 155, 172, 255), (105, 110, 128, 255), (222, 222, 232, 255)
    # tail
    c.poly(rounded_poly([(330, 560), (450, 470), (470, 560), (360, 620)], 30), GREY_D)
    # legs
    if pose == "dance":
        c.thick_line([(200, 600), (150, 700), (190, 780)], GREY, 34)
        c.thick_line([(290, 600), (380, 670), (440, 640)], GREY, 34)
        c.ell((150, 760, 240, 805), GREY_D)
        c.ell((420, 610, 470, 670), GREY_D)
    else:
        c.thick_line([(200, 600), (185, 780)], GREY, 34)
        c.thick_line([(290, 600), (305, 780)], GREY, 34)
        c.ell((140, 760, 230, 805), GREY_D)
        c.ell((265, 760, 355, 805), GREY_D)
    c.ell((140, 330, 350, 650), GREY, ow=10)                  # body
    c.ell((185, 400, 305, 630), LIGHT, ow=0)
    # arms
    if pose == "dance":
        c.thick_line([(160, 400), (90, 300), (80, 200)], GREY, 30)
        c.thick_line([(330, 400), (400, 470), (430, 540)], GREY, 30)
        hands = [(80, 190), (432, 548)]
    elif pose == "open":
        c.thick_line([(160, 400), (70, 420), (40, 340)], GREY, 30)
        c.thick_line([(330, 400), (420, 420), (450, 340)], GREY, 30)
        hands = [(40, 330), (450, 330)]
    else:
        c.thick_line([(160, 400), (190, 470), (232, 450)], GREY, 30)
        c.thick_line([(330, 400), (300, 470), (258, 450)], GREY, 30)
        hands = [(225, 450), (265, 450)]
    for hx, hy in hands:
        c.ell((hx - 24, hy - 24, hx + 24, hy + 24), GREY_D, ow=8)
    # head
    for ex, flip in ((165, -1), (325, 1)):
        c.poly([(ex - 55, 140), (ex + 15 * flip, 20), (ex + 55, 140)], GREY, ow=10)
        c.poly([(ex - 25, 125), (ex + 10 * flip, 60), (ex + 25, 125)],
               (250, 160, 175, 255), ow=0)
    c.ell((115, 80, 375, 350), GREY, ow=11)
    c.ell((180, 220, 310, 345), LIGHT, ow=8)
    c.ell((222, 215, 268, 250), OUT, ow=0)
    eye(c, 195, 175, 36, look=(0.1, 0.2))
    eye(c, 295, 175, 36, look=(0.1, 0.2))
    c.chord((205, 255, 285, 330), 0, 180, (120, 20, 40, 255), ow=7)
    c.chord((225, 285, 265, 330), 0, 180, (240, 90, 110, 255), ow=0)
    return c.done()


# ---------------------------------------------------------------- 4. tea
BLUE = (30, 75, 190, 255)


def pattern_layer(w, h, seed):
    """Blue-and-white 'paxta' (cotton) style pattern."""
    lay = Image.new("RGBA", (w * SS, h * SS), (250, 252, 255, 255))
    d = ImageDraw.Draw(lay)
    step = 70 * SS
    for k in range(-h * SS, w * SS + h * SS, step):
        d.line([(k, 0), (k + h * SS, h * SS)], fill=BLUE, width=7 * SS)
        d.line([(k, h * SS), (k + h * SS, 0)], fill=BLUE, width=7 * SS)
    rnd = random.Random(seed)
    for gx in range(0, w * SS + step, step):
        for gy in range(0, h * SS + step, step):
            cx, cy = gx + step / 2, gy + step / 2 - 0
            cx = gx
            cy = gy + step / 2
            r = 15 * SS
            for a in range(3):
                ang = a * 2 * math.pi / 3 + 0.5
                x, y = cx + math.cos(ang) * r * 0.8, cy + math.sin(ang) * r * 0.8
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255),
                          outline=BLUE, width=4 * SS)
            d.ellipse([cx - 6 * SS, cy - 6 * SS, cx + 6 * SS, cy + 6 * SS],
                      fill=(235, 180, 40, 255))
    return lay


def draw_teapot():
    """Spout points LEFT; spout tip at (14, 150) in local coordinates."""
    c = Canvas(540, 460)
    # spout
    c.poly([(150, 280), (60, 210), (14, 140), (40, 130), (95, 190), (165, 230)],
           (250, 252, 255, 255), ow=9)
    c.line([(28, 140), (50, 155)], BLUE, 8)
    # handle
    c.arc((380, 170, 520, 360), 270, 90, OUT, 40)
    c.arc((380, 170, 520, 360), 270, 90, BLUE, 22)
    # body with pattern
    body_box = (110, 120, 450, 440)
    mask = Image.new("L", c.im.size, 0)
    ImageDraw.Draw(mask).ellipse(Canvas.B(body_box), fill=255)
    pat = pattern_layer(540, 460, 1)
    c.im.paste(pat, (0, 0), mask)
    c.ell(body_box, None, ow=11)
    # eyes on white patches
    for ex in (225, 335):
        c.ell((ex - 55, 220, ex + 55, 330), (255, 255, 255, 255), ow=0)
        eye(c, ex, 275, 42, look=(-0.2, 0.05))
    mouth(c, 280, 360, 90, 32)
    # lid + knob
    c.chord((190, 70, 370, 170), 180, 360, (250, 252, 255, 255), ow=9)
    c.rrect((180, 110, 380, 135), 10, BLUE, ow=8)
    c.ell((255, 35, 305, 85), (235, 180, 40, 255), ow=8)
    return c.done()


TEAPOT_SPOUT = (14, 140)


def draw_pony(step=0):
    c = Canvas(680, 600)
    BR, BR_D, MANE = (190, 118, 62, 255), (140, 82, 40, 255), (95, 50, 30, 255)
    # tail
    c.poly(rounded_poly([(560, 220), (665, 250), (650, 400), (600, 300)], 30), MANE)
    # legs (two poses)
    legs = ([(230, 330, 180, 480), (300, 330, 330, 485), (470, 330, 430, 480),
             (520, 330, 580, 470)] if step == 0 else
            [(230, 330, 270, 485), (300, 330, 250, 475), (470, 330, 520, 485),
             (520, 330, 470, 480)])
    for x0, y0, x1, y1 in legs:
        c.thick_line([(x0, y0), (x1, y1)], BR, 34)
        c.rrect((x1 - 26, y1 - 8, x1 + 26, y1 + 26), 8, OUT, ow=0)
    c.ell((180, 200, 580, 400), BR, ow=11)                     # body
    c.ell((260, 300, 500, 395), (220, 160, 105, 255), ow=0)
    # neck + head
    c.poly([(150, 120), (250, 110), (300, 260), (200, 300)], BR, ow=10)
    c.ell((30, 40, 230, 200), BR, ow=11)
    c.ell((5, 100, 120, 200), (225, 165, 115, 255), ow=9)       # muzzle
    c.ell((30, 135, 48, 153), OUT, ow=0)
    c.poly([(150, 60), (175, -0), (205, 70)], BR, ow=9)        # ear
    eye(c, 135, 100, 32, look=(-0.3, 0))
    c.arc((25, 150, 110, 195), 20, 150, OUT, 7)
    for i in range(6):                                          # mane
        y = 40 + i * 42
        x = 200 + i * 18
        c.poly([(x, y), (x + 60, y + 20), (x + 10, y + 50)], MANE, ow=7)
    # saddle with ikat-ish stripes
    c.rrect((290, 180, 480, 250), 20, (220, 40, 60, 255), ow=9)
    for i, col in enumerate(((255, 210, 40, 255), (40, 120, 220, 255),
                             (255, 255, 255, 255))):
        c.line([(320 + i * 50, 190), (335 + i * 50, 240)], col, 12)
    return c.done()


def draw_piala(fill=0.0):
    c = Canvas(260, 150)
    mask = Image.new("L", c.im.size, 0)
    ImageDraw.Draw(mask).chord(Canvas.B((10, -60, 250, 140)), 0, 180, fill=255)
    c.im.paste(pattern_layer(260, 150, 2), (0, 0), mask)
    c.chord((10, -60, 250, 140), 0, 180, None, ow=9)
    c.ell((10, 25, 250, 75), (255, 255, 255, 255), ow=9)
    if fill > 0:
        k = 0.4 + 0.6 * fill
        c.ell((130 - 110 * k, 50 - 22 * k, 130 + 110 * k, 50 + 22 * k),
              (150, 180, 40, 255), ow=0)
    c.rrect((90, 130, 170, 146), 6, BLUE, ow=6)
    return c.done()


# ---------------------------------------------------------------- scenery
def sky_gradient(w, h, top, bottom):
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line([(0, y), (w, y)], fill=col)
    return im


def draw_sun():
    c = Canvas(420, 420)
    for i in range(14):
        a = i * 2 * math.pi / 14
        a2 = a + 0.12
        c.poly([(210 + 120 * math.cos(a - 0.12), 210 + 120 * math.sin(a - 0.12)),
                (210 + 205 * math.cos(a), 210 + 205 * math.sin(a)),
                (210 + 120 * math.cos(a2), 210 + 120 * math.sin(a2))],
               (255, 200, 40, 255), ow=7)
    c.ell((80, 80, 340, 340), (255, 225, 60, 255), ow=10)
    eye(c, 170, 190, 26, look=(0, 0.1))
    eye(c, 250, 190, 26, look=(0, 0.1))
    c.arc((150, 200, 270, 290), 20, 160, OUT, 9)
    return c.done()


def draw_cloud(w=360, h=170):
    c = Canvas(w, h)
    for box in ((20, 60, 160, 160), (90, 15, 250, 160), (190, 45, 340, 160)):
        c.ell(box, (255, 255, 255, 255), ow=7)
    c.rrect((40, 100, 320, 162), 30, (255, 255, 255, 255), ow=0)
    c.line([(45, 160), (318, 160)], OUT, 7)
    return c.done()


def draw_house(c, x0, y0, w, h, wall, door=True, rnd=None):
    rnd = rnd or random.Random(0)
    c.rrect((x0, y0, x0 + w, y0 + h), 6, wall, ow=8)
    c.rrect((x0 - 10, y0 - 18, x0 + w + 10, y0 + 6), 4,
            tuple(int(v * 0.8) for v in wall[:3]) + (255,), ow=8)
    for bx in range(int(x0 + 15), int(x0 + w - 10), 45):      # roof beams
        c.ell((bx, y0 + 10, bx + 16, y0 + 26), (120, 70, 35, 255), ow=4)
    for k in range(rnd.randint(1, 2)):
        wx = x0 + 30 + k * (w // 2)
        if wx + 70 > x0 + w - 20:
            break
        c.rrect((wx, y0 + 55, wx + 70, y0 + 135), 8, (40, 110, 200, 255), ow=7)
        c.line([(wx + 35, y0 + 55), (wx + 35, y0 + 135)], OUT, 5, caps=False)
    if door and w > 220:
        dx = x0 + w - 130
        c.rrect((dx, y0 + h - 170, dx + 95, y0 + h), 10, (30, 100, 190, 255), ow=8)
        c.rrect((dx + 15, y0 + h - 150, dx + 80, y0 + h - 95), 6,
                (60, 140, 220, 255), ow=5)
        c.ell((dx + 70, y0 + h - 90, dx + 82, y0 + h - 78), (240, 190, 40, 255), ow=0)


def draw_dome(c, cx, by, r):
    c.rrect((cx - r * 0.9, by - r * 0.9, cx + r * 0.9, by + 10), 6,
            (230, 205, 160, 255), ow=8)
    c.chord((cx - r, by - r * 1.6, cx + r, by - r * 0.1), 180, 360,
            (40, 190, 200, 255), ow=8)
    for k in (-0.5, 0, 0.5):
        c.arc((cx - r * abs(k) - 5, by - r * 1.6, cx + r * abs(k) + 5, by - r * 0.1),
              180, 360, (20, 150, 160, 255), 5)
    c.line([(cx, by - r * 0.85), (cx, by - r * 1.05)], OUT, 6)
    c.ell((cx - 9, by - r * 1.12, cx + 9, by - r * 0.95), (240, 190, 40, 255), ow=4)


def draw_courtyard(W=1080, H=1920):
    """Static courtyard: sky, distant dome, flat-roof houses, tiles, grapevine."""
    bg = sky_gradient(W, H, (70, 170, 255), (175, 228, 255))
    c = Canvas(W, H)
    draw_dome(c, 800, 960, 150)
    c.rrect((640, 640, 680, 960), 6, (230, 205, 160, 255), ow=8)  # minaret
    c.rrect((630, 610, 690, 650), 6, (40, 190, 200, 255), ow=7)
    rnd = random.Random(11)
    walls = [(232, 196, 145, 255), (222, 180, 128, 255), (240, 210, 165, 255)]
    draw_house(c, -20, 900, 380, 420, walls[0], rnd=rnd)
    draw_house(c, 720, 960, 380, 360, walls[2], rnd=rnd)
    draw_house(c, 330, 1010, 420, 320, walls[1], rnd=rnd)
    # courtyard tiles
    c.rrect((-20, 1310, W + 20, H + 20), 0, (214, 160, 105, 255), ow=8)
    for y in range(1310, H, 70):
        c.line([(0, y), (W, y)], (180, 125, 80, 255), 4, caps=False)
        off = 0 if (y // 70) % 2 else 70
        for x in range(off, W, 140):
            c.line([(x, y), (x, y + 70)], (180, 125, 80, 255), 4, caps=False)
    # grapevine trellis
    for x in range(-40, W + 60, 220):
        c.rrect((x, -20, x + 30, 260), 6, (140, 90, 50, 255), ow=7)
    c.rrect((-20, 60, W + 20, 95), 6, (150, 98, 55, 255), ow=7)
    c.rrect((-20, 180, W + 20, 210), 6, (150, 98, 55, 255), ow=7)
    for i in range(34):
        x, y = rnd.uniform(-30, W + 30), rnd.uniform(-20, 240)
        r = rnd.uniform(40, 70)
        col = rnd.choice([(70, 160, 60, 255), (90, 185, 70, 255), (55, 140, 55, 255)])
        for a in range(5):
            ang = a * 2 * math.pi / 5 + i
            lx, ly = x + math.cos(ang) * r * 0.5, y + math.sin(ang) * r * 0.5
            c.ell((lx - r * 0.55, ly - r * 0.55, lx + r * 0.55, ly + r * 0.55), col, ow=5)
    for gx in (110, 330, 560, 790, 980):
        gy = rnd.uniform(220, 270)
        for row in range(5):
            for k in range(5 - row):
                x = gx + (k - (4 - row) / 2) * 30
                y = gy + row * 27
                c.ell((x - 17, y - 17, x + 17, y + 17), (130, 50, 150, 255), ow=4)
                c.ell((x - 9, y - 10, x - 2, y - 3), (200, 150, 220, 255), ow=0)
    # tapchan (raised platform) with carpet, bottom-left
    c.rrect((-30, 1360, 330, 1410), 8, (150, 95, 50, 255), ow=8)
    c.rrect((-30, 1330, 320, 1370), 8, (210, 40, 60, 255), ow=8)
    for x in range(10, 300, 60):
        c.poly([(x, 1350), (x + 20, 1338), (x + 40, 1350), (x + 20, 1362)],
               (255, 210, 40, 255), ow=0)
    layer = c.done()
    bg.alpha_composite(layer)
    return bg


def draw_rooftops(W=1080, H=1920):
    bg = sky_gradient(W, H, (60, 160, 255), (190, 235, 255))
    c = Canvas(W, H)
    rnd = random.Random(5)
    walls = [(232, 196, 145, 255), (222, 180, 128, 255), (240, 210, 165, 255),
             (210, 170, 120, 255)]
    draw_dome(c, 250, 1080, 120)
    rows = [(1050, 0.9), (1220, 1.0), (1420, 1.1)]
    for base, sc in rows:
        x = -60 + rnd.uniform(0, 60)
        while x < W:
            w = rnd.uniform(220, 360) * sc
            h = rnd.uniform(240, 360) * sc
            draw_house(c, x, base + rnd.uniform(-40, 40), w, h + 600,
                       rnd.choice(walls), door=False, rnd=rnd)
            x += w + rnd.uniform(-10, 30)
    bg.alpha_composite(c.done())
    return bg


def draw_sunburst(size, c1, c2, rays=24):
    im = Image.new("RGBA", (size, size), c1)
    d = ImageDraw.Draw(im)
    cx = cy = size / 2
    R = size
    for i in range(rays):
        if i % 2:
            continue
        a0 = i * 2 * math.pi / rays
        a1 = (i + 1) * 2 * math.pi / rays
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=c2)
    return im


# ---------------------------------------------------------------- assets
def load_or_draw(assets_dir, name, fn, *args, target_h=None):
    """Use assets/<name>.png when present, otherwise the drawn version."""
    path = os.path.join(assets_dir, f"{name}.png") if assets_dir else None
    if path and os.path.isfile(path):
        im = Image.open(path).convert("RGBA")
        ref = fn(*args) if target_h is None else None
        th = target_h or ref.height
        return im.resize((max(1, int(im.width * th / im.height)), th), Image.LANCZOS)
    return fn(*args)


def build_sprites(assets_dir=None, W=1080, H=1920):
    A = assets_dir
    s = {}
    s["samsa"] = [load_or_draw(A, "samsalino", draw_samsa, False),
                  load_or_draw(A, "samsalino", draw_samsa, True)]
    s["tandir"] = load_or_draw(A, "tandir", draw_tandir)
    s["kazan"] = load_or_draw(A, "plovolino", draw_kazan)
    s["carrot"] = load_or_draw(A, "carrot", draw_carrot)
    s["croc"] = {(su, mo): load_or_draw(A, "dutarini", draw_croc, su, mo)
                 for su in (False, True) for mo in (False, True)}
    s["wolf"] = {p: load_or_draw(A, "wolf", draw_wolf, p)
                 for p in ("dance", "open", "clap")}
    s["wolf"]["dance_m"] = ImageOps.mirror(s["wolf"]["dance"])
    s["teapot"] = load_or_draw(A, "chaynikoni", draw_teapot)
    s["pony"] = [load_or_draw(A, "pony", draw_pony, 0),
                 load_or_draw(A, "pony", draw_pony, 1)]
    s["piala"] = [load_or_draw(A, "piala", draw_piala, f / 8) for f in range(9)]
    s["sun"] = draw_sun()
    s["cloud"] = draw_cloud()
    s["courtyard"] = load_or_draw(A, "background", draw_courtyard, W, H, target_h=H)
    if s["courtyard"].size != (W, H):
        s["courtyard"] = ImageOps.fit(s["courtyard"], (W, H))
    s["rooftops"] = load_or_draw(A, "rooftops", draw_rooftops, W, H, target_h=H)
    if s["rooftops"].size != (W, H):
        s["rooftops"] = ImageOps.fit(s["rooftops"], (W, H))
    size = 2300
    s["burst"] = {
        "title": draw_sunburst(size, (255, 205, 40, 255), (255, 140, 30, 255)),
        "samsa": draw_sunburst(size, (255, 170, 40, 255), (255, 225, 90, 255)),
        "kazan": draw_sunburst(size, (235, 60, 60, 255), (255, 120, 70, 255)),
        "croc": draw_sunburst(size, (70, 190, 80, 255), (150, 225, 90, 255)),
        "tea": draw_sunburst(size, (40, 110, 230, 255), (90, 175, 255, 255)),
        "final": draw_sunburst(size, (240, 60, 170, 255), (255, 200, 40, 255), 32),
    }
    return s
