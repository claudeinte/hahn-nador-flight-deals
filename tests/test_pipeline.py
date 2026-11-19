import json
from datetime import date

import pytest
from PIL import Image

import flightdeals.cli as cli
from conftest import berlin, make_snapshot
from flightdeals.facebook import publish, publishing_enabled
from flightdeals.models import Fare
from flightdeals.posts import VerificationError, build_calendar_post, verify_fare

PRICES = {("HHN-NDR", date(2026, 12, 6)): 19.99, ("NDR-HHN", date(2026, 12, 15)): 18.99,
          ("HHN-NDR", date(2027, 1, 8)): 59.99, ("NDR-HHN", date(2027, 1, 20)): 120.0,
          ("HHN-NDR", date(2026, 11, 28)): 210.0}


def _run_at(cfg, monkeypatch, now, prices=PRICES, failed=frozenset(), force=None):
    monkeypatch.setenv("FLIGHTDEALS_NOW", now.isoformat())
    monkeypatch.setattr(cli, "fetch_all", lambda c, n: make_snapshot(n, prices, failed))
    return cli.cmd_run(cfg, force)


def _posts(cfg):
    return sorted(p.parent for p in cfg.output_dir.rglob("beitrag.json"))


def test_calendar_images_are_1080x1350_and_german(cfg):
    now = berlin(2026, 11, 20, 8, 5)
    d = build_calendar_post(cfg, make_snapshot(now, PRICES), now, "taeglich", [date(2026, 11, 1), date(2026, 12, 1)])
    imgs = sorted(d.glob("*.png"))
    assert [i.name for i in imgs] == ["01_kalender_2026-11.png", "02_kalender_2026-12.png"]
    for i in imgs:
        assert Image.open(i).size == (1080, 1350)
    text = (d / "beitrag.txt").read_text()
    lines = text.splitlines()
    assert lines[0] == "🗞️ Flug-News · Freitag, 20.11.2026"
    assert lines[1].startswith("📅 November 2026 & Dezember 2026: 🇩🇪 Frankfurt-Hahn ✈️ 🇲🇦 Nador")
    assert lines[2] == "🕒 Preise geprüft am 20.11.2026 um 08:05 Uhr – können sich jederzeit ändern."
    assert "Günstigster Hin- und Rückflug" in text and "38,98 €" in text
    assert "Keine Verbindung zu Ryanair" in text and "ryanair.com/de/de" in text
    assert "Basic-Tarif" in text


def test_daily_post_at_8_berlin_once_per_day(cfg, monkeypatch):
    assert _run_at(cfg, monkeypatch, berlin(2026, 11, 20, 7, 30)) == 0     # vor 08:00 → nichts
    assert _posts(cfg) == []
    _run_at(cfg, monkeypatch, berlin(2026, 11, 20, 8, 10))                  # Freitag 08:10 → 2 Monate
    posts = _posts(cfg)
    assert len(posts) == 1 and len(list(posts[0].glob("*.png"))) == 2
    _run_at(cfg, monkeypatch, berlin(2026, 11, 20, 14, 0))                  # gleicher Tag → nicht nochmal
    assert len(_posts(cfg)) == 1


def test_sunday_post_has_six_months(cfg, monkeypatch):
    _run_at(cfg, monkeypatch, berlin(2026, 11, 22, 8, 1))                   # Sonntag
    posts = _posts(cfg)
    assert len(posts) == 1 and "wochen-kalender" in posts[0].name
    assert len(list(posts[0].glob("*.png"))) == 6


def test_summer_time_handled(cfg, monkeypatch):
    # 06:05 UTC im Juli = 08:05 Berlin (Sommerzeit) → Tagesbeitrag fällig
    from datetime import datetime, timezone
    now = datetime(2027, 7, 14, 6, 5, tzinfo=timezone.utc).astimezone(berlin(2027, 1, 1).tzinfo)
    assert now.hour == 8
    _run_at(cfg, monkeypatch, now, prices={("HHN-NDR", date(2027, 7, 20)): 49.0})
    assert len(_posts(cfg)) == 1


def test_all_fetches_failed_creates_nothing(cfg, monkeypatch):
    from flightdeals.fetch import months_to_fetch
    now = berlin(2026, 11, 20, 8, 30)
    failed = {(r, m) for r in ("HHN-NDR", "NDR-HHN") for m in months_to_fetch(now.date(), 6)}
    assert _run_at(cfg, monkeypatch, now, failed=failed) == 1
    assert _posts(cfg) == []


def test_alert_posts_limited_to_three_per_day(cfg, monkeypatch):
    _run_at(cfg, monkeypatch, berlin(2026, 11, 20, 1, 0))                   # Basislauf (Nacht)
    for i, h in enumerate((3, 4, 5, 6)):                                     # vier neue Top-Angebote
        prices = {**PRICES, ("HHN-NDR", date(2027, 2, 1 + i)): 20.0 + i}
        _run_at(cfg, monkeypatch, berlin(2026, 11, 20, h, 0), prices=prices)
    alert_posts = [p for p in _posts(cfg) if "angebote" in p.name]
    assert len(alert_posts) == 3


def test_verify_rejects_stale_or_wrong_prices(cfg):
    now = berlin(2026, 11, 20, 9)
    snap = make_snapshot(now, PRICES, failed={("HHN-NDR", date(2027, 1, 1))})
    good = snap.month("HHN-NDR", date(2026, 12, 1)).fares[date(2026, 12, 6)]
    verify_fare(snap, good, now)
    with pytest.raises(VerificationError):
        verify_fare(snap, Fare("HHN-NDR", date(2026, 12, 6), 9.99, "10:00", "12:00"), now)   # falscher Preis
    with pytest.raises(VerificationError):
        verify_fare(snap, Fare("HHN-NDR", date(2027, 1, 8), 59.99, "10:00", "12:00"), now)  # Monat fehlgeschlagen


def test_facebook_disabled_by_default(cfg, monkeypatch, tmp_path):
    ok, reason = publishing_enabled(cfg)
    assert not ok and "autopublish" in reason
    monkeypatch.setenv("FACEBOOK_AUTOPUBLISH", "true")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "1")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "x")
    assert not publishing_enabled(cfg)[0]                                   # config bleibt AUS
    cfg.raw["facebook"]["autopublish"] = True
    assert publishing_enabled(cfg)[0]
    d = tmp_path / "post"
    d.mkdir()
    (d / "beitrag.json").write_text(json.dumps({"bilder": [], "testdaten": True}))
    assert publish(d, cfg)["veroeffentlicht"] is False                     # Testdaten nie veröffentlichen


def test_tiefstpreis_photo_style_both_directions(cfg, tmp_path):
    from flightdeals.models import Alert
    from flightdeals.render.alert import render_alert
    now = berlin(2026, 11, 19, 1, 52)
    for route, day in (("HHN-NDR", date(2027, 1, 10)), ("NDR-HHN", date(2026, 12, 18))):
        a = Alert("NEUER_TIEFSTPREIS", fare=Fare(route, day, 16.99, "06:40", "08:45"), old_price=23.99)
        img = render_alert(cfg, a, None, now, now).img
        assert img.size == (1080, 1350)
        assert img.getpixel((540, 300)) != (13, 17, 23)        # Foto im Hintergrund sichtbar
    other = Alert("PREISSTURZ", fare=Fare("HHN-NDR", date(2026, 12, 4), 24.99, "18:20", "20:25"), old_price=34.99)
    from flightdeals.storage import History
    img2 = render_alert(cfg, other, History(tmp_path / "h.json"), now, now).img
    assert img2.getpixel((1070, 700)) == (13, 17, 23)           # andere Typen: unverändert ohne Foto
