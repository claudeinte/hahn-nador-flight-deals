"""VORSCHAU (nur Entwurf, nichts wird veröffentlicht): Story-Kalender 1080×1920 für einen Monat.

Aufruf:
    .venv/bin/python scripts/vorschau_story_kalender.py 2026-11              # echte Veränderungen zum Vortag
    .venv/bin/python scripts/vorschau_story_kalender.py 2027-08 --testdaten  # Beispiel-Veränderungen (im Bild markiert)

Veränderung = aktueller Preis minus Preis desselben Flugs im letzten gespeicherten Preisstand vom VORTAG
(data/snapshots/). Gibt es dort keinen Preis → „NEU“.
"""
import calendar as pycal
import glob
import hashlib
import math
import pickle
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config  # noqa: E402
from flightdeals.fetch import fetch_all  # noqa: E402
from flightdeals.render.common import Painter  # noqa: E402
from flightdeals.texts import MONATE, WOCHENTAGE, fmt_price  # noqa: E402

W, H = 1080, 1920
N_MONATE = 11                         # Kalender pro Tag: aktueller Monat + 10 folgende
PAD, G = 12, 4                        # Seitenrand, Abstand zwischen Zellen
GOLD = (245, 197, 66)
UP, DOWN, SAME, NEW = (240, 82, 82), (34, 197, 94), (160, 170, 185), (76, 154, 255)
PAST_BG, PAST_FG = (38, 42, 50), (92, 98, 110)

# Monats-Themen. Deko-Farben bewusst ohne kräftiges Grün/Rot (Verwechslung mit ▼/▲ vermeiden).
THEMES = {
    11: dict(deco="herbst", sky=((150, 92, 40), (70, 40, 26)), ground=((92, 58, 32), (52, 34, 22)),
             body=((30, 20, 16), (14, 10, 9)), cell=(48, 34, 26), cell_off=(32, 24, 19), accent=(232, 150, 60),
             leaves=[(236, 160, 60), (214, 120, 40), (246, 196, 90), (170, 100, 50)]),
    8: dict(deco="strand", sky=((70, 160, 225), (20, 80, 150)), sea=((20, 120, 185), (10, 70, 125)),
            sand=(226, 196, 140), body=((10, 26, 46), (6, 14, 26)), cell=(18, 38, 62), cell_off=(12, 26, 44),
            accent=(90, 180, 255)),
}
THEMES.update({
    9: dict(deco="herbst", sky=((205, 150, 70), (96, 66, 32)), ground=((110, 80, 40), (64, 46, 26)),
            body=((30, 24, 14), (13, 11, 7)), cell=(50, 40, 24), cell_off=(34, 28, 18), accent=(226, 170, 60),
            leaves=[(246, 206, 90), (226, 170, 60), (200, 140, 50), (250, 226, 140)]),
    10: dict(deco="herbst", sky=((180, 98, 44), (84, 44, 26)), ground=((100, 60, 32), (58, 36, 22)),
             body=((32, 20, 14), (14, 9, 7)), cell=(52, 34, 24), cell_off=(34, 24, 18), accent=(236, 130, 50),
             leaves=[(240, 140, 50), (220, 110, 40), (250, 180, 70), (180, 96, 44)]),
    12: dict(deco="winter", orb="mond", sky=((22, 40, 92), (10, 22, 56)), snow=((228, 236, 250), (190, 205, 230)),
             body=((10, 18, 42), (5, 9, 22)), cell=(20, 33, 64), cell_off=(14, 23, 46), accent=(110, 160, 255)),
    1: dict(deco="winter", orb="sonne", sky=((160, 205, 238), (80, 140, 200)), snow=((246, 250, 255), (205, 225, 245)),
            body=((12, 30, 48), (6, 14, 24)), cell=(22, 44, 68), cell_off=(15, 31, 48), accent=(110, 195, 240)),
    2: dict(deco="winter", orb="mond", sky=((104, 70, 164), (46, 28, 92)), snow=((236, 228, 250), (200, 188, 230)),
            body=((24, 16, 46), (10, 8, 22)), cell=(42, 31, 72), cell_off=(29, 22, 50), accent=(170, 130, 245)),
    3: dict(deco="fruehling", sky=((160, 210, 236), (100, 160, 210)), meadow=((128, 162, 92), (92, 128, 70)),
            flowers=[(250, 200, 220), (255, 255, 255), (250, 222, 110), (210, 180, 240)],
            body=((16, 28, 22), (8, 14, 11)), cell=(30, 48, 40), cell_off=(21, 34, 28), accent=(120, 180, 150)),
    4: dict(deco="fruehling", sky=((130, 214, 224), (46, 146, 166)), meadow=((70, 156, 146), (46, 116, 110)),
            flowers=[(250, 170, 210), (255, 255, 255), (250, 222, 110), (255, 200, 150)],
            body=((8, 30, 34), (4, 14, 16)), cell=(16, 52, 58), cell_off=(12, 37, 41), accent=(60, 200, 210)),
    5: dict(deco="fruehling", sky=((130, 196, 178), (46, 116, 100)), meadow=((36, 118, 88), (24, 86, 64)),
            flowers=[(255, 255, 255), (250, 230, 120), (220, 190, 245), (250, 190, 210)],
            body=((6, 30, 24), (3, 14, 11)), cell=(15, 50, 41), cell_off=(10, 35, 29), accent=(50, 180, 140)),
    6: dict(deco="sonne", sky=((255, 214, 100), (226, 150, 44)), field=((214, 176, 76), (172, 132, 44)),
            body=((34, 26, 8), (14, 11, 4)), cell=(54, 43, 17), cell_off=(37, 30, 12), accent=(240, 176, 40)),
    7: dict(deco="strand", sky=((255, 166, 76), (224, 96, 44)), sea=((40, 112, 164), (20, 62, 112)),
            sand=(232, 194, 134), body=((36, 18, 8), (14, 8, 4)), cell=(58, 33, 19), cell_off=(39, 24, 14),
            accent=(250, 140, 50)),
})
DECO_END = 156                        # bis hier reicht die Kopf-Deko (liegt hinter der Instagram-Leiste)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _palm(dd, x, by, h, lean, s, col):
    pts = [(x + lean * (i / 10) ** 2, by - h * i / 10) for i in range(11)]
    dd.line(pts, fill=col, width=int(11 * s), joint="curve")
    tx, ty = pts[-1]
    for ang, ln in ((-165, 80), (-135, 88), (-100, 62), (-62, 84), (-25, 90), (12, 74), (165, 70)):
        a = math.radians(ang)
        L = ln * s
        mx, my = tx + L * .5 * math.cos(a), ty + L * .5 * math.sin(a) - 13 * s
        ex, ey = tx + L * math.cos(a), ty + L * math.sin(a) + 20 * s
        nx, ny = -math.sin(a) * 9 * s, math.cos(a) * 9 * s
        dd.polygon([(tx, ty), (mx + nx, my + ny), (ex, ey), (mx - nx, my - ny)], fill=col)


def _leaf(dd, x, y, size, ang, col):
    a = math.radians(ang)
    pts = []
    for k in range(13):
        t = k / 12 * 2 * math.pi
        px, py = math.cos(t) * size, math.sin(t) * size * 0.45
        pts.append((x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)))
    dd.polygon(pts, fill=col)
    dd.line((x - size * math.cos(a), y - size * math.sin(a), x + size * math.cos(a), y + size * math.sin(a)),
            fill=tuple(max(0, c - 60) for c in col[:3]) + (col[3],), width=2)


def deco_strand(th, deco):
    dd = ImageDraw.Draw(deco)
    for y in range(98):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / 98), 255))
    cx, cy, r = 800, 56, 38
    glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - 120, cy - 120, cx + 120, cy + 120), fill=(255, 230, 150, 120))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    dd = ImageDraw.Draw(deco)
    for j in range(r, 0, -1):
        dd.ellipse((cx - j, cy - j, cx + j, cy + j), fill=(*lerp((255, 248, 200), (255, 196, 60), j / r), 255))
    for y in range(98, 130):
        dd.line((0, y, W, y), fill=(*lerp(*th["sea"], (y - 98) / 32), 255))
    for i, y in enumerate(range(101, 128, 6)):
        dd.line((cx - 38 + i * 6, y, cx + 38 - i * 6, y), fill=(255, 240, 180, 170 - i * 30), width=3)
    for x0 in range(-60, W, 120):
        dd.arc((x0, 124, x0 + 120, 136), 200, 340, fill=(255, 255, 255, 200), width=3)
    for y in range(130, DECO_END):
        dd.line((0, y, W, y), fill=(*th["sand"], 255))
    _palm(dd, 1005, 150, 84, -24, 0.66, (20, 28, 40, 255))
    _palm(dd, 66, 150, 64, 14, 0.52, (20, 28, 40, 255))


def deco_herbst(th, deco):
    dd = ImageDraw.Draw(deco)
    for y in range(DECO_END):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / DECO_END), 255))
    glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((620, -60, 980, 200), fill=(255, 190, 110, 90))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))
    dd = ImageDraw.Draw(deco)
    # Hügel
    for k, (base, amp, col) in enumerate(((116, 20, th["ground"][0]), (136, 14, th["ground"][1]))):
        pts = [(x, base - amp * math.sin(x / 170 + k * 1.7)) for x in range(0, W + 10, 10)]
        dd.polygon(pts + [(W, DECO_END), (0, DECO_END)], fill=(*col, 255))
    # Baum rechts
    tc = (40, 26, 18, 255)
    dd.line((990, 156, 985, 80), fill=tc, width=12)
    for (x1, y1, x2, y2) in ((986, 110, 940, 70), (987, 96, 1035, 62), (985, 84, 960, 40), (986, 88, 1010, 35)):
        dd.line((x1, y1, x2, y2), fill=tc, width=6)
    rnd = random.Random(11)
    for _ in range(46):                                  # Laub im Baum
        x, y = 985 + rnd.randint(-75, 70), 55 + rnd.randint(-35, 35)
        _leaf(dd, x, y, rnd.randint(9, 14), rnd.randint(0, 180), (*rnd.choice(th["leaves"]), 255))
    for _ in range(26):                                  # fallende Blätter
        x, y = rnd.randint(0, 900), rnd.randint(10, 140)
        _leaf(dd, x, y, rnd.randint(7, 12), rnd.randint(0, 180), (*rnd.choice(th["leaves"]), 220))


MEDALS = {   # (hell, mittel, dunkel) – Gold, Silber, Bronze
    1: ((255, 236, 150), (240, 190, 50), (168, 120, 18)),
    2: ((250, 252, 255), (200, 206, 216), (120, 128, 142)),
    3: ((246, 186, 130), (205, 127, 50), (126, 72, 26)),
}
RIBBON = ((52, 96, 196), (120, 160, 235))     # Band blau (kein Rot/Grün → keine Verwechslung mit ▲/▼)


def draw_medal(img, cx, cy, r, rank, font_path):
    """Olympia-Medaille mit Band und großer Zahl, 4-fach überabgetastet für glatte Kanten."""
    from PIL import ImageFont
    S = 4
    w, h = int(r * 2.5), int(r * 2.55)
    lay = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    mx, my = w * S / 2, (h - r - 1) * S             # Mittelpunkt der Scheibe
    R = r * S
    bw = r * 0.7 * S                                # Bandbreite
    for sgn, col in ((-1, RIBBON[0]), (1, RIBBON[1])):
        top_x = mx + sgn * r * 0.75 * S
        d.polygon([(top_x - bw / 2, 0), (top_x + bw / 2, 0), (mx + sgn * bw * 0.15 + bw / 2 * (sgn > 0), my - R * 0.7),
                   (mx + sgn * bw * 0.15 - bw / 2 * (sgn < 0), my - R * 0.7)], fill=col)
    light, mid, dark = MEDALS[rank]
    d.ellipse((mx - R - S, my - R - S, mx + R + S, my + R + S), fill=(0, 0, 0, 90))
    d.ellipse((mx - R, my - R, mx + R, my + R), fill=dark)
    for k in range(int(R * 0.86), 0, -1):            # Verlauf hell (oben links) → mittel
        t = k / (R * 0.86)
        c = lerp(light, mid, t)
        off = (1 - t) * R * 0.18
        d.ellipse((mx - k - off, my - k - off, mx + k - off, my + k - off), fill=c)
    d.ellipse((mx - R * 0.86, my - R * 0.86, mx + R * 0.86, my + R * 0.86), outline=dark, width=max(2, int(S * 1.2)))
    f = ImageFont.truetype(font_path, int(R * 1.35))
    d.text((mx, my + S * 0.5), str(rank), font=f, fill=dark, anchor="mm")
    lay = lay.resize((w, h), Image.LANCZOS)
    img.paste(lay, (int(cx - w / 2), int(cy - (h - r - 1))), lay)
    return w


def deco_winter(th, deco):
    dd = ImageDraw.Draw(deco)
    for y in range(DECO_END):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / DECO_END), 255))
    cx, cy = 820, 58
    glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    gc = (255, 250, 220, 110) if th["orb"] == "sonne" else (220, 230, 255, 90)
    ImageDraw.Draw(glow).ellipse((cx - 110, cy - 110, cx + 110, cy + 110), fill=gc)
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    dd = ImageDraw.Draw(deco)
    if th["orb"] == "sonne":
        dd.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=(255, 252, 230, 255))
    else:
        dd.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(244, 246, 255, 255))
        dd.ellipse((cx - 16, cy - 36, cx + 40, cy + 22), fill=(*th["sky"][0], 255))
        rnd = random.Random(3)
        for _ in range(40):
            x, y = rnd.randint(0, W), rnd.randint(4, 90)
            dd.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, rnd.randint(120, 230)))
    for k, (base, amp) in enumerate(((112, 18), (134, 12))):
        pts = [(x, base - amp * math.sin(x / 150 + k * 2.1)) for x in range(0, W + 10, 10)]
        dd.polygon(pts + [(W, DECO_END), (0, DECO_END)], fill=(*th["snow"][k], 255))
    for (x, by, hh) in ((960, 140, 70), (1010, 146, 54), (60, 146, 58), (104, 150, 42)):   # Tannen mit Schnee
        for i in range(3):
            w_ = hh * (0.55 - i * 0.13)
            ty = by - hh * (0.35 + i * 0.28)
            dd.polygon([(x, ty - hh * 0.32), (x - w_, ty + hh * 0.12), (x + w_, ty + hh * 0.12)], fill=(24, 44, 60, 255))
            dd.polygon([(x, ty - hh * 0.32), (x - w_ * 0.45, ty - hh * 0.12), (x + w_ * 0.45, ty - hh * 0.12)],
                       fill=(240, 246, 255, 255))
        dd.rectangle((x - 4, by - hh * 0.25, x + 4, by), fill=(40, 30, 26, 255))
    rnd = random.Random(8)
    for _ in range(70):                                  # Schneeflocken
        x, y, r_ = rnd.randint(0, W), rnd.randint(0, DECO_END), rnd.choice((1.5, 2, 2.5, 3))
        dd.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 255, 255, rnd.randint(150, 240)))


def _flower(dd, x, y, r, col):
    for k in range(5):
        a = k * 2 * math.pi / 5
        px, py = x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9
        dd.ellipse((px - r * 0.62, py - r * 0.62, px + r * 0.62, py + r * 0.62), fill=(*col, 255))
    dd.ellipse((x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45), fill=(250, 200, 60, 255))


def deco_fruehling(th, deco):
    dd = ImageDraw.Draw(deco)
    for y in range(DECO_END):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / DECO_END), 255))
    glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((700, -60, 940, 160), fill=(255, 245, 200, 110))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    dd = ImageDraw.Draw(deco)
    dd.ellipse((790, 22, 850, 82), fill=(255, 244, 190, 255))
    for cx_, cy_ in ((200, 50), (480, 34)):              # Wolken
        for dx, dy, rr in ((0, 0, 22), (24, -8, 26), (50, 0, 20), (26, 8, 20)):
            dd.ellipse((cx_ + dx - rr, cy_ + dy - rr, cx_ + dx + rr, cy_ + dy + rr), fill=(255, 255, 255, 220))
    for k, (base, amp) in enumerate(((118, 16), (138, 10))):
        pts = [(x, base - amp * math.sin(x / 160 + k * 1.3)) for x in range(0, W + 10, 10)]
        dd.polygon(pts + [(W, DECO_END), (0, DECO_END)], fill=(*th["meadow"][k], 255))
    tc = (80, 56, 40, 255)                               # Blütenbaum rechts
    dd.line((990, 154, 986, 86), fill=tc, width=11)
    for (x1, y1, x2, y2) in ((987, 110, 945, 76), (988, 98, 1030, 66), (986, 90, 966, 50)):
        dd.line((x1, y1, x2, y2), fill=tc, width=6)
    rnd = random.Random(21)
    for _ in range(60):
        x, y, r_ = 985 + rnd.randint(-72, 66), 62 + rnd.randint(-32, 30), rnd.randint(6, 11)
        dd.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(*rnd.choice(th["flowers"][:1] + [(255, 230, 240)]), 235))
    for _ in range(40):                                  # Blumen auf der Wiese
        x, y = rnd.randint(0, 900), rnd.randint(128, 152)
        _flower(dd, x, y, rnd.randint(4, 7), rnd.choice(th["flowers"]))


def deco_sonne(th, deco):
    dd = ImageDraw.Draw(deco)
    for y in range(DECO_END):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / DECO_END), 255))
    cx, cy = 800, 70
    rays = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for i in range(16):
        a = i * math.pi / 8
        rd.polygon([(cx, cy), (cx + 600 * math.cos(a - 0.07), cy + 600 * math.sin(a - 0.07)),
                    (cx + 600 * math.cos(a + 0.07), cy + 600 * math.sin(a + 0.07))], fill=(255, 250, 210, 60))
    deco.alpha_composite(rays.filter(ImageFilter.GaussianBlur(6)))
    dd = ImageDraw.Draw(deco)
    for j in range(46, 0, -1):
        dd.ellipse((cx - j, cy - j, cx + j, cy + j), fill=(*lerp((255, 252, 220), (255, 200, 60), j / 46), 255))
    for k, (base, amp) in enumerate(((120, 14), (138, 10))):
        pts = [(x, base - amp * math.sin(x / 140 + k * 1.9)) for x in range(0, W + 10, 10)]
        dd.polygon(pts + [(W, DECO_END), (0, DECO_END)], fill=(*th["field"][k], 255))
    for x in range(-40, W, 26):                          # Feldreihen
        dd.line((x, DECO_END, x + 60, 126), fill=(*th["field"][1], 200), width=2)


def background(th):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp(*th["body"], y / H))
    deco = Image.new("RGBA", (W, DECO_END), (0, 0, 0, 0))
    {"strand": deco_strand, "herbst": deco_herbst, "winter": deco_winter, "fruehling": deco_fruehling,
     "sonne": deco_sonne}[th["deco"]](th, deco)
    img.paste(deco, (0, 0), deco)
    ov = Image.new("RGBA", (W, 60), (0, 0, 0, 0))   # weicher Übergang in den dunklen Körper
    od = ImageDraw.Draw(ov)
    for y in range(60):
        od.line((0, y, W, y), fill=(*th["body"][0], int(255 * min(1, y / 34))))
    img.paste(ov, (0, DECO_END - 26), ov)
    # Fuß-Deko (unter der Antwortleiste – nur Stimmung)
    bot = Image.new("RGBA", (W, 110), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bot)
    if th["deco"] == "strand":
        for y in range(110):
            bd.line((0, y, W, y), fill=(*lerp(*th["sea"], y / 110), int(255 * min(1, y / 36))))
        for x0 in range(-60, W, 120):
            bd.arc((x0, 30, x0 + 120, 44), 200, 340, fill=(255, 255, 255, 110), width=3)
            bd.arc((x0 + 60, 66, x0 + 180, 80), 200, 340, fill=(255, 255, 255, 70), width=3)
    elif th["deco"] == "winter":
        for y in range(110):
            bd.line((0, y, W, y), fill=(*th["snow"][1], int(230 * min(1, y / 46))))
        rnd = random.Random(9)
        for _ in range(60):
            x, y, r_ = rnd.randint(0, W), rnd.randint(0, 80), rnd.choice((1.5, 2, 3))
            bd.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 255, 255, 220))
    elif th["deco"] == "fruehling":
        for y in range(110):
            bd.line((0, y, W, y), fill=(*th["meadow"][1], int(255 * min(1, y / 40))))
        rnd = random.Random(13)
        for _ in range(34):
            _flower(bd, rnd.randint(0, W), rnd.randint(36, 66), rnd.randint(5, 8), rnd.choice(th["flowers"]))
    elif th["deco"] == "sonne":
        for y in range(110):
            bd.line((0, y, W, y), fill=(*th["field"][1], int(255 * min(1, y / 40))))
        for x in range(-40, W, 26):
            bd.line((x, 110, x + 40, 30), fill=(*th["field"][0], 160), width=2)
    else:
        for y in range(110):
            bd.line((0, y, W, y), fill=(*th["ground"][1], int(255 * min(1, y / 40))))
        rnd = random.Random(5)
        for _ in range(40):
            _leaf(bd, rnd.randint(0, W), rnd.randint(30, 66), rnd.randint(7, 12), rnd.randint(0, 180),
                  (*rnd.choice(th["leaves"]), 200))
    img.paste(bot, (0, H - 110), bot)
    return img


def fake_delta(route, day):
    """TESTDATEN: deterministische Beispiel-Veränderungen (nur für die Vorschau)."""
    h = int(hashlib.md5(f"{route}{day}".encode()).hexdigest(), 16) % 9
    return [-10.0, -5.0, -3.01, 0.0, 0.0, 5.0, 2.0, 12.5, None][h]


def fmt_delta(dv):
    v = abs(dv)
    s = f"{v:.0f}" if abs(v - round(v)) < 0.005 else f"{v:.2f}".replace(".", ",")
    return ("−" if dv < 0 else "+") + s + " €"


def previous_day_prices(today):
    """Preise aus dem letzten gespeicherten Preisstand vom Vortag (oder früher) – {(route, tag): preis}."""
    best = None
    for f in sorted(glob.glob(str(PROJ / "data" / "snapshots" / "*.pkl"))):
        sn = pickle.load(open(f, "rb"))
        if sn.fetched_at.date() < today:
            best = sn
    if not best:
        return {}, None
    return {(fa.route, fa.day): fa.price for fa in best.fares()}, best.fetched_at


def render_month(cfg, snap, prev, YY, MM, now, testdaten=False):
    """Ein Monats-Story-Bild (1080×1920) – gibt das PIL-Bild zurück."""
    th = THEMES[MM]
    today = now.date()
    p = Painter(cfg)
    p.img = background(th)
    p.d = ImageDraw.Draw(p.img)
    t = p.t

    # ---------- Kopf ----------
    title = f"{MONATE[MM - 1].upper()} {YY}"
    ft = p.fit(title, "extrabold", 112, W - 2 * PAD - 130)
    p.d.text((PAD + 3, 215), title, font=ft, fill=(0, 0, 0), anchor="lm")
    p.d.text((PAD, 212), title, font=ft, fill=(255, 255, 255), anchor="lm")
    p.d.text((PAD + 2, 292), f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr",
             font=p.fit(f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr", "bold", 30, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="lm")
    lx, ly = W - PAD - 52, 214
    p.d.ellipse((lx - 52, ly - 52, lx + 52, ly + 52), fill=(255, 255, 255))
    p.d.ellipse((lx - 47, ly - 47, lx + 47, ly + 47), fill=t.accent)
    p.plane(lx, ly, 56, -35, (255, 255, 255))
    items = [("t", "▼ günstiger", DOWN), ("t", "▲ teurer", UP), ("t", "● gleich", SAME), ("t", "NEU", NEW),
             ("t", "– kein Flug", (150, 160, 175)), ("x", "vorbei", (140, 146, 158)), ("m", "Top 3 günstigste Flüge", GOLD)]
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")
    for fs in range(22, 15, -1):
        fl = p.font("bold", fs)
        def iw(k, s_):
            return p.tw(s_, fl) + (22 if k == "x" else 66 if k == "m" else 0)
        total = sum(iw(k, s_) for k, s_, _ in items)
        if total + 6 * 14 <= W - 2 * PAD - 4:
            break
    gapl = (W - 2 * PAD - 4 - total) / (len(items) - 1)
    x, ly2 = PAD + 2, 335
    for k, s_, col in items:
        if k == "x":
            p.d.line((x + 1, ly2 - 7, x + 15, ly2 + 7), fill=col, width=3)
            p.d.line((x + 1, ly2 + 7, x + 15, ly2 - 7), fill=col, width=3)
            p.d.text((x + 22, ly2), s_, font=fl, fill=col, anchor="lm")
        elif k == "m":
            for i in range(3):
                draw_medal(p.img, x + 10 + i * 21, ly2 + 3, 9, i + 1, fpath)
            p.d = ImageDraw.Draw(p.img)
            p.d.text((x + 66, ly2), s_, font=fl, fill=col, anchor="lm")
        else:
            p.d.text((x, ly2), s_, font=fl, fill=col, anchor="lm")
        x += iw(k, s_) + gapl

    # ---------- Kalender ----------
    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(YY, MM)
    cw = (W - 2 * PAD - 6 * G) // 7
    TOP, BOTTOM, HEAD, GAPB = 360, 1716, 74, 12
    ch = min(116, int((BOTTOM - TOP - 2 * HEAD - GAPB - 2 * (len(weeks) - 1) * G) / (2 * len(weeks))))

    def block(top, route, label, outbound):
        fares = {f.day: f for f in snap.fares(route) if f.day.year == YY and f.day.month == MM and f.day >= today}
        ranked = sorted(fares.values(), key=lambda f: (f.price, f.day))[:3]   # Top 3 (nur kommende Tage)
        rank = {f.day: i + 1 for i, f in enumerate(ranked)}
        best = ranked[0] if ranked else None
        # großes Flugzeug in Flugrichtung: Hinflug → nach rechts, Rückflug ← nach links
        p.d.ellipse((PAD, top - 2, PAD + 54, top + 52), fill=th["accent"])
        p.plane(PAD + 27, top + 25, 23, -18 if outbound else 198, (255, 255, 255))
        fT = p.font("extrabold", 40)
        p.d.text((PAD + 66, top + 25), label.upper(), font=fT, fill=(255, 255, 255), anchor="lm")
        x = PAD + 66 + p.tw(label.upper(), fT) + 16
        f2 = p.font("semibold", 25)
        o, d_ = route.split("-")
        cc = {"HHN": "DE", "NDR": "MA"}
        for i, code in enumerate((o, d_)):
            if i:
                p.d.text((x + 2, top + 25), "→", font=f2, fill=(190, 200, 215), anchor="lm")
                x += p.tw("→", f2) + 10
            x += p.flag(cc[code], x, top + 15, 20) + 8
            p.d.text((x, top + 25), cfg.city(code), font=f2, fill=(232, 238, 246), anchor="lm")
            x += p.tw(cfg.city(code), f2) + 6
        if best:
            lab_ = f"ab {fmt_price(best.price)}"
            fa_ = p.font("extrabold", 30)
            p.d.text((W - PAD - 2, top + 25), lab_, font=fa_, fill=GOLD, anchor="rm")
            draw_medal(p.img, W - PAD - 2 - p.tw(lab_, fa_) - 22, top + 30, 13, 1, fpath)
            p.d = ImageDraw.Draw(p.img)
        for c, wd in enumerate(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]):
            p.d.text((PAD + c * (cw + G) + cw / 2, top + 59), wd, font=p.font("bold", 22),
                     fill=(175, 188, 205) if c < 6 else (255, 190, 140), anchor="mm")
        y0 = top + HEAD
        fd = p.font("bold", 25)
        for r_, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day.month != MM:
                    continue
                x0, yy = PAD + c * (cw + G), y0 + r_ * (ch + G)
                box = (x0, yy, x0 + cw, yy + ch)
                if day < today:                          # vorbei: grau, X, kein Preis
                    p.d.rounded_rectangle(box, 12, fill=PAST_BG)
                    p.d.text((x0 + 9, yy + 5), str(day.day), font=p.font("bold", 22), fill=PAST_FG)
                    cx, cy, s = x0 + cw / 2, yy + ch / 2 + 8, 15
                    p.d.line((cx - s, cy - s, cx + s, cy + s), fill=PAST_FG, width=5)
                    p.d.line((cx - s, cy + s, cx + s, cy - s), fill=PAST_FG, width=5)
                    continue
                f = fares.get(day)
                p.d.rounded_rectangle(box, 12, fill=th["cell"] if f else th["cell_off"])
                p.d.text((x0 + 9, yy + 5), str(day.day), font=p.font("bold", 22), fill=(185, 196, 212))
                if not f:
                    p.d.text((x0 + cw / 2, yy + ch / 2 + 8), "–", font=p.font("bold", 36), fill=(110, 120, 135), anchor="mm")
                    continue
                price = f"{f.price:.2f}".replace(".", ",")
                fp = p.fit(price, "extrabold", 42, cw - 10)
                p.d.text((x0 + cw - 6, yy + ch * 0.72), price, font=fp, fill=(255, 255, 255), anchor="rs")
                if testdaten:
                    dv = fake_delta(route, day)
                else:
                    old = prev.get((route, day))
                    dv = None if old is None else round(f.price - old, 2)
                by = yy + ch - 5
                if dv is None:
                    p.d.rounded_rectangle((x0 + cw - 66, by - 25, x0 + cw - 5, by + 1), 12, fill=NEW)
                    p.d.text((x0 + cw - 35, by - 11), "NEU", font=p.font("extrabold", 18), fill=(255, 255, 255), anchor="mm")
                elif abs(dv) < 0.005:
                    p.d.text((x0 + cw - 6, by), "● ±0 €", font=fd, fill=SAME, anchor="rs")
                else:
                    txt = ("▼ " if dv < 0 else "▲ ") + fmt_delta(dv)
                    p.d.text((x0 + cw - 6, by), txt, font=p.fit(txt, "bold", 25, cw - 10),
                             fill=DOWN if dv < 0 else UP, anchor="rs")
                if day in rank:                          # Top 3: Rahmen + Medaille oben rechts
                    rk = rank[day]
                    p.d.rounded_rectangle(box, 12, outline=MEDALS[rk][1], width=5)
                    draw_medal(p.img, x0 + cw - 23, yy + 24, 15, rk, fpath)
                    p.d = ImageDraw.Draw(p.img)
        return y0 + len(weeks) * (ch + G) - G

    end1 = block(TOP, cfg.route_out, "Hinflug", True)
    end2 = block(end1 + GAPB, cfg.route_ret, "Rückflug", False)

    # ---------- Fuß ----------
    y = end2 + 30
    p.d.text((W / 2, y), "Die Flugpreise können sich im Laufe des Tages jederzeit ändern.",
             font=p.fit("Die Flugpreise können sich im Laufe des Tages jederzeit ändern.", "bold", 30, W - 2 * PAD),
             fill=(255, 255, 255), anchor="mm")
    p.d.text((W / 2, y + 34), "Preise in € pro Person (Basic-Tarif) · Veränderung zum Vortag · Buchung nur auf ryanair.com",
             font=p.font("semibold", 19), fill=(195, 205, 218), anchor="mm")
    fu = p.font("semibold", 18)
    tw_ = p.tw("Unabhängige Infoseite · keine Verbindung zu Ryanair", fu)
    p.d.rounded_rectangle((W / 2 - tw_ / 2 - 14, H - 38, W / 2 + tw_ / 2 + 14, H - 7), 14, fill=(0, 0, 0, 150) if False else lerp(th["body"][1], (0, 0, 0), 0.4))
    for dx, dy in ((2, 2), (0, 0)):
        p.d.text((W / 2 + dx, H - 22 + dy), "Unabhängige Infoseite · keine Verbindung zu Ryanair",
                 font=p.font("semibold", 18), fill=(0, 0, 0) if dx else (240, 244, 250), anchor="mm")
    if testdaten:
        lab = "VORSCHAU · Veränderungen = TESTDATEN"
        fv = p.font("extrabold", 20)
        bw = p.tw(lab, fv) + 30
        p.d.rounded_rectangle(((W - bw) / 2, H - 80, (W + bw) / 2, H - 48), 16, fill=(255, 210, 80))
        p.d.text((W / 2, H - 64), lab, font=fv, fill=(30, 25, 10), anchor="mm")
    return p.img


def story_view(img, cfg, idx=1, n=N_MONATE + 1):
    """Vorschau wie in der Story-Ansicht (Instagram-Bedienelemente simuliert), halbe Größe."""
    p = Painter(cfg)
    m = img.convert("RGBA")
    ui = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    u = ImageDraw.Draw(ui)
    seg = (W - 32) // n
    for i in range(n):
        x0 = 16 + i * seg
        u.rounded_rectangle((x0 + 3, 22, x0 + seg - 3, 28), 3, fill=(255, 255, 255, 230 if i < idx else 110))
    u.ellipse((24, 50, 104, 130), fill=(255, 255, 255, 255))
    u.text((122, 90), "hahn.nador.fluege  ·  1 Std.", font=p.font("bold", 30), fill=(255, 255, 255, 255), anchor="lm")
    u.line((W - 70, 72, W - 40, 102), fill=(255, 255, 255, 255), width=5)
    u.line((W - 70, 102, W - 40, 72), fill=(255, 255, 255, 255), width=5)
    u.rounded_rectangle((24, H - 140, W - 190, H - 60), 40, outline=(255, 255, 255, 220), width=3)
    u.text((70, H - 100), "Nachricht senden …", font=p.font("medium", 30), fill=(255, 255, 255, 220), anchor="lm")
    u.text((W - 130, H - 100), "♡", font=p.font("bold", 46), fill=(255, 255, 255, 255), anchor="mm")
    m.alpha_composite(ui)
    return m.convert("RGB").resize((540, 960), Image.LANCZOS)


def next_months(today, n=9):
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def render_summary(cfg, snap, months, now):
    """Story 1: Übersicht – günstigster Hin- und Rückflug je Monat, Top 3 je Richtung mit Medaillen."""
    today = now.date()
    p = Painter(cfg)
    t = p.t
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp((12, 24, 46), (5, 10, 20), y / H))
    # Kopf-Deko: Nachthimmel mit Sternen und Flugbogen Frankfurt-Hahn → Nador
    deco = Image.new("RGBA", (W, DECO_END), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    for y in range(DECO_END):
        dd.line((0, y, W, y), fill=(*lerp((40, 70, 140), (14, 28, 60), y / DECO_END), 255))
    rnd = random.Random(2)
    for _ in range(60):
        x, y = rnd.randint(0, W), rnd.randint(4, DECO_END - 10)
        dd.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(255, 255, 255, rnd.randint(110, 230)))
    pts = [(120 + (840 * i / 40), 130 - 95 * math.sin(math.pi * i / 40)) for i in range(41)]
    for i in range(0, 40, 2):
        dd.line((pts[i], pts[i + 1]), fill=(255, 255, 255, 200), width=4)
    img.paste(deco, (0, 0), deco)
    p.img = img
    p.d = ImageDraw.Draw(p.img)
    p.d.ellipse((540 - 30, 35 - 30, 540 + 30, 35 + 30), fill=t.accent)
    p.plane(540, 35, 24, 0, (255, 255, 255))
    ov = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for y in range(60):
        od.line((0, y, W, y), fill=(12, 24, 46, int(255 * min(1, y / 34))))
    p.img.paste(ov, (0, DECO_END - 26), ov)
    p.d = ImageDraw.Draw(p.img)
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")

    title = "BESTPREISE PRO MONAT"
    ftt = p.fit(title, "extrabold", 112, W - 2 * PAD - 128)
    p.d.text((PAD + 3, 215), title, font=ftt, fill=(0, 0, 0), anchor="lm")
    p.d.text((PAD, 212), title, font=ftt, fill=(255, 255, 255), anchor="lm")
    lx, ly = W - PAD - 52, 214
    p.d.ellipse((lx - 52, ly - 52, lx + 52, ly + 52), fill=(255, 255, 255))
    p.d.ellipse((lx - 47, ly - 47, lx + 47, ly + 47), fill=t.accent)
    p.plane(lx, ly, 56, -35, (255, 255, 255))
    p.d.text((PAD + 2, 292), f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr",
             font=p.fit(f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr", "bold", 30, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="lm")
    sub = f"Die günstigsten Hin- und Rückflüge der nächsten {len(months)} Monate"
    p.d.text((PAD + 2, 336), sub, font=p.fit(sub, "bold", 27, W - 2 * PAD - 8),
             fill=(190, 205, 225), anchor="lm")

    rows = []
    for (y_, m_) in months:
        def cheapest(route):
            fs = [f for f in snap.fares(route) if f.day.year == y_ and f.day.month == m_ and f.day >= today]
            return min(fs, key=lambda f: (f.price, f.day)) if fs else None
        rows.append(((y_, m_), cheapest(cfg.route_out), cheapest(cfg.route_ret)))

    def ranks(idx):
        ok = sorted([(r[idx].price, r[idx].day, i) for i, r in enumerate(rows) if r[idx]])[:3]
        return {i: k + 1 for k, (_, _, i) in enumerate(ok)}

    # Spaltenköpfe
    col1, col2 = 330, 700
    hy = 388
    for x_, lab, route, outb in ((col1, "HINFLUG", cfg.route_out, True), (col2, "RÜCKFLUG", cfg.route_ret, False)):
        p.d.ellipse((x_, hy - 21, x_ + 42, hy + 21), fill=t.accent)
        p.plane(x_ + 21, hy, 17, -18 if outb else 198, (255, 255, 255))
        p.d.text((x_ + 52, hy), lab, font=p.font("extrabold", 30), fill=(255, 255, 255), anchor="lm")
        p.flag_pair(route, x_ + 52 + p.tw(lab, p.font("extrabold", 30)) + 10, hy - 10, 20)
    p.d.text((PAD + 6, hy), "MONAT", font=p.font("extrabold", 26), fill=(170, 185, 205), anchor="lm")

    # Preisfarben (nur in dieser Übersicht): <25 grün · 25–49,99 gelb · 50–100 orange · >100 rot
    BANDS = [((34, 197, 94), "unter 25 €"), ((250, 204, 21), "25 – 49,99 €"), ((251, 146, 60), "50 – 100 €"),
             ((240, 82, 82), "über 100 €")]

    def band(pr):
        return BANDS[0][0] if pr < 25 else BANDS[1][0] if pr < 50 else BANDS[2][0] if pr <= 100 else BANDS[3][0]

    fl = p.font("bold", 24)
    widths = [30 + p.tw(lab, fl) for _, lab in BANDS]
    gap = (W - 2 * PAD - 12 - sum(widths)) / (len(BANDS) - 1)
    x, ly2 = PAD + 6, 436
    for (col, lab), w_ in zip(BANDS, widths):
        p.d.ellipse((x, ly2 - 11, x + 22, ly2 + 11), fill=col)
        p.d.text((x + 30, ly2), lab, font=fl, fill=col, anchor="lm")
        x += w_ + gap

    top, bottom = 462, 1716
    n = len(rows)
    gp = 6 if n > 9 else 8
    rh = (bottom - top - gp * (n - 1)) / n
    k = min(1.0, rh / 136)              # Schrift an Zeilenhöhe anpassen
    for i, ((y_, m_), fo, fr) in enumerate(rows):
        yy = top + i * (rh + gp)
        th = THEMES[m_]
        p.d.rounded_rectangle((PAD, yy, W - PAD, yy + rh), 16, fill=th["cell"])
        p.d.rounded_rectangle((PAD, yy, PAD + 12, yy + rh), 6, fill=th["accent"])
        p.d.text((PAD + 30, yy + rh / 2 - 16 * k), MONATE[m_ - 1], font=p.font("extrabold", int(36 * k)), fill=(255, 255, 255), anchor="lm")
        p.d.text((PAD + 30, yy + rh / 2 + 24 * k), str(y_), font=p.font("bold", int(24 * k)), fill=(185, 198, 215), anchor="lm")
        for x_, f in ((col1, fo), (col2, fr)):
            if not f:
                p.d.text((x_ + 120, yy + rh / 2), "–", font=p.font("bold", 40), fill=(110, 120, 135), anchor="mm")
                continue
            col = band(f.price)
            p.d.rounded_rectangle((x_ - 10, yy + 12, x_ - 4, yy + rh - 12), 3, fill=col)
            p.d.text((x_ + 6, yy + rh / 2 - 13 * k), fmt_price(f.price), font=p.font("extrabold", int(48 * k)), fill=col, anchor="lm")
            p.d.text((x_ + 8, yy + rh / 2 + 30 * k), f"{WOCHENTAGE[f.day.weekday()][:2]}, {f.day:%d.%m.} · {f.departure} Uhr",
                     font=p.font("semibold", max(19, int(23 * k))), fill=(205, 214, 228), anchor="lm")

    y = bottom + 30
    p.d.text((W / 2, y), "Die Flugpreise können sich im Laufe des Tages jederzeit ändern.",
             font=p.fit("Die Flugpreise können sich im Laufe des Tages jederzeit ändern.", "bold", 30, W - 2 * PAD),
             fill=(255, 255, 255), anchor="mm")
    p.d.text((W / 2, y + 34), "Preise pro Person (Basic-Tarif) · nur kommende Tage · Buchung nur auf ryanair.com",
             font=p.font("semibold", 19), fill=(195, 205, 218), anchor="mm")
    lab = "Unabhängige Infoseite · keine Verbindung zu Ryanair"
    fu = p.font("semibold", 18)
    p.d.text((W / 2, H - 22), lab, font=fu, fill=(220, 228, 240), anchor="mm")
    return p.img


def main_alle(testdaten=False):
    cfg = load_config()
    cfg["route"]["months_ahead"] = N_MONATE
    now = cfg.now()
    snap = fetch_all(cfg, now)
    bad = [k for k, m in snap.months.items() if not m.ok]
    if bad:
        sys.exit(f"Preisabfrage unvollständig ({bad}) – keine Bilder (keine alten Preise zeigen).")
    (PROJ / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    pickle.dump(snap, open(PROJ / "data" / "snapshots" / now.strftime("%Y-%m-%d_%H%M.pkl"), "wb"))
    prev, prev_at = previous_day_prices(now.date())
    print("Vergleich mit Preisstand vom", prev_at)
    months = next_months(now.date(), N_MONATE)
    out = PROJ / "output" / "stories" / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    imgs = [render_summary(cfg, snap, months, now)]
    imgs[0].save(out / "01_uebersicht.png")
    for i, (y_, m_) in enumerate(months, start=2):
        im = render_month(cfg, snap, prev, y_, m_, now, testdaten)
        im.save(out / f"{i:02d}_kalender_{y_}-{m_:02d}.png")
        imgs.append(im)
    # Übersichtsblatt aller 10 Stories
    cols = 6
    rows_ = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 228 + 12, rows_ * 396 + 12), (30, 30, 34))
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((216, 384), Image.LANCZOS), (12 + (k % cols) * 228, 12 + (k // cols) * 396))
    sheet.save(out / "00_alle_stories.png")
    story_view(imgs[0], cfg, 1).save(out / "ansicht_01.png")
    print(out)


if __name__ == "__main__":
    if "--alle" in sys.argv:
        main_alle("--testdaten" in sys.argv)
    else:
        cfg_ = load_config()
        cfg_["route"]["months_ahead"] = N_MONATE
        now_ = cfg_.now()
        snap_ = fetch_all(cfg_, now_)
        prev_, _ = previous_day_prices(now_.date())
        YY_, MM_ = map(int, sys.argv[1].split("-"))
        img_ = render_month(cfg_, snap_, prev_, YY_, MM_, now_, "--testdaten" in sys.argv)
        o_ = PROJ / "output" / "vorschau"
        o_.mkdir(parents=True, exist_ok=True)
        img_.save(o_ / f"story_kalender_{YY_}-{MM_:02d}.png")
        story_view(img_, cfg_).save(o_ / f"story_kalender_{YY_}-{MM_:02d}_ansicht.png")
        print(o_)
