"""PREISSTURZ eines Monats: alle Flüge HHN⇄NDR eines Monats, die seit einem früheren Preisstand
günstiger geworden sind – ein Bild (dunkler Standardstil) + Beitragstext.

Aufruf:
    .venv/bin/python scripts/preissturz_monat.py 2027-01            # vergleicht mit dem letzten Stand, der ≥ 12 h alt ist
    .venv/bin/python scripts/preissturz_monat.py 2027-01 --stunden 24
Jeder Aufruf speichert den aktuellen Preisstand in data/snapshots/ (für spätere Vergleiche).
Ausgabe: output/facebook_ahora/preissturz_<monat>/
"""
import argparse, pickle, sys
from datetime import timedelta
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
SNAP = PROJ / "data" / "snapshots"
from flightdeals.config import load_config
from flightdeals.fetch import fetch_all
from flightdeals.render.common import Painter, W, H, M, mix
from flightdeals.texts import MONATE, WOCHENTAGE, WOCHENTAGE_KURZ, fmt_price, fmt_checked, edition_line, booking_link

cfg = load_config(PROJ / "config.toml")
ap = argparse.ArgumentParser(); ap.add_argument("monat", help="z. B. 2027-01"); ap.add_argument("--stunden", type=float, default=12)
args = ap.parse_args()
YY, MM = map(int, args.monat.split("-")); MNAME = f"{MONATE[MM - 1]} {YY}"
new = fetch_all(cfg, cfg.now()); now = new.fetched_at
SNAP.mkdir(parents=True, exist_ok=True)
olds = []
for f in sorted(SNAP.glob("*.pkl")):
    sn = pickle.load(open(f, "rb"))
    if now - sn.fetched_at >= timedelta(hours=args.stunden): olds.append(sn)
pickle.dump(new, open(SNAP / now.strftime("%Y-%m-%d_%H%M.pkl"), "wb"))
if not olds: sys.exit(f"Kein Preisstand gefunden, der mindestens {args.stunden:g} h alt ist – später erneut versuchen.")
old = olds[-1]; then = old.fetched_at
idx = lambda sn: {(f.route, f.day): f for f in sn.fares()}
o, n = idx(old), idx(new)
def drops(route):
    out = [(n[k], o[k].price) for k in n if k[0] == route and k[1].year == YY and k[1].month == MM
           and k in o and o[k].price - n[k].price >= 3]
    return sorted(out, key=lambda x: (-(x[1] - x[0].price) / x[1], x[0].day))
hin, rueck = drops("HHN-NDR"), drops("NDR-HHN")
jan_out = sorted((f for (r, d), f in n.items() if r == "HHN-NDR" and d.year == YY and d.month == MM), key=lambda f: (f.price, f.day))
best = jan_out[0]
if not hin and not rueck: sys.exit(f"Keine Preissenkung im {MNAME} seit {then:%d.%m.%Y %H:%M}.")
print("hin", [(str(f.day), op, f.price) for f, op in hin]); print("rueck", [(str(f.day), op, f.price) for f, op in rueck]); print("best", best)

# Hinflug: die 4 stärksten einzeln, Rest gruppiert nach (alt, neu)
top_hin, rest = hin[:4], hin[4:]
groups = {}
for f, op in rest: groups.setdefault((op, f.price), []).append(f)
rest_groups = sorted(groups.items(), key=lambda kv: -len(kv[1]))

p = Painter(cfg); t = p.t
p.header(kicker="FLUG-NEWS", when=now)
y = 130
p.pill(M, y, "PREISSTURZ", "extrabold", 34, (255, 255, 255), t.red, pad_x=22, pad_y=11)
p.text((M, y + 82), f"{MNAME}: Flüge jetzt günstiger", "extrabold", 52, t.text, max_w=W - 2 * M)
p.text((M, y + 150), f"Vergleich mit den Preisen vom {then.strftime('%d.%m.%Y')} · pro Person, nur Hinflug bzw. Rückflug",
       "semibold", 22, t.muted, max_w=W - 2 * M)

def section(y, route, label, rows, groups_):
    p.route_title(route, M, y, 30)
    lf = p.font("extrabold", 24)
    p.pill(W - M, y - 2, label, "extrabold", 22, t.background, t.accent, pad_x=16, pad_y=8, anchor_right=True)
    y += 54
    for f, op in rows:
        p.rrect((M, y, W - M, y + 70), 16, fill=t.card if hasattr(t, "card") else mix(t.background, (255, 255, 255), 0.06))
        p.text((M + 24, y + 35), f"{WOCHENTAGE_KURZ[f.day.weekday()]}, {f.day.strftime('%d.%m.')} · {f.departure} Uhr", "bold", 30, t.text, anchor="lm")
        fo = p.font("semibold", 28); old = fmt_price(op); xo = 560
        p.d.text((xo, y + 35), old, font=fo, fill=t.muted, anchor="lm")
        wo = p.tw(old, fo); p.d.line((xo - 3, y + 36, xo + wo + 3, y + 36), fill=t.red, width=4)
        p.text((xo + wo + 14, y + 35), "→", "bold", 28, t.muted, anchor="lm")
        p.text((xo + wo + 52, y + 35), fmt_price(f.price), "extrabold", 36, t.green, anchor="lm")
        pct = round((op - f.price) / op * 100)
        p.pill(W - M - 16, y + 15, f"−{pct} %", "extrabold", 22, (255, 255, 255), t.red, pad_x=12, pad_y=8, anchor_right=True)
        y += 80
    for (op, np_), fs in groups_:
        days = ", ".join(f.day.strftime("%d.") for f in sorted(fs, key=lambda f: f.day))
        h = 104
        p.rrect((M, y, W - M, y + h), 16, fill=mix(t.background, (255, 255, 255), 0.06))
        p.text((M + 24, y + 18), f"+ {len(fs)} weitere Tage: ", "bold", 28, t.text)
        fo = p.font("semibold", 28); old = fmt_price(op); xo = 560
        p.d.text((xo, y + 34), old, font=fo, fill=t.muted, anchor="lm")
        wo = p.tw(old, fo); p.d.line((xo - 3, y + 35, xo + wo + 3, y + 35), fill=t.red, width=4)
        p.text((xo + wo + 14, y + 34), "→", "bold", 28, t.muted, anchor="lm")
        p.text((xo + wo + 52, y + 34), fmt_price(np_), "extrabold", 36, t.green, anchor="lm")
        p.text((M + 24, y + 64), f"am {days}{MM:02d}.", "semibold", 24, t.muted, max_w=W - 2 * M - 48)
        y += h + 10
    return y + 14

y = section(y + 210, "HHN-NDR", "HINFLUG", top_hin, rest_groups[:1])
y = section(y, "NDR-HHN", "RÜCKFLUG", rueck[:2], [])
# Tipp
p.rrect((M, y, W - M, y + 74), 16, fill=mix(t.background, t.green, 0.18), outline=t.green, width=2)
p.text((M + 24, y + 37), f"Günstigster {MONATE[MM - 1]}-Hinflug: {WOCHENTAGE[best.day.weekday()]}, {best.day.strftime('%d.%m.')} · {best.departure} Uhr",
       "bold", 27, t.text, anchor="lm", max_w=640)
p.text((W - M - 24, y + 37), fmt_price(best.price), "extrabold", 40, t.green, anchor="rm")
y += 90
p.text((M, y), f"Preise {fmt_checked(now)} – können sich jederzeit ändern.", "semibold", 21, t.muted)
ft = p.footer([(cfg["fare"]["baggage_note"], t.muted), (cfg["page"]["disclaimer"], t.grey)], size=16)
p.info_strip(ft - 10)
print("content bottom", y + 30, "strip top approx", ft - 10)
out = PROJ / f"output/facebook_ahora/preissturz_{args.monat}"; out.mkdir(parents=True, exist_ok=True)
p.img.save(out / "preissturz_januar.png")

# Text
def line(f, op, fl):
    pct = round((op - f.price) / op * 100)
    return (f"{fl} {WOCHENTAGE[f.day.weekday()]}, {f.day.strftime('%d.%m.%Y')} · {f.departure} Uhr: "
            f"{fmt_price(op)} → {fmt_price(f.price)} (−{pct} %)\n🔗 {booking_link(*f.route.split('-'), f.day)}")
hl = "\n\n".join(line(f, op, "✈️") for f, op in top_hin)
gl = "\n".join(f"✈️ {op_np[0]:.2f} → {fmt_price(op_np[1])}: ".replace(".", ",").replace(f"{op_np[0]:.2f}".replace(".", ","), fmt_price(op_np[0])) +
               ", ".join(f.day.strftime("%d.%m.") for f in sorted(fs, key=lambda f: f.day)) for op_np, fs in rest_groups)
rl = "\n\n".join(line(f, op, "✈️") for f, op in rueck[:2])
txt = f"""{edition_line(now)}

📉 Preissturz im {MONATE[MM - 1]}: 🇩🇪 Frankfurt-Hahn ✈️ 🇲🇦 Nador – viele Flüge jetzt günstiger, bis zu −{max(round((op - f.price) / op * 100) for f, op in hin + rueck)} %!
🕒 Preise {fmt_checked(now)} – können sich jederzeit ändern.

{cfg['page']['stories_hint']}

Verglichen mit den Preisen vom {then.strftime('%d.%m.%Y')} um {then.strftime('%H:%M')} Uhr (pro Person):

🛫 Hinflug 🇩🇪 → 🇲🇦
{hl}

Außerdem günstiger:
{gl}

🛬 Rückflug 🇲🇦 → 🇩🇪
{rl}

💡 Günstigster {MONATE[MM - 1]}-Hinflug: {WOCHENTAGE[best.day.weekday()]}, {best.day.strftime('%d.%m.%Y')} · {best.departure} Uhr · {fmt_price(best.price)}
🔗 {booking_link('HHN', 'NDR', best.day)}

👉 Buchung nur über die offizielle Ryanair-Seite.

🧳 {cfg['fare']['baggage_note']}

{cfg['page']['like_cta']}

ℹ️ {cfg['page']['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich auf ryanair.com.

{cfg['page']['hashtags']}
"""
(out / "beitrag.txt").write_text(txt); print(txt)
