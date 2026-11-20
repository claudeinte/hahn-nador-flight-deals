"""Willkommens-Beitrag quadratisch (1080×1080) ohne Kopfzeile – passt ohne Zuschneiden in Instagram."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config
from flightdeals.render.common import Painter, M, W, mix

S = 1080; C = S / 2
cfg = load_config(); p = Painter(cfg); t = p.t
bg = Image.new("RGBA", (S, S), (*t.background, 255))
gl = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse((90, 0, 990, 700), fill=(*t.accent, 55))
bg.alpha_composite(gl.filter(ImageFilter.GaussianBlur(150)))
p.img = bg.convert("RGB"); p.d = ImageDraw.Draw(p.img)

cy = 130
p.d.ellipse((C - 78, cy - 78, C + 78, cy + 78), fill=(255, 255, 255))
p.d.ellipse((C - 72, cy - 72, C + 72, cy + 72), fill=t.accent)
p.plane(C, cy, 92, -35, (255, 255, 255))

p.d.text((C, 272), "WILLKOMMEN!", font=p.font("extrabold", 84), fill=t.text, anchor="mm")
p.d.text((C, 352), "FRANKFURT-HAHN", font=p.font("extrabold", 52), fill=t.text, anchor="mm")
ay = 422
def arrow(x0, x1, y, col):
    d = 1 if x1 > x0 else -1
    p.d.line((x0, y, x1 - d * 20, y), fill=col, width=8)
    p.d.polygon([(x1, y), (x1 - d * 26, y - 15), (x1 - d * 26, y + 15)], fill=col)
arrow(C - 75, C + 75, ay - 14, (255, 255, 255)); arrow(C + 75, C - 75, ay + 14, t.green)
p.flag("DE", C - 200, ay - 24, 48); p.flag("MA", C + 200 - 72, ay - 24, 48)
p.d.text((C, 496), "NADOR", font=p.font("extrabold", 74), fill=t.green, anchor="mm")

items = ["Täglich geprüfte Preise – Hin- und Rückflug", "Preisstürze & neue Tiefstpreise",
         "Flugkalender für jeden Monat", "Stories mit direktem Buchungslink"]
top, rh = 568, 56
p.rrect((M, top, S - M, top + rh * len(items) + 30), 24, fill=mix(t.background, (255, 255, 255), 0.06), outline=t.border, width=2)
for i, txt in enumerate(items):
    y = top + 15 + i * rh + rh / 2
    p.d.ellipse((M + 32, y - 17, M + 66, y + 17), fill=t.green)
    p.d.line([(M + 41, y + 1), (M + 48, y + 8), (M + 59, y - 8)], fill=(255, 255, 255), width=5, joint="curve")
    p.text((M + 86, y), txt, "semibold", 32, t.text, anchor="lm", max_w=S - 2 * M - 110)

y = top + rh * len(items) + 30 + 34
lbl = "Folgen & keine Angebote verpassen!"
f = p.font("extrabold", 36); pw = p.tw(lbl, f) + 60
p.pill((S - pw) / 2, y, lbl, "extrabold", 36, t.background, t.green, pad_x=30, pad_y=14)
p.d.text((C, 1010), "Unabhängige Infoseite · keine Verbindung zu Ryanair · Buchung nur auf ryanair.com",
         font=p.font("medium", 20), fill=t.muted, anchor="mm")
p.d.text((C, 1042), "Preise pro Person im Basic-Tarif, mit Datum und Uhrzeit der Prüfung – können sich jederzeit ändern.",
         font=p.font("medium", 18), fill=t.grey, anchor="mm")

out = PROJ / "output" / "facebook_ahora" / "willkommen"; out.mkdir(parents=True, exist_ok=True)
p.img.crop((0, 0, S, S)).save(out / "willkommen_quadrat.png")
