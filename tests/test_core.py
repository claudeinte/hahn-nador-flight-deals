from datetime import date

import pytest

from conftest import berlin, make_snapshot
from flightdeals.alerts import detect
from flightdeals.analysis import best_combo, future_fares
from flightdeals.fetch import parse_month
from flightdeals.storage import History, State
from flightdeals.texts import fmt_date, fmt_date_wd, fmt_price, month_name


# ------------------------------------------------------------------ Formate ----
def test_price_format():
    assert fmt_price(29.99) == "29,99 €"
    assert fmt_price(5) == "5,00 €"
    assert fmt_price(1234.5) == "1.234,50 €"


def test_date_format_and_german_names():
    assert fmt_date(date(2026, 12, 6)) == "06.12.2026"
    assert fmt_date_wd(date(2026, 12, 6)) == "So, 06.12.2026"
    assert month_name(2026, 3) == "März 2026"


# ------------------------------------------------------------------ Abfrage ----
def _api(items):
    return {"outbound": {"fares": items}}


def _item(day, value, cur="EUR"):
    return {"day": day, "price": {"value": value, "currencyCode": cur},
            "departureDate": f"{day}T06:10:00", "arrivalDate": f"{day}T08:15:00"}


def test_parse_month_ok(cfg):
    res = parse_month(_api([_item("2026-12-01", 19.99),
                            {"day": "2026-12-02", "price": None, "unavailable": True}]),
                      "HHN-NDR", date(2026, 12, 1), cfg)
    assert res.ok and res.fares[date(2026, 12, 1)].price == 19.99
    assert res.fares[date(2026, 12, 1)].departure == "06:10"
    assert date(2026, 12, 2) in res.no_flight_days


@pytest.mark.parametrize("item", [_item("2026-12-01", 19.99, "GBP"), _item("2026-12-01", 0.5),
                                  _item("2026-12-01", 99999)])
def test_parse_month_rejects_wrong_data(cfg, item):
    with pytest.raises(ValueError):
        parse_month(_api([item]), "HHN-NDR", date(2026, 12, 1), cfg)


# ------------------------------------------------------------- Kombination -----
def test_best_combo_return_after_outbound_and_next_month(cfg):
    now = berlin(2026, 11, 20, 9, 0)
    snap = make_snapshot(now, {("HHN-NDR", date(2026, 11, 28)): 20.0,
                               ("NDR-HHN", date(2026, 11, 25)): 5.5,     # vor dem Hinflug → ungültig
                               ("NDR-HHN", date(2026, 12, 5)): 25.0})    # Folgemonat → gültig
    c = best_combo(future_fares(snap, "HHN-NDR", now), future_fares(snap, "NDR-HHN", now), 3, 30,
                   out_month=date(2026, 11, 1))
    assert c.inbound.day == date(2026, 12, 5)
    assert c.nights == 7 and c.total == 45.0


def test_best_combo_respects_min_max_nights(cfg):
    now = berlin(2026, 11, 1, 9, 0)
    snap = make_snapshot(now, {("HHN-NDR", date(2026, 11, 10)): 20.0,
                               ("NDR-HHN", date(2026, 11, 11)): 10.0,    # 1 Nacht (< 3)
                               ("NDR-HHN", date(2026, 12, 30)): 10.0,    # 50 Nächte (> 30)
                               ("NDR-HHN", date(2026, 11, 20)): 30.0})
    c = best_combo(future_fares(snap, "HHN-NDR", now), future_fares(snap, "NDR-HHN", now), 3, 30)
    assert c.inbound.day == date(2026, 11, 20)


def test_past_flights_excluded(cfg):
    now = berlin(2026, 11, 20, 12, 0)
    snap = make_snapshot(now, {("HHN-NDR", date(2026, 11, 20)): 9.99,   # heute 10:00 → schon weg
                               ("HHN-NDR", date(2026, 11, 21)): 30.0})
    assert [f.day for f in future_fares(snap, "HHN-NDR", now)] == [date(2026, 11, 21)]


# ------------------------------------------------------------------ Verlauf ----
def test_history_records_only_changes_and_ignores_failed_months(cfg, tmp_path):
    h = History(tmp_path / "h.json")
    now = berlin(2026, 11, 20, 9, 0)
    d = date(2026, 12, 6)
    h.record(make_snapshot(now, {("HHN-NDR", d): 30.0}))
    h.record(make_snapshot(berlin(2026, 11, 20, 15), {("HHN-NDR", d): 30.0}))   # gleich → kein Eintrag
    h.record(make_snapshot(berlin(2026, 11, 20, 21), {("HHN-NDR", d): 25.0}))
    assert [e["p"] for e in h.series(f"HHN-NDR|{d}")] == [30.0, 25.0]
    h.record(make_snapshot(berlin(2026, 11, 21, 3), {}, failed={("HHN-NDR", date(2026, 12, 1))}))
    assert h.last_price(f"HHN-NDR|{d}") == 25.0      # fehlgeschlagener Monat ändert nichts
    h.record(make_snapshot(berlin(2026, 11, 21, 9), {}))
    assert h.last_price(f"HHN-NDR|{d}") is None      # Flug verschwunden


# ------------------------------------------------------------------ Angebote ---
def _setup(tmp_path, base_prices, now):
    h, s = History(tmp_path / "h.json"), State(tmp_path / "s.json")
    h.record(make_snapshot(now, base_prices))
    return h, s


def test_no_alerts_on_first_run(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    h, s = History(tmp_path / "h.json"), State(tmp_path / "s.json")
    assert detect(make_snapshot(now, {("HHN-NDR", date(2026, 12, 6)): 5.99}), h, s, cfg, now) == []


@pytest.mark.parametrize("old,new,expected", [
    (50.0, 39.0, True),    # −11 € / −22 %  → ja
    (50.0, 41.0, False),   # −9 €           → nein (unter 10 €)
    (200.0, 185.0, False), # −15 € / −7,5 % → nein (unter 20 %)
])
def test_price_drop_thresholds(cfg, tmp_path, old, new, expected):
    now = berlin(2026, 11, 20, 9)
    d = date(2027, 2, 10)
    h, s = _setup(tmp_path, {("HHN-NDR", d): old, ("HHN-NDR", date(2027, 2, 1)): 10.0}, now)
    alerts = detect(make_snapshot(now, {("HHN-NDR", d): new, ("HHN-NDR", date(2027, 2, 1)): 10.0}), h, s, cfg, now)
    assert any(a.kind == "PREISSTURZ" for a in alerts) is expected


def test_top_offer_new_flight_and_no_repeat(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    base = {("HHN-NDR", date(2027, 1, 5)): 15.0}
    h, s = _setup(tmp_path, base, now)
    snap = make_snapshot(now, {**base, ("HHN-NDR", date(2027, 1, 20)): 24.99})
    alerts = [a for a in detect(snap, h, s, cfg, now) if a.fare]
    assert [a.kind for a in alerts] == ["TOP_ANGEBOT"]
    s.mark_alerted(alerts[0].dedupe_key, now)
    assert [a for a in detect(snap, h, s, cfg, now) if a.fare] == []      # gleicher Preis → keine Wiederholung


def test_multiple_conditions_single_alert(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    d = date(2026, 11, 24)                                    # in 4 Tagen → Last-Minute
    h, s = _setup(tmp_path, {("HHN-NDR", d): 49.99}, now)
    alerts = [a for a in detect(make_snapshot(now, {("HHN-NDR", d): 19.99}), h, s, cfg, now) if a.fare]
    assert len(alerts) == 1
    a = alerts[0]
    assert a.kind == "PREISSTURZ"
    assert set(a.also) == {"NEUER_TIEFSTPREIS", "LAST_MINUTE"}
    assert a.old_price == 49.99 and round(a.saving, 2) == 30.0


def test_new_monthly_low(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    h, s = _setup(tmp_path, {("HHN-NDR", date(2027, 3, 3)): 40.0, ("HHN-NDR", date(2027, 3, 10)): 45.0}, now)
    snap = make_snapshot(now, {("HHN-NDR", date(2027, 3, 3)): 40.0, ("HHN-NDR", date(2027, 3, 10)): 38.0})
    kinds = [a.kind for a in detect(snap, h, s, cfg, now) if a.fare]
    assert kinds == ["NEUER_TIEFSTPREIS"]


def test_cheap_round_trip(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    base = {("HHN-NDR", date(2027, 1, 10)): 60.0, ("NDR-HHN", date(2027, 1, 20)): 60.0}
    h, s = _setup(tmp_path, base, now)
    snap = make_snapshot(now, {("HHN-NDR", date(2027, 1, 10)): 60.0, ("NDR-HHN", date(2027, 1, 20)): 60.0,
                               ("HHN-NDR", date(2027, 1, 12)): 31.0, ("NDR-HHN", date(2027, 1, 19)): 31.0})
    assert not any(a.kind == "GUENSTIGER_HIN_RUECK" for a in detect(snap, h, s, cfg, now))   # 62 € ≥ 50 €
    snap = make_snapshot(now, {("HHN-NDR", date(2027, 1, 12)): 24.0, ("NDR-HHN", date(2027, 1, 19)): 22.0})
    combos = [a for a in detect(snap, h, s, cfg, now) if a.kind == "GUENSTIGER_HIN_RUECK"]
    assert len(combos) == 1 and combos[0].combo.total == 46.0 and combos[0].combo.nights == 7


def test_failed_month_never_used_for_alerts(cfg, tmp_path):
    now = berlin(2026, 11, 20, 9)
    d = date(2027, 2, 10)
    h, s = _setup(tmp_path, {("HHN-NDR", d): 80.0}, now)
    snap = make_snapshot(now, {}, failed={("HHN-NDR", date(2027, 2, 1))})
    assert detect(snap, h, s, cfg, now) == []


def test_calendar_combo_same_month_option(cfg):
    now = berlin(2026, 11, 20, 9)
    snap = make_snapshot(now, {("HHN-NDR", date(2026, 11, 24)): 20.0,
                               ("NDR-HHN", date(2026, 11, 28)): 60.0,
                               ("NDR-HHN", date(2026, 12, 5)): 10.0})
    outs, rets = future_fares(snap, "HHN-NDR", now), future_fares(snap, "NDR-HHN", now)
    assert best_combo(outs, rets, 3, 30, out_month=date(2026, 11, 1)).inbound.day == date(2026, 12, 5)
    same = best_combo(outs, rets, 3, 30, out_month=date(2026, 11, 1), same_month=True)
    assert same.inbound.day == date(2026, 11, 28)


def test_top3_categories_distinct_and_within_nights(cfg):
    from flightdeals.analysis import top_combos
    now = berlin(2026, 11, 20, 9)
    snap = make_snapshot(now, {("HHN-NDR", date(2026, 12, 6)): 19.99, ("NDR-HHN", date(2026, 12, 15)): 18.99,
                               ("HHN-NDR", date(2026, 12, 4)): 34.99, ("NDR-HHN", date(2026, 12, 8)): 26.79,
                               ("NDR-HHN", date(2026, 12, 22)): 26.63, ("NDR-HHN", date(2027, 1, 2)): 90.0})
    combos = top_combos(future_fares(snap, "HHN-NDR", now), future_fares(snap, "NDR-HHN", now),
                        cfg["top3"]["categories"], [date(2026, 11, 1), date(2026, 12, 1)])
    labels = [cat["label"] for cat, _ in combos]
    assert labels == ["Günstigste Kombination", "Kurztrip", "Familienbesuch"]
    pairs = [(c.outbound.day, c.inbound.day) for _, c in combos]
    assert len(set(pairs)) == 3                                   # keine doppelte Kombination
    for cat, c in combos:
        assert cat["min_nights"] <= c.nights <= cat["max_nights"] and c.inbound.day > c.outbound.day
    assert pairs[0] == (date(2026, 12, 6), date(2026, 12, 15))    # 38,98 € günstigste


def test_all_image_texts_exist_in_font(cfg):
    """Jedes Zeichen, das in Bildern vorkommt, muss in der Schrift vorhanden sein (keine leeren Kästchen)."""
    from fontTools.ttLib import TTFont
    from flightdeals.texts import ALERT_TITLES, MONATE, T, WOCHENTAGE
    cmap = TTFont(str(cfg.fonts_dir / "Inter-ExtraBold.ttf")).getBestCmap()
    texts = list(T.values()) + list(ALERT_TITLES.values()) + MONATE + WOCHENTAGE + [
        cfg["page"]["name"], cfg["page"]["disclaimer"], cfg["page"]["badge"], cfg["page"]["booking_hint"],
        cfg["fare"]["baggage_note"], "↔ → · – − × € % ",
        *[c["label"] for c in cfg["top3"]["categories"]]]
    missing = {ch for s in texts for ch in s if not ch.isspace() and ord(ch) not in cmap}
    assert not missing, f"Zeichen fehlen in der Schrift: {missing}"
