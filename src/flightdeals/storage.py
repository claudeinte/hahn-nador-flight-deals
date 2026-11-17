"""Persistente Daten: Preisverlauf je Flug, Monats-Tiefstpreise und Status der Beiträge.

Die Dateien liegen in data/ und werden von GitHub Actions nach jedem Lauf zurück ins
Repository geschrieben, damit der Verlauf zwischen den Läufen erhalten bleibt.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .models import Snapshot


def _load(path: Path, default: dict) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return json.loads(json.dumps(default))


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    tmp.replace(path)


class History:
    """flights:      "HHN-NDR|2026-12-12" -> [{"t": iso, "p": 39.91 | null}, …]  (nur bei Änderung)
       monthly_min:  "HHN-NDR|2026-12"    -> {"p": 19.99, "day": "2026-12-08", "t": iso}"""

    def __init__(self, path: Path):
        self.path = path
        self.data = _load(path, {"flights": {}, "monthly_min": {}})

    def save(self):
        _save(self.path, self.data)

    @property
    def is_empty(self) -> bool:
        return not self.data["flights"]

    def series(self, key: str) -> list[dict]:
        return self.data["flights"].get(key, [])

    def last_price(self, key: str) -> float | None:
        s = self.series(key)
        return s[-1]["p"] if s else None

    def known(self, key: str) -> bool:
        return key in self.data["flights"]

    def monthly_min(self, route: str, month: date) -> dict | None:
        return self.data["monthly_min"].get(f"{route}|{month.strftime('%Y-%m')}")

    def record(self, snap: Snapshot) -> None:
        """Speichert neue Preise. Nur Monate mit erfolgreicher Abfrage werden verändert."""
        t = snap.fetched_at.isoformat(timespec="seconds")
        for (route, month), res in snap.months.items():
            if not res.ok:
                continue
            for fare in res.fares.values():
                s = self.data["flights"].setdefault(fare.key, [])
                if not s or s[-1]["p"] != fare.price:
                    s.append({"t": t, "p": fare.price})
                mk = f"{route}|{month.strftime('%Y-%m')}"
                cur = self.data["monthly_min"].get(mk)
                if cur is None or fare.price < cur["p"]:
                    self.data["monthly_min"][mk] = {"p": fare.price, "day": fare.day.isoformat(), "t": t}
            for day in res.no_flight_days:
                key = f"{route}|{day.isoformat()}"
                s = self.data["flights"].get(key)
                if s and s[-1]["p"] is not None:
                    s.append({"t": t, "p": None})     # Flug nicht mehr verfügbar / ausverkauft


class State:
    """alerted: dedupe_key -> iso  ·  posts: "YYYY-MM-DD" -> {"daily": bool, "extra": int}"""

    def __init__(self, path: Path):
        self.path = path
        self.data = _load(path, {"alerted": {}, "posts": {}, "last_update": None})

    def save(self):
        _save(self.path, self.data)

    def was_alerted(self, key: str) -> bool:
        return key in self.data["alerted"]

    def mark_alerted(self, key: str, when: datetime) -> None:
        self.data["alerted"][key] = when.isoformat(timespec="seconds")

    def day(self, d: date) -> dict:
        return self.data["posts"].setdefault(d.isoformat(), {"daily": False, "extra": 0})

    def prune(self, today: date, keep_days: int = 60) -> None:
        """Alte Einträge entfernen, damit die Dateien klein bleiben."""
        limit = today.toordinal() - keep_days
        self.data["posts"] = {k: v for k, v in self.data["posts"].items()
                              if date.fromisoformat(k).toordinal() >= limit}
        self.data["alerted"] = {k: v for k, v in self.data["alerted"].items()
                                if datetime.fromisoformat(v).date().toordinal() >= limit}
