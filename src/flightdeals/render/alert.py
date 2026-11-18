"""Angebotsbilder für die fünf Meldungstypen (mit Preisverlauf-Grafik)."""
from __future__ import annotations

from datetime import datetime

from ..config import Config
from ..models import Alert, Fare
from ..texts import ALERT_TITLES, T, fmt_date_wd, fmt_datetime, fmt_nights, fmt_pct, fmt_price
from .common import H, M, W, Painter, mix, price_color

KIND_COLOR = {
    "PREISSTURZ": "red",
    "TOP_ANGEBOT": "green",
    "GUENSTIGER_HIN_RUECK": "teal",
    "NEUER_TIEFSTPREIS": "purple",
    "LAST_MINUTE": "orange",
}

SUBLINE = {
    "PREISSTURZ": "Der Preis ist deutlich gefallen",
    "TOP_ANGEBOT": "Neuer Flug zum Top-Preis",
    "GUENSTIGER_HIN_RUECK": "Hin und zurück zum Sparpreis",
    "NEUER_TIEFSTPREIS": "So günstig war dieser Monat noch nie",
    "LAST_MINUTE": "Kurzfristig günstig fliegen",
}


def _chart(p: Painter, box, series_list, title: str):
    """Einfaches Liniendiagramm. series_list: [(label, color, [(datetime, price|None), …]), …]"""
    t = p.t
    x0, y0, x1, y1 = box
    p.rrect(box, 18, fill=t.surface)
    p.text((x0 + 24, y0 + 18), title, "bold", 24, t.text)
    pts_all = [(ts, pr) for _, _, s in series_list for ts, pr in s if pr is not None]
    if len(pts_all) < 2:
        p.text(((x0 + x1) / 2, (y0 + y1) / 2 + 14), "Noch zu wenig Verlauf für eine Grafik", "medium", 22, t.muted, anchor="mm")
        return
    gx0, gx1, gy0, gy1 = x0 + 110, x1 - 30, y0 + 70, y1 - 52
    tmin = min(ts for ts, _ in pts_all).timestamp()
    tmax = max(ts for ts, _ in pts_all).timestamp()
    pmin, pmax = min(pr for _, pr in pts_all), max(pr for _, pr in pts_all)
    if pmax - pmin < 1:
        pmin, pmax = pmin - 5, pmax + 5
    pad = (pmax - pmin) * 0.12
    pmin, pmax = max(0, pmin - pad), pmax + pad

    def X(ts):
        return gx0 + (ts.timestamp() - tmin) / max(1, tmax - tmin) * (gx1 - gx0)

    def Y(pr):
        return gy1 - (pr - pmin) / (pmax - pmin) * (gy1 - gy0)

    for frac in (0, 0.5, 1):                       # Hilfslinien + Beschriftung
        val = pmin + (pmax - pmin) * frac
        y = Y(val)
        p.d.line((gx0, y, gx1, y), fill=t.border, width=1)
        p.text((gx0 - 12, y), fmt_price(val), "medium", 17, t.muted, anchor="rm")
    first = min(ts for ts, _ in pts_all)
    last = max(ts for ts, _ in pts_all)
    p.text((gx0, gy1 + 14), first.strftime("%d.%m."), "medium", 17, t.muted, anchor="lt")
    p.text((gx1, gy1 + 14), last.strftime("%d.%m."), "medium", 17, t.muted, anchor="rt")

    for label, color, s in series_list:
        pts = [(X(ts), Y(pr)) for ts, pr in s if pr is not None]
        if len(pts) >= 2:
            # Stufenlinie: ein Preis gilt bis zur nächsten Änderung
            step = []
            for i, (x, y) in enumerate(pts):
                if i:
                    step.append((x, step[-1][1]))
                step.append((x, y))
            step.append((gx1, step[-1][1]))
            p.d.line(step, fill=color, width=5, joint="curve")
        for x, y in pts[-1:]:
            p.d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=color, outline=t.surface, width=3)
    if len(series_list) > 1:
        lx = x1 - 30
        for label, color, _ in reversed(series_list):
            f = p.font("semibold", 18)
            w = p.tw(label, f)
            p.d.text((lx - w, y0 + 22), label, font=f, fill=color)
            lx -= w + 30


def _compare_card(p: Painter, box, alert: Alert, cfg: Config):
    """Für neue Flüge ohne Verlauf: Vergleich mit dem Durchschnittspreis des Monats."""
    t = p.t
    x0, y0, x1, y1 = box
    p.rrect(box, 18, fill=t.surface)
    f = alert.fare
    avg = alert.ref["month_avg"]
    from ..texts import MONATE
    mon = MONATE[f.day.month - 1]
    cy = (y0 + y1) / 2
    p.text((x0 + 24, y0 + 18), "Preisvergleich", "bold", 24, t.text)
    p.text(((x0 + x1) / 2, cy - 70), f"Durchschnittspreis {mon} ({f.origin} → {f.destination})", "semibold", 26, t.muted, anchor="mm")
    p.text(((x0 + x1) / 2, cy - 18), fmt_price(avg), "extrabold", 56, t.text, anchor="mm")
    if avg > f.price:
        pct = (avg - f.price) / avg * 100
        p.text(((x0 + x1) / 2, cy + 60), f"Dieser Flug ist {fmt_pct(pct)} günstiger", "bold", 34,
               price_color(f.price, cfg, t), anchor="mm")


def _leg_card(p: Painter, top: int, label: str, fare: Fare, cfg: Config):
    t = p.t
    p.rrect((M, top, W - M, top + 116), 18, fill=t.surface)
    out = fare.route == cfg.route_out
    p.plane(M + 42, top + 29, 22, -28 if out else 28, t.accent)
    f_l = p.text((M + 70, top + 18), label.upper(), "bold", 20, t.accent)
    p.flag_pair(fare.route, M + 70 + p.tw(label.upper(), f_l) + 12, top + 20, 17)
    p.text((M + 24, top + 48), f"{cfg.city(fare.origin)} → {cfg.city(fare.destination)}", "bold", 30, t.text)
    p.text((M + 24, top + 86), f"{fmt_date_wd(fare.day, long=True)} · {fare.departure}–{fare.arrival} Uhr",
           "medium", 21, t.muted)
    p.text((W - M - 24, top + 58), fmt_price(fare.price), "extrabold", 44, price_color(fare.price, cfg, t), anchor="rm")


def render_alert(cfg: Config, alert: Alert, history, now: datetime, updated: datetime) -> Painter:
    p = Painter(cfg)
    t = p.t
    color = getattr(t, KIND_COLOR[alert.kind])
    p.header()

    # Titel-Badge
    title = ALERT_TITLES[alert.kind]
    _, bx1, by1 = p.pill(M, 92, title, "extrabold", 40, t.background, color, pad_x=26, pad_y=14)
    p.text((M, by1 + 16), SUBLINE[alert.kind], "semibold", 26, t.muted)
    y = by1 + 58
    if alert.also:
        x = M
        for k in alert.also:
            x0, x1, _ = p.pill(x, y, "+ " + ALERT_TITLES[k], "bold", 18, color, mix(t.background, color, 0.18), pad_x=14, pad_y=7)
            x = x1 + 10
        y += 46

    if alert.combo:
        c = alert.combo
        _leg_card(p, y + 6, T["outbound"], c.outbound, cfg)
        _leg_card(p, y + 136, T["return"], c.inbound, cfg)
        y += 270
        p.text((M, y + 10), T["total"], "semibold", 28, t.muted)
        p.text((M, y + 46), fmt_price(c.total), "extrabold", 120, price_color(c.total, cfg, t))
        p.text((W - M, y + 70), T["per_person"], "bold", 32, t.text, anchor="ra")
        p.text((W - M, y + 112), f"{fmt_nights(c.nights)} in {cfg['route']['destination_name']}", "semibold", 28, t.muted, anchor="ra")
        y += 200
        series = [("Hinflug", t.accent, _series(history, c.outbound.key)),
                  ("Rückflug", t.teal, _series(history, c.inbound.key))]
    else:
        f = alert.fare
        p.text((M, y + 4), f"{cfg.city(f.origin)} → {cfg.city(f.destination)}", "extrabold", 50, t.text, max_w=W - 2 * M)
        p.text((M, y + 66), f"{f.origin} → {f.destination} · {cfg['route']['airline']} · Direktflug", "medium", 24, t.muted)
        p.text((M, y + 116), fmt_date_wd(f.day, long=True), "bold", 40, t.text)
        p.text((M, y + 166), f"Abflug {f.departure} Uhr · Ankunft {f.arrival} Uhr (Ortszeit)", "medium", 24, t.muted)
        y += 222

        # Preisblock
        px = M
        if alert.old_price:
            fo = p.font("semibold", 46)
            old = fmt_price(alert.old_price)
            p.d.text((px, y + 18), old, font=fo, fill=t.muted)
            wo = p.tw(old, fo)
            p.d.line((px - 4, y + 44, px + wo + 4, y + 44), fill=t.red, width=5)
            p.text((px + wo + 22, y + 22), "→", "bold", 44, t.muted)
        p.text((M, y + 74), fmt_price(f.price), "extrabold", 130, price_color(f.price, cfg, t))
        p.text((W - M, y + 112), T["per_person"], "bold", 32, t.text, anchor="ra")

        parts = []
        if alert.kind == "LAST_MINUTE":
            d = alert.ref.get("days_left", 0)
            parts.append("Abflug heute" if d == 0 else ("Abflug morgen" if d == 1 else f"Abflug in {d} Tagen"))
        if alert.kind == "NEUER_TIEFSTPREIS" and alert.ref.get("month_min") and not alert.saving:
            parts.append(f"Bisheriger Monats-Tiefstpreis: {fmt_price(alert.ref['month_min'])}")
        if alert.saving and alert.saving_pct:
            parts.append(f"−{fmt_pct(alert.saving_pct)}  ·  {fmt_price(alert.saving)} {T['saved']}")
        if alert.kind == "TOP_ANGEBOT" and not parts:
            parts.append("Neu im Angebot")
        info = "  ·  ".join(parts) or None
        if info:
            p.pill(M, y + 232, info, "bold", 28, color, mix(t.background, color, 0.2), pad_x=22, pad_y=12)
        y += 310
        series = [("Preis", color, _series(history, f.key))]

    footer_top = p.footer([
        (cfg["fare"]["baggage_note"], t.muted),
        (f"{T['updated']}: {fmt_datetime(updated)} · {T['may_change']}", t.muted),
        (cfg["page"]["disclaimer"], t.grey),
    ], size=17, bottom=H - 22)
    footer_top = p.info_strip(footer_top - 12)
    box = (M, y, W - M, max(y + 260, footer_top - 26))
    points = sum(1 for _, _, s in series for _, pr in s if pr is not None)
    if points < 2 and alert.fare and alert.ref.get("month_avg"):
        _compare_card(p, box, alert, cfg)
    else:
        _chart(p, box, series, T["price_history"])
    if alert.test:
        p.test_banner()
    return p


def _series(history, key: str):
    return [(datetime.fromisoformat(e["t"]), e["p"]) for e in history.series(key)]
