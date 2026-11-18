"""Befehlszeile.

  python -m flightdeals run                 Preise abfragen, Verlauf speichern, Angebote erkennen,
                                            fällige Beiträge erstellen (täglich 08:00 / sonntags 6 Monate)
  python -m flightdeals run --force daily   Tagesbeitrag sofort erstellen (zum Testen)
  python -m flightdeals run --force weekly  Wochenbeitrag (6 Monate) sofort erstellen
  python -m flightdeals demo                Echte Kalender (aktueller + nächster Monat) und je ein
                                            Beispielbild für jede Angebotsart (TESTDATEN)
  python -m flightdeals top3                Beitrag "Top 3 Kombinationen" (aktueller + nächster Monat)
  python -m flightdeals publish <ordner>    Einen vorbereiteten Beitrag veröffentlichen (nur wenn freigegeben)
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from .alerts import baseline_keys, detect
from .analysis import best_combo, future_fares
from .config import load_config
from .facebook import publish, publishing_enabled
from .fetch import fetch_all
from .models import Alert
from .posts import build_alert_post, build_calendar_post, build_top3_post, calendar_months
from .storage import History, State
from .summary import write_summary

log = logging.getLogger("flightdeals")


def cmd_run(cfg, force: str | None) -> int:
    now = cfg.now()
    today = now.date()
    history = History(cfg.data_dir / "history.json")
    state = State(cfg.data_dir / "state.json")
    notes, posts = [], []

    snap = fetch_all(cfg, now)
    if not snap.any_ok:
        notes.append("Alle Preisabfragen sind fehlgeschlagen. Es wird nichts erstellt (keine alten Preise).")
        write_summary(cfg, now, snap, [], [], notes)
        return 1
    if snap.errors:
        notes.append(f"{len(snap.errors)} Monatsabfrage(n) fehlgeschlagen – diese Tage erscheinen mit ? und "
                     "werden nicht für Angebote verwendet.")

    alerts = detect(snap, history, state, cfg, now)       # Vergleich mit dem bisherigen Verlauf …
    if history.is_empty:
        notes.append("Erster Lauf: Preise als Basis gespeichert, noch keine Angebotsmeldungen.")
        for key in baseline_keys(snap, cfg, now):
            state.mark_alerted(key, now)
    history.record(snap)                                   # … danach neue Preise speichern

    day = state.day(today)
    sch = cfg["schedule"]
    due = force in ("daily", "weekly") or (now.hour >= sch["daily_post_hour"] and not day["daily"])
    if due:
        weekly = force == "weekly" or (force is None and today.weekday() == sch["weekly_post_weekday"])
        months = calendar_months(now, sch["weekly_months"] if weekly else sch["daily_months"])
        posts.append(build_calendar_post(cfg, snap, now, "woechentlich" if weekly else "taeglich", months))
        day["daily"] = True

    if alerts:
        if day["extra"] < cfg["alerts"]["max_extra_posts_per_day"]:
            posts.append(build_alert_post(cfg, snap, alerts, history, now))
            day["extra"] += 1
            for a in alerts:
                state.mark_alerted(a.dedupe_key, now)
        else:
            notes.append("Tageslimit für zusätzliche Beiträge erreicht – Angebote werden später erneut geprüft.")

    enabled, reason = publishing_enabled(cfg)
    for d in posts:
        res = publish(d, cfg) if enabled else {"veroeffentlicht": False, "grund": reason}
        log.info("Beitrag %s – Facebook: %s", d.name, res)
    if not enabled:
        notes.append(f"Facebook-Veröffentlichung deaktiviert ({reason}). Beiträge liegen nur im Ausgabeordner.")

    state.data["last_update"] = now.isoformat(timespec="seconds")
    state.prune(today)
    history.save()
    state.save()
    print(write_summary(cfg, now, snap, alerts, posts, notes))
    return 0


def _synthetic_history(path: Path, now, series: dict) -> History:
    h = History(path)
    for key, prices in series.items():
        n = len(prices)
        h.data["flights"][key] = [{"t": (now - timedelta(days=(n - i) * 2)).isoformat(timespec="seconds"), "p": p}
                                  for i, p in enumerate(prices)]
    return h


def cmd_demo(cfg) -> int:
    """Echte Kalender + je ein klar gekennzeichnetes Testbild pro Angebotsart."""
    now = cfg.now()
    base = cfg.output_dir / "demo" / now.strftime("%Y-%m-%d_%H%M")
    snap = fetch_all(cfg, now)
    if not snap.any_ok:
        print("Preisabfrage fehlgeschlagen – keine Demo möglich.")
        return 1
    cal = build_calendar_post(cfg, snap, now, "taeglich", calendar_months(now, 2), out_dir=base / "kalender")
    print("Kalender (echte Preise):", cal)

    outs, rets = future_fares(snap, cfg.route_out, now), future_fares(snap, cfg.route_ret, now)
    if len(outs) < 4 or not rets:
        print("Zu wenige Flüge für Beispielangebote.")
        return 0
    soon = [f for f in outs + rets if (f.day - now.date()).days <= cfg["alerts"]["last_minute_days"]]
    rep = dataclasses.replace
    f_drop = rep(outs[3], price=22.99)
    f_top = rep(outs[min(6, len(outs) - 1)], price=24.99)
    f_low = rep(outs[min(9, len(outs) - 1)], price=17.99)
    f_last = rep(soon[0] if soon else outs[0], price=21.99)
    st = cfg["stay"]
    combo = best_combo(outs, rets, st["min_nights"], st["max_nights"])
    combo = rep(combo, outbound=rep(combo.outbound, price=19.99), inbound=rep(combo.inbound, price=21.99))

    tmp = Path(tempfile.mkdtemp()) / "history.json"
    hist = _synthetic_history(tmp, now, {
        f_drop.key: [49.99, 54.99, 44.99, 39.99, 22.99],
        f_top.key: [24.99],
        f_low.key: [29.99, 26.99, 24.99, 21.99, 17.99],
        f_last.key: [34.99, 39.99, 29.99, 21.99],
        combo.outbound.key: [34.99, 29.99, 19.99],
        combo.inbound.key: [39.99, 26.99, 21.99],
    })
    days_left = max(0, (f_last.day - now.date()).days)
    examples = [
        Alert("PREISSTURZ", fare=f_drop, old_price=39.99, test=True),
        Alert("TOP_ANGEBOT", fare=f_top, test=True),
        Alert("GUENSTIGER_HIN_RUECK", combo=combo, test=True),
        Alert("NEUER_TIEFSTPREIS", fare=f_low, old_price=21.99, ref={"month_min": 21.99}, test=True),
        Alert("LAST_MINUTE", fare=f_last, old_price=29.99, also=["PREISSTURZ"], ref={"days_left": days_left}, test=True),
    ]
    for a in examples:
        d = build_alert_post(cfg, snap, [a], hist, now, out_dir=base / "angebote" / a.kind.lower())
        print("Beispiel (TESTDATEN):", d)
    print("\nAlle Demo-Dateien:", base)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="flightdeals", description="Frankfurt-Hahn – Nador | Günstige Flüge finden")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--force", choices=["daily", "weekly"], default=None)
    sub.add_parser("demo")
    sub.add_parser("top3")
    pb = sub.add_parser("publish")
    pb.add_argument("post_dir", type=Path)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.cmd == "run":
        return cmd_run(cfg, args.force)
    if args.cmd == "demo":
        return cmd_demo(cfg)
    if args.cmd == "top3":
        now = cfg.now()
        snap = fetch_all(cfg, now)
        if not snap.any_ok:
            print("Preisabfrage fehlgeschlagen – nichts erstellt.")
            return 1
        print("Top 3:", build_top3_post(cfg, snap, now))
        return 0
    if args.cmd == "publish":
        print(publish(args.post_dir, cfg))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
