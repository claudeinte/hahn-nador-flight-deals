"""Willkommens-Beitrag (1080×1350, ohne Preise – veraltet nie) + Text für Instagram/Facebook."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config
from flightdeals.render.common import Painter, M, W, H, mix

cfg = load_config(); cfg["page"]["news_banner"] = False      # ohne Datum: Beitrag bleibt gültig
cfg["page"]["booking_hint"] = "Alle Flüge werden von Ryanair durchgeführt. Gebucht wird nur auf ryanair.com – wir verkaufen keine Tickets."
p = Painter(cfg); t = p.t; C = W / 2
bg = Image.new("RGBA", (W, H), (*t.background, 255))
gl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse((90, 60, 990, 820), fill=(*t.accent, 55))
bg.alpha_composite(gl.filter(ImageFilter.GaussianBlur(150)))
p.img = bg.convert("RGB"); p.d = ImageDraw.Draw(p.img)
p.header()

# Logo (wie Profilbild)
cy = 215
p.d.ellipse((C - 92, cy - 92, C + 92, cy + 92), fill=(255, 255, 255))
p.d.ellipse((C - 85, cy - 85, C + 85, cy + 85), fill=t.accent)
p.plane(C, cy, 108, -35, (255, 255, 255))

p.d.text((C, 380), "WILLKOMMEN!", font=p.font("extrabold", 92), fill=t.text, anchor="mm")
p.d.text((C, 470), "FRANKFURT-HAHN", font=p.font("extrabold", 56), fill=t.text, anchor="mm")
ay = 548
def arrow(x0, x1, y, col):
    d = 1 if x1 > x0 else -1
    p.d.line((x0, y, x1 - d * 20, y), fill=col, width=8)
    p.d.polygon([(x1, y), (x1 - d * 26, y - 15), (x1 - d * 26, y + 15)], fill=col)
arrow(C - 75, C + 75, ay - 15, (255, 255, 255)); arrow(C + 75, C - 75, ay + 15, t.green)
p.flag("DE", C - 200, ay - 25, 50); p.flag("MA", C + 200 - 75, ay - 25, 50)
p.d.text((C, 628), "NADOR", font=p.font("extrabold", 80), fill=t.green, anchor="mm")

# Was es hier gibt
items = ["Täglich geprüfte Preise – Hin- und Rückflug",
         "Preisstürze & neue Tiefstpreise",
         "Flugkalender für jeden Monat",
         "Stories mit direktem Buchungslink"]
top = 720
p.rrect((M, top, W - M, top + 62 * len(items) + 40), 26, fill=mix(t.background, (255, 255, 255), 0.06), outline=t.border, width=2)
for i, txt in enumerate(items):
    y = top + 30 + i * 62 + 22
    p.d.ellipse((M + 34, y - 18, M + 70, y + 18), fill=t.green)
    p.d.line([(M + 43, y + 1), (M + 50, y + 9), (M + 62, y - 8)], fill=(255, 255, 255), width=5, joint="curve")
    p.text((M + 92, y), txt, "semibold", 34, t.text, anchor="lm", max_w=W - 2 * M - 120)

y = top + 62 * len(items) + 40 + 50
lbl = "Folgen & keine Angebote verpassen!"
f = p.font("extrabold", 38); pw = p.tw(lbl, f) + 64
p.pill((W - pw) / 2, y, lbl, "extrabold", 38, t.background, t.green, pad_x=32, pad_y=16)

ft = p.footer([("Alle Preise pro Person im Basic-Tarif, immer mit Datum und Uhrzeit der Prüfung.", t.muted),
               (cfg["page"]["disclaimer"], t.grey)], size=17)
p.info_strip(ft - 12)

out = PROJ / "output" / "facebook_ahora" / "willkommen"; out.mkdir(parents=True, exist_ok=True)
p.img.save(out / "willkommen.png")
txt = f"""👋 Willkommen bei Frankfurt-Hahn ⇄ Nador 🇩🇪🇲🇦✈️

Du fliegst regelmäßig in die Heimat oder besuchst Familie in Nador? Hier findest du die günstigsten Flüge zwischen Frankfurt-Hahn und Nador – einfach und übersichtlich.

✅ Täglich geprüfte Preise – Hin- und Rückflug
📉 Preisstürze & neue Tiefstpreise
📅 Flugkalender für jeden Monat
📲 Stories mit direktem Buchungslink

Alle Preise sind pro Person im Basic-Tarif und werden mit Datum und Uhrzeit der Prüfung angegeben – denn Flugpreise können sich jederzeit ändern.

🔔 Folge uns, damit du kein Angebot verpasst, und teile die Seite mit Familie und Freunden!

{cfg['page']['like_cta']}

ℹ️ {cfg['page']['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich auf ryanair.com.

{cfg['page']['hashtags']} #Marokko #Heimaturlaub #MarokkanerInDeutschland #FlügeNachMarokko
"""
(out / "beitrag.txt").write_text(txt); print(txt)
