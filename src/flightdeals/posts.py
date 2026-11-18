"""Erstellt fertige Beiträge (Bilder + Text) im Ausgabeordner.

Struktur:  output/<JJJJ-MM-TT>/<HHMM>_<typ>/
              01_kalender_2026-12.png …   bzw.   01_preissturz_hhn-ndr_2026-12-12.png …
              beitrag.txt     (Facebook-Text, Deutsch)
              beitrag.json    (Metadaten: Typ, Bilder, Links, Veröffentlichungsstatus)
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .analysis import best_combo, future_fares, top_combos
from .config import Config
from .fetch import add_months
from .models import Alert, Combo, Snapshot
from .render.alert import render_alert
from .render.calendar import render_month
from .render.top3 import render_top3
from .texts import (ALERT_TITLES, T, booking_link, fmt_date_wd, fmt_datetime, fmt_nights, fmt_pct,
                    fmt_price, month_name, round_trip_link)

TYPE_DIR = {"taeglich": "taeglicher-kalender", "woechentlich": "wochen-kalender", "angebot": "angebote",
            "top3": "top3-kombinationen"}


class VerificationError(Exception):
    pass


def post_dir(cfg: Config, now: datetime, kind: str) -> Path:
    d = cfg.output_dir / now.strftime("%Y-%m-%d") / f"{now.strftime('%H%M')}_{TYPE_DIR.get(kind, kind)}"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- Prüfung -------
def verify_fare(snap: Snapshot, fare, now: datetime):
    """Nur echte, in DIESER Abfrage bestätigte Preise und keine vergangenen Flüge."""
    res = snap.month(fare.route, fare.day.replace(day=1))
    if res is None or not res.ok:
        raise VerificationError(f"{fare.key}: Monat nicht erfolgreich abgefragt")
    cur = res.fares.get(fare.day)
    if cur is None or abs(cur.price - fare.price) > 0.001:
        raise VerificationError(f"{fare.key}: Preis stimmt nicht mit aktueller Abfrage überein")
    if fare.day < now.date():
        raise VerificationError(f"{fare.key}: Flug liegt in der Vergangenheit")


def verify_combo(snap: Snapshot, combo: Combo, cfg: Config, now: datetime):
    verify_fare(snap, combo.outbound, now)
    verify_fare(snap, combo.inbound, now)
    st = cfg["stay"]
    if combo.inbound.day <= combo.outbound.day:
        raise VerificationError("Rückflug liegt nicht nach dem Hinflug")
    if not (st["min_nights"] <= combo.nights <= st["max_nights"]):
        raise VerificationError("Aufenthaltsdauer außerhalb der Einstellungen")


# ---------------------------------------------------------------- Texte ---------
def flag_emoji(country: str) -> str:
    """'DE' -> 🇩🇪 (Facebook zeigt Flaggen-Emojis im Text an)."""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in country.upper())


def _flags(cfg: Config) -> tuple[str, str]:
    r = cfg["route"]
    return flag_emoji(r["origin_country"]), flag_emoji(r["destination_country"])


def _footer_text(cfg: Config, snap: Snapshot) -> str:
    """Gemeinsamer Abschluss aller Beiträge – jede Information nur einmal."""
    return (f"🧳 {cfg['fare']['baggage_note']}\n"
            f"🕒 Stand: {fmt_datetime(snap.fetched_at)}\n\n"
            f"ℹ️ {cfg['page']['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich "
            f"auf ryanair.com.\n\n{cfg['page']['hashtags']}")


def combo_lines(cfg: Config, c: Combo) -> str:
    r = cfg["route"]
    fo, fd = _flags(cfg)
    return (f"🛫 {T['outbound']} {fo} → {fd}: {fmt_date_wd(c.outbound.day)} · {c.outbound.departure} Uhr · "
            f"{fmt_price(c.outbound.price)}\n"
            f"🛬 {T['return']} {fd} → {fo}: {fmt_date_wd(c.inbound.day)} · {c.inbound.departure} Uhr · "
            f"{fmt_price(c.inbound.price)}\n"
            f"💶 {T['total']}: {fmt_price(c.total)} pro Person · {fmt_nights(c.nights)} in {r['destination_name']}\n\n"
            f"👉 Buchung nur über die offizielle Ryanair-Seite:\n"
            f"🔗 {round_trip_link(r['origin'], r['destination'], c.outbound.day, c.inbound.day)}")


def calendar_text(cfg: Config, snap: Snapshot, months: list[date], combos: dict) -> str:
    """Erste Zeile = das Wichtigste (Monat, Strecke mit Flaggen, Preis), denn Facebook zeigt
    vor "Mehr anzeigen" nur 1–2 Zeilen."""
    r = cfg["route"]
    fo, fd = _flags(cfg)
    names = " & ".join(month_name(m.year, m.month) for m in months) if len(months) <= 2 else \
        f"{month_name(months[0].year, months[0].month)} – {month_name(months[-1].year, months[-1].month)}"
    route = f"{fo} {r['origin_name']} ✈️ {fd} {r['destination_name']}"
    if combos:
        cheapest = min(c.total for c in combos.values())
        parts = [f"📅 {names}: {route} – hin & zurück ab {fmt_price(cheapest)} pro Person!",
                 f"Alle {r['airline']}-Preise im Kalender 👇", ""]
    else:
        parts = [f"📅 {names}: {route}", f"Alle {r['airline']}-Preise im Kalender 👇", ""]
    for m in months:
        c = combos.get(m)
        if len(months) > 1:
            parts.append(f"💚 {T['best_combo']} – {month_name(m.year, m.month)}:")
        parts.append(combo_lines(cfg, c) if c else T["no_combo"])
        parts.append("")
    if snap.errors:
        parts.append("❓ Für einige Tage konnten keine Preise abgefragt werden (im Kalender mit ? markiert).\n")
    parts.append("🟢 unter 50 € · 🟡 50–99 € · 🟠 100–200 € · 🔴 über 200 €")
    parts.append(_footer_text(cfg, snap))
    return "\n".join(parts)


def alert_line(cfg: Config, a: Alert) -> str:
    title = ALERT_TITLES[a.kind]
    if a.combo:
        return f"🔥 {title}\n{combo_lines(cfg, a.combo)}"
    f = a.fare
    line = (f"🔥 {title}: {cfg.city(f.origin)} → {cfg.city(f.destination)}\n"
            f"📅 {fmt_date_wd(f.day)} · {f.departure} Uhr\n💶 ")
    if a.old_price:
        line += f"Vorher {fmt_price(a.old_price)} → jetzt {fmt_price(f.price)}"
        if a.saving and a.saving_pct:
            line += f" (−{fmt_pct(a.saving_pct)}, {fmt_price(a.saving)} {T['saved']})"
    else:
        line += f"Jetzt {fmt_price(f.price)}"
    line += " pro Person"
    if a.also:
        line += "\n⭐ Außerdem: " + ", ".join(ALERT_TITLES[k] for k in a.also)
    line += f"\n👉 Buchung nur über die offizielle Ryanair-Seite:\n🔗 {booking_link(f.origin, f.destination, f.day)}"
    return line


def alerts_text(cfg: Config, snap: Snapshot, alerts: list[Alert]) -> str:
    head = "🚨 Neue Angebote Frankfurt-Hahn ⇄ Nador" if len(alerts) > 1 else "🚨 Neues Angebot Frankfurt-Hahn ⇄ Nador"
    body = "\n\n".join(alert_line(cfg, a) for a in alerts)
    return f"{head}\n\n{body}\n\n{_footer_text(cfg, snap)}"


def _write(d: Path, kind: str, text: str, images: list[str], extra: dict, test: bool):
    (d / "beitrag.txt").write_text(text, encoding="utf-8")
    meta = {"typ": kind, "bilder": images, "erstellt": datetime.now().isoformat(timespec="seconds"),
            "testdaten": test, "veroeffentlicht": False, "status": "vorbereitet (Facebook-Veröffentlichung deaktiviert)",
            **extra}
    (d / "beitrag.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- Beiträge ------
def calendar_months(now: datetime, count: int) -> list[date]:
    first = now.date().replace(day=1)
    return [add_months(first, i) for i in range(count)]


def build_calendar_post(cfg: Config, snap: Snapshot, now: datetime, kind: str, months: list[date],
                        test: bool = False, out_dir: Path | None = None) -> Path:
    st = cfg["stay"]
    outs, rets = future_fares(snap, cfg.route_out, now), future_fares(snap, cfg.route_ret, now)
    d = out_dir or post_dir(cfg, now, kind)
    images, combos = [], {}
    for i, m in enumerate(months, 1):
        combo = best_combo(outs, rets, st["min_nights"], st["max_nights"], out_month=m,
                           same_month=st.get("calendar_combo_same_month", True))
        if combo:
            verify_combo(snap, combo, cfg, now)
            combos[m] = combo
        name = f"{i:02d}_kalender_{m.strftime('%Y-%m')}.png"
        render_month(cfg, m, snap, combo, now, test=test).save(d / name)
        images.append(name)
    links = {m.strftime("%Y-%m"): round_trip_link(cfg["route"]["origin"], cfg["route"]["destination"],
                                                  c.outbound.day, c.inbound.day) for m, c in combos.items()}
    _write(d, kind, calendar_text(cfg, snap, months, combos), images, {"links": links}, test)
    return d


def build_alert_post(cfg: Config, snap: Snapshot, alerts: list[Alert], history, now: datetime,
                     out_dir: Path | None = None) -> Path:
    test = any(a.test for a in alerts)
    if not test:
        for a in alerts:
            verify_combo(snap, a.combo, cfg, now) if a.combo else verify_fare(snap, a.fare, now)
    d = out_dir or post_dir(cfg, now, "angebot")
    for a in alerts:                      # Monatsdurchschnitt für den Preisvergleich
        if a.fare and "month_avg" not in a.ref:
            res = snap.month(a.fare.route, a.fare.day.replace(day=1))
            if res and res.ok and res.fares:
                a.ref["month_avg"] = round(sum(x.price for x in res.fares.values()) / len(res.fares), 2)
    images, links = [], []
    for i, a in enumerate(alerts[: cfg["alerts"]["max_items_per_alert_post"]], 1):
        ident = (f"{a.combo.outbound.day}_{a.combo.inbound.day}" if a.combo
                 else f"{a.fare.route.lower()}_{a.fare.day}")
        name = f"{i:02d}_{a.kind.lower()}_{ident}.png"
        render_alert(cfg, a, history, now, snap.fetched_at).save(d / name)
        images.append(name)
    for a in alerts:
        if a.combo:
            r = cfg["route"]
            links.append(round_trip_link(r["origin"], r["destination"], a.combo.outbound.day, a.combo.inbound.day))
        else:
            links.append(booking_link(a.fare.origin, a.fare.destination, a.fare.day))
    _write(d, "angebot", alerts_text(cfg, snap, alerts), images,
           {"angebote": [a.kind for a in alerts], "links": links}, test)
    return d


# ---------------------------------------------------------------- Top 3 ---------
MEDAL_EMOJI = ["🥇", "🥈", "🥉"]


def top3_text(cfg: Config, snap: Snapshot, months: list[date], combos: list) -> str:
    r = cfg["route"]
    names = " & ".join(month_name(m.year, m.month).split()[0] for m in months) + f" {months[-1].year}"
    if not combos:
        return f"🏆 Top 3 Kombinationen {r['origin_name']} ⇄ {r['destination_name']} ({names})\n\n{T['no_combo']}"
    cheapest = min(c.total for _, c in combos)
    parts = [f"🏆 Top 3 Kombinationen {r['origin_name']} ⇄ {r['destination_name']} – Abflug im {names}",
             f"Hin und zurück schon ab {fmt_price(cheapest)} pro Person 👇", ""]
    for i, (cat, c) in enumerate(combos):
        parts.append(f"{MEDAL_EMOJI[i]} {cat['label']} – {fmt_nights(c.nights)} in {r['destination_name']}")
        parts.append(f"🛫 {T['outbound']}: {fmt_date_wd(c.outbound.day)} · {c.outbound.departure} Uhr · {fmt_price(c.outbound.price)}")
        parts.append(f"🛬 {T['return']}: {fmt_date_wd(c.inbound.day)} · {c.inbound.departure} Uhr · {fmt_price(c.inbound.price)}")
        parts.append(f"💶 {T['total']}: {fmt_price(c.total)} pro Person")
        parts.append(f"🔗 {round_trip_link(r['origin'], r['destination'], c.outbound.day, c.inbound.day)}")
        parts.append("")
    parts.append("👉 Buchung nur über die offizielle Ryanair-Seite (Links oben).\n")
    parts.append(_footer_text(cfg, snap))
    return "\n".join(parts)


def build_top3_post(cfg: Config, snap: Snapshot, now: datetime, months: list[date] | None = None,
                    out_dir: Path | None = None) -> Path:
    t3 = cfg["top3"]
    months = months or calendar_months(now, t3["months"])
    combos = top_combos(future_fares(snap, cfg.route_out, now), future_fares(snap, cfg.route_ret, now),
                        t3["categories"], months)
    combos.sort(key=lambda x: (x[1].total, x[1].outbound.day))   # Medaillen nach Preis: 🥇 günstigste zuerst
    for _, c in combos:                                   # nur echte, aktuell bestätigte Preise
        verify_fare(snap, c.outbound, now)
        verify_fare(snap, c.inbound, now)
        if c.inbound.day <= c.outbound.day:
            raise VerificationError("Rückflug liegt nicht nach dem Hinflug")
    d = out_dir or post_dir(cfg, now, "top3")
    name = f"01_top3_{months[0].strftime('%Y-%m')}_{months[-1].strftime('%Y-%m')}.png"
    render_top3(cfg, combos, months, snap.fetched_at).save(d / name)
    links = [round_trip_link(cfg["route"]["origin"], cfg["route"]["destination"], c.outbound.day, c.inbound.day)
             for _, c in combos]
    _write(d, "top3", top3_text(cfg, snap, months, combos), [name],
           {"kombinationen": [{"kategorie": cat["label"], "hin": str(c.outbound.day), "rueck": str(c.inbound.day),
                               "gesamt": c.total} for cat, c in combos], "links": links}, False)
    return d
