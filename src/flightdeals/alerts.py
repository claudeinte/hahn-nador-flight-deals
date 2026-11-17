"""Erkennung der Angebote.

Muss VOR History.record() aufgerufen werden, weil mit den bisher gespeicherten Preisen
verglichen wird.

Regeln (Schwellenwerte in config.toml):
  PREISSTURZ          Preis fällt um mindestens X € UND mindestens Y %.
  TOP_ANGEBOT         Neuer Flug (vorher unbekannt oder nicht verfügbar) unter X €.
  NEUER_TIEFSTPREIS   Niedriger als der bisher niedrigste Preis dieses Monats (Verlauf nötig).
  LAST_MINUTE         Abflug in den nächsten N Tagen und unter X €.
  GUENSTIGER_HIN_RUECK  Günstigste Kombination unter X €.

Ein Flug erzeugt höchstens EINE Meldung (Priorität laut config); weitere erfüllte
Bedingungen werden in Alert.also vermerkt. Gleicher Flug + gleicher Preis wird nie zweimal
gemeldet.
"""
from __future__ import annotations

from datetime import datetime

from .analysis import best_combo, departure_dt, future_fares
from .config import Config
from .models import Alert, Snapshot
from .storage import History, State


def detect(snap: Snapshot, history: History, state: State, cfg: Config, now: datetime) -> list[Alert]:
    a = cfg["alerts"]
    if history.is_empty:
        return []   # erster Lauf: nur Basis speichern, keine Flut an "neuen" Flügen melden

    alerts: list[Alert] = []
    for route in (cfg.route_out, cfg.route_ret):
        for fare in future_fares(snap, route, now):
            prev = history.last_price(fare.key)
            new = fare.price
            kinds = []

            if prev is not None and prev - new >= a["price_drop_min_eur"] \
                    and (prev - new) / prev * 100 >= a["price_drop_min_pct"]:
                kinds.append("PREISSTURZ")

            mm = history.monthly_min(route, fare.day.replace(day=1))
            if mm is not None and new < mm["p"] - 0.005:
                kinds.append("NEUER_TIEFSTPREIS")

            days_left = (departure_dt(fare, now.tzinfo) - now).total_seconds() / 86400
            if 0 <= days_left <= a["last_minute_days"] and new < a["last_minute_below"]:
                kinds.append("LAST_MINUTE")

            is_new = (not history.known(fare.key)) or prev is None
            if is_new and new < a["top_offer_below"]:
                kinds.append("TOP_ANGEBOT")

            if not kinds:
                continue
            kinds.sort(key=lambda k: a["priority"].index(k))
            alert = Alert(kind=kinds[0], fare=fare, also=kinds[1:],
                          old_price=prev if (prev is not None and prev > new) else None)
            if mm is not None:
                alert.ref["month_min"] = mm["p"]
            alert.ref["days_left"] = max(0, int(days_left))
            if not state.was_alerted(alert.dedupe_key):
                alerts.append(alert)

    st = cfg["stay"]
    combo = best_combo(future_fares(snap, cfg.route_out, now), future_fares(snap, cfg.route_ret, now),
                       st["min_nights"], st["max_nights"])
    if combo and combo.total < a["cheap_round_trip_below"]:
        alert = Alert(kind="GUENSTIGER_HIN_RUECK", combo=combo)
        if not state.was_alerted(alert.dedupe_key):
            alerts.append(alert)

    order = a["priority"] + ["GUENSTIGER_HIN_RUECK"]
    alerts.sort(key=lambda x: (order.index(x.kind), -(x.saving or 0), x.new_price))
    return alerts


def baseline_keys(snap: Snapshot, cfg: Config, now: datetime) -> list[str]:
    """Beim ersten Lauf: aktuelle günstigste Kombination als 'schon gesehen' markieren,
    damit sie beim nächsten Lauf nicht fälschlich als neu gemeldet wird."""
    st = cfg["stay"]
    combo = best_combo(future_fares(snap, cfg.route_out, now), future_fares(snap, cfg.route_ret, now),
                       st["min_nights"], st["max_nights"])
    return [Alert(kind="GUENSTIGER_HIN_RUECK", combo=combo).dedupe_key] if combo else []
