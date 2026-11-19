"""Deutsche Texte, Datums- und Preisformate, offizielle Ryanair-Links."""
from __future__ import annotations

from datetime import date, datetime

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
WOCHENTAGE_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

T = {
    "calendar": "Flugkalender",
    "outbound": "Hinflug",
    "return": "Rückflug",
    "best_combo": "Günstigster Hin- und Rückflug",
    "total": "Gesamtpreis",
    "nights": "Nächte",
    "night": "Nacht",
    "per_person": "Pro Person",
    "updated": "Zuletzt aktualisiert",
    "no_flight": "Kein Flug verfügbar",
    "past": "Vergangene Tage",
    "may_change": "Preise können sich ändern",
    "no_data": "Keine Daten",
    "no_combo": "Keine passende Kombination verfügbar",
    "price_history": "Preisverlauf",
    "saved": "gespart",
    "check_book": "Prüfen & buchen auf ryanair.com",
    "test_banner": "TESTDATEN – NUR BEISPIEL, KEIN ECHTES ANGEBOT",
}

ALERT_TITLES = {
    "PREISSTURZ": "PREISSTURZ",
    "TOP_ANGEBOT": "TOP-ANGEBOT",
    "GUENSTIGER_HIN_RUECK": "GÜNSTIGER HIN- UND RÜCKFLUG",
    "NEUER_TIEFSTPREIS": "NEUER TIEFSTPREIS",
    "LAST_MINUTE": "LAST-MINUTE-ANGEBOT",
}


def fmt_price(value: float) -> str:
    """29.99 -> '29,99 €'; 1234.5 -> '1.234,50 €'"""
    s = f"{value:,.2f}"                      # 1,234.50
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_date_wd(d: date, long: bool = False) -> str:
    wd = (WOCHENTAGE if long else WOCHENTAGE_KURZ)[d.weekday()]
    return f"{wd}, {fmt_date(d)}"


def fmt_date_wd_short(d: date) -> str:
    """'Di, 24.11.' – kurz, für Bilder mit wenig Platz (Jahr steht im Titel)."""
    return f"{WOCHENTAGE_KURZ[d.weekday()]}, {d.strftime('%d.%m.')}"


def fmt_checked(dt: datetime) -> str:
    """'Preis geprüft am 19.11.2026 um 01:38 Uhr' – schützt vor dem Vorwurf falscher Preise."""
    return f"geprüft am {dt.strftime('%d.%m.%Y')} um {dt.strftime('%H:%M')} Uhr"


def edition_line(dt: datetime) -> str:
    """Erste Zeile jedes Beitrags: '🗞️ Flug-News · Donnerstag, 19.11.2026'"""
    return f"🗞️ Flug-News · {WOCHENTAGE[dt.weekday()]}, {dt.strftime('%d.%m.%Y')}"


def fmt_datetime(dt: datetime) -> str:
    return f"{dt.strftime('%d.%m.%Y')}, {dt.strftime('%H:%M')} Uhr"


def month_name(year: int, month: int) -> str:
    return f"{MONATE[month - 1]} {year}"


def fmt_nights(n: int) -> str:
    return f"{n} {T['night'] if n == 1 else T['nights']}"


def fmt_pct(p: float) -> str:
    return f"{p:.0f} %"


def booking_link(origin: str, destination: str, day: date) -> str:
    """Offizieller Ryanair-Link (deutsche Seite) für einen einfachen Flug."""
    return ("https://www.ryanair.com/de/de/trip/flights/select?adults=1&teens=0&children=0&infants=0"
            f"&dateOut={day.isoformat()}&isReturn=false&originIata={origin}&destinationIata={destination}")


def round_trip_link(origin: str, destination: str, out_day: date, ret_day: date) -> str:
    return ("https://www.ryanair.com/de/de/trip/flights/select?adults=1&teens=0&children=0&infants=0"
            f"&dateOut={out_day.isoformat()}&dateIn={ret_day.isoformat()}&isReturn=true"
            f"&originIata={origin}&destinationIata={destination}")
