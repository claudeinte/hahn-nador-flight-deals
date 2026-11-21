"""Beitrag „Bestpreise pro Monat“: Bild (gleich wie Story 01) + Text mit Buchungslink für jedes Ticket.

Aufruf: .venv/bin/python scripts/bestpreise_beitrag.py
Ausgabe: output/facebook_ahora/bestpreise_<datum>/bestpreise_pro_monat.png (9:16), bestpreise_instagram_4x5.png
(1080×1350 für den Instagram-Feed), beitrag.txt (Facebook, mit Links), beitrag_instagram.txt (ohne Links)
Bild und Text stammen aus derselben Preisabfrage → Preise stimmen immer überein.
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(PROJ / "scripts"))
from flightdeals.config import load_config  # noqa: E402
from flightdeals.fetch import fetch_all  # noqa: E402
from flightdeals.texts import MONATE, WOCHENTAGE, booking_link, edition_line, fmt_checked, fmt_price  # noqa: E402
import vorschau_story_kalender as v  # noqa: E402


def dot(p):
    return "🟢" if p < 25 else "🟡" if p < 50 else "🟠" if p <= 100 else "🔴"


def instagram_kurz(t, limit=2200):
    """Instagram erlaubt max. 2200 Zeichen: doppelten Stories-Satz weglassen, Einrückung kürzen,
    notfalls letzte Hashtags streichen."""
    t = t.replace("📲 Alle Tage und Preise findest du täglich in unseren Stories.\n", "")
    t = t.replace("\n   🛫", "\n 🛫").replace("\n   🛬", "\n 🛬")
    while len(t) > limit:
        head, tags = t.rstrip("\n").rsplit("\n", 1)
        parts = tags.split()
        if len(parts) <= 8:
            break
        t = head + "\n" + " ".join(parts[:-1]) + "\n"
    return t


def main():
    cfg = load_config()
    cfg["route"]["months_ahead"] = v.N_MONATE
    now = cfg.now()
    snap = fetch_all(cfg, now)
    if any(not m.ok for m in snap.months.values()):
        sys.exit("Preisabfrage unvollständig – kein Beitrag (keine alten Preise zeigen).")
    today = now.date()
    months = v.next_months(today, v.N_MONATE)
    out = PROJ / "output" / "facebook_ahora" / f"bestpreise_{now:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    v.render_summary(cfg, snap, months, now).save(out / "bestpreise_pro_monat.png")
    v.render_summary_feed(cfg, snap, months, now).save(out / "bestpreise_instagram_4x5.png")   # Instagram-Feed

    def cheapest(route, y, m):
        fs = [f for f in snap.fares(route) if f.day.year == y and f.day.month == m and f.day >= today]
        return min(fs, key=lambda f: (f.price, f.day)) if fs else None

    def leg(icon, lab, f, o, d, links):
        if not f:
            return f"   {icon} {lab}: –"
        s = f"   {icon} {lab}: {dot(f.price)} {fmt_price(f.price)} ({WOCHENTAGE[f.day.weekday()][:2]}, {f.day:%d.%m.})"
        return s + (f"\n   🔗 {booking_link(o, d, f.day)}" if links else "")

    def text(links):
        blocks, allo, allr = [], [], []
        for y, m in months:
            o, r = cheapest(cfg.route_out, y, m), cheapest(cfg.route_ret, y, m)
            allo += [o] if o else []
            allr += [r] if r else []
            blocks.append(f"📅 {MONATE[m - 1]} {y}\n" + leg("🛫", "Hin", o, "HHN", "NDR", links) + "\n"
                          + leg("🛬", "Rück", r, "NDR", "HHN", links))
        bo = min(allo, key=lambda f: (f.price, f.day))
        br = min(allr, key=lambda f: (f.price, f.day))
        book = ("👉 Buchung nur über die offizielle Ryanair-Seite: ryanair.com" if links
                else "👉 Buchung nur über die offizielle Ryanair-Seite: ryanair.com")
        return f"""{edition_line(now)}

💶 Bestpreise pro Monat: 🇩🇪 Frankfurt-Hahn ✈️ 🇲🇦 Nador – Hinflug ab {fmt_price(bo.price)}, Rückflug ab {fmt_price(br.price)}!
🕒 Preise bei Ryanair {fmt_checked(now)} – können sich im Laufe des Tages jederzeit ändern.

{cfg['page']['stories_hint'] if links else cfg['page']['instagram_stories_hint']}

Der günstigste Hin- und Rückflug für jeden Monat (pro Person, nur kommende Tage):

""" + "\n\n".join(blocks) + f"""

🟢 unter 25 € · 🟡 25–49,99 € · 🟠 50–100 € · 🔴 über 100 €

{book}
📲 Alle Tage und Preise findest du täglich in unseren Stories.

🧳 {cfg['fare']['baggage_note']}

{cfg['page']['like_cta']}

ℹ️ {cfg['page']['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich auf ryanair.com.

{cfg['page']['hashtags'] if links else cfg['page']['instagram_hashtags']}
"""
    (out / "beitrag.txt").write_text(text(True), encoding="utf-8")
    (out / "beitrag_instagram.txt").write_text(instagram_kurz(text(False)), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
