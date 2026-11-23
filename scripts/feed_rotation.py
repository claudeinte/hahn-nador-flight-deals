"""Feed-Rotation (Nutzerwunsch 23.11.2026): statt jeden Tag „günstigster Hin- und Rückflug“ wechseln die
Feed-Beiträge (Facebook + Instagram, 4:5) in einem 7-Tage-Kreis. Die Nummern sind die Story-Nummern:

    Tag 1: #1 #2   günstigster Hinflug, günstigster Rückflug   (eigene 4:5-Bilder aus feed_bestpreis.py)
    Tag 2: #3      Preisstürze  – gibt es keine, wird am selben Tag direkt Tag 3 veröffentlicht
    Tag 3: #4 #5   Top 5 günstigste Hinflüge / Rückflüge
    Tag 4: #6 #7 #8  Familie Hinflug / Rückflug / Hin & Zurück
    Tag 5: #9      Top 5 Kombinationen
    Tag 6: #10     Günstig nach Dauer
    Tag 7: #11     Bestpreise pro Monat   (eigenes 4:5-Bild render_summary_feed)
    danach wieder Tag 1.

Dieses Skript veröffentlicht NICHTS: es wählt den heutigen Schritt (Stand in data/feed_rotation.json),
erstellt Bilder (4:5, PNG + JPEG) und Texte (Facebook mit Ryanair-Links, Instagram ohne Links) im Ordner --out
und schreibt feed_plan.json. Veröffentlicht wird mit scripts/feed_publish.py.
Preise = derselbe Preisstand wie die Stories (letzter Stand in data/snapshots/).

Aufruf:  python scripts/feed_rotation.py --story-ordner output/stories/<datum> --out public/<datum> [--schritt N]
"""
import argparse
import glob
import json
import pickle
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(PROJ / "scripts"))
from flightdeals.config import load_config  # noqa: E402
from flightdeals.texts import WOCHENTAGE, booking_link, edition_line, fmt_checked, fmt_price, round_trip_link  # noqa: E402
import vorschau_story_kalender as v  # noqa: E402

STATE = PROJ / "data" / "feed_rotation.json"
SCHRITTE = [["guenstigster_hinflug", "guenstigster_rueckflug"],
            ["preisstuerze"],
            ["top5_guenstigste_hinfluege", "top5_guenstigste_rueckfluege"],
            ["familie_hinflug", "familie_rueckflug", "familie_hin_und_zurueck"],
            ["top5_kombinationen"],
            ["nach_dauer"],
            ["bestpreise_pro_monat"]]
HIN = "🇩🇪 Frankfurt-Hahn → 🇲🇦 Nador"
RUECK = "🇲🇦 Nador → 🇩🇪 Frankfurt-Hahn"
BEIDE = "🇩🇪 Frankfurt-Hahn ⇄ 🇲🇦 Nador"
MEDAL = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"naechster_schritt": 0, "heute": {}}


def schritt_heute(st, heute):
    h = st.get("heute") or {}
    return h["schritt"] if h.get("tag") == heute else st.get("naechster_schritt", 0)


def tag(d, kurz=False):
    return f"{WOCHENTAGE[d.weekday()][:2]}, {d:%d.%m.%Y}" if not kurz else f"{WOCHENTAGE[d.weekday()][:2]}, {d:%d.%m.}"


def feed_bild(story_png):
    """Story 1080×1920 → Feed 1080×1350: ganze Story verkleinert in der Mitte, daneben derselbe Hintergrund
    weich und dunkler (Instagram erlaubt im Feed höchstens 4:5)."""
    s = Image.open(story_png).convert("RGB")
    bg = s.resize((1080, 1920), Image.LANCZOS).crop((0, 285, 1080, 1635)).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    fg = s.resize((759, 1350), Image.LANCZOS)
    bg.paste(fg, ((1080 - 759) // 2, 0))
    return bg


def ig_kurz(t, limit=2190):
    def n(x):
        return len(x.encode("utf-16-le")) // 2
    while n(t) > limit:
        head, tags = t.rstrip("\n").rsplit("\n", 1)
        parts = tags.split()
        if len(parts) <= 6:
            break
        t = head + "\n" + " ".join(parts[:-1]) + "\n"
    return t


def text(cfg, now, hook, body_fb, body_ig, platform):
    pg = cfg["page"]
    fb = platform == "facebook"
    t = f"""{edition_line(now)}

{hook}
🕒 Preise bei Ryanair {fmt_checked(now)} – können sich im Laufe des Tages jederzeit ändern.

{pg['stories_hint'] if fb else pg['instagram_stories_hint']}

{body_fb if fb else body_ig}

👉 Buchung nur über die offizielle Ryanair-Seite: ryanair.com

🧳 {cfg['fare']['baggage_note']}

{pg['like_cta']}

ℹ️ {pg['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich auf ryanair.com.

{pg['hashtags'] if fb else pg['instagram_hashtags']}
"""
    return t if fb else ig_kurz(t)


def lines(rows):
    """rows: Liste von (Textzeile, Link oder None) → (Facebook-Text mit Links, Instagram-Text ohne)."""
    fb, ig = [], []
    for ln, link in rows:
        fb.append(ln)
        ig.append(ln)
        if link:
            fb.append(f"🔗 {link}")
    return "\n".join(fb), "\n".join(ig)


def daten(cfg, snap, now):
    today = now.date()
    outs = sorted(v._future(snap, cfg, cfg.route_out, today), key=lambda f: (f.price, f.day))
    rets = sorted(v._future(snap, cfg, cfg.route_ret, today), key=lambda f: (f.price, f.day))
    return today, outs, rets


def inhalt(name, cfg, snap, now):
    """Hook + Zeilen für einen Beitrag. Gibt (hook, rows) zurück; rows = [(zeile, link|None), …]."""
    today, outs, rets = daten(cfg, snap, now)
    r = cfg["route"]
    O, D = r["origin"], r["destination"]
    pp = " pro Person"
    if name in ("top5_guenstigste_hinfluege", "top5_guenstigste_rueckfluege"):
        rueck = name.endswith("rueckfluege")
        fs = (rets if rueck else outs)[:5]
        route, (o, d) = (RUECK, (D, O)) if rueck else (HIN, (O, D))
        hook = (f"🏆 Die 5 günstigsten {'Rückflüge' if rueck else 'Hinflüge'} {route} – "
                f"schon ab {fmt_price(fs[0].price)}{pp}!")
        rows = [(f"Alle Flüge der nächsten {v.N_MONATE} Monate verglichen:", None), ("", None)]
        rows += [(f"{MEDAL[i]} {tag(f.day)} · Abflug {f.departure} Uhr · {fmt_price(f.price)}{pp}", booking_link(o, d, f.day))
                 for i, f in enumerate(fs)]
        return hook, rows
    if name in ("familie_hinflug", "familie_rueckflug"):
        rueck = name == "familie_rueckflug"
        f = (rets if rueck else outs)[0]
        route, (o, d) = (RUECK, (D, O)) if rueck else (HIN, (O, D))
        hook = (f"👨‍👩‍👧‍👦 Günstigster {'Rückflug' if rueck else 'Hinflug'} für Familien: {route} – "
                f"für 4 Personen zusammen {fmt_price(round(f.price * 4, 2))}!")
        rows = [(f"{'🛬' if rueck else '🛫'} {tag(f.day)} · Abflug {f.departure} Uhr · {fmt_price(f.price)}{pp}",
                 booking_link(o, d, f.day)), ("", None), ("Gesamtpreis für die ganze Familie:", None)]
        rows += [(f"👥 {n} Personen: {fmt_price(round(f.price * n, 2))}", None) for n in range(2, 7)]
        rows += [("", None), ("(Preis pro Person × Anzahl Personen, Basic-Tarif)", None)]
        return hook, rows
    if name == "familie_hin_und_zurueck":
        pairs = [(o_, r_) for o_ in outs for r_ in rets if 3 <= (r_.day - o_.day).days <= 30]
        o_, r_ = min(pairs, key=lambda x: (round(x[0].price + x[1].price, 2), x[0].day))
        tot, nights = o_.price + r_.price, (r_.day - o_.day).days
        hook = (f"👨‍👩‍👧‍👦 Günstigstes Hin & Zurück für Familien: {BEIDE} – {nights} Nächte in Nador, "
                f"{fmt_price(tot)}{pp}!")
        rows = [(f"🛫 Hinflug: {tag(o_.day)} · Abflug {o_.departure} Uhr · {fmt_price(o_.price)}", None),
                (f"🛬 Rückflug: {tag(r_.day)} · Abflug {r_.departure} Uhr · {fmt_price(r_.price)}",
                 round_trip_link(O, D, o_.day, r_.day)), ("", None), ("Gesamtpreis hin & zurück für die ganze Familie:", None)]
        rows += [(f"👥 {n} Personen: {fmt_price(round(tot * n, 2))}", None) for n in range(2, 7)]
        rows += [("", None), ("(Preis pro Person × Anzahl Personen, Basic-Tarif, Hin- und Rückflug einzeln gebucht)", None)]
        return hook, rows
    if name == "top5_kombinationen":
        combos = sorted(((o_.price + r_.price, o_.day, r_.day, o_, r_) for o_ in outs for r_ in rets
                         if 3 <= (r_.day - o_.day).days <= 30), key=lambda c: (round(c[0], 2), c[1], c[2]))
        top, used = [], set()
        for c in combos:
            if c[1] in used:
                continue
            used.add(c[1])
            top.append(c)
            if len(top) == 5:
                break
        hook = f"🏆 Die 5 günstigsten Kombinationen pro Person hin & zurück: {BEIDE} – schon ab {fmt_price(top[0][0])}{pp}!"
        rows = [(f"3–30 Nächte · die günstigsten der nächsten {v.N_MONATE} Monate:", None), ("", None)]
        for i, (tot, _, _, o_, r_) in enumerate(top):
            rows.append((f"{MEDAL[i]} {fmt_price(tot)}{pp} · {(r_.day - o_.day).days} Nächte", None))
            rows.append((f"   🛫 {tag(o_.day, True)} {o_.departure} Uhr ({fmt_price(o_.price)}) · "
                         f"🛬 {tag(r_.day, True)} {r_.departure} Uhr ({fmt_price(r_.price)})",
                         round_trip_link(O, D, o_.day, r_.day)))
        return hook, rows
    if name == "nach_dauer":
        spans = [("1 Woche", 6, 8), ("2 Wochen", 13, 15), ("3 Wochen", 20, 22), ("1 Monat", 28, 31)]
        rows, best_all = [], None
        for lab, a_, b_ in spans:
            best = min(((o_.price + r_.price, o_.day, o_, r_) for o_ in outs for r_ in rets
                        if a_ <= (r_.day - o_.day).days <= b_), default=None, key=lambda c: (round(c[0], 2), c[1]))
            if not best:
                rows.append((f"⏳ {lab} ({a_}–{b_} Nächte): keine passenden Flüge", None))
                continue
            tot, _, o_, r_ = best
            best_all = tot if best_all is None else min(best_all, tot)
            rows.append((f"⏳ {lab} ({(r_.day - o_.day).days} Nächte): {fmt_price(tot)}{pp}", None))
            rows.append((f"   🛫 {tag(o_.day, True)} {o_.departure} Uhr · 🛬 {tag(r_.day, True)} {r_.departure} Uhr",
                         round_trip_link(O, D, o_.day, r_.day)))
            rows.append(("", None))
        hook = (f"⏳ Günstig nach Reisedauer: hin & zurück {BEIDE} – für 1, 2, 3 Wochen oder 1 Monat"
                + (f", schon ab {fmt_price(best_all)}{pp}!" if best_all else "."))
        return hook, rows[:-1] if rows and rows[-1][0] == "" else rows
    if name == "bestpreise_pro_monat":
        months = v.next_months(today, v.N_MONATE)
        rows = []
        for y_, m_ in months:
            rows.append((f"📅 {v.MONATE[m_ - 1]} {y_}", None))
            for route, ic, lab, (o, d) in ((cfg.route_out, "🛫", "Hin", (O, D)), (cfg.route_ret, "🛬", "Rück", (D, O))):
                fs = [f for f in v._future(snap, cfg, route, today) if (f.day.year, f.day.month) == (y_, m_)]
                if not fs:
                    rows.append((f"   {ic} {lab}: keine Flüge", None))
                    continue
                f = min(fs, key=lambda x: (x.price, x.day))
                rows.append((f"   {ic} {lab}: {tag(f.day, True)} · {fmt_price(f.price)}", booking_link(o, d, f.day)))
        hook = f"📅 Bestpreise pro Monat: {BEIDE} – der günstigste Hin- und Rückflug in jedem Monat (pro Person)."
        return hook, rows
    raise ValueError(name)


def preisstuerze_inhalt(cfg, snap, now):
    today = now.date()
    prev, prev_at = v.week_ago_prices(today)
    r = cfg["route"]
    O, D = r["origin"], r["destination"]
    rows, best_pct = [], 0
    for route, ic, lab, (o, d) in ((cfg.route_out, "🛫", "Hinflug " + HIN, (O, D)), (cfg.route_ret, "🛬", "Rückflug " + RUECK, (D, O))):
        out = []
        for f in snap.fares(route):
            old = prev.get((route, f.day))
            if f.day >= today and old and old > f.price and (old - f.price) / old * 100 > 20:
                out.append(((old - f.price) / old * 100, f, old))
        out = sorted(out, key=lambda x: (-x[0], x[1].day))[:3]
        if not out:
            continue
        rows.append((f"{ic} {lab}:", None))
        for pct, f, old in out:
            best_pct = max(best_pct, pct)
            rows.append((f"   📉 {tag(f.day)} · {f.departure} Uhr · jetzt {fmt_price(f.price)} statt {fmt_price(old)} "
                         f"(−{pct:.0f} %)", booking_link(o, d, f.day)))
        rows.append(("", None))
    when = f"{WOCHENTAGE[prev_at.weekday()]}, {prev_at:%d.%m.%Y}" if prev_at else "vorher"
    hook = f"📉 Preissturz: Flüge {BEIDE} bis zu {best_pct:.0f} % günstiger als am {when}!"
    rows.append((f"(Vergleich mit dem Preisstand vom {when}, pro Person, Basic-Tarif)", None))
    return hook, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story-ordner", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--schritt", type=int, default=None, help="nur zum Testen: Schritt 0–6 erzwingen")
    a = ap.parse_args()
    sdir, out = Path(a.story_ordner), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    heute = sdir.name                                       # Ordnername = Datum (YYYY-MM-DD)
    cfg = load_config()
    cfg["route"]["months_ahead"] = v.N_MONATE
    snap = pickle.load(open(sorted(glob.glob(str(PROJ / "data" / "snapshots" / "*.pkl")))[-1], "rb"))
    now = snap.fetched_at
    st = load_state()
    schritt = a.schritt if a.schritt is not None else schritt_heute(st, heute)
    stories = {p.stem[3:]: p for p in sdir.glob("[0-9][0-9]_*.png")}
    hinweis = ""
    if SCHRITTE[schritt] == ["preisstuerze"] and "preisstuerze" not in stories:
        hinweis = "keine Preisstürze heute → direkt Tag 3"
        schritt += 1
    items = []
    for name in SCHRITTE[schritt]:
        if name in ("guenstigster_hinflug", "guenstigster_rueckflug"):   # fertige 4:5-Beiträge aus feed_bestpreis.py
            datei = "feed_1_hinflug" if name.endswith("hinflug") else "feed_2_rueckflug"
            if not (out / f"{datei}.png").exists():
                sys.exit(f"{datei}.png fehlt – zuerst scripts/feed_bestpreis.py --out {out} ausführen")
            items.append({"name": name, "datei": datei})
            continue
        datei = f"feed_r_{name}"
        img = (v.render_summary_feed(cfg, snap, v.next_months(now.date(), v.N_MONATE), now)
               if name == "bestpreise_pro_monat" else feed_bild(stories[name]))
        img.save(out / f"{datei}.png")
        img.convert("RGB").save(out / f"{datei}.jpg", "JPEG", quality=95, subsampling=0, optimize=True)
        hook, rows = preisstuerze_inhalt(cfg, snap, now) if name == "preisstuerze" else inhalt(name, cfg, snap, now)
        body_fb, body_ig = lines(rows)
        for plat in ("facebook", "instagram"):
            (out / f"{datei}_{plat}.txt").write_text(text(cfg, now, hook, body_fb, body_ig, plat), encoding="utf-8")
        items.append({"name": name, "datei": datei})
    plan = {"datum": heute, "schritt": schritt, "tag_im_kreis": schritt + 1, "hinweis": hinweis, "beitraege": items}
    (out / "feed_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    print(json.dumps(plan, ensure_ascii=False))


if __name__ == "__main__":
    main()
