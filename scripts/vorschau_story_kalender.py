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


def background(th):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp(*th["body"], y / H))
    deco = Image.new("RGBA", (W, DECO_END), (0, 0, 0, 0))
    {"strand": deco_strand, "herbst": deco_herbst}[th["deco"]](th, deco)
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


def main(ym, testdaten=False):
    YY, MM = map(int, ym.split("-"))
    th = THEMES[MM]
    cfg = load_config()
    cfg["route"]["months_ahead"] = 10
    now = cfg.now()
    today = now.date()
    snap = fetch_all(cfg, now)
    (PROJ / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    pickle.dump(snap, open(PROJ / "data" / "snapshots" / now.strftime("%Y-%m-%d_%H%M.pkl"), "wb"))
    prev, prev_at = previous_day_prices(today)
    print("Vergleich mit Preisstand vom", prev_at)

    p = Painter(cfg)
    p.img = background(th)
    p.d = ImageDraw.Draw(p.img)
    t = p.t

    # ---------- Kopf ----------
    title = f"{MONATE[MM - 1].upper()} {YY}"
    ft = p.fit(title, "extrabold", 112, W - 2 * PAD - 130)
    p.d.text((PAD + 3, 215), title, font=ft, fill=(0, 0, 0), anchor="lm")
    p.d.text((PAD, 212), title, font=ft, fill=(255, 255, 255), anchor="lm")
    p.d.text((PAD + 2, 292), f"Preise geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr",
             font=p.font("bold", 30), fill=(232, 238, 246), anchor="lm")
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
    TOP, BOTTOM, HEAD, GAPB = 360, 1716, 68, 12
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
            p.d.text((PAD + c * (cw + G) + cw / 2, top + 60), wd, font=p.font("bold", 22),
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
    for dx, dy in ((2, 2), (0, 0)):
        p.d.text((W / 2 + dx, H - 22 + dy), "Unabhängige Infoseite · keine Verbindung zu Ryanair",
                 font=p.font("semibold", 18), fill=(0, 0, 0) if dx else (240, 244, 250), anchor="mm")
    if testdaten:
        lab = "VORSCHAU · Veränderungen = TESTDATEN"
        fv = p.font("extrabold", 20)
        bw = p.tw(lab, fv) + 30
        p.d.rounded_rectangle(((W - bw) / 2, H - 80, (W + bw) / 2, H - 48), 16, fill=(255, 210, 80))
        p.d.text((W / 2, H - 64), lab, font=fv, fill=(30, 25, 10), anchor="mm")
    print(f"Zelle {cw}×{ch}, Kalender-Ende {end2}, Fußzeile {y + 34}")

    out = PROJ / "output" / "vorschau"
    out.mkdir(parents=True, exist_ok=True)
    fn = out / f"story_kalender_{YY}-{MM:02d}.png"
    p.img.save(fn)

    # Ansicht wie in der Story (Instagram-Bedienelemente simuliert)
    m = p.img.convert("RGBA")
    ui = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    u = ImageDraw.Draw(ui)
    for i in range(10):
        x0 = 16 + i * ((W - 32) // 10)
        u.rounded_rectangle((x0 + 3, 22, x0 + (W - 32) // 10 - 3, 28), 3, fill=(255, 255, 255, 230 if i < 2 else 110))
    u.ellipse((24, 50, 104, 130), fill=(255, 255, 255, 255))
    u.text((122, 90), "hahn.nador.fluege  ·  1 Std.", font=p.font("bold", 30), fill=(255, 255, 255, 255), anchor="lm")
    u.line((W - 70, 72, W - 40, 102), fill=(255, 255, 255, 255), width=5)
    u.line((W - 70, 102, W - 40, 72), fill=(255, 255, 255, 255), width=5)
    u.rounded_rectangle((24, H - 140, W - 190, H - 60), 40, outline=(255, 255, 255, 220), width=3)
    u.text((70, H - 100), "Nachricht senden …", font=p.font("medium", 30), fill=(255, 255, 255, 220), anchor="lm")
    u.text((W - 130, H - 100), "♡", font=p.font("bold", 46), fill=(255, 255, 255, 255), anchor="mm")
    m.alpha_composite(ui)
    m.convert("RGB").resize((540, 960), Image.LANCZOS).save(out / f"story_kalender_{YY}-{MM:02d}_ansicht.png")
    print(fn)


if __name__ == "__main__":
    main(sys.argv[1], testdaten="--testdaten" in sys.argv)
