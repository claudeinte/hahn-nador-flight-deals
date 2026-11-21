"""VORSCHAU (nur Entwurf, nichts wird veröffentlicht): Story-Kalender 1080×1920 für einen Monat.
Echte aktuelle Preise; die Veränderungen zum Vortag sind TESTDATEN, solange es noch keinen
gespeicherten Preisstand vom Vortag für diesen Monat gibt (wird im Bild deutlich angezeigt).

Aufruf: .venv/bin/python scripts/vorschau_story_kalender.py 2027-08
"""
import calendar as pycal
import hashlib
import math
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config  # noqa: E402
from flightdeals.fetch import fetch_all  # noqa: E402
from flightdeals.render.common import Painter  # noqa: E402
from flightdeals.texts import MONATE, WOCHENTAGE, fmt_price  # noqa: E402

W, H = 1080, 1920
PAD = 36
GOLD = (245, 197, 66)
UP, DOWN, SAME, NEW = (240, 82, 82), (34, 197, 94), (150, 160, 175), (76, 154, 255)

# Monats-Themen (Deko-Farben bewusst ohne reines Grün/Rot, damit sie nicht mit ▲/▼ verwechselt werden)
THEMES = {
    8: dict(name="Mittelmeer", sky=((70, 160, 225), (20, 80, 150)), sea=((20, 120, 185), (10, 70, 125)),
            sand=(226, 196, 140), body=((10, 26, 46), (6, 14, 26)), cell=(18, 38, 62), cell_off=(12, 26, 44),
            accent=(90, 180, 255)),
}


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background(th):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):                                   # Körper: dunkler Verlauf
        d.line((0, y, W, y), fill=lerp(*th["body"], y / H))
    # Kopf-Deko 0–300: Himmel, Sonne, Meer, Strand, Palmen (liegt teils unter der Instagram-Leiste – nur Deko)
    deco = Image.new("RGBA", (W, 330), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    for y in range(190):
        dd.line((0, y, W, y), fill=(*lerp(*th["sky"], y / 190), 255))
    cx, cy, r = 820, 120, 62
    glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - 170, cy - 170, cx + 170, cy + 170), fill=(255, 230, 150, 120))
    deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(45)))
    dd = ImageDraw.Draw(deco)
    for j in range(r, 0, -1):
        dd.ellipse((cx - j, cy - j, cx + j, cy + j), fill=(*lerp((255, 248, 200), (255, 196, 60), j / r), 255))
    for y in range(190, 250):
        dd.line((0, y, W, y), fill=(*lerp(*th["sea"], (y - 190) / 60), 255))
    for i, y in enumerate(range(194, 246, 8)):
        dd.line((cx - 60 + i * 6, y, cx + 60 - i * 6, y), fill=(255, 240, 180, 170 - i * 22), width=3)
    for x0 in range(-60, W, 120):
        dd.arc((x0, 244, x0 + 120, 258), 200, 340, fill=(255, 255, 255, 200), width=3)
    for y in range(250, 330):
        a = 255 if y < 272 else int(255 * (1 - (y - 272) / 58))
        dd.line((0, y, W, y), fill=(*th["sand"], a))
    c_ = (20, 28, 40, 255)

    def palm(x, by, h, lean, s):
        pts = [(x + lean * (i / 10) ** 2, by - h * i / 10) for i in range(11)]
        dd.line(pts, fill=c_, width=int(11 * s), joint="curve")
        tx, ty = pts[-1]
        for ang, ln in ((-165, 80), (-135, 88), (-100, 62), (-62, 84), (-25, 90), (12, 74), (165, 70)):
            a = math.radians(ang)
            L = ln * s
            mx, my = tx + L * .5 * math.cos(a), ty + L * .5 * math.sin(a) - 13 * s
            ex, ey = tx + L * math.cos(a), ty + L * math.sin(a) + 20 * s
            nx, ny = -math.sin(a) * 9 * s, math.cos(a) * 9 * s
            dd.polygon([(tx, ty), (mx + nx, my + ny), (ex, ey), (mx - nx, my - ny)], fill=c_)
    palm(990, 268, 150, -36, 1.0)
    palm(80, 268, 110, 22, 0.8)
    img.paste(deco, (0, 0), deco)
    # Übergang zum dunklen Körper, damit Monatsname gut lesbar ist
    ov = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for y in range(200):
        od.line((0, y, W, y), fill=(*th["body"][0], int(255 * min(1, y / 120))))
    img.paste(ov, (0, 250), ov)
    return img


def fake_delta(route, day):
    """TESTDATEN für die Vorschau: deterministische Beispiel-Veränderungen."""
    h = int(hashlib.md5(f"{route}{day}".encode()).hexdigest(), 16) % 9
    return [-10.0, -5.0, -3.01, 0.0, 0.0, 5.0, 2.0, 12.5, None][h]


def fmt_delta(dv):
    v = abs(dv)
    s = f"{v:.0f}" if abs(v - round(v)) < 0.005 else f"{v:.2f}".replace(".", ",")
    return ("−" if dv < 0 else "+") + s + " €"


def main(ym):
    YY, MM = map(int, ym.split("-"))
    th = THEMES[MM]
    cfg = load_config()
    cfg["route"]["months_ahead"] = 10
    now = cfg.now()
    snap = fetch_all(cfg, now)
    (PROJ / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    pickle.dump(snap, open(PROJ / "data" / "snapshots" / now.strftime("%Y-%m-%d_%H%M.pkl"), "wb"))
    month0 = date(YY, MM, 1)

    p = Painter(cfg)
    p.img = background(th)
    p.d = ImageDraw.Draw(p.img)
    t = p.t

    # Kopf: Monat groß, Prüfzeit, Logo
    p.d.text((PAD + 3, 333), f"{MONATE[MM - 1].upper()} {YY}", font=p.font("extrabold", 112), fill=(0, 0, 0), anchor="lm")
    p.d.text((PAD, 330), f"{MONATE[MM - 1].upper()} {YY}", font=p.font("extrabold", 112), fill=(255, 255, 255), anchor="lm")
    p.d.text((PAD, 402), f"Preise geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr",
             font=p.font("semibold", 27), fill=(214, 226, 240), anchor="lm")
    lx, ly = W - PAD - 52, 330
    p.d.ellipse((lx - 52, ly - 52, lx + 52, ly + 52), fill=(255, 255, 255))
    p.d.ellipse((lx - 47, ly - 47, lx + 47, ly + 47), fill=t.accent)
    p.plane(lx, ly, 56, -35, (255, 255, 255))
    p.d.text((lx, ly + 72), "Hahn ⇄ Nador".replace("⇄", "↔"), font=p.font("bold", 17), fill=(214, 226, 240), anchor="mm")

    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(YY, MM)
    cw = (W - 2 * PAD - 6 * 6) // 7
    ch, gap = 84, 6

    def block(top, route, label, flags):
        fares = {f.day: f for f in snap.fares(route) if f.day.year == YY and f.day.month == MM}
        best = min(fares.values(), key=lambda f: (f.price, f.day)) if fares else None
        # Titelzeile
        p.d.ellipse((PAD, top + 2, PAD + 40, top + 42), fill=th["accent"])
        p.plane(PAD + 20, top + 22, 15, -28 if label == "Hinflug" else 28, (255, 255, 255))
        p.d.text((PAD + 54, top + 22), label.upper(), font=p.font("extrabold", 34), fill=(255, 255, 255), anchor="lm")
        x = PAD + 54 + p.tw(label.upper(), p.font("extrabold", 34)) + 18
        f2 = p.font("semibold", 24)
        o, d_ = route.split("-")
        cc = {"HHN": "DE", "NDR": "MA"}
        for i, code in enumerate((o, d_)):
            if i:
                p.d.text((x + 2, top + 22), "→", font=f2, fill=(180, 195, 215), anchor="lm")
                x += p.tw("→", f2) + 12
            x += p.flag(cc[code], x, top + 13, 18) + 8
            p.d.text((x, top + 22), cfg.city(code), font=f2, fill=(214, 226, 240), anchor="lm")
            x += p.tw(cfg.city(code), f2) + 8
        if best:
            p.d.text((W - PAD, top + 22), f"★ ab {fmt_price(best.price)}", font=p.font("extrabold", 28), fill=GOLD, anchor="rm")
        # Wochentage
        for c, wd in enumerate(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]):
            p.d.text((PAD + c * (cw + 6) + cw / 2, top + 62), wd, font=p.font("bold", 21),
                     fill=(150, 165, 185) if c < 6 else (255, 170, 120), anchor="mm")
        y0 = top + 78
        for r_, week in enumerate(weeks):
            for c, day in enumerate(week):
                x0, yy = PAD + c * (cw + 6), y0 + r_ * (ch + gap)
                if day.month != MM:
                    continue
                f = fares.get(day)
                p.d.rounded_rectangle((x0, yy, x0 + cw, yy + ch), 12, fill=th["cell"] if f else th["cell_off"])
                p.d.text((x0 + 9, yy + 5), str(day.day), font=p.font("semibold", 19), fill=(150, 165, 185))
                if not f:
                    p.d.text((x0 + cw / 2, yy + ch / 2 + 6), "–", font=p.font("bold", 30), fill=(80, 95, 115), anchor="mm")
                    continue
                p.d.text((x0 + cw - 9, yy + 55), f"{f.price:.2f}".replace(".", ","), font=p.font("extrabold", 31),
                         fill=(255, 255, 255), anchor="rs")
                dv = fake_delta(route, day)
                fd = p.font("bold", 17)
                if dv is None:
                    p.d.rounded_rectangle((x0 + cw - 52, yy + 61, x0 + cw - 8, yy + 80), 9, fill=NEW)
                    p.d.text((x0 + cw - 30, yy + 71), "NEU", font=p.font("extrabold", 13), fill=(255, 255, 255), anchor="mm")
                elif dv == 0:
                    p.d.text((x0 + cw - 9, yy + 78), "● ±0 €", font=fd, fill=SAME, anchor="rs")
                else:
                    p.d.text((x0 + cw - 9, yy + 78), ("▼ " if dv < 0 else "▲ ") + fmt_delta(dv), font=fd,
                             fill=DOWN if dv < 0 else UP, anchor="rs")
                if best and day == best.day:
                    p.d.rounded_rectangle((x0, yy, x0 + cw, yy + ch), 12, outline=GOLD, width=4)
                    p.d.text((x0 + cw - 10, yy + 15), "★", font=p.font("bold", 22), fill=GOLD, anchor="rm")
        return y0 + len(weeks) * (ch + gap) - gap

    end1 = block(440, cfg.route_out, "Hinflug", None)
    end2 = block(end1 + 22, cfg.route_ret, "Rückflug", None)

    # Legende + Hinweis
    y = end2 + 26
    items = [("▼ günstiger", DOWN), ("▲ teurer", UP), ("● gleich", SAME), ("NEU", NEW), ("– kein Flug", (120, 135, 155)),
             ("★ günstigster Tag", GOLD)]
    fl = p.font("bold", 20)
    total = sum(p.tw(s, fl) for s, _ in items) + 26 * (len(items) - 1)
    x = (W - total) / 2
    for s, col in items:
        p.d.text((x, y), s, font=fl, fill=col, anchor="lm")
        x += p.tw(s, fl) + 26
    p.d.text((W / 2, y + 34), "Preise in € pro Person (Basic-Tarif) · Veränderung zum Vortag · Preise können sich jederzeit ändern",
             font=p.font("medium", 17), fill=(170, 182, 200), anchor="mm")
    p.d.text((W / 2, y + 60), "Unabhängige Infoseite · keine Verbindung zu Ryanair · Buchung nur auf ryanair.com",
             font=p.font("medium", 16), fill=(120, 135, 155), anchor="mm")
    # Vorschau-Hinweis (Testdaten)
    lab = "VORSCHAU · Veränderungen = TESTDATEN"
    fv = p.font("extrabold", 20)
    bw = p.tw(lab, fv) + 30
    p.d.rounded_rectangle(((W - bw) / 2, y + 88, (W + bw) / 2, y + 122), 17, fill=(255, 210, 80))
    p.d.text((W / 2, y + 105), lab, font=fv, fill=(30, 25, 10), anchor="mm")

    out = PROJ / "output" / "vorschau"
    out.mkdir(parents=True, exist_ok=True)
    fn = out / f"story_kalender_{YY}-{MM:02d}.png"
    p.img.save(fn)

    # Zusätzlich: wie es in der Story-Ansicht aussieht (Instagram-Bedienelemente simuliert)
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
    main(sys.argv[1])
