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
DECO_END = 156
OFF = 36                              # Sonder-Stories: Kopf tiefer, außerhalb der Instagram-Leiste
HH = DECO_END + OFF
ARC_Y = HH - 24                        # Endpunkte des Flugbogens
ARC_X0, ARC_X1, ARC_AMP = 400, 720, 56
PLANE_T = 0.62                         # Flugzeug etwas rechts der Mitte (Profilname links bleibt frei)                        # bis hier reicht die Kopf-Deko (liegt hinter der Instagram-Leiste)


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
    # Glanz in der Mitte, feine Sterne und zwei Flugzeuge mit Kondensstreifen (Monatsfarbe als Akzent)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((40, 420, 1040, 1600), fill=(*th["accent"], 46))
    lay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    ld = ImageDraw.Draw(lay)
    rnd = random.Random(31)
    for _ in range(110):
        x, y = rnd.randint(0, W), rnd.randint(DECO_END, H - 120)
        r_ = rnd.choice((1.0, 1.4, 1.8))
        ld.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 255, 255, rnd.randint(30, 90)))
    base = img.convert("RGBA")
    base.alpha_composite(lay)
    return base.convert("RGB")


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
    TOP, BOTTOM, HEAD, GAPB = 360, 1690, 74, 12
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
        f2 = p.font("bold", 26)
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
    _ft = "Preise in € pro Person (Basic-Tarif) · Veränderung zum Vortag · Buchung nur auf ryanair.com"
    p.d.text((W / 2, y + 34), _ft, font=p.fit(_ft, "bold", 21, W - 2 * PAD), fill=(205, 214, 226), anchor="mm")
    fu = p.font("bold", 21)
    tw_ = p.tw("Unabhängige Infoseite · keine Verbindung zu Ryanair", fu)
    p.d.rounded_rectangle((W / 2 - tw_ / 2 - 14, H - 38, W / 2 + tw_ / 2 + 14, H - 7), 14, fill=(0, 0, 0, 150) if False else lerp(th["body"][1], (0, 0, 0), 0.4))
    for dx, dy in ((2, 2), (0, 0)):
        p.d.text((W / 2 + dx, H - 22 + dy), "Unabhängige Infoseite · keine Verbindung zu Ryanair",
                 font=p.font("bold", 21), fill=(0, 0, 0) if dx else (240, 244, 250), anchor="mm")
    if testdaten:
        lab = "VORSCHAU · Veränderungen = TESTDATEN"
        fv = p.font("extrabold", 20)
        bw = p.tw(lab, fv) + 30
        p.d.rounded_rectangle(((W - bw) / 2, H - 80, (W + bw) / 2, H - 48), 16, fill=(255, 210, 80))
        p.d.text((W / 2, H - 64), lab, font=fv, fill=(30, 25, 10), anchor="mm")
    for x_, y_, a_, sc_ in ((170, 1846, 6, 0.8), (1000, 1850, -6, 0.7)):   # Flugzeuge im Fuß (über dem Hinweis)
        L_ = 260 * sc_
        ar = math.radians(a_)
        for k_ in range(24):
            t0, t1 = k_ / 24, (k_ + 1) / 24
            p.d.line((x_ - L_ * (1 - t0) * math.cos(ar), y_ - L_ * (1 - t0) * math.sin(ar),
                      x_ - L_ * (1 - t1) * math.cos(ar), y_ - L_ * (1 - t1) * math.sin(ar)),
                     fill=lerp(th["body"][1], (255, 255, 255), 0.2 + 0.6 * t1), width=max(2, int(6 * sc_ * t1)))
        p.plane(x_, y_, int(40 * sc_), a_, (255, 255, 255))
    return p.img


def story_view(img, cfg, idx=1, n=N_MONATE + 3):
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


def _header_sky(deco, kind, arc=True):
    """Kopf-Himmel für Sonder-Stories: 'nacht' (Sterne), 'tag' (blauer Himmel, Sonne, Wolken), 'gold' (Sonnenuntergang, Funkeln)."""
    dd = ImageDraw.Draw(deco)
    top, bot = {"nacht": ((40, 70, 140), (14, 28, 60)), "tag": ((96, 170, 236), (40, 104, 186)),
                "gold": ((252, 196, 92), (168, 74, 96)), "tuerkis": ((60, 190, 200), (24, 70, 120))}[kind]
    hgt = deco.size[1]
    for y in range(hgt):
        dd.line((0, y, W, y), fill=(*lerp(top, bot, y / hgt), 255))
    rnd = random.Random(2)
    if kind == "nacht":
        for _ in range(60):
            x, y = rnd.randint(0, W), rnd.randint(4, hgt - 10)
            dd.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(255, 255, 255, rnd.randint(110, 230)))
    elif kind == "tag":
        glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((-10, -50, 170, 130), fill=(255, 236, 160, 120))
        deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        dd = ImageDraw.Draw(deco)
        dd.ellipse((40, 8, 120, 88), fill=(255, 238, 150, 255))
        for cx_, cy_, sc in ((300, 46, 1.0), (760, 30, 0.8), (1000, 70, 0.9), (620, 104, 0.6)):
            for dx, dy, rr in ((0, 0, 22), (26, -10, 28), (56, 0, 22), (28, 8, 22), (-22, 6, 16)):
                dd.ellipse((cx_ + (dx - rr) * sc, cy_ + (dy - rr) * sc, cx_ + (dx + rr) * sc, cy_ + (dy + rr) * sc),
                           fill=(255, 255, 255, 235))
    else:                                                    # gold: Funkeln wie Konfetti/Sterne
        for _ in range(38):
            x, y, r_ = rnd.randint(0, W), rnd.randint(6, hgt - 14), rnd.choice((4, 5, 6, 8))
            col = (255, 246, 200, rnd.randint(170, 250))
            dd.polygon([(x, y - r_), (x + r_ * .28, y - r_ * .28), (x + r_, y), (x + r_ * .28, y + r_ * .28),
                        (x, y + r_), (x - r_ * .28, y + r_ * .28), (x - r_, y), (x - r_ * .28, y - r_ * .28)], fill=col)
    if not arc:
        return
    pts = [(ARC_X0 + ((ARC_X1 - ARC_X0) * i / 24), ARC_Y - ARC_AMP * math.sin(math.pi * i / 24)) for i in range(25)]
    for i in range(0, 24, 2):
        dd.line((pts[i], pts[i + 1]), fill=(255, 255, 255, 235), width=6)


BODY = {   # Kopf-Unterkante → Mitte → unten
    "tag": ((40, 104, 186), (18, 46, 96), (6, 14, 34)),
    "gold": ((168, 74, 96), (70, 30, 66), (16, 10, 30)),
    "nacht": ((14, 28, 60), (12, 22, 52), (4, 8, 22)),
}


def _story_body(kind):
    """Ganzer Hintergrund für Sonder-Stories: Himmel geht weich in einen getönten Körper über,
    dazu Sterne/Funkeln und Flugzeuge mit Kondensstreifen am Rand."""
    c0, c1, c2 = BODY[kind]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        if y < HH:
            col = c0
        else:
            u = (y - HH) / (H - HH)
            col = lerp(c0, c1, u / 0.35) if u < 0.35 else lerp(c1, c2, (u - 0.35) / 0.65)
        d.line((0, y, W, y), fill=col)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    rnd = random.Random({"tag": 1, "gold": 2, "nacht": 3}[kind])
    for _ in range(90):
        x, y = rnd.randint(0, W), rnd.randint(HH, H)
        r_ = rnd.choice((1.2, 1.6, 2.2))
        ld.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 255, 255, rnd.randint(40, 120)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gcol = {"tag": (90, 160, 255, 50), "gold": (255, 170, 90, 46), "nacht": (120, 140, 255, 40)}[kind]
    ImageDraw.Draw(glow).ellipse((60, 520, 1020, 1500), fill=gcol)
    lay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(150)))
    planes = [(170, 1850, 8, 1.0), (1000, 1886, -6, 0.8)]
    for x, y, ang, sc in planes:
        a = math.radians(ang)
        L = 400 * sc
        for k in range(30):
            t0, t1 = k / 30, (k + 1) / 30
            ld.line((x - L * (1 - t0) * math.cos(a), y - L * (1 - t0) * math.sin(a),
                     x - L * (1 - t1) * math.cos(a), y - L * (1 - t1) * math.sin(a)),
                    fill=(255, 255, 255, int(12 + 100 * t1)), width=max(2, int(7 * sc * t1)))
    base = img.convert("RGBA")
    base.alpha_composite(lay)
    return base.convert("RGB"), planes


def draw_airliner_side(img, cx, cy, length, angle_deg=-6.0, flip=False):
    """Realistisches Verkehrsflugzeug in Seitenansicht (leicht steigend): Rumpf mit Licht/Schatten,
    Fensterreihe, Türen, Cockpit, Triebwerk mit Einlauf, Flügel, Seitenleitwerk in Seitenfarben (blau/türkis,
    neutral – kein Airline-Design), Schlagschatten. flip=True: Nase nach links."""
    S = 4
    L = length * S
    Wb, Hb = int(L * 1.15), int(L * 0.62)
    lay = Image.new("RGBA", (Wb, Hb), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ox, oy = Wb * 0.07, Hb * 0.55                       # Heck-Mittelpunkt des Rumpfes
    fh = L * 0.115                                       # Rumpfhöhe
    def X(u):                                            # 0 = Heck, 1 = Nase
        return ox + u * L

    # --- ferner Flügel (dunkler, hinter dem Rumpf)
    d.polygon([(X(0.52), oy - fh * 0.10), (X(0.33), oy - fh * 1.35), (X(0.27), oy - fh * 1.35), (X(0.40), oy - fh * 0.10)],
              fill=(150, 162, 180, 255))
    # --- Seitenleitwerk (Verlauf blau → türkis)
    fin = [(X(0.02), oy - fh * 0.35), (X(0.10), oy - fh * 2.55), (X(0.17), oy - fh * 2.55), (X(0.21), oy - fh * 0.40)]
    finm = Image.new("L", lay.size, 0)
    ImageDraw.Draw(finm).polygon(fin, fill=255)
    grad = Image.new("RGBA", lay.size)
    gd = ImageDraw.Draw(grad)
    for yy in range(Hb):
        gd.line((0, yy, Wb, yy), fill=lerp((30, 90, 200), (40, 190, 210), min(1, max(0, (oy - yy) / (fh * 2.6)))) + (255,))
    lay.paste(grad, (0, 0), finm)
    d = ImageDraw.Draw(lay)
    d.line([(X(0.105), oy - fh * 2.45), (X(0.165), oy - fh * 2.45)], fill=(255, 255, 255, 200), width=int(S * 2))
    # --- Rumpf: senkrechter Verlauf (oben hell, unten Schatten), runde Nase, spitzes Heck
    body = Image.new("L", lay.size, 0)
    bd = ImageDraw.Draw(body)
    def bez(p0, p1, p2, p3, n=24):
        return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
                for t in (i / n for i in range(n + 1))]
    top_y, bot_y = oy - fh / 2, oy + fh / 2
    tip = (X(1.0), oy + fh * 0.12)                             # Nasenspitze leicht unter der Mitte (typisch Airliner)
    outline = ([(X(0.14), top_y), (X(0.84), top_y)]
               + bez((X(0.84), top_y), (X(0.93), top_y), (X(0.985), oy - fh * 0.22), tip)          # Oberseite → Spitze
               + bez(tip, (X(0.995), oy + fh * 0.38), (X(0.95), bot_y), (X(0.86), bot_y))          # Spitze → Unterseite
               + [(X(0.16), bot_y)]
               + bez((X(0.16), bot_y), (X(0.08), bot_y), (X(0.03), oy - fh * 0.05), (X(0.0), oy - fh * 0.30))  # Heck unten
               + [(X(0.01), oy - fh * 0.42), (X(0.14), top_y)])
    bd.polygon(outline, fill=255)
    shade = Image.new("RGBA", lay.size)
    sd = ImageDraw.Draw(shade)
    for yy in range(Hb):
        u = (yy - (oy - fh / 2)) / fh
        if u < 0.18:
            col = lerp((255, 255, 255), (246, 249, 253), u / 0.18)
        elif u < 0.62:
            col = lerp((246, 249, 253), (214, 222, 233), (u - 0.18) / 0.44)
        else:
            col = lerp((214, 222, 233), (150, 162, 182), min(1, (u - 0.62) / 0.38))
        sd.line((0, yy, Wb, yy), fill=col + (255,))
    lay.paste(shade, (0, 0), body)
    d = ImageDraw.Draw(lay)
    # Zierstreifen (Seitenfarbe), Fenster, Türen, Cockpit
    d.line([(X(0.16), oy + fh * 0.12), (X(0.88), oy + fh * 0.12)], fill=(40, 150, 220, 255), width=int(fh * 0.07))
    for k in range(34):
        u = 0.22 + k * 0.019
        if 0.47 < u < 0.51:
            continue
        x = X(u)
        d.rounded_rectangle((x - fh * 0.045, oy - fh * 0.20, x + fh * 0.045, oy - fh * 0.05), radius=int(fh * 0.04),
                            fill=(46, 62, 88, 255))
    for u in (0.20, 0.84):
        d.rounded_rectangle((X(u) - fh * 0.08, oy - fh * 0.33, X(u) + fh * 0.08, oy + fh * 0.18), radius=int(fh * 0.05),
                            outline=(170, 182, 198, 255), width=int(S * 1.2))
    # Cockpitfenster: ein dunkles, schräges Scheibenband entlang der Nasenrundung mit feinen Rahmen
    wpoly = [(X(0.893), oy - fh * 0.33), (X(0.935), oy - fh * 0.30), (X(0.968), oy - fh * 0.19),
             (X(0.958), oy - fh * 0.09), (X(0.900), oy - fh * 0.17)]
    d.polygon(wpoly, fill=(30, 42, 66, 255))
    for u0 in (0.913, 0.935, 0.952):
        d.line([(X(u0), oy - fh * 0.33), (X(u0 - 0.004), oy - fh * 0.14)], fill=(214, 222, 233, 255), width=int(S * 1.6))
    d.line([(X(0.898), oy - fh * 0.30), (X(0.940), oy - fh * 0.27)], fill=(140, 170, 210, 200), width=int(S * 1.2))  # Spiegelung
    # Höhenleitwerk
    d.polygon([(X(0.03), oy - fh * 0.15), (X(-0.03), oy - fh * 0.05), (X(0.10), oy + fh * 0.02), (X(0.16), oy - fh * 0.02)],
              fill=(196, 206, 220, 255))
    # --- naher Flügel (unter dem Rumpf nach vorne unten) mit Triebwerk
    d.polygon([(X(0.40), oy + fh * 0.30), (X(0.60), oy + fh * 0.25), (X(0.45), oy + fh * 1.55), (X(0.36), oy + fh * 1.55)],
              fill=(214, 222, 234, 255))
    d.line([(X(0.36), oy + fh * 1.55), (X(0.45), oy + fh * 1.55)], fill=(150, 162, 182, 255), width=int(S * 2))
    ey = oy + fh * 0.80
    eng = Image.new("L", lay.size, 0)
    ImageDraw.Draw(eng).rounded_rectangle((X(0.47), ey - fh * 0.24, X(0.62), ey + fh * 0.24), radius=int(fh * 0.24), fill=255)
    eg = Image.new("RGBA", lay.size)
    egd = ImageDraw.Draw(eg)
    for yy in range(int(ey - fh * 0.3), int(ey + fh * 0.3)):
        u = (yy - (ey - fh * 0.24)) / (fh * 0.48)
        egd.line((0, yy, Wb, yy), fill=lerp((244, 247, 252), (120, 134, 156), max(0, min(1, u))) + (255,))
    lay.paste(eg, (0, 0), eng)
    d = ImageDraw.Draw(lay)
    d.ellipse((X(0.605), ey - fh * 0.22, X(0.635), ey + fh * 0.22), fill=(40, 48, 62, 255))
    d.ellipse((X(0.612), ey - fh * 0.12, X(0.628), ey + fh * 0.12), fill=(170, 180, 196, 255))
    # Glanzlicht oben
    d.line([(X(0.18), oy - fh * 0.40), (X(0.84), oy - fh * 0.40)], fill=(255, 255, 255, 230), width=int(fh * 0.05))
    if flip:
        lay = lay.transpose(Image.FLIP_LEFT_RIGHT)
    lay = lay.rotate(-angle_deg if not flip else angle_deg, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sh.putalpha(lay.getchannel("A").point(lambda v: int(v * 0.42)))
    sh = sh.filter(ImageFilter.GaussianBlur(S * 7))
    w2, h2 = lay.width // S, lay.height // S
    lay = lay.resize((w2, h2), Image.LANCZOS)
    sh = sh.resize((w2, h2), Image.LANCZOS)
    base = img.convert("RGBA")
    base.alpha_composite(sh, (int(cx - w2 / 2 + 10), int(cy - h2 / 2 + 16)))
    base.alpha_composite(lay, (int(cx - w2 / 2), int(cy - h2 / 2)))
    return base.convert("RGB")


def draw_airliner(img, cx, cy, length, angle_deg=0.0):
    """Realistisches Verkehrsflugzeug (Draufsicht): Rumpf mit Schattierung, gepfeilte Flügel, Triebwerke,
    Höhenleitwerk, Cockpitfenster und Schlagschatten. angle 0 = Nase nach rechts. 4-fach überabgetastet."""
    S = 4
    L = length * S
    box = int(L * 1.25)
    lay = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = box / 2
    # Koordinaten relativ: x entlang Rumpf (−0.5 Heck … +0.5 Nase), y quer
    def P(x, y):
        return (c + x * L, c + y * L)
    white, light, mid, dark = (250, 252, 255, 255), (226, 232, 240, 255), (186, 196, 210, 255), (120, 132, 150, 255)
    # Flügel (gepfeilt) mit Schattenkante
    for sgn in (-1, 1):
        wing = [P(0.10, 0.045 * sgn), P(-0.08, 0.47 * sgn), P(-0.16, 0.47 * sgn), P(-0.10, 0.045 * sgn)]
        d.polygon(wing, fill=light)
        d.line([P(-0.08, 0.47 * sgn), P(-0.16, 0.47 * sgn)], fill=mid, width=int(S * 2))
        d.line([P(0.10, 0.045 * sgn), P(-0.08, 0.47 * sgn)], fill=white, width=int(S * 2))
        # Triebwerk
        ex, ey = 0.02, 0.19 * sgn
        d.rounded_rectangle((c + (ex - 0.07) * L, c + (ey - 0.03) * L, c + (ex + 0.06) * L, c + (ey + 0.03) * L),
                            radius=int(0.03 * L), fill=mid)
        d.ellipse((c + (ex + 0.035) * L, c + (ey - 0.026) * L, c + (ex + 0.075) * L, c + (ey + 0.026) * L), fill=dark)
        # Höhenleitwerk
        tail = [P(-0.36, 0.03 * sgn), P(-0.47, 0.17 * sgn), P(-0.51, 0.17 * sgn), P(-0.45, 0.03 * sgn)]
        d.polygon(tail, fill=light)
    # Rumpf: Verlauf von hell (Mitte) zu mittel (Rand)
    for k in range(10, 0, -1):                                # Rumpf inkl. runder Nase in einem Stück
        w_ = 0.055 * k / 10
        col = lerp(mid[:3], white[:3], 1 - k / 10) + (255,)
        d.rounded_rectangle((c - 0.5 * L, c - w_ * L, c + 0.5 * L, c + w_ * L), radius=int(w_ * L), fill=col)
    d.polygon([P(-0.50, -0.012), P(-0.56, 0), P(-0.50, 0.012)], fill=mid)                       # Heckspitze
    d.line([P(-0.42, 0), P(-0.50, 0)], fill=dark, width=int(S * 2.5))                          # Seitenleitwerk (oben)
    d.polygon([P(0.405, -0.03), P(0.445, -0.024), P(0.445, 0.024), P(0.405, 0.03)], fill=(50, 70, 100, 255))  # Cockpitfenster
    d.line([P(-0.40, 0), P(0.38, 0)], fill=(255, 255, 255, 160), width=int(S * 1.5))           # Glanzlinie
    lay = lay.rotate(-angle_deg, resample=Image.BICUBIC, expand=False)
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sh.putalpha(lay.getchannel("A").point(lambda v: int(v * 0.45)))
    sh = sh.filter(ImageFilter.GaussianBlur(S * 6))
    size = box // S
    sh = sh.resize((size, size), Image.LANCZOS)
    lay = lay.resize((size, size), Image.LANCZOS)
    base = img.convert("RGBA")
    base.alpha_composite(sh, (int(cx - size / 2 + 8), int(cy - size / 2 + 12)))
    base.alpha_composite(lay, (int(cx - size / 2), int(cy - size / 2)))
    return base.convert("RGB")


def _route_marks(p):
    """Kopfzeile der Sonder-Stories: links 🇩🇪 Frankfurt-Hahn (am linken Rand), rechts Nador 🇲🇦 (am rechten Rand),
    dazwischen der gestrichelte Flugbogen mit großem Flugzeug."""
    t = p.t
    f = p.font("extrabold", 40)
    y = ARC_Y
    # links
    xf = 24
    xf += p.flag("DE", xf, y - 17, 34) + 12
    for dx in (3, 0):
        p.d.text((xf + dx, y + dx), "Frankfurt-Hahn", font=f, fill=(0, 0, 0) if dx else (255, 255, 255), anchor="lm")
    a0 = xf + p.tw("Frankfurt-Hahn", f) + 26
    # rechts (bündig am rechten Rand)
    fw = 51                                                   # Flaggenbreite bei Höhe 34
    xr_flag = W - 24 - fw
    p.flag("MA", xr_flag, y - 17, 34)
    xn = xr_flag - 12 - p.tw("Nador", f)
    for dx in (3, 0):
        p.d.text((xn + dx, y + dx), "Nador", font=f, fill=(0, 0, 0) if dx else (255, 255, 255), anchor="lm")
    a1 = xn - 26
    amp = 58
    pts = [(a0 + (a1 - a0) * i / 24, y - amp * math.sin(math.pi * i / 24)) for i in range(25)]
    for i in range(0, 24, 2):
        p.d.line((pts[i][0] + 2, pts[i][1] + 2, pts[i + 1][0] + 2, pts[i + 1][1] + 2), fill=(0, 0, 0), width=6)
        p.d.line((pts[i], pts[i + 1]), fill=(255, 255, 255), width=6)
    for (x, c) in ((a0, t.accent), (a1, t.green)):
        p.d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=c, outline=(255, 255, 255), width=3)
    t_ = 0.5
    px = a0 + (a1 - a0) * t_
    py = y - amp
    p.img = draw_airliner_side(p.img, px, py - 6, 250, -4)
    p.d = ImageDraw.Draw(p.img)


def render_summary(cfg, snap, months, now):
    """Story 1: Übersicht – günstigster Hin- und Rückflug je Monat, Top 3 je Richtung mit Medaillen."""
    today = now.date()
    p = Painter(cfg)
    t = p.t
    img, planes_ = _story_body("tag")
    deco = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
    _header_sky(deco, "tag", arc=False)
    img.paste(deco, (0, 0), deco)
    p.img = img
    p.d = ImageDraw.Draw(p.img)
    for x_, y_, a_, sc_ in planes_:
        p.plane(x_, y_, int(44 * sc_), a_, (255, 255, 255))
    _route_marks(p)
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")

    title = "BESTPREISE PRO MONAT"
    ftt = p.fit(title, "extrabold", 112, W - 2 * PAD)
    p.d.text((W / 2 + 3, 215 + OFF), title, font=ftt, fill=(0, 0, 0), anchor="mm")
    p.d.text((W / 2, 212 + OFF), title, font=ftt, fill=(255, 255, 255), anchor="mm")
    p.d.text((W / 2, 292 + OFF - 4), f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr",
             font=p.fit(f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr", "bold", 30, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="mm")
    sub = f"Hin- und Rückflug · die günstigsten Preise der nächsten {len(months)} Monate"
    p.d.text((W / 2, 336 + OFF - 6), sub, font=p.fit(sub, "bold", 27, W - 2 * PAD - 8),
             fill=(190, 205, 225), anchor="mm")

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
    hy = 414
    for x_, lab, rt, outb in ((col1, "HINFLUG", "Frankfurt-Hahn → Nador", True), (col2, "RÜCKFLUG", "Nador → Frankfurt-Hahn", False)):
        p.d.ellipse((x_, hy - 21, x_ + 42, hy + 21), fill=t.accent)
        p.plane(x_ + 21, hy, 17, -18 if outb else 198, (255, 255, 255))
        p.d.text((x_ + 52, hy - 8), lab, font=p.font("extrabold", 28), fill=(255, 255, 255), anchor="lm")
        p.d.text((x_ + 53, hy + 19), rt, font=p.font("bold", 21), fill=(190, 205, 225), anchor="lm")
    p.d.text((PAD + 6, hy), "MONAT", font=p.font("extrabold", 26), fill=(170, 185, 205), anchor="lm")

    # Preisfarben (nur in dieser Übersicht): <25 grün · 25–49,99 gelb · 50–100 orange · >100 rot
    BANDS = [((34, 197, 94), "unter 25 €"), ((250, 204, 21), "25 – 49,99 €"), ((251, 146, 60), "50 – 100 €"),
             ((240, 82, 82), "über 100 €")]

    def band(pr):
        return BANDS[0][0] if pr < 25 else BANDS[1][0] if pr < 50 else BANDS[2][0] if pr <= 100 else BANDS[3][0]

    fl = p.font("bold", 24)
    widths = [30 + p.tw(lab, fl) for _, lab in BANDS]
    gap = (W - 2 * PAD - 12 - sum(widths)) / (len(BANDS) - 1)
    x, ly2 = PAD + 6, 470
    for (col, lab), w_ in zip(BANDS, widths):
        p.d.ellipse((x, ly2 - 11, x + 22, ly2 + 11), fill=col)
        p.d.text((x + 30, ly2), lab, font=fl, fill=col, anchor="lm")
        x += w_ + gap

    top, bottom = 494, 1690
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
    _ft = "Preise pro Person (Basic-Tarif) · nur kommende Tage · Buchung nur auf ryanair.com"
    p.d.text((W / 2, y + 34), _ft, font=p.fit(_ft, "bold", 21, W - 2 * PAD), fill=(205, 214, 226), anchor="mm")
    lab = "Unabhängige Infoseite · keine Verbindung zu Ryanair"
    fu = p.font("bold", 21)
    p.d.text((W / 2, H - 22), lab, font=fu, fill=(220, 228, 240), anchor="mm")
    return p.img


def _frame(cfg, now, title, subtitle, sky="nacht"):
    """Gemeinsamer Rahmen für Sonder-Stories: Nachthimmel mit Flugbogen, Titel, Prüfzeit, Untertitel, Logo."""
    p = Painter(cfg)
    t = p.t
    img, planes_ = _story_body(sky if sky in BODY else "nacht")
    deco = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
    _header_sky(deco, sky, arc=False)
    img.paste(deco, (0, 0), deco)
    p.img = img
    p.d = ImageDraw.Draw(p.img)
    for x_, y_, a_, sc_ in planes_:
        p.plane(x_, y_, int(44 * sc_), a_, (255, 255, 255))
    _route_marks(p)
    ftt = p.fit(title, "extrabold", 112, W - 2 * PAD)
    p.d.text((W / 2 + 3, 215 + OFF), title, font=ftt, fill=(0, 0, 0), anchor="mm")
    p.d.text((W / 2, 212 + OFF), title, font=ftt, fill=(255, 255, 255), anchor="mm")
    chk = f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr"
    p.d.text((W / 2, 292 + OFF - 4), chk, font=p.fit(chk, "bold", 30, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="mm")
    p.d.text((W / 2, 336 + OFF - 6), subtitle, font=p.fit(subtitle, "bold", 27, W - 2 * PAD - 8), fill=(190, 205, 225), anchor="mm")
    return p


def _footer(p, extra="Preise pro Person (Basic-Tarif) · Hin- und Rückflug einzeln gebucht · Buchung nur auf ryanair.com"):
    y = 1716
    msg = "Die Flugpreise können sich im Laufe des Tages jederzeit ändern."
    p.d.text((W / 2, y), msg, font=p.fit(msg, "bold", 30, W - 2 * PAD), fill=(255, 255, 255), anchor="mm")
    p.d.text((W / 2, y + 34), extra, font=p.fit(extra, "bold", 21, W - 2 * PAD), fill=(195, 205, 218), anchor="mm")
    p.d.text((W / 2, H - 22), "Unabhängige Infoseite · keine Verbindung zu Ryanair", font=p.font("bold", 21),
             fill=(220, 228, 240), anchor="mm")


def _rank_badge(p, cx, cy, r, rank, fpath):
    if rank <= 3:
        draw_medal(p.img, cx, cy, r, rank, fpath)
        p.d = ImageDraw.Draw(p.img)
    else:                                                   # Platz 4/5: schlichte Plakette
        p.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(60, 78, 104), outline=(150, 168, 192), width=3)
        p.d.text((cx, cy + 1), str(rank), font=p.font("extrabold", int(r * 1.3)), fill=(235, 242, 250), anchor="mm")


def _combo_card(p, top, h, rank, o, r_, fpath, label=None):
    """Karte: Hinflug + Rückflug + Gesamtpreis. label = z. B. „1 Woche“ statt Medaille."""
    t = p.t
    tot = o.price + r_.price
    nights = (r_.day - o.day).days
    col = MEDALS[rank][1] if rank and rank <= 3 else (70, 90, 118)
    x0_, y0_, x1_, y1_ = int(PAD), int(top), int(W - PAD), int(top + h)
    reg = p.img.crop((x0_, y0_, x1_, y1_)).filter(ImageFilter.GaussianBlur(14)).convert("RGBA")
    reg.alpha_composite(Image.new("RGBA", reg.size, (10, 18, 40, 175)))
    m_ = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m_).rounded_rectangle((0, 0, reg.width - 1, reg.height - 1), 22, fill=255)
    p.img.paste(reg.convert("RGB"), (x0_, y0_), m_)
    p.d = ImageDraw.Draw(p.img)
    p.d.rounded_rectangle((PAD, top, W - PAD, top + h), 22, outline=col, width=4)
    x0 = PAD + 26
    if label:
        p.d.rounded_rectangle((x0 + 3, top + 21, x0 + p.tw(label, p.font("extrabold", 32)) + 42, top + 73), 26, fill=(0, 0, 0))
        p.d.rounded_rectangle((x0, top + 18, x0 + p.tw(label, p.font("extrabold", 32)) + 39, top + 70), 26, fill=GOLD,
                              outline=(255, 255, 255), width=3)
        p.d.text((x0 + 20, top + 44), label, font=p.font("extrabold", 32), fill=(40, 28, 6), anchor="lm")
    else:
        _rank_badge(p, x0 + 34, top + h / 2 + 4, 34, rank, fpath)
    lx = x0 + (0 if label else 92)
    rows = ((o, "Hin", -18, "HHN-NDR"), (r_, "Rück", 198, "NDR-HHN"))
    y1 = top + (h * 0.47 if label else h * 0.33)
    step = h * 0.27 if label else h * 0.34
    for k, (f, lab, ang, route) in enumerate(rows):
        yy = y1 + k * step
        p.d.ellipse((lx, yy - 19, lx + 38, yy + 19), fill=t.accent)
        p.plane(lx + 19, yy, 15, ang, (255, 255, 255))
        xt = lx + 52
        rt = "Hinflug · Frankfurt-Hahn → Nador" if route == "HHN-NDR" else "Rückflug · Nador → Frankfurt-Hahn"
        p.d.text((xt, yy - 20), rt, font=p.font("bold", 22), fill=(178, 194, 214), anchor="lm")
        dt = f"{WOCHENTAGE[f.day.weekday()][:2]}, {f.day:%d.%m.%Y} · {f.departure}"
        fdt = p.font("bold", 29)
        p.d.text((xt, yy + 14), dt, font=fdt, fill=(235, 242, 250), anchor="lm")
        p.d.text((xt + p.tw(dt, fdt) + 14, yy + 14), fmt_price(f.price), font=p.font("bold", 26), fill=(188, 202, 220), anchor="lm")
    p.d.text((W - PAD - 26, top + h / 2 + (12 if label else -12)), fmt_price(tot), font=p.font("extrabold", 58),
             fill=GOLD if (rank or 9) <= 3 or label else (255, 255, 255), anchor="rm")
    p.d.text((W - PAD - 26, top + h / 2 + (60 if label else 36)), f"hin & zurück · {nights} Nächte",
             font=p.font("bold", 23), fill=(190, 205, 225), anchor="rm")


def _future(snap, cfg, route, today):
    return [f for f in snap.fares(route) if f.day >= today]


def render_kombis(cfg, snap, now, n=5, min_n=3, max_n=30):
    """Story: Top 5 günstigste Hin- und Rückflug-Kombinationen (verschiedene Hinflugtage)."""
    today = now.date()
    outs, rets = _future(snap, cfg, cfg.route_out, today), _future(snap, cfg, cfg.route_ret, today)
    combos = sorted(((o.price + r.price, o.day, r.day, o, r) for o in outs for r in rets
                     if min_n <= (r.day - o.day).days <= max_n), key=lambda c: (round(c[0], 2), c[1], c[2]))
    top, used = [], set()
    for c in combos:
        if c[1] in used:
            continue
        used.add(c[1])
        top.append(c)
        if len(top) == n:
            break
    p = _frame(cfg, now, "TOP 5 KOMBINATIONEN",
               f"Hin- und Rückflug · {min_n}–{max_n} Nächte · die günstigsten der nächsten {N_MONATE} Monate", sky="gold")
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")
    y0, y1, gap = 410, 1688, 14
    h = (y1 - y0 - gap * (n - 1)) / n
    for i, c in enumerate(top):
        _combo_card(p, y0 + i * (h + gap), h, i + 1, c[3], c[4], fpath)
    _footer(p)
    return p.img


def render_dauer(cfg, snap, now):
    """Story: günstigster Hin- und Rückflug je Aufenthaltsdauer (1 Woche, 2 Wochen, 3 Wochen, 1 Monat)."""
    today = now.date()
    outs, rets = _future(snap, cfg, cfg.route_out, today), _future(snap, cfg, cfg.route_ret, today)
    spans = [("1 Woche", 6, 8), ("2 Wochen", 13, 15), ("3 Wochen", 20, 22), ("1 Monat", 28, 31)]
    p = _frame(cfg, now, "GÜNSTIG NACH DAUER", "Hin- und Rückflug · günstigster Preis für 1, 2, 3 Wochen oder 1 Monat")
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")
    y0, y1, gap = 410, 1688, 16
    h = (y1 - y0 - gap * 3) / 4
    for i, (lab, a_, b_) in enumerate(spans):
        best = min(((o.price + r.price, o.day, o, r) for o in outs for r in rets if a_ <= (r.day - o.day).days <= b_),
                   default=None, key=lambda c: (round(c[0], 2), c[1]))
        top = y0 + i * (h + gap)
        if not best:
            p.d.rounded_rectangle((PAD, top, W - PAD, top + h), 22, fill=(20, 36, 62))
            p.d.text((W / 2, top + h / 2), f"{lab}: keine passenden Flüge", font=p.font("bold", 32), fill=(170, 180, 195), anchor="mm")
            continue
        _combo_card(p, top, h, None, best[2], best[3], fpath, label=f"{lab} ({a_}–{b_} Nächte)")
    _footer(p)
    return p.img


def render_summary_feed(cfg, snap, months, now):
    """„Bestpreise pro Monat“ im Instagram-Feed-Format 4:5 (1080×1350) – wird im Feed nicht beschnitten."""
    FH = 1350
    today = now.date()
    p = Painter(cfg)
    t = p.t
    img = Image.new("RGB", (W, FH))
    d = ImageDraw.Draw(img)
    for y in range(FH):
        d.line((0, y, W, y), fill=lerp((12, 24, 46), (5, 10, 20), y / FH))
    deco = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
    _header_sky(deco, "tag", arc=False)           # eigener, flacherer Bogen weiter unten
    img.paste(deco, (0, 0), deco)
    p.img = img
    p.d = ImageDraw.Draw(p.img)
    ay, amp = 104, 52
    pts = [(170 + (740 * i / 40), ay - amp * math.sin(math.pi * i / 40)) for i in range(41)]
    for i in range(0, 40, 2):
        p.d.line((pts[i], pts[i + 1]), fill=(255, 255, 255), width=5)
    for (x, y), col in (((170, ay), t.accent), ((910, ay), t.green)):
        p.d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=col, outline=(255, 255, 255), width=3)
    f = p.font("extrabold", 30)
    tw_ = p.tw("HHN", f)
    p.d.text((152 - tw_ + 2, ay + 2), "HHN", font=f, fill=(0, 0, 0), anchor="lm")
    p.d.text((152 - tw_, ay), "HHN", font=f, fill=(255, 255, 255), anchor="lm")
    p.flag("DE", 152 - tw_ - 50, ay - 13, 26)
    p.d.text((930, ay + 2), "Nador", font=f, fill=(0, 0, 0), anchor="lm")
    p.d.text((928, ay), "Nador", font=f, fill=(255, 255, 255), anchor="lm")
    p.flag("MA", 928 + p.tw("Nador", f) + 10, ay - 13, 26)
    px, py = 540, ay - amp
    p.d.ellipse((px - 40, py - 40, px + 40, py + 40), fill=(255, 255, 255))
    p.d.ellipse((px - 35, py - 35, px + 35, py + 35), fill=t.accent)
    p.plane(px, py, 38, 0, (255, 255, 255))
    ov = Image.new("RGBA", (W, 50), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for y in range(50):
        od.line((0, y, W, y), fill=(12, 24, 46, int(255 * min(1, y / 28))))
    p.img.paste(ov, (0, 112), ov)
    p.d = ImageDraw.Draw(p.img)

    title = "BESTPREISE PRO MONAT"
    ftt = p.fit(title, "extrabold", 96, W - 2 * PAD)
    p.d.text((W / 2 + 3, 188), title, font=ftt, fill=(0, 0, 0), anchor="mm")
    p.d.text((W / 2, 185), title, font=ftt, fill=(255, 255, 255), anchor="mm")
    chk = f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr"
    p.d.text((W / 2, 250), chk, font=p.fit(chk, "bold", 28, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="mm")
    sub = f"Hin- und Rückflug · die günstigsten Preise der nächsten {len(months)} Monate"
    p.d.text((W / 2, 288), sub, font=p.fit(sub, "bold", 24, W - 2 * PAD - 8), fill=(190, 205, 225), anchor="mm")

    col1, col2 = 330, 700
    hy = 330
    for x_, lab, rt, outb in ((col1, "HINFLUG", "Frankfurt-Hahn → Nador", True), (col2, "RÜCKFLUG", "Nador → Frankfurt-Hahn", False)):
        p.d.ellipse((x_, hy - 19, x_ + 38, hy + 19), fill=t.accent)
        p.plane(x_ + 19, hy, 15, -18 if outb else 198, (255, 255, 255))
        p.d.text((x_ + 48, hy - 8), lab, font=p.font("extrabold", 25), fill=(255, 255, 255), anchor="lm")
        p.d.text((x_ + 49, hy + 16), rt, font=p.font("bold", 17), fill=(190, 205, 225), anchor="lm")
    p.d.text((PAD + 6, hy), "MONAT", font=p.font("extrabold", 23), fill=(170, 185, 205), anchor="lm")
    BANDS = [((34, 197, 94), "unter 25 €"), ((250, 204, 21), "25 – 49,99 €"), ((251, 146, 60), "50 – 100 €"),
             ((240, 82, 82), "über 100 €")]

    def band(pr):
        return BANDS[0][0] if pr < 25 else BANDS[1][0] if pr < 50 else BANDS[2][0] if pr <= 100 else BANDS[3][0]
    fl = p.font("bold", 22)
    widths = [28 + p.tw(lab, fl) for _, lab in BANDS]
    gap = (W - 2 * PAD - 12 - sum(widths)) / (len(BANDS) - 1)
    x, ly2 = PAD + 6, 378
    for (col, lab), w_ in zip(BANDS, widths):
        p.d.ellipse((x, ly2 - 10, x + 20, ly2 + 10), fill=col)
        p.d.text((x + 28, ly2), lab, font=fl, fill=col, anchor="lm")
        x += w_ + gap

    rows = []
    for (y_, m_) in months:
        def cheapest(route):
            fs = [f_ for f_ in snap.fares(route) if f_.day.year == y_ and f_.day.month == m_ and f_.day >= today]
            return min(fs, key=lambda f_: (f_.price, f_.day)) if fs else None
        rows.append(((y_, m_), cheapest(cfg.route_out), cheapest(cfg.route_ret)))
    top, bottom, gp = 402, 1272, 5
    n = len(rows)
    rh = (bottom - top - gp * (n - 1)) / n
    for i, ((y_, m_), fo, fr) in enumerate(rows):
        yy = top + i * (rh + gp)
        th = THEMES[m_]
        p.d.rounded_rectangle((PAD, yy, W - PAD, yy + rh), 12, fill=th["cell"])
        p.d.rounded_rectangle((PAD, yy, PAD + 10, yy + rh), 5, fill=th["accent"])
        p.d.text((PAD + 26, yy + rh / 2), f"{MONATE[m_ - 1]} {str(y_)[2:]}", font=p.font("extrabold", 28), fill=(255, 255, 255), anchor="lm")
        for x_, f_ in ((col1, fo), (col2, fr)):
            if not f_:
                p.d.text((x_ + 100, yy + rh / 2), "–", font=p.font("bold", 32), fill=(110, 120, 135), anchor="mm")
                continue
            col = band(f_.price)
            p.d.rounded_rectangle((x_ - 10, yy + 9, x_ - 5, yy + rh - 9), 3, fill=col)
            pr = fmt_price(f_.price)
            fp = p.font("extrabold", 34)
            p.d.text((x_ + 4, yy + rh / 2 - 1), pr, font=fp, fill=col, anchor="lm")
            p.d.text((x_ + 12 + p.tw(pr, fp), yy + rh / 2 + 2), f"{WOCHENTAGE[f_.day.weekday()][:2]}, {f_.day:%d.%m.}",
                     font=p.font("bold", 20), fill=(205, 214, 228), anchor="lm")
    msg = "Die Flugpreise können sich im Laufe des Tages jederzeit ändern."
    p.d.text((W / 2, 1298), msg, font=p.fit(msg, "bold", 26, W - 2 * PAD), fill=(255, 255, 255), anchor="mm")
    ex = "Preise pro Person (Basic-Tarif) · Buchung nur auf ryanair.com · Unabhängige Infoseite, keine Verbindung zu Ryanair"
    p.d.text((W / 2, 1330), ex, font=p.fit(ex, "bold", 18, W - 2 * PAD), fill=(195, 205, 218), anchor="mm")
    return p.img


def _contrail(p, a, b, apex_y, plane_t=0.5):
    """Flugbogen a→b: durchgezogener, auslaufender Kondensstreifen bis zum Flugzeug, danach gestrichelt, Pin am Ziel."""
    t = p.t
    ctrl = ((a[0] + b[0]) / 2, apex_y)

    def B(u):
        return ((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * ctrl[0] + u ** 2 * b[0],
                (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * ctrl[1] + u ** 2 * b[1])
    lay = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    n = 80
    for i in range(n):
        u0, u1 = plane_t * i / n, plane_t * (i + 1) / n
        k = (i + 1) / n
        ld.line((B(u0), B(u1)), fill=(255, 255, 255, int(50 + 205 * k)), width=int(3 + 7 * k))
    u = plane_t + 0.06
    while u < 0.86:
        ld.line((B(u), B(min(u + 0.03, 0.86))), fill=(230, 238, 250, 235), width=6)
        u += 0.05
    glow = lay.filter(ImageFilter.GaussianBlur(6))
    base = p.img.convert("RGBA")
    base.alpha_composite(glow)
    base.alpha_composite(lay)
    p.img = base.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    p.d.ellipse((a[0] - 11, a[1] - 11, a[0] + 11, a[1] + 11), fill=t.accent, outline=(255, 255, 255), width=3)
    ex, ey = B(1.0)                                         # große Pfeilspitze genau am Ziel
    bx_, by_ = B(0.88)
    ang = math.atan2(ey - by_, ex - bx_)
    L, Wd = 54, 30
    tip = (ex, ey)
    pts_ = [tip, (tip[0] - L * math.cos(ang) + Wd * math.cos(ang + math.pi / 2), tip[1] - L * math.sin(ang) + Wd * math.sin(ang + math.pi / 2)),
            (tip[0] - L * math.cos(ang) * 0.72, tip[1] - L * math.sin(ang) * 0.72),
            (tip[0] - L * math.cos(ang) - Wd * math.cos(ang + math.pi / 2), tip[1] - L * math.sin(ang) - Wd * math.sin(ang + math.pi / 2))]
    p.d.polygon([(x_ + 3, y_ + 3) for x_, y_ in pts_], fill=(0, 0, 0))
    p.d.polygon(pts_, fill=t.green, outline=(255, 255, 255), width=3)
    x, y = B(plane_t)
    qx, qy = B(plane_t + 0.01)
    p.img = draw_airliner_side(p.img, x, y - 4, 270, math.degrees(math.atan2(qy - y, qx - x)))
    p.d = ImageDraw.Draw(p.img)


def render_bestangebot(cfg, snap, now, rueck=False):
    """Blickfang-Story: günstigster Hinflug (Frankfurt-Hahn → Nador) bzw. mit rueck=True günstigster Rückflug
    (Nador → Frankfurt-Hahn) in den nächsten Monaten. Abflugort immer links, Ziel rechts mit Pfeil."""
    from flightdeals.render.photo_alert import _cover, _photo
    today = now.date()
    route = cfg.route_ret if rueck else cfg.route_out
    outs = [f for f in snap.fares(route) if f.day >= today]
    src_city, dst_city = ("Nador", "Frankfurt-Hahn") if rueck else ("Frankfurt-Hahn", "Nador")
    src_flag, dst_flag = ("MA", "DE") if rueck else ("DE", "MA")
    best = min(outs, key=lambda f: (f.price, f.day))
    p = Painter(cfg)
    t = p.t
    ph = cfg["photos"]
    pd_ = PROJ / "assets" / "photos"
    # Sonnenuntergangs-Himmel oben, Skylines (Abflugort links, Ziel rechts) unten, Flugzeuge mit Kondensstreifen
    HOR = 660                                                 # Horizont: hier beginnen die Fotos
    bg = Image.new("RGBA", (W, H), (8, 14, 26, 255))
    sky = Image.new("RGBA", (W, HOR + 200), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sky)
    stops = [(0, (14, 22, 70)), (0.45, (92, 44, 130)), (0.78, (220, 92, 110)), (1.0, (255, 170, 90))]
    for y in range(sky.height):
        u = y / sky.height
        for (u0, c0), (u1, c1) in zip(stops, stops[1:]):
            if u0 <= u <= u1:
                sd.line((0, y, W, y), fill=(*lerp(c0, c1, (u - u0) / (u1 - u0)), 255))
                break
    glow = Image.new("RGBA", sky.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 360, HOR - 160, W / 2 + 360, HOR + 260), fill=(255, 210, 120, 150))
    sky.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    rnd = random.Random(12)
    sd = ImageDraw.Draw(sky)
    for _ in range(70):
        x, y = rnd.randint(0, W), rnd.randint(0, 340)
        sd.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, rnd.randint(90, 200)))
    bg.alpha_composite(sky, (0, 0))
    fra = _cover(_photo(str(pd_ / ph["origin_file"])), W // 2 + 80, H - HOR + 300, 0.55, 0.30).convert("RGBA")
    ndr = _cover(_photo(str(pd_ / ph["destination_file"])), W // 2 + 80, H - HOR + 300, 0.62, 0.42).convert("RGBA")
    left, right = (ndr, fra) if rueck else (fra, ndr)
    for img_, x_, side in ((left, 0, "l"), (right, W - right.width, "r")):
        m = Image.new("L", img_.size, 255)
        md = ImageDraw.Draw(m)
        for yy in range(300):                                 # oben weich in den Himmel
            md.line((0, yy, img_.width, yy), fill=int(255 * (yy / 300) ** 1.6))
        if side == "r":
            for xx in range(160):
                for yy in range(0, img_.height, 1):
                    pass
            mm = Image.new("L", img_.size, 255)
            mmd = ImageDraw.Draw(mm)
            for xx in range(160):
                mmd.line((xx, 0, xx, img_.height), fill=int(255 * xx / 160))
            from PIL import ImageChops
            m = ImageChops.multiply(m, mm)
        # dunkler Foto-Himmel durchsichtig, Lichter der Stadt bleiben (Helligkeitsmaske, oben stärker)
        from PIL import ImageChops
        lum = img_.convert("L").point(lambda v_: min(255, int(v_ * 3.2)))
        grad = Image.new("L", img_.size, 0)
        gd_ = ImageDraw.Draw(grad)
        for yy in range(img_.height):
            gd_.line((0, yy, img_.width, yy), fill=int(255 * min(1, max(0, (yy - 160) / 380))))
        solid = Image.new("L", img_.size, 255)
        lm = Image.composite(solid, lum, grad)
        m = ImageChops.multiply(m, lm)
        img_.putalpha(m)
        bg.alpha_composite(img_, (x_, HOR - 300))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for yy in range(HOR - 100, H):
        od.line((0, yy, W, yy), fill=(6, 10, 24, int(min(120, max(0, (yy - HOR - 200) * 0.12)))))
    bg.alpha_composite(ov)
    planes_ = [(170, 600, -16, 1.0), (930, 300, 18, 0.8), (880, 660, -10, 0.6), (120, 1780, 10, 0.9), (960, 1640, -14, 0.8)]
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pld = ImageDraw.Draw(pl)
    for x, y, ang, sc in planes_:
        a_ = math.radians(ang)
        L = 380 * sc
        for k in range(30):
            t0, t1 = k / 30, (k + 1) / 30
            pld.line((x - L * (1 - t0) * math.cos(a_), y - L * (1 - t0) * math.sin(a_),
                      x - L * (1 - t1) * math.cos(a_), y - L * (1 - t1) * math.sin(a_)),
                     fill=(255, 255, 255, int(14 + 120 * t1)), width=max(2, int(7 * sc * t1)))
    bg.alpha_composite(pl)
    p.img = bg.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    for x, y, ang, sc in planes_:
        p.plane(x, y, int(46 * sc), ang, (255, 255, 255))

    def shadow(xy, txt, font, fill, anchor="mm", off=3):
        p.d.text((xy[0] + off, xy[1] + off), txt, font=font, fill=(0, 0, 0), anchor=anchor)
        p.d.text(xy, txt, font=font, fill=fill, anchor=anchor)

    # Kopf
    lab = f"BESTPREIS · NÄCHSTE {N_MONATE} MONATE"
    fl = p.font("extrabold", 46)
    bw = p.tw(lab, fl) + 150
    x0, y0, x1, y1 = (W - bw) / 2, 196, (W + bw) / 2, 284
    p.d.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), 22, fill=(0, 0, 0))
    p.d.rounded_rectangle((x0, y0, x1, y1), 22, fill=GOLD, outline=(255, 255, 255), width=4)
    for cxn in (x0, x1):
        p.d.ellipse((cxn - 16, (y0 + y1) / 2 - 16, cxn + 16, (y0 + y1) / 2 + 16), fill=(18, 24, 72))
    for yy in range(int(y0) + 12, int(y1) - 8, 14):
        p.d.line((x0 + 96, yy, x0 + 96, yy + 7), fill=(150, 110, 20), width=3)
    p.plane(x0 + 52, (y0 + y1) / 2, 30, -20, (60, 40, 6))
    p.d.text((x0 + 120, (y0 + y1) / 2 + 2), lab, font=fl, fill=(40, 28, 6), anchor="lm")
    if rueck:
        lines_ = ["DER GÜNSTIGSTE RÜCKFLUG", "NACH FRANKFURT-HAHN"]
    else:
        lines_ = ["DER GÜNSTIGSTE", "FLUG NACH NADOR"]
    ft2 = min((p.fit(l_, "extrabold", 92, W - 2 * PAD - 20) for l_ in lines_), key=lambda f_: f_.size)
    shadow((W / 2, 372), lines_[0], ft2, (255, 255, 255))
    shadow((W / 2, 470), lines_[1], ft2, (255, 255, 255))

    # Flugbogen mit Städten
    ya = 700
    _contrail(p, (150, ya), (930, ya), 540, 0.5)
    fcity = p.font("extrabold", 40)
    p.flag(src_flag, 56, ya + 34, 30)
    shadow((116, ya + 50), src_city, fcity, (255, 255, 255), anchor="lm")
    tw_ = p.tw(dst_city, fcity)
    shadow((W - 56 - 52 - tw_, ya + 50), dst_city, fcity, (255, 255, 255), anchor="lm")
    p.flag(dst_flag, W - 56 - 42, ya + 34, 30)

    # Glas-Karte mit dem Angebot
    cx0, cy0, cx1, cy1 = 48, 830, W - 48, 1520
    reg = p.img.crop((cx0, cy0, cx1, cy1)).filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
    reg.alpha_composite(Image.new("RGBA", reg.size, (8, 14, 30, 120)))
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, reg.width - 1, reg.height - 1), 36, fill=255)
    p.img.paste(reg.convert("RGB"), (cx0, cy0), m)
    p.d = ImageDraw.Draw(p.img)
    p.d.rounded_rectangle((cx0, cy0, cx1, cy1), 36, outline=GOLD, width=5)
    p.d.ellipse((W / 2 - 40, cy0 + 34, W / 2 + 40, cy0 + 114), fill=t.accent)
    p.plane(W / 2, cy0 + 74, 34, -18, (255, 255, 255))
    p.d.text((W / 2 + 2, cy0 + 152), "RÜCKFLUG · EINFACHE STRECKE, PRO PERSON" if rueck else "HINFLUG · EINFACHE STRECKE, PRO PERSON", font=p.font("extrabold", 30), fill=(0, 0, 0), anchor="mm")
    p.d.text((W / 2, cy0 + 150), "RÜCKFLUG · EINFACHE STRECKE, PRO PERSON" if rueck else "HINFLUG · EINFACHE STRECKE, PRO PERSON", font=p.font("extrabold", 30), fill=(200, 214, 232), anchor="mm")
    shadow((W / 2, cy0 + 222), f"{WOCHENTAGE[best.day.weekday()]}, {best.day:%d.%m.%Y}", p.font("extrabold", 58), (255, 255, 255))
    shadow((W / 2, cy0 + 290), f"Abflug {best.departure} Uhr · {src_city} → {dst_city}", p.font("bold", 32), (225, 234, 245), off=2)
    price = fmt_price(best.price)
    fp = p.font("extrabold", 210)
    glow = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((W / 2, cy0 + 470), price, font=fp, fill=(34, 197, 94, 170), anchor="mm")
    base = p.img.convert("RGBA")
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    p.img = base.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    p.d.text((W / 2, cy0 + 470), price, font=fp, fill=(60, 220, 120), anchor="mm")
    shadow((W / 2, cy0 + 620), "Basic-Tarif · nur 1 kleine Tasche (40×30×20 cm)", p.font("bold", 28), (220, 230, 242), off=2)

    chk = f"Preis bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr"
    shadow((W / 2, 1580), chk, p.fit(chk, "bold", 30, W - 2 * PAD), (255, 255, 255), off=2)
    shadow((W / 2, 1626), "Der Preis kann sich im Laufe des Tages jederzeit ändern.", p.font("bold", 28), (225, 232, 242), off=2)
    if not rueck:                                            # nur in der ersten Story
        nxt = "Alle Preise und Termine in den nächsten Stories →"
        fn = p.font("extrabold", 30)
        nw = p.tw(nxt, fn) + 50
        p.d.rounded_rectangle(((W - nw) / 2, 1664, (W + nw) / 2, 1716), 26, fill=t.accent)
        p.d.text((W / 2, 1690), nxt, font=fn, fill=(255, 255, 255), anchor="mm")
    p.d.text((W / 2, H - 50), cfg["photos"]["credit"], font=p.fit(cfg["photos"]["credit"], "bold", 16, W - 2 * PAD),
             fill=(190, 200, 215), anchor="mm")
    p.d.text((W / 2, H - 24), "Unabhängige Infoseite · keine Verbindung zu Ryanair · Buchung nur auf ryanair.com",
             font=p.font("bold", 18), fill=(220, 228, 240), anchor="mm")
    return p.img


def week_ago_prices(today):
    """Preisstand von vor einer Woche (letzter Stand mit Datum ≤ heute−7). Gibt es noch keinen so alten Stand,
    wird der älteste vorhandene genommen – das Datum steht immer im Bild."""
    from datetime import timedelta
    snaps = []
    for f in sorted(glob.glob(str(PROJ / "data" / "snapshots" / "*.pkl"))):
        sn = pickle.load(open(f, "rb"))
        snaps.append(sn)
    if not snaps:
        return {}, None
    snaps.sort(key=lambda x: x.fetched_at)
    old = [x for x in snaps if x.fetched_at.date() <= today - timedelta(days=7)]
    best = old[-1] if old else snaps[0]
    return {(fa.route, fa.day): fa.price for fa in best.fares()}, best.fetched_at


def _sale_background(cfg=None):
    """Eigener Flug-Hintergrund für Preisstürze: Abendhimmel (Violett → Nachtblau), Wolken,
    Flugzeuge mit Kondensstreifen – eindeutig „Fliegen“, nicht Börse."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp((92, 46, 140), (10, 16, 48), (y / H) ** 0.8))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    rnd = random.Random(4)
    for _ in range(14):                                  # weiche Wolken
        cx, cy, sc = rnd.randint(-100, W + 100), rnd.choice((rnd.randint(40, 520), rnd.randint(1500, 1880))), rnd.uniform(.8, 1.8)
        for dx, dy, rr in ((0, 0, 50), (55, -22, 62), (120, 0, 50), (60, 18, 48), (-48, 12, 36)):
            ld.ellipse((cx + (dx - rr) * sc, cy + (dy - rr) * sc, cx + (dx + rr) * sc, cy + (dy + rr) * sc),
                       fill=(255, 220, 240, 26))
    lay = lay.filter(ImageFilter.GaussianBlur(10))
    ld = ImageDraw.Draw(lay)
    p = Painter(cfg) if cfg else None
    planes = [(250, 110, 14, 1.3), (1000, 540, -22, 0.9), (150, 1560, 12, 1.1), (900, 1800, -14, 1.0), (760, 70, 6, 0.7)]
    for x, y, ang, sc in planes:                         # Kondensstreifen
        a = math.radians(ang)
        L = 420 * sc
        for k in range(30):
            t0, t1 = k / 30, (k + 1) / 30
            ld.line((x - L * (1 - t0) * math.cos(a), y - L * (1 - t0) * math.sin(a),
                     x - L * (1 - t1) * math.cos(a), y - L * (1 - t1) * math.sin(a)),
                    fill=(255, 255, 255, int(14 + 110 * t1)), width=max(2, int(8 * sc * t1)))
    base = img.convert("RGBA")
    base.alpha_composite(lay)
    img = base.convert("RGB")
    if p:
        p.img = img
        p.d = ImageDraw.Draw(p.img)
        for x, y, ang, sc in planes:
            p.plane(x, y, int(52 * sc), ang, (255, 255, 255))
        img = p.img
    return img


def _starburst(p, cx, cy, r, text, fill=(240, 62, 62)):
    """Großer Rabatt-Stern mit Text (z. B. −29 %)."""
    pts = []
    for k in range(32):
        ang = math.pi * k / 16 - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.84
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    p.d.polygon([(x + 5, y + 6) for x, y in pts], fill=(0, 0, 0))
    p.d.polygon(pts, fill=fill, outline=(255, 255, 255), width=5)
    f = p.fit(text, "extrabold", int(r * 0.62), int(r * 1.5))
    p.d.text((cx, cy + 2), text, font=f, fill=(255, 255, 255), anchor="mm")


def render_preisstuerze(cfg, snap, prev, prev_at, now, min_pct=20.0):
    """Story vor den Kalendern: Top 3 Hin- und Rückflüge (nächste Monate), die seit einer Woche um mehr als
    min_pct % günstiger geworden sind. Nur Richtungen mit Treffern; keine Story (None), wenn nichts gefallen ist."""
    today = now.date()
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")

    def drops(route):
        out = []
        for f in snap.fares(route):
            old = prev.get((route, f.day))
            if f.day >= today and old and old > f.price:
                pct = (old - f.price) / old * 100
                if pct > min_pct:
                    out.append((pct, f, old))
        return sorted(out, key=lambda x: (-x[0], x[1].day))[:3]

    sections = [(lab_, r_, ob, drops(r_)) for lab_, r_, ob in
                (("HINFLUG", cfg.route_out, True), ("RÜCKFLUG", cfg.route_ret, False))]
    sections = [x for x in sections if x[3]]
    if not sections:
        return None
    p = Painter(cfg)
    t = p.t
    p.img = _sale_background(cfg)
    p.d = ImageDraw.Draw(p.img)
    week = prev_at and (today - prev_at.date()).days >= 7
    when_long = ((f"von vor einer Woche ({WOCHENTAGE[prev_at.weekday()]}, {prev_at:%d.%m.%Y})" if week
                  else f"vom {WOCHENTAGE[prev_at.weekday()]}, {prev_at:%d.%m.%Y}") if prev_at else "")
    when_short = ((f"vor einer Woche ({WOCHENTAGE[prev_at.weekday()][:2]}, {prev_at:%d.%m.})" if week
                   else f"am {WOCHENTAGE[prev_at.weekday()][:2]}, {prev_at:%d.%m.}") if prev_at else "vorher")

    def shadow(xy, txt, font, fill, anchor="mm", off=3):
        p.d.text((xy[0] + off, xy[1] + off), txt, font=font, fill=(0, 0, 0), anchor=anchor)
        p.d.text(xy, txt, font=font, fill=fill, anchor=anchor)

    # Kopf
    # großes rotes Ticket-Band „ÜBER 20 % GÜNSTIGER“ mit Flugzeug
    lab = f"ÜBER {min_pct:.0f} % GÜNSTIGER"
    fl = p.font("extrabold", 56)
    bw = p.tw(lab, fl) + 150
    x0, y0, x1, y1 = (W - bw) / 2, 196, (W + bw) / 2, 290
    p.d.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), 22, fill=(0, 0, 0))
    p.d.rounded_rectangle((x0, y0, x1, y1), 22, fill=(236, 50, 60), outline=(255, 255, 255), width=4)
    for cxn in (x0, x1):                                 # Ticket-Einkerbungen
        p.d.ellipse((cxn - 16, (y0 + y1) / 2 - 16, cxn + 16, (y0 + y1) / 2 + 16), fill=lerp((92, 46, 140), (10, 16, 48), .1))
    for yy in range(int(y0) + 12, int(y1) - 8, 14):     # Perforation links
        p.d.line((x0 + 96, yy, x0 + 96, yy + 7), fill=(255, 210, 210), width=3)
    p.plane(x0 + 52, (y0 + y1) / 2, 30, -20, (255, 255, 255))
    p.d.text((x0 + 120, (y0 + y1) / 2 + 2), lab, font=fl, fill=(255, 255, 255), anchor="lm")
    shadow((W / 2, 380), "PREISSTÜRZE", p.font("extrabold", 124), (255, 255, 255))
    chk = f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr"
    shadow((W / 2, 466), chk, p.fit(chk, "bold", 30, W - 2 * PAD), (240, 236, 250), off=2)
    sub = f"Verglichen mit den Preisen {when_long}"
    shadow((W / 2, 506), sub, p.fit(sub, "bold", 27, W - 2 * PAD), (214, 200, 240), off=2)

    def route_head(y, label, outb):
        o, d_ = (("Frankfurt-Hahn", "DE"), ("Nador", "MA")) if outb else (("Nador", "MA"), ("Frankfurt-Hahn", "DE"))
        fT, fC = p.font("extrabold", 42), p.font("bold", 30)
        wl = 60 + 14 + p.tw(label, fT) + 24 + 46 + 10 + p.tw(o[0], fC) + 44 + 46 + 10 + p.tw(d_[0], fC)
        x = (W - wl) / 2
        p.d.ellipse((x, y - 30, x + 60, y + 30), fill=t.accent)
        p.plane(x + 30, y, 25, -18 if outb else 198, (255, 255, 255))
        x += 74
        shadow((x, y), label, fT, (255, 255, 255), anchor="lm", off=2)
        x += p.tw(label, fT) + 24
        x += p.flag(o[1], x, y - 15, 30) + 10
        p.d.text((x, y), o[0], font=fC, fill=(225, 238, 232), anchor="lm")
        x += p.tw(o[0], fC) + 10
        p.d.text((x + 12, y), "→", font=fC, fill=(170, 220, 195), anchor="mm")
        x += 34
        x += p.flag(d_[1], x, y - 15, 30) + 10
        p.d.text((x, y), d_[0], font=fC, fill=(225, 238, 232), anchor="lm")

    def glass(box, outline, r=34):
        x0, y0, x1, y1 = map(int, box)
        reg = p.img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(20)).convert("RGBA")
        reg.alpha_composite(Image.new("RGBA", reg.size, (12, 16, 44, 200)))
        m = Image.new("L", reg.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, reg.width - 1, reg.height - 1), r, fill=255)
        p.img.paste(reg.convert("RGB"), (x0, y0), m)
        p.d = ImageDraw.Draw(p.img)
        p.d.rounded_rectangle(box, r, outline=outline, width=5)

    n_items = sum(len(x[3]) for x in sections)
    top, bottom = 550, 1680
    if n_items == 1:                                      # ein Treffer: groß wie die Bestpreis-Story
        label, route, outb, items = sections[0]
        pct, f, old = items[0]
        route_head(612, label, outb)
        cx0, cy0, cx1, cy1 = 48, 690, W - 48, 1560
        glass((cx0, cy0, cx1, cy1), GOLD)
        p.d.text((W / 2, cy0 + 90), f"{WOCHENTAGE[f.day.weekday()]}, {f.day:%d.%m.%Y}", font=p.font("extrabold", 62),
                 fill=(255, 255, 255), anchor="mm")
        p.d.text((W / 2, cy0 + 160), f"Abflug {f.departure} Uhr · einfache Strecke, pro Person", font=p.font("bold", 30),
                 fill=(200, 225, 212), anchor="mm")
        fo = p.font("extrabold", 78)
        os_ = fmt_price(old)
        wo = p.tw(os_, fo)
        p.d.text((W / 2, cy0 + 270), os_, font=fo, fill=(170, 182, 196), anchor="mm")
        p.d.line((W / 2 - wo / 2 - 8, cy0 + 274, W / 2 + wo / 2 + 8, cy0 + 262), fill=(240, 62, 62), width=9)
        p.d.text((W / 2, cy0 + 330), f"Preis {when_short}", font=p.font("bold", 28), fill=(160, 178, 190), anchor="mm")
        price = fmt_price(f.price)
        fp = p.font("extrabold", 200)
        gl = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((W / 2, cy0 + 500), price, font=fp, fill=(34, 197, 94, 170), anchor="mm")
        base = p.img.convert("RGBA")
        base.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18)))
        p.img = base.convert("RGB")
        p.d = ImageDraw.Draw(p.img)
        p.d.text((W / 2, cy0 + 500), price, font=fp, fill=(60, 220, 120), anchor="mm")
        p.d.text((W / 2, cy0 + 630), "jetzt", font=p.font("extrabold", 34), fill=(120, 230, 160), anchor="mm")
        sv = f"Du sparst {fmt_price(old - f.price)}"
        fs = p.font("extrabold", 40)
        sw = p.tw(sv, fs) + 60
        p.d.rounded_rectangle(((W - sw) / 2, cy0 + 690, (W + sw) / 2, cy0 + 756), 33, fill=(22, 130, 64))
        p.d.text((W / 2, cy0 + 723), sv, font=fs, fill=(255, 255, 255), anchor="mm")
        _starburst(p, cx1 - 120, cy0 + 300, 120, f"−{pct:.0f} %")
    else:
        HEAD_H, GAP_C = 92, 16
        ch_ = int(min(250, (bottom - top - len(sections) * HEAD_H - (n_items - 1) * GAP_C) / n_items))
        total = len(sections) * HEAD_H + n_items * ch_ + (n_items - 1) * GAP_C
        y = top + max(0, (bottom - top - total) / 2)
        for label, route, outb, items in sections:
            route_head(y + 44, label, outb)
            y += HEAD_H
            for k, (pct, f, old) in enumerate(items):
                col = MEDALS[k + 1][1]
                glass((PAD + 6, y, W - PAD - 6, y + ch_), col, 26)
                draw_medal(p.img, PAD + 64, y + ch_ / 2 + 4, 30, k + 1, fpath)
                p.d = ImageDraw.Draw(p.img)
                xl = PAD + 120
                p.d.text((xl, y + ch_ * 0.28), f"{WOCHENTAGE[f.day.weekday()]}, {f.day:%d.%m.%Y} · {f.departure} Uhr",
                         font=p.font("extrabold", 32), fill=(255, 255, 255), anchor="lm")
                fo, fn_ = p.font("extrabold", 38), p.font("extrabold", 64)
                os_, ns_ = fmt_price(old), fmt_price(f.price)
                yy = y + ch_ * 0.68
                p.d.text((xl, yy), os_, font=fo, fill=(170, 182, 196), anchor="lm")
                wo = p.tw(os_, fo)
                p.d.line((xl - 4, yy + 3, xl + wo + 4, yy - 3), fill=(240, 62, 62), width=6)
                p.d.text((xl + wo + 30, yy), "→", font=p.font("extrabold", 36), fill=(170, 220, 195), anchor="mm")
                p.d.text((xl + wo + 58, yy), ns_, font=fn_, fill=(60, 220, 120), anchor="lm")
                r_ = min(ch_ / 2 - 8, 92)
                _starburst(p, W - PAD - 30 - r_, y + ch_ / 2, r_, f"−{pct:.0f} %")
                y += ch_ + GAP_C
            y += 8
    msg = "Die Flugpreise können sich im Laufe des Tages jederzeit ändern."
    shadow((W / 2, 1716), msg, p.fit(msg, "bold", 30, W - 2 * PAD), (255, 255, 255), off=2)
    ex = "Preise pro Person (Basic-Tarif) · Buchung nur auf ryanair.com"
    p.d.text((W / 2, 1752), ex, font=p.font("bold", 21), fill=(190, 220, 205), anchor="mm")
    p.d.text((W / 2, H - 24), "Unabhängige Infoseite · keine Verbindung zu Ryanair", font=p.font("bold", 20),
             fill=(220, 236, 228), anchor="mm")
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
    pv_w, pat_w = week_ago_prices(now.date())
    seq = [("01_guenstigster_hinflug", render_bestangebot(cfg, snap, now)),
           ("02_guenstigster_rueckflug", render_bestangebot(cfg, snap, now, rueck=True)),
           ("03_top5_kombinationen", render_kombis(cfg, snap, now)),
           ("04_nach_dauer", render_dauer(cfg, snap, now)),
           ("05_bestpreise_pro_monat", render_summary(cfg, snap, months, now))]
    ps = render_preisstuerze(cfg, snap, pv_w, pat_w, now)
    if ps is not None:                                        # nur wenn es Preisstürze gibt
        seq.append(("06_preisstuerze", ps))
    for y_, m_ in months:
        seq.append((f"{len(seq) + 1:02d}_kalender_{y_}-{m_:02d}", render_month(cfg, snap, prev, y_, m_, now, testdaten)))
    imgs = []
    for name, im in seq:
        im.save(out / f"{name}.png")
        imgs.append(im)
    (out / "anzahl.txt").write_text(str(len(seq)))
    # Übersichtsblatt aller 10 Stories
    cols = 6
    rows_ = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 228 + 12, rows_ * 396 + 12), (30, 30, 34))
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((216, 384), Image.LANCZOS), (12 + (k % cols) * 228, 12 + (k // cols) * 396))
    sheet.save(out / "00_alle_stories.png")
    story_view(imgs[0], cfg, 1, len(imgs)).save(out / "ansicht_01.png")
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
