"""Profilbild für Instagram/Facebook (1080×1080, kreis-sicher):
Flugzeug-Logo, FRANKFURT-HAHN ⇄ NADOR mit Hin- und Rückflug-Pfeil und Flaggen."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
PROJ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(PROJ / "src"))
from flightdeals.config import load_config
from flightdeals.render.common import Painter

cfg = load_config(); p = Painter(cfg); t = p.t
S, C = 1080, 540
bg = Image.new("RGB", p.img.size, t.background).convert("RGBA")
glow = Image.new("RGBA", bg.size, (0, 0, 0, 0)); ImageDraw.Draw(glow).ellipse((140, 120, 940, 920), fill=(*t.accent, 60))
bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
p.img.paste(bg.convert("RGB")); p.d = ImageDraw.Draw(p.img)

# Flugzeug-Logo
cy = 255
p.d.ellipse((C - 128, cy - 128, C + 128, cy + 128), fill=(255, 255, 255))
p.d.ellipse((C - 118, cy - 118, C + 118, cy + 118), fill=t.accent)
p.plane(C, cy, 150, -35, (255, 255, 255))

# Städte
p.d.text((C, 480), "FRANKFURT-HAHN", font=p.font("extrabold", 86), fill=t.text, anchor="mm")
p.d.text((C, 735), "NADOR", font=p.font("extrabold", 132), fill=t.green, anchor="mm")

# Flaggen + Hin- und Rückflug-Pfeil (⇄) dazwischen
ay = 607
def arrow(x0, x1, y, col):
    d = 1 if x1 > x0 else -1
    p.d.line((x0, y, x1 - d * 26, y), fill=col, width=10)
    p.d.polygon([(x1, y), (x1 - d * 34, y - 20), (x1 - d * 34, y + 20)], fill=col)
arrow(C - 95, C + 95, ay - 20, (255, 255, 255))      # Hinflug →
arrow(C + 95, C - 95, ay + 20, t.green)              # Rückflug ←
p.flag("DE", C - 245, ay - 32, 64)
p.flag("MA", C + 245 - 96, ay - 32, 64)

p.d.text((C, 855), "GÜNSTIGE FLÜGE", font=p.font("bold", 48), fill=t.muted, anchor="mm")

out = PROJ / "output" / "perfil"; out.mkdir(parents=True, exist_ok=True)
img = p.img.crop((0, 0, S, S)); img.save(out / "profilbild.png")
m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).ellipse((0, 0, S, S), fill=255)
prev = Image.new("RGB", (S, S), (255, 255, 255)); prev.paste(img, (0, 0), m)
prev.resize((360, 360), Image.LANCZOS).save(out / "vorschau_kreis.png")
prev.resize((110, 110), Image.LANCZOS).save(out / "vorschau_klein.png")
