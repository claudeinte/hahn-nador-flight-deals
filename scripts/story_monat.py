"""Instagram-Story 1080×1920: günstigster Hinflug und günstigster Rückflug eines Monats (HHN⇄NDR).
Aufruf: .venv/bin/python scripts/story_monat.py 2026-12
Story verschwindet nach 24 h – passend für Preise, die sich schnell ändern.
Oben/unten je ~250 px frei lassen (dort liegen Instagram-Bedienelemente); Platz für den Link-Sticker ist markiert."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config
from flightdeals.fetch import fetch_all
from flightdeals.render.common import Painter, M, W, mix, price_color
from flightdeals.texts import MONATE, WOCHENTAGE, fmt_price, fmt_checked, booking_link

YY, MM = map(int, sys.argv[1].split("-"))
cfg = load_config(); now = cfg.now(); snap = fetch_all(cfg, now)
def cheapest(route):
    fs = [f for f in snap.fares(route) if f.day.year == YY and f.day.month == MM and f.day >= now.date()]
    return min(fs, key=lambda f: (f.price, f.day)) if fs else None
hin, rueck = cheapest(cfg.route_out), cheapest(cfg.route_ret)
print("Hinflug", hin); print("Rückflug", rueck)

H2 = 1920
p = Painter(cfg); t = p.t
bg = Image.new("RGBA", (W, H2), (*t.background, 255))
gl = Image.new("RGBA", (W, H2), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse((60, 380, 1020, 1340), fill=(*t.accent, 55))
bg.alpha_composite(gl.filter(ImageFilter.GaussianBlur(170)))
p.img = bg.convert("RGB"); p.d = ImageDraw.Draw(p.img)

# Kopf (unterhalb der Instagram-Leiste)
y = 270
p.rrect((M, y + 2, M + 8, y + 32), 3, fill=t.accent)
p.text((M + 22, y), f"FLUG-NEWS · {WOCHENTAGE[now.weekday()].upper()}, {now:%d.%m.%Y}", "extrabold", 30, t.accent)
p.text((M + 22, y + 44), "Unabhängige Infoseite · Frankfurt-Hahn ⇄ Nador".replace("⇄", "↔"), "medium", 22, t.muted)

# Titel
y = 400
p.d.text((W / 2, y), "GÜNSTIGSTE FLÜGE", font=p.font("extrabold", 74), fill=t.text, anchor="mm")
f = p.font("extrabold", 44); pw = p.tw(f"IM {MONATE[MM - 1].upper()} {YY}", f) + 60
p.pill((W - pw) / 2, y + 50, f"IM {MONATE[MM - 1].upper()} {YY}", "extrabold", 44, t.background, t.green, pad_x=30, pad_y=14)

def card(top, label, fare, ang):
    h = 340
    col = price_color(fare.price, cfg, t)
    p.rrect((M, top, W - M, top + h), 32, fill=t.surface_2, outline=col, width=4)
    p.d.ellipse((M + 36, top + 34, M + 116, top + 114), fill=t.accent)
    p.plane(M + 76, top + 74, 30, ang, (255, 255, 255))
    p.text((M + 140, top + 42), label, "extrabold", 44, t.text)
    x = M + 40
    o, d = fare.route.split("-")
    cc = {cfg["route"]["origin"]: "DE", cfg["route"]["destination"]: "MA"}
    fnt = p.font("bold", 34)
    for i, code in enumerate((o, d)):
        if i:
            p.d.text((x + 6, top + 158), "→", font=fnt, fill=t.muted); x += p.tw("→", fnt) + 20
        x += p.flag(cc[code], x, top + 164, 30) + 12
        p.d.text((x, top + 156), cfg.city(code), font=fnt, fill=t.text); x += p.tw(cfg.city(code), fnt) + 10
    p.text((M + 40, top + 222), f"{WOCHENTAGE[fare.day.weekday()]}, {fare.day:%d.%m.%Y}", "bold", 38, t.text)
    p.text((M + 40, top + 274), f"{fare.departure} Uhr · pro Person", "semibold", 30, t.muted)
    p.text((W - M - 36, top + 306), fmt_price(fare.price), "extrabold", 100, col, anchor="rs")

top = 570
if hin: card(top, "Hinflug", hin, -28); top += 360
if rueck: card(top, "Rückflug", rueck, 28); top += 360

# Platz für den Link-Sticker
p.d.rounded_rectangle((M + 120, top + 0, W - M - 120, top + 100), 28, outline=mix(t.background, t.text, 0.45), width=3)
p.d.text((W / 2, top + 50), "Link-Sticker hier", font=p.font("semibold", 30), fill=mix(t.background, t.text, 0.45), anchor="mm")
p.text((W / 2, top + 150), "Zum Buchen: Link antippen → ryanair.com", "bold", 32, t.text, anchor="mm")

# Fuß (oberhalb der unteren Instagram-Leiste)
y = top + 215
p.text((W / 2, y), f"Preise {fmt_checked(now)} – können sich jederzeit ändern.", "semibold", 24, t.muted, anchor="mm")
p.text((W / 2, y + 38), "Basic-Tarif: nur 1 kleine Tasche (40×30×20 cm) inklusive.", "semibold", 24, t.muted, anchor="mm")
p.text((W / 2, y + 76), "Unabhängige Infoseite · keine Verbindung zu Ryanair", "semibold", 24, t.grey, anchor="mm")

out = PROJ / "output" / "facebook_ahora" / f"story_{YY}-{MM:02d}"; out.mkdir(parents=True, exist_ok=True)
p.img.save(out / "story.png")
links = []
if hin: links.append(f"Hinflug: {booking_link(*hin.route.split('-'), hin.day)}")
if rueck: links.append(f"Rückflug: {booking_link(*rueck.route.split('-'), rueck.day)}")
(out / "links.txt").write_text("\n".join(links) + "\n")
print(out); print("\n".join(links))
