"""Profilbild für Instagram/Facebook (1080×1080, kreis-sicher): Hahn ✈ Nador im Seitenstil."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config
from flightdeals.render import photo_alert as pa
from flightdeals.render.common import Painter, W, mix

cfg = load_config(); p = Painter(cfg); t = p.t
S = 1080
# Hintergrund: dunkler Verlauf mit leichtem blauen Schein in der Mitte
bg = Image.new("RGB", (W, p.img.height), t.background)
glow = Image.new("RGBA", bg.size, (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
g.ellipse((140, 120, 940, 920), fill=(*t.accent, 60))
bg = bg.convert("RGBA"); bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
p.img.paste(bg.convert("RGB")); p.d = ImageDraw.Draw(p.img)

# Flugbogen (gleicher Stil wie NEUER TIEFSTPREIS)
left, right = (240, 400), (840, 400)
pa._arc(p, left, right, 60)
# Flaggen unter Start und Ziel
for (x, y), c in ((left, "DE"), (right, "MA")):
    p.flag(c, x - 42, y + 34, 56)

f = p.font("extrabold", 150)
p.d.text((S / 2, 625), "HAHN", font=f, fill=t.text, anchor="mm")
p.d.text((S / 2, 780), "NADOR", font=f, fill=t.green, anchor="mm")
p.d.text((S / 2, 890), "GÜNSTIGE FLÜGE", font=p.font("bold", 46), fill=t.muted, anchor="mm")

out = PROJ / "output" / "perfil"; out.mkdir(parents=True, exist_ok=True)
img = p.img.crop((0, 0, S, S))
img.save(out / "profilbild.png")
# Vorschau mit Kreis-Maske (so sieht es auf Instagram aus)
m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).ellipse((0, 0, S, S), fill=255)
prev = Image.new("RGB", (S, S), (255, 255, 255)); prev.paste(img, (0, 0), m)
prev.resize((360, 360), Image.LANCZOS).save(out / "vorschau_kreis.png")
print(out)
