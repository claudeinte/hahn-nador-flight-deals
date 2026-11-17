"""Preisabfrage bei Ryanair (Tagestiefstpreise je Monat und Strecke).

Hinweis: Ryanair bietet keine offizielle öffentliche Preis-API an. Dieses Modul nutzt
den Endpunkt, den auch ryanair.com für den Preiskalender verwendet. Laut robots.txt ist
/api für automatische Zugriffe nicht freigegeben – siehe README ("Datenquelle und Risiko").
Um den Server zu schonen: wenige Anfragen, Pause zwischen den Anfragen, Wiederholungen
mit Wartezeit.
"""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from datetime import date, datetime

from .config import Config
from .models import Fare, MonthResult, Snapshot

log = logging.getLogger(__name__)

URL = ("https://www.ryanair.com/api/farfnd/v4/oneWayFares/{o}/{d}/cheapestPerDay"
       "?outboundMonthOfDate={m}&currency={c}")
USER_AGENT = "Mozilla/5.0 (compatible; hahn-nador-flight-deals/1.0)"


def _ssl_context():
    try:
        import certifi  # lokal auf macOS fehlen sonst oft Zertifikate
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def months_to_fetch(today: date, count: int) -> list[date]:
    first = today.replace(day=1)
    return [add_months(first, i) for i in range(count)]


def _download(url: str, cfg: Config) -> dict:
    f = cfg["fetch"]
    last = None
    for attempt in range(1, f["retries"] + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=f["timeout_seconds"], context=_ssl_context()) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError) as e:
            last = e
            log.warning("Abfrage fehlgeschlagen (Versuch %s/%s): %s", attempt, f["retries"], e)
            if attempt < f["retries"]:
                time.sleep(f["retry_backoff_seconds"] * attempt)
    raise RuntimeError(f"Abfrage nach {f['retries']} Versuchen fehlgeschlagen: {last}")


def parse_month(data: dict, route: str, month: date, cfg: Config) -> MonthResult:
    """Wandelt die Antwort in Fares um und prüft jeden Preis auf Plausibilität."""
    f = cfg["fetch"]
    currency = cfg["route"]["currency"]
    res = MonthResult(route=route, month=month, ok=True)
    fares = (data.get("outbound") or {}).get("fares")
    if not isinstance(fares, list):
        raise ValueError("Unerwartetes Antwortformat (outbound.fares fehlt)")
    for item in fares:
        day = date.fromisoformat(item["day"])
        if (day.year, day.month) != (month.year, month.month):
            continue
        price = item.get("price")
        if not price or item.get("unavailable") or item.get("soldOut"):
            res.no_flight_days.add(day)
            continue
        if price.get("currencyCode") != currency:
            raise ValueError(f"Falsche Währung: {price.get('currencyCode')}")
        value = float(price["value"])
        if not (f["min_valid_price"] <= value <= f["max_valid_price"]):
            raise ValueError(f"Unplausibler Preis {value} am {day}")
        dep, arr = item.get("departureDate") or "", item.get("arrivalDate") or ""
        res.fares[day] = Fare(route=route, day=day, price=round(value, 2), departure=dep[11:16], arrival=arr[11:16])
    return res


def fetch_month(route: str, month: date, cfg: Config) -> MonthResult:
    o, d = route.split("-")
    url = URL.format(o=o, d=d, m=month.isoformat(), c=cfg["route"]["currency"])
    try:
        return parse_month(_download(url, cfg), route, month, cfg)
    except Exception as e:  # Fehler werden markiert, alte Preise werden NICHT verwendet
        log.error("%s %s: %s", route, month.strftime("%Y-%m"), e)
        return MonthResult(route=route, month=month, ok=False, error=str(e))


def fetch_all(cfg: Config, now: datetime, fetcher=fetch_month) -> Snapshot:
    snap = Snapshot(fetched_at=now)
    months = months_to_fetch(now.date(), cfg["route"]["months_ahead"])
    first = True
    for route in (cfg.route_out, cfg.route_ret):
        for m in months:
            if not first and fetcher is fetch_month:
                time.sleep(cfg["fetch"]["request_delay_seconds"])
            first = False
            snap.months[(route, m)] = fetcher(route, m, cfg)
    return snap
