"""Auswertung: verfügbare zukünftige Flüge und günstigste Hin- und Rückflug-Kombination."""
from __future__ import annotations

from datetime import date, datetime, time

from .models import Combo, Fare, Snapshot


def departure_dt(fare: Fare, tz) -> datetime:
    hh, mm = (fare.departure or "00:00").split(":")
    return datetime.combine(fare.day, time(int(hh), int(mm)), tzinfo=tz)


def future_fares(snap: Snapshot, route: str, now: datetime) -> list[Fare]:
    """Nur echte, aktuell abgefragte Flüge, deren Abflug noch in der Zukunft liegt."""
    return [f for f in snap.fares(route) if departure_dt(f, now.tzinfo) > now]


def best_combo(outs: list[Fare], rets: list[Fare], min_nights: int, max_nights: int,
               out_month: date | None = None, same_month: bool = False) -> Combo | None:
    """Günstigste Kombination. Der Rückflug darf im Folgemonat liegen.
    Rückflug muss nach dem Hinflug sein (mindestens min_nights Nächte)."""
    best = None
    min_nights = max(1, min_nights)
    for o in outs:
        if out_month and (o.day.year, o.day.month) != (out_month.year, out_month.month):
            continue
        for r in rets:
            if same_month and (r.day.year, r.day.month) != (o.day.year, o.day.month):
                continue
            nights = (r.day - o.day).days
            if nights < min_nights or nights > max_nights:
                continue
            c = Combo(outbound=o, inbound=r)
            if best is None or (c.total, o.day, r.day) < (best.total, best.outbound.day, best.inbound.day):
                best = c
    return best


def top_combos(outs: list[Fare], rets: list[Fare], categories: list[dict],
               out_months: list[date]) -> list[tuple[dict, Combo]]:
    """Beste Kombination je Kategorie (z. B. günstigste, Kurztrip, Familienbesuch).
    Hinflug in einem der out_months; keine Kombination wird zweimal verwendet."""
    allowed = {(m.year, m.month) for m in out_months}
    outs = [o for o in outs if (o.day.year, o.day.month) in allowed]
    used: set = set()
    result = []
    for cat in categories:
        best = None
        for o in outs:
            for r in rets:
                nights = (r.day - o.day).days
                if nights < max(1, cat["min_nights"]) or nights > cat["max_nights"]:
                    continue
                if (o.day, r.day) in used:
                    continue
                c = Combo(outbound=o, inbound=r)
                if best is None or (c.total, o.day, r.day) < (best.total, best.outbound.day, best.inbound.day):
                    best = c
        if best:
            used.add((best.outbound.day, best.inbound.day))
            result.append((cat, best))
    return result
