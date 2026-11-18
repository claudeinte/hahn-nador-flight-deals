"""Gemeinsame Zeichenfunktionen: Schriften, Farben, Kopf- und Fußzeile, Testbanner."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import Config

W, H = 1080, 1350
M = 48  # Seitenrand

WEIGHTS = {"regular": "Inter-Regular.ttf", "medium": "Inter-Medium.ttf", "semibold": "Inter-SemiBold.ttf",
           "bold": "Inter-Bold.ttf", "extrabold": "Inter-ExtraBold.ttf"}


def hex2rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


class Theme:
    def __init__(self, cfg: Config):
        for k, v in cfg["theme"].items():
            setattr(self, k, hex2rgb(v))


class Painter:
    """Kapselt Bild, Zeichenfläche, Schriften und Theme."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.t = Theme(cfg)
        self.img = Image.new("RGB", (W, H), self.t.background)
        self.d = ImageDraw.Draw(self.img)
        self.fonts_dir = cfg.fonts_dir

    def font(self, weight: str, size: int) -> ImageFont.FreeTypeFont:
        return _font(str(self.fonts_dir / WEIGHTS[weight]), size)

    def tw(self, text: str, font) -> int:
        return int(self.d.textlength(text, font=font))

    def fit(self, text: str, weight: str, size: int, max_w: int, min_size: int = 12):
        while size > min_size and self.tw(text, self.font(weight, size)) > max_w:
            size -= 1
        return self.font(weight, size)

    def text(self, xy, text, weight, size, fill, anchor="la", max_w: int | None = None):
        f = self.fit(text, weight, size, max_w) if max_w else self.font(weight, size)
        self.d.text(xy, text, font=f, fill=fill, anchor=anchor)
        return f

    def rrect(self, box, r, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

    def pill(self, x, y, text, weight, size, fg, bg, pad_x=18, pad_y=10, anchor_right=False):
        f = self.font(weight, size)
        w = self.tw(text, f)
        h = size + pad_y * 2
        x0 = x - w - pad_x * 2 if anchor_right else x
        self.rrect((x0, y, x0 + w + pad_x * 2, y + h), h // 2, fill=bg)
        self.d.text((x0 + pad_x, y + h / 2), text, font=f, fill=fg, anchor="lm")
        return x0, x0 + w + pad_x * 2, y + h

    def wrap(self, text: str, font, max_w: int) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = f"{cur} {w}".strip()
            if self.tw(test, font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def paragraph(self, x, y, text, weight, size, fill, max_w, line_gap=6) -> int:
        f = self.font(weight, size)
        for line in self.wrap(text, f, max_w):
            self.d.text((x, y), line, font=f, fill=fill)
            y += size + line_gap
        return y

    # --- wiederkehrende Elemente -------------------------------------------------
    def header(self):
        t = self.t
        label = self.cfg["page"].get("badge", "Unabhängige Infoseite")
        f = self.font("semibold", 18)
        bw = self.tw(label, f) + 32
        self.text((M, 40), self.cfg["page"]["name"], "semibold", 24, t.muted, max_w=W - 2 * M - bw - 20)
        # neutrales Etikett (kein Airline-Logo, damit nichts wie ein offizieller Ryanair-Beitrag aussieht)
        self.rrect((W - M - bw, 34, W - M, 70), 18, outline=t.border, width=2)
        self.d.text((W - M - bw / 2, 52), label, font=f, fill=t.muted, anchor="mm")

    def footer(self, lines: list[tuple[str, tuple]], size: int = 17, bottom: int = H - 26) -> int:
        """Zeichnet Zeilen (Text, Farbe) von unten nach oben; gibt die oberste y-Position zurück."""
        f = self.font("medium", size)
        wrapped = []
        for text, color in lines:
            for line in self.wrap(text, f, W - 2 * M):
                wrapped.append((line, color))
        y = bottom - len(wrapped) * (size + 7)
        top = y
        for line, color in wrapped:
            self.d.text((M, y), line, font=f, fill=color)
            y += size + 7
        return top

    def plane(self, cx: float, cy: float, size: float, angle: float, color: tuple):
        """Flugzeug-Symbol (Silhouette, Nase nach rechts). angle in Grad: negativ = steigt (Hinflug),
        positiv = sinkt (Rückflug). Wird 4-fach vergrößert gezeichnet und verkleinert (glatte Kanten)."""
        k = 4
        s = int(size * k)
        layer = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        parts = [
            [(-1.0, -0.10), (0.70, -0.10), (1.0, 0.0), (0.70, 0.10), (-1.0, 0.10)],          # Rumpf
            [(0.15, -0.06), (-0.30, -0.95), (-0.48, -0.95), (-0.20, -0.06)],                 # Flügel oben
            [(0.15, 0.06), (-0.30, 0.95), (-0.48, 0.95), (-0.20, 0.06)],                      # Flügel unten
            [(-0.70, -0.06), (-0.92, -0.42), (-1.02, -0.42), (-0.90, -0.06)],                 # Leitwerk oben
            [(-0.70, 0.06), (-0.92, 0.42), (-1.02, 0.42), (-0.90, 0.06)],                     # Leitwerk unten
        ]
        a = math.radians(angle)
        ca, sa = math.cos(a), math.sin(a)
        for poly in parts:
            pts = [(s + (x * ca - y * sa) * s * 0.5, s + (x * sa + y * ca) * s * 0.5) for x, y in poly]
            d.polygon(pts, fill=(*color, 255))
        layer = layer.resize((int(size * 2), int(size * 2)), Image.LANCZOS)
        self.img.paste(layer, (int(cx - size), int(cy - size)), layer)
        self.d = ImageDraw.Draw(self.img)

    def flag(self, country: str, x: float, y: float, h: int) -> int:
        """Zeichnet eine kleine Flagge (DE oder MA) mit Oberkante y. Gibt die Breite zurück."""
        k = 4
        w = int(h * (5 / 3 if country == "DE" else 3 / 2))
        layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        W_, H_ = w * k, h * k
        if country == "DE":
            for i, col in enumerate(((0, 0, 0), (221, 0, 0), (255, 206, 0))):
                d.rectangle((0, i * H_ / 3, W_, (i + 1) * H_ / 3), fill=col)
        else:  # MA: rot mit grünem Pentagramm
            d.rectangle((0, 0, W_, H_), fill=(193, 39, 45))
            cx, cy, r = W_ / 2, H_ / 2, H_ * 0.30
            pts = [(cx + r * math.sin(math.radians(i * 72)), cy - r * math.cos(math.radians(i * 72))) for i in range(5)]
            for i in range(5):
                d.line((pts[i], pts[(i + 2) % 5]), fill=(0, 98, 51), width=max(3, int(H_ * 0.07)))
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W_ - 1, H_ - 1), radius=3 * k, fill=255)
        layer.putalpha(mask)
        layer = layer.resize((w, h), Image.LANCZOS)
        self.img.paste(layer, (int(x), int(y)), layer)
        self.d = ImageDraw.Draw(self.img)
        return w

    def info_strip(self, bottom: int) -> int:
        """Hervorgehobene Hinweis-Leiste (Ryanair / Buchung über Link im Beitrag). Gibt die Oberkante zurück."""
        t = self.t
        text = self.cfg["page"]["booking_hint"]
        f = self.font("semibold", 19)
        lines = self.wrap(text, f, W - 2 * M - 86)
        h = 26 + len(lines) * 27
        top = bottom - h
        self.rrect((M, top, W - M, bottom), 14, fill=mix(t.background, t.accent, 0.14), outline=mix(t.background, t.accent, 0.5))
        cx, cy = M + 32, top + h / 2                     # Info-Symbol (Kreis mit "i")
        self.d.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), outline=t.accent, width=3)
        self.d.text((cx, cy + 1), "i", font=self.font("extrabold", 20), fill=t.accent, anchor="mm")
        y = top + 13
        for line in lines:
            self.d.text((M + 62, y), line, font=f, fill=t.text)
            y += 27
        return top

    def test_banner(self):
        t = self.t
        self.d.rectangle((0, 0, W, 22), fill=t.test_banner)
        self.d.text((W / 2, 11), "TESTDATEN – NUR BEISPIEL", font=self.font("extrabold", 15), fill=t.background, anchor="mm")
        # diagonales Wasserzeichen
        mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        md = ImageDraw.Draw(mark)
        md.text((W / 2, H / 2), "TESTDATEN", font=self.font("extrabold", 150), fill=(*t.test_banner, 20), anchor="mm")
        mark = mark.rotate(32, resample=Image.BICUBIC)
        self.img.paste(mark, (0, 0), mark)
        self.d = ImageDraw.Draw(self.img)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(path, "PNG", optimize=True)


@lru_cache(maxsize=256)
def _font(path: str, size: int):
    return ImageFont.truetype(path, size)


def price_color(price: float, cfg: Config, t: Theme) -> tuple:
    c = cfg["price_colors"]
    if price < c["green_below"]:
        return t.green
    if price < c["yellow_below"]:
        return t.yellow
    if price <= c["orange_up_to"]:
        return t.orange
    return t.red
