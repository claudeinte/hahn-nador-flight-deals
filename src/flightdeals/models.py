"""Datenmodelle."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class Fare:
    route: str            # "HHN-NDR"
    day: date
    price: float          # EUR, pro Person, Basic-Tarif
    departure: str        # "06:10"
    arrival: str          # "08:15"

    @property
    def origin(self) -> str:
        return self.route.split("-")[0]

    @property
    def destination(self) -> str:
        return self.route.split("-")[1]

    @property
    def key(self) -> str:
        return f"{self.route}|{self.day.isoformat()}"


@dataclass
class MonthResult:
    route: str
    month: date                       # erster Tag des Monats
    ok: bool
    fares: dict = field(default_factory=dict)   # date -> Fare (nur Tage mit Flug)
    no_flight_days: set = field(default_factory=set)
    error: str = ""


@dataclass
class Snapshot:
    fetched_at: datetime
    months: dict = field(default_factory=dict)  # (route, month) -> MonthResult

    def month(self, route: str, month: date) -> MonthResult | None:
        return self.months.get((route, month))

    def fares(self, route: str | None = None) -> list[Fare]:
        out = []
        for (r, _), res in self.months.items():
            if res.ok and (route is None or r == route):
                out.extend(res.fares.values())
        return sorted(out, key=lambda f: (f.route, f.day))

    @property
    def any_ok(self) -> bool:
        return any(m.ok for m in self.months.values())

    @property
    def errors(self) -> list[MonthResult]:
        return [m for m in self.months.values() if not m.ok]


@dataclass
class Combo:
    outbound: Fare
    inbound: Fare

    @property
    def nights(self) -> int:
        return (self.inbound.day - self.outbound.day).days

    @property
    def total(self) -> float:
        return round(self.outbound.price + self.inbound.price, 2)

    @property
    def key(self) -> str:
        return f"COMBO|{self.outbound.day}|{self.inbound.day}"


@dataclass
class Alert:
    kind: str                 # PREISSTURZ, TOP_ANGEBOT, GUENSTIGER_HIN_RUECK, NEUER_TIEFSTPREIS, LAST_MINUTE
    fare: Fare | None = None
    combo: Combo | None = None
    old_price: float | None = None
    also: list = field(default_factory=list)   # weitere erfüllte Bedingungen
    ref: dict = field(default_factory=dict)    # Zusatzinfos, z. B. bisheriger Monats-Tiefstpreis
    test: bool = False

    @property
    def new_price(self) -> float:
        return self.combo.total if self.combo else self.fare.price

    @property
    def saving(self) -> float | None:
        if self.old_price is None:
            return None
        return round(self.old_price - self.new_price, 2)

    @property
    def saving_pct(self) -> float | None:
        if not self.old_price:
            return None
        return (self.old_price - self.new_price) / self.old_price * 100

    @property
    def dedupe_key(self) -> str:
        """Gleicher Flug + gleicher Preis = keine erneute Meldung."""
        if self.combo:
            return f"{self.combo.key}|{self.combo.total:.2f}"
        return f"{self.fare.key}|{self.fare.price:.2f}"
