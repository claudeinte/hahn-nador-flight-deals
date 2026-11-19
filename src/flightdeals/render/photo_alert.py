"""Fotostil (nur für NEUER TIEFSTPREIS): Frankfurt und Nador bei Nacht als Hintergrund,
gepunkteter Flugbogen mit Flugzeug in der Mitte in Flugrichtung.

Hinflug: Bogen von Frankfurt-Hahn (links) nach Nador (rechts), Flugzeug zeigt nach rechts.
Rückflug: Bogen von Nador (rechts) nach Frankfurt-Hahn (links), Flugzeug zeigt nach links.
Fotos: assets/photos (CC BY-SA 4.0, Urheber werden im Bild genannt).
"""
from __future__ import annotations

import math
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw

from ..config import Config
from ..models import Alert
from ..texts import ALERT_TITLES, MONATE, fmt_checked, fmt_date_wd, fmt_pct, fmt_price, month_name
from .common import H, M, W, Painter, mix, price_color


@lru_cache(maxsize=4)
def _photo(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def _cover(img: Image.Image, w: int, h: int, fx: float, fy: float) -> Image.Image:
    s = max(w / img.width, h / img.height)
    im = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.LANCZOS)
    x, y = int((im.width - w) * fx), int((im.height - h) * fy)
    return im.crop((x, y, x + w, y + h))


def _background(p: Painter, cfg: Config):
    ph = cfg["photos"]
    d = cfg.root / "assets" / "photos"
    left = _cover(_photo(str(d / ph["origin_file"])), W // 2, H, 0.55, 0.35)
    right = _cover(_photo(str(d / ph["destination_file"])), W - W // 2, H, 0.66, 0.6)
    p.img.paste(left, (0, 0))
    p.img.paste(right, (W // 2, 0))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    bg = p.t.background
    for yy in range(H):                       # oben: Kopfzeile lesbar · Mitte: Fotos sichtbar · unten: Preis lesbar
        if yy < 170:
            a = 190 - yy * 0.9
        elif yy < 480:
            a = 40
        else:
            a = min(238, 40 + (yy - 480) * 0.75)
        od.line((0, yy, W, yy), fill=(*bg, int(a)))
    p.img.paste(ov, (0, 0), ov)
    p.d = ImageDraw.Draw(p.img)


def _shadow_text(p: Painter, xy, text, weight, size, fill, anchor="la"):
    f = p.font(weight, size)
    x, y = xy
    for dx, dy in ((2, 3), (0, 3), (3, 2)):
        p.d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0), anchor=anchor)
    p.d.text((x, y), text, font=f, fill=fill, anchor=anchor)


def _bezier(a, c, b, t):
    return ((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t ** 2 * b[0],
            (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t ** 2 * b[1])


def _arc(p: Painter, start, end, apex_y: float):
    """Gepunkteter Bogen von start nach end, Flugzeug in der Mitte zeigt Richtung end."""
    ctrl = ((start[0] + end[0]) / 2, apex_y)
    n = 46
    for i in range(n + 1):
        t = i / n
        if abs(t - 0.5) < 0.07:
            continue
        x, y = _bezier(start, ctrl, end, t)
        done = t < 0.5                                      # schon geflogen = kräftiger
        r = 5 if done else 4
        p.d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255) if done else (200, 210, 225))
    for (x, y), col in ((start, p.t.accent), (end, p.t.green)):   # Abflug blau · Ankunft grün
        p.d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=col, outline=(255, 255, 255), width=3)
    x, y = _bezier(start, ctrl, end, 0.5)
    qx, qy = _bezier(start, ctrl, end, 0.51)
    ang = math.degrees(math.atan2(qy - y, qx - x))
    p.d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=p.t.accent)
    p.plane(x, y, 26, ang, (255, 255, 255))


def render_tiefstpreis_photo(cfg: Config, alert: Alert, updated: datetime) -> Painter:
    p = Painter(cfg)
    t = p.t
    f = alert.fare
    r = cfg["route"]
    _background(p, cfg)
    p.header(kicker="FLUG-NEWS", when=updated)

    # Städte: Frankfurt-Hahn immer links, Nador immer rechts
    y = 400
    size = 42
    fnt = p.font("extrabold", size)
    x = M
    x_o = x + p.flag(r["origin_country"], x, y + 8, 30) + 12
    _shadow_text(p, (x_o, y), r["origin_name"], "extrabold", size, (255, 255, 255))
    x_d_flag = W - M - p.tw(r["destination_name"], fnt) - 30 - 12
    x_d = x_d_flag + p.flag(r["destination_country"], x_d_flag, y + 8, 30) + 12
    _shadow_text(p, (x_d, y), r["destination_name"], "extrabold", size, (255, 255, 255))

    left_pt, right_pt = (M + 120, y - 18), (x_d_flag + 40, y - 18)
    outbound = f.route == cfg.route_out
    _arc(p, left_pt, right_pt, 120) if outbound else _arc(p, right_pt, left_pt, 120)

    # Angebot
    top = 560
    color = t.purple
    p.pill(M, top, ALERT_TITLES[alert.kind], "extrabold", 38, t.background, color, pad_x=24, pad_y=13)
    leg = "Hinflug" if outbound else "Rückflug"
    p.text((M, top + 82), f"{fmt_date_wd(f.day, long=True)} · {f.departure} Uhr", "bold", 38, t.text)
    _shadow_text(p, (W - M, top + 90), leg, "extrabold", 28, (255, 255, 255), anchor="ra")
    y2 = top + 150
    if alert.old_price:
        fo = p.font("semibold", 44)
        old = fmt_price(alert.old_price)
        p.d.text((M, y2), old, font=fo, fill=t.muted)
        wo = p.tw(old, fo)
        p.d.line((M - 4, y2 + 27, M + wo + 4, y2 + 27), fill=t.red, width=5)
        p.text((M + wo + 22, y2 + 2), "→", "bold", 42, t.muted)
    _shadow_text(p, (M - 4, top + 200), fmt_price(f.price), "extrabold", 150, price_color(f.price, cfg, t))
    p.text((W - M, top + 262), "Pro Person", "bold", 32, t.text, anchor="ra")
    parts = []
    if alert.saving and alert.saving_pct:
        parts.append(f"−{fmt_pct(alert.saving_pct)}  ·  {fmt_price(alert.saving)} gespart")
    else:
        parts.append(f"Neuer Tiefstpreis für {month_name(f.day.year, f.day.month)}")
    p.pill(M, top + 372, parts[0], "bold", 28, color, mix(t.background, color, 0.25), pad_x=22, pad_y=12)
    p.text((M, top + 446), f"Neuer Tiefstpreis für {MONATE[f.day.month - 1]} {f.day.year} · Preis {fmt_checked(updated)}"
           f" – kann sich jederzeit ändern.", "semibold", 21, t.muted, max_w=W - 2 * M)

    # Fuß: Hinweisleiste, Gepäck, Haftungsausschluss, Bildnachweis
    p.d.text((M, H - 26), cfg["photos"]["credit"], font=p.font("medium", 14), fill=mix(t.muted, t.background, 0.3))
    foot_top = p.footer([(cfg["fare"]["baggage_note"], t.muted), (cfg["page"]["disclaimer"], t.grey)],
                        size=16, bottom=H - 40)
    p.info_strip(foot_top - 10)
    if alert.test:
        p.test_banner()
    return p
