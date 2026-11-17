"""Monatsbild: Hinflug- und Rückflug-Kalender + günstigste Kombination."""
from __future__ import annotations

import calendar as pycal
from datetime import date, datetime

from ..analysis import departure_dt
from ..config import Config
from ..models import Combo, Snapshot
from ..texts import T, WOCHENTAGE_KURZ, fmt_date_wd, fmt_datetime, fmt_nights, fmt_price, month_name
from .common import H, M, W, Painter, mix, price_color

GAP = 6
CELL_W = (W - 2 * M - 6 * GAP) / 7
HEAD_H = 72          # Titel + Wochentage über dem Raster


def day_state(snap: Snapshot, route: str, day: date, now: datetime):
    """('price', Fare) | ('none', None) | ('past', None) | ('error', None)"""
    if day < now.date():
        return "past", None
    res = snap.month(route, day.replace(day=1))
    if res is None or not res.ok:
        return "error", None
    fare = res.fares.get(day)
    if fare is None:
        return "none", None
    if departure_dt(fare, now.tzinfo) <= now:
        return "past", None
    return "price", fare


def _calendar_block(p: Painter, top: int, title: str, subtitle: str, route: str, month: date,
                    snap: Snapshot, now: datetime, highlight: set, cell_h: int):
    t, cfg = p.t, p.cfg
    f_title = p.text((M, top), title, "bold", 30, t.text)
    p.text((M + p.tw(title, f_title) + 14, top + 6), subtitle, "medium", 24, t.muted)
    wd_y = top + 46
    for i, wd in enumerate(WOCHENTAGE_KURZ):
        cx = M + i * (CELL_W + GAP) + CELL_W / 2
        p.text((cx, wd_y), wd, "semibold", 19, t.red if i == 6 else t.muted, anchor="mt")

    grid_top = top + 72
    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month)
    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if day.month != month.month:
                continue
            x0 = M + c * (CELL_W + GAP)
            y0 = grid_top + r * (cell_h + GAP)
            box = (x0, y0, x0 + CELL_W, y0 + cell_h)
            cx, cy = x0 + CELL_W / 2, y0 + cell_h / 2
            price_size = 28 if cell_h >= 60 else 25
            state, fare = day_state(snap, route, day, now)
            if state == "price":
                col = price_color(fare.price, cfg, t)
                p.rrect(box, 10, fill=mix(t.surface, col, 0.16), outline=mix(t.surface, col, 0.45))
                p.text((x0 + 7, y0 + 4), str(day.day), "semibold", 14, t.muted)
                p.text((cx + 6, y0 + cell_h - 6), fmt_price(fare.price), "extrabold", price_size, col, anchor="ms",
                       max_w=int(CELL_W - 22))
            elif state == "past":
                p.rrect(box, 10, fill=mix(t.background, t.surface, 0.5))
                p.text((x0 + 8, y0 + 5), str(day.day), "semibold", 15, t.grey)
                p.text((cx + 6, cy + 4), "X", "semibold", 22, t.grey, anchor="mm")
            elif state == "none":
                p.rrect(box, 10, fill=t.surface)
                p.text((x0 + 8, y0 + 5), str(day.day), "semibold", 15, t.grey)
                p.text((cx + 6, cy + 4), "–", "bold", 24, t.grey, anchor="mm")
            else:  # error
                p.rrect(box, 10, fill=t.surface, outline=t.border)
                p.text((x0 + 8, y0 + 5), str(day.day), "semibold", 15, t.muted)
                p.text((cx + 6, cy + 4), "?", "bold", 26, t.muted, anchor="mm")
            if day in highlight and state == "price":
                p.rrect((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), 12, outline=t.text, width=3)


def _combo_card(p: Painter, top: int, combo: Combo | None, height: int = 160):
    t, cfg = p.t, p.cfg
    green = t.green
    p.rrect((M, top, W - M, top + height), 18, fill=t.surface_2, outline=green, width=2)
    p.text((M + 24, top + 18), T["best_combo"], "bold", 27, green)
    if combo is None:
        p.text((M + 24, top + 72), T["no_combo"], "medium", 24, t.muted)
        return
    right_w = 300
    left_end = W - M - right_w - 34
    for i, (label, fare) in enumerate(((T["outbound"], combo.outbound), (T["return"], combo.inbound))):
        y = top + 66 + i * 42
        p.text((M + 24, y), label, "semibold", 21, t.muted)
        p.text((M + 140, y - 1), f"{fmt_date_wd(fare.day)} · {fare.departure} Uhr", "semibold", 23, t.text)
        p.text((left_end, y - 2), fmt_price(fare.price), "bold", 25, price_color(fare.price, cfg, t), anchor="ra")
    rx = W - M - 24
    p.text((rx, top + 20), T["total"], "semibold", 20, t.muted, anchor="ra")
    p.text((rx, top + 44), fmt_price(combo.total), "extrabold", 54, green, anchor="ra")
    p.text((rx, top + 112), f"{T['per_person']} · {fmt_nights(combo.nights)} in {cfg['route']['destination_name']}",
           "medium", 19, t.muted, anchor="ra", max_w=right_w + 60)


def _legend(p: Painter, top: int, draw: bool = True) -> int:
    t, c = p.t, p.cfg["price_colors"]
    items = [
        ("box", t.green, f"unter {c['green_below']} €"),
        ("box", t.yellow, f"{c['green_below']} – {c['yellow_below'] - 1} €"),
        ("box", t.orange, f"{c['yellow_below']} – {c['orange_up_to']} €"),
        ("box", t.red, f"über {c['orange_up_to']} €"),
        ("X", t.grey, T["past"]),
        ("–", t.grey, T["no_flight"]),
        ("?", t.muted, T["no_data"]),
    ]
    f = p.font("medium", 18)
    x, y = M, top
    for kind, col, label in items:
        w = 22 + p.tw(label, f) + 22
        if x + w > W - M:
            x, y = M, y + 30
        if draw:
            if kind == "box":
                p.rrect((x, y + 3, x + 16, y + 19), 4, fill=col)
            else:
                p.text((x + 8, y + 11), kind, "bold", 18, col, anchor="mm")
            p.d.text((x + 24, y + 1), label, font=f, fill=p.t.muted)
        x += w
    return y + 26


def render_month(cfg: Config, month: date, snap: Snapshot, combo: Combo | None, now: datetime,
                 test: bool = False) -> Painter:
    p = Painter(cfg)
    t = p.t
    r = cfg["route"]
    p.header()
    p.text((M, 82), T["calendar"].upper(), "bold", 22, t.accent)
    p.text((M, 108), month_name(month.year, month.month), "extrabold", 54, t.text)

    hl_out = {combo.outbound.day} if combo else set()
    hl_ret = {combo.inbound.day} if combo else set()

    # --- Layout von unten nach oben berechnen, damit nichts überlappt ---------------
    footer_lines = [
        (f"{T['updated']}: {fmt_datetime(snap.fetched_at)} · Preise {T['per_person'].split()[0].lower()} "
         f"{T['per_person'].split()[1]}, Basic-Tarif (nur 1 kleine Tasche) · {T['may_change']}", t.muted),
        (cfg["page"]["disclaimer"], t.grey),
    ]
    f_foot = p.font("medium", 16)
    n_foot = sum(len(p.wrap(txt, f_foot, W - 2 * M)) for txt, _ in footer_lines)
    footer_top = H - 18 - n_foot * (16 + 7)
    legend_h = _legend(p, 0, draw=False)                   # Höhe der Legende (1 oder 2 Zeilen)
    legend_top = footer_top - 12 - legend_h
    combo_h = 160
    combo_top = legend_top - 14 - combo_h

    top1 = 186
    rows = len(pycal.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month))
    space = combo_top - 16 - top1                           # Platz für beide Kalender
    block_h = (space - 16) / 2
    cell_h = int(min(66, (block_h - HEAD_H - (rows - 1) * GAP) / rows))
    real_block = HEAD_H + rows * cell_h + (rows - 1) * GAP

    _calendar_block(p, top1, T["outbound"], f"{r['origin_name']} → {r['destination_name']}",
                    cfg.route_out, month, snap, now, hl_out, cell_h)
    top2 = top1 + real_block + 22
    _calendar_block(p, top2, T["return"], f"{r['destination_name']} → {r['origin_name']}",
                    cfg.route_ret, month, snap, now, hl_ret, cell_h)
    combo_top = max(combo_top, top2 + real_block + 18)
    _combo_card(p, combo_top, combo, combo_h)
    _legend(p, combo_top + combo_h + 14)
    p.footer(footer_lines, size=16, bottom=H - 18)
    if test:
        p.test_banner()
    return p
