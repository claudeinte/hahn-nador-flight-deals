"""Bild "Top 3 Kombinationen": drei Hin- und Rückflug-Kombinationen für unterschiedliche Reisearten."""
from __future__ import annotations

from datetime import date, datetime

from ..config import Config
from ..models import Combo
from ..texts import T, fmt_date_wd_short, fmt_datetime, fmt_nights, fmt_price, month_name
from .common import H, M, W, Painter, hex2rgb, mix, price_color

MEDALS = [hex2rgb("#F5C542"), hex2rgb("#C9D1DC"), hex2rgb("#D08B4E")]   # Gold, Silber, Bronze


def _medal(p: Painter, cx: float, cy: float, rank: int):
    col = MEDALS[rank - 1]
    p.d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=col)
    p.d.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), outline=mix(col, (255, 255, 255), 0.45), width=2)
    p.text((cx, cy + 1), str(rank), "extrabold", 32, p.t.background, anchor="mm")


def _card(p: Painter, top: int, h: int, rank: int, cat: dict, c: Combo, cfg: Config):
    t = p.t
    box_top = top
    top = top + max(0, (h - 200) // 2) - 4             # Inhalt (≈200 px hoch) mittig setzen
    border = mix(t.background, MEDALS[rank - 1], 0.7 if rank == 1 else 0.35)
    p.rrect((M, box_top, W - M, box_top + h), 20, fill=t.surface_2 if rank == 1 else t.surface, outline=border,
            width=3 if rank == 1 else 2)
    _medal(p, M + 52, top + 50, rank)
    p.text((M + 98, top + 22), cat["label"], "extrabold", 30, t.text, max_w=520)
    p.text((M + 98, top + 60), f"{fmt_nights(c.nights)} in {cfg['route']['destination_name']}", "semibold", 21, t.muted)

    for i, fare in enumerate((c.outbound, c.inbound)):
        y = top + 106 + i * 44
        p.plane(M + 46, y + 14, 19, -28 if i == 0 else 28, t.accent)
        f_l = p.text((M + 72, y), T["outbound"] if i == 0 else T["return"], "semibold", 22, t.muted)
        p.flag_pair(fare.route, M + 72 + p.tw("Rückflug", f_l) + 12, y + 4, 18)
        p.text((M + 272, y - 1), f"{fmt_date_wd_short(fare.day)} · {fare.departure} Uhr", "semibold", 24, t.text)
        p.text((W - M - 290, y - 1), fmt_price(fare.price), "bold", 24, price_color(fare.price, cfg, t), anchor="ra")

    rx = W - M - 26
    p.text((rx, top + 22), T["total"], "semibold", 19, t.muted, anchor="ra")
    p.text((rx, top + 44), fmt_price(c.total), "extrabold", 50, price_color(c.total / 2, cfg, t), anchor="ra")
    p.text((rx, top + 104), T["per_person"], "semibold", 19, t.muted, anchor="ra")


def render_top3(cfg: Config, combos: list, months: list[date], updated: datetime, test: bool = False) -> Painter:
    p = Painter(cfg)
    t = p.t
    p.header()
    p.pill(M, 92, "TOP 3 KOMBINATIONEN", "extrabold", 38, t.background, MEDALS[0], pad_x=26, pad_y=14)
    names = " & ".join(month_name(m.year, m.month).split()[0] for m in months)
    p.text((M, 182), f"Hin- und Rückflug · Abflug im {names} {months[-1].year}", "semibold", 26, t.muted, max_w=W - 2 * M)
    r = cfg["route"]
    p.text((M, 222), f"{r['origin_name']} ↔ {r['destination_name']}", "extrabold", 44, t.text)

    footer_top = p.footer([
        (cfg["fare"]["baggage_note"], t.muted),
        (f"{T['updated']}: {fmt_datetime(updated)} · Preise pro Person · {T['may_change']}", t.muted),
        (cfg["page"]["disclaimer"], t.grey),
    ], size=17, bottom=H - 22)
    strip_top = p.info_strip(footer_top - 12)

    top, bottom = 300, strip_top - 22
    n = max(1, len(combos))
    gap = 24
    h = min(250, int((bottom - top - gap * (n - 1)) / n))
    top += max(0, (bottom - top - (n * h + (n - 1) * gap)) // 2)    # Karten vertikal zentrieren
    for i, (cat, c) in enumerate(combos):
        _card(p, top + i * (h + gap), h, i + 1, cat, c, cfg)
    if not combos:
        p.text((W / 2, (top + bottom) / 2), T["no_combo"], "semibold", 28, t.muted, anchor="mm")
    if test:
        p.test_banner()
    return p
