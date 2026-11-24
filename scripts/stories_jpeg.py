"""Convierte las stories PNG del día en JPEG para Instagram (public/<datum>/)."""
import pathlib
import sys

from PIL import Image

d = sys.argv[1]
pathlib.Path(f"public/{d}").mkdir(parents=True, exist_ok=True)
src = sorted(f for f in pathlib.Path(f"output/stories/{d}").glob("[0-9][0-9]_*.png") if not f.name.startswith("00_"))
n = int(pathlib.Path(f"output/stories/{d}/anzahl.txt").read_text().strip())
assert len(src) == n, f"{len(src)} Bilder statt {n}"
for f in src:
    # Qualität 95 und ohne Farb-Unterabtastung (4:4:4) → Schrift bleibt scharf, auch farbige Preise
    Image.open(f).convert("RGB").save(f"public/{d}/{f.stem}.jpg", "JPEG", quality=95, subsampling=0, optimize=True)
print("JPEG:", [f.stem for f in src])
