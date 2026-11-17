import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flightdeals.config import load_config  # noqa: E402
from flightdeals.models import Fare, MonthResult, Snapshot  # noqa: E402

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHTDEALS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FLIGHTDEALS_OUTPUT_DIR", str(tmp_path / "output"))
    for k in ("FACEBOOK_AUTOPUBLISH", "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(k, raising=False)
    return load_config(ROOT / "config.toml")


def berlin(*args) -> datetime:
    return datetime(*args, tzinfo=BERLIN)


def make_snapshot(now: datetime, prices: dict, failed: set = frozenset(), months=6) -> Snapshot:
    """prices: {("HHN-NDR", date): price}. Alle anderen Tage = kein Flug."""
    from flightdeals.fetch import months_to_fetch
    snap = Snapshot(fetched_at=now)
    for route in ("HHN-NDR", "NDR-HHN"):
        for m in months_to_fetch(now.date(), months):
            if (route, m) in failed:
                snap.months[(route, m)] = MonthResult(route=route, month=m, ok=False, error="Testfehler")
                continue
            res = MonthResult(route=route, month=m, ok=True)
            d = m
            while d.month == m.month:
                p = prices.get((route, d))
                if p is None:
                    res.no_flight_days.add(d)
                else:
                    res.fares[d] = Fare(route=route, day=d, price=p, departure="10:00", arrival="12:05")
                d = date.fromordinal(d.toordinal() + 1)
            snap.months[(route, m)] = res
    return snap
