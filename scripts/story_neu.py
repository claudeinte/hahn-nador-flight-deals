"""Fünf Zusatz-Stories (1080×1920) im Stil der Sonder-Stories, jede mit eigenem Hintergrund
(Nutzerwunsch 23.11.2026, Reihenfolge siehe vorschau_story_kalender.main_alle):
Top 5 günstigste Hinflüge, Top 5 günstigste Rückflüge, günstigster Hinflug für Familien (2–6 Personen),
günstigster Rückflug für Familien, günstigstes Hin & Zurück für Familien.
Bei Hin-/Rückflug zeigen Flugzeug, Pfeil und Deko-Flugzeuge immer in Flugrichtung
(Frankfurt-Hahn links, Nador rechts).

Wird von vorschau_story_kalender.py benutzt: setup(sys.modules[__name__]) übergibt dessen Hilfsfunktionen."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from flightdeals.render.common import Painter
from flightdeals.texts import WOCHENTAGE, fmt_price

sk = None
W = H = PAD = HH = OFF = GOLD = None


def setup(module):
    global sk, W, H, PAD, HH, OFF, GOLD
    sk = module
    W, H, PAD, HH, OFF, GOLD = sk.W, sk.H, sk.PAD, sk.HH, sk.OFF, sk.GOLD


# Neue Hintergründe (Kopf oben, unten, Körper c0→c1→c2, Glow, Deko-Art)
THEMES = {
    "tuerkis": dict(head=((70, 200, 205), (22, 104, 140)), body=((22, 104, 140), (12, 54, 82), (4, 18, 32)),
                    glow=(80, 220, 230, 46), deco="wellen"),
    "violett": dict(head=((168, 120, 230), (82, 46, 150)), body=((82, 46, 150), (40, 22, 86), (12, 6, 30)),
                    glow=(190, 140, 255, 44), deco="sterne"),
    "koralle": dict(head=((255, 150, 120), (196, 70, 110)), body=((196, 70, 110), (84, 28, 70), (22, 8, 28)),
                    glow=(255, 140, 140, 44), deco="herzen"),
    "polar": dict(head=((40, 60, 110), (20, 110, 120)), body=((20, 110, 120), (14, 46, 74), (4, 12, 26)),
                  glow=(90, 255, 200, 40), deco="aurora"),
    "bernstein": dict(head=((255, 176, 70), (200, 96, 30)), body=((200, 96, 30), (92, 40, 22), (24, 10, 8)),
                      glow=(255, 180, 80, 46), deco="sonne"),
}


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def header(deco, th, seed):
    dd = ImageDraw.Draw(deco)
    top, bot = th["head"]
    hgt = deco.size[1]
    for y in range(hgt):
        dd.line((0, y, W, y), fill=(*lerp(top, bot, y / hgt), 255))
    rnd = random.Random(seed)
    kind = th["deco"]
    if kind == "wellen":
        for k in range(3):
            pts = [(x, hgt - 30 - k * 26 + 10 * math.sin(x / 70 + k)) for x in range(0, W + 20, 20)]
            dd.line(pts, fill=(255, 255, 255, 90 - k * 22), width=4)
        for _ in range(26):
            x, y = rnd.randint(0, W), rnd.randint(6, hgt - 60)
            dd.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255, rnd.randint(120, 220)))
    elif kind == "sterne":
        for _ in range(70):
            x, y = rnd.randint(0, W), rnd.randint(4, hgt - 8)
            r = rnd.choice((1.4, 1.8, 2.4))
            dd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.randint(120, 240)))
        dd.ellipse((W - 150, 18, W - 80, 88), fill=(250, 240, 210, 255))
        dd.ellipse((W - 128, 10, W - 66, 72), fill=(*top, 255))
    elif kind == "herzen":
        for _ in range(22):
            x, y, s = rnd.randint(0, W), rnd.randint(10, hgt - 20), rnd.choice((7, 9, 12))
            col = (255, 235, 235, rnd.randint(130, 220))
            dd.ellipse((x - s, y - s, x, y), fill=col)
            dd.ellipse((x, y - s, x + s, y), fill=col)
            dd.polygon([(x - s, y - s / 2), (x + s, y - s / 2), (x, y + s)], fill=col)
    elif kind == "aurora":
        lay = Image.new("RGBA", deco.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        for k, col in enumerate(((90, 255, 190, 120), (120, 200, 255, 90), (190, 130, 255, 80))):
            pts = [(x, 40 + k * 28 + 22 * math.sin(x / 120 + k * 1.7)) for x in range(-20, W + 40, 20)]
            ld.line(pts, fill=col, width=26)
        deco.alpha_composite(lay.filter(ImageFilter.GaussianBlur(14)))
        dd = ImageDraw.Draw(deco)
        for _ in range(50):
            x, y = rnd.randint(0, W), rnd.randint(4, hgt - 8)
            dd.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, rnd.randint(110, 220)))
    elif kind == "sonne":
        glow = Image.new("RGBA", deco.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((W - 240, -90, W + 40, 190), fill=(255, 240, 170, 150))
        deco.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        dd = ImageDraw.Draw(deco)
        dd.ellipse((W - 150, 14, W - 60, 104), fill=(255, 236, 150, 255))
        for i in range(12):
            a = math.radians(i * 30)
            cx, cy = W - 105, 59
            dd.line((cx + 58 * math.cos(a), cy + 58 * math.sin(a), cx + 78 * math.cos(a), cy + 78 * math.sin(a)),
                    fill=(255, 236, 150, 230), width=4)


def body(th, seed, rueck=False):
    c0, c1, c2 = th["body"]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        if y < HH:
            col = c0
        else:
            u = (y - HH) / (H - HH)
            col = lerp(c0, c1, u / 0.35) if u < 0.35 else lerp(c1, c2, (u - 0.35) / 0.65)
        d.line((0, y, W, y), fill=col)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    rnd = random.Random(seed)
    for _ in range(90):
        x, y = rnd.randint(0, W), rnd.randint(HH, H)
        r_ = rnd.choice((1.2, 1.6, 2.2))
        ld.ellipse((x - r_, y - r_, x + r_, y + r_), fill=(255, 255, 255, rnd.randint(40, 120)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((60, 520, 1020, 1500), fill=th["glow"])
    lay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(150)))
    planes = [(170, 1850, 8, 1.0), (1000, 1886, -6, 0.8)]
    if rueck:                                              # Rückflug: Deko-Flugzeuge fliegen nach links
        planes = [(W - x, y, 180 - ang, sc) for x, y, ang, sc in planes]
    for x, y, ang, sc in planes:
        a = math.radians(ang)
        L = 400 * sc
        for k in range(30):
            t0, t1 = k / 30, (k + 1) / 30
            ld.line((x - L * (1 - t0) * math.cos(a), y - L * (1 - t0) * math.sin(a),
                     x - L * (1 - t1) * math.cos(a), y - L * (1 - t1) * math.sin(a)),
                    fill=(255, 255, 255, int(12 + 100 * t1)), width=max(2, int(7 * sc * t1)))
    base = img.convert("RGBA")
    base.alpha_composite(lay)
    return base.convert("RGB"), planes



def route_marks_dir(p, rueck):
    """Kopfzeile wie sk._route_marks, aber nur EINE Richtung: Hin (FRA-Hahn -> Nador) oder Rück (Nador -> FRA-Hahn).
    Kondensstreifen hinter dem Flugzeug, gestrichelte Linie + Pfeilspitze zum Ziel, grüner Punkt = Ziel, blauer = Start."""
    t = p.t
    f = p.font("extrabold", 40)
    y = sk.ARC_Y
    xf = 24
    xf += p.flag("DE", xf, y - 17, 34) + 12
    for dx in (3, 0):
        p.d.text((xf + dx, y + dx), "Frankfurt-Hahn", font=f, fill=(0, 0, 0) if dx else (255, 255, 255), anchor="lm")
    a0 = xf + p.tw("Frankfurt-Hahn", f) + 26
    xr_flag = W - 24 - 51
    p.flag("MA", xr_flag, y - 17, 34)
    xn = xr_flag - 12 - p.tw("Nador", f)
    for dx in (3, 0):
        p.d.text((xn + dx, y + dx), "Nador", font=f, fill=(0, 0, 0) if dx else (255, 255, 255), anchor="lm")
    a1 = xn - 26
    start, end = (a1, a0) if rueck else (a0, a1)          # u=0 Start, u=1 Ziel
    B = lambda u: (start + (end - start) * u, y - 58 * math.sin(math.pi * u))
    lay = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    span = abs(end - start)
    u_tail = 0.5 - 100 / span                              # hier endet der Rumpf hinten / beginnt vorne
    u_nose = 0.5 + 100 / span
    n = 50
    for i in range(n):                                     # Kondensstreifen Start -> Heck
        u0, u1 = u_tail * i / n, u_tail * (i + 1) / n
        k = (i + 1) / n
        ld.line((B(u0), B(u1)), fill=(255, 255, 255, int(60 + 195 * k)), width=int(3 + 6 * k))
    u = u_nose
    while u < 0.955:                                       # gestrichelt Nase -> Ziel (bis in die Pfeilspitze)
        ld.line((B(u), B(min(u + 0.04, 0.955))), fill=(255, 255, 255, 235), width=5)
        u += 0.075
    base = p.img.convert("RGBA")
    base.alpha_composite(lay.filter(ImageFilter.GaussianBlur(4)))
    base.alpha_composite(lay)
    p.img = base.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    (tx, ty), (bx, by) = B(0.995), B(0.93)                 # Pfeilspitze am Ziel
    a = math.atan2(ty - by, tx - bx)
    Lh, Wh = 26, 15
    pts = [(tx, ty), (tx - Lh * math.cos(a) + Wh * math.sin(a), ty - Lh * math.sin(a) - Wh * math.cos(a)),
           (tx - Lh * math.cos(a) - Wh * math.sin(a), ty - Lh * math.sin(a) + Wh * math.cos(a))]
    p.d.polygon([(x_ + 2, y_ + 2) for x_, y_ in pts], fill=(0, 0, 0))
    p.d.polygon(pts, fill=t.green, outline=(255, 255, 255), width=2)
    sx = start
    p.d.ellipse((sx - 11, y - 11, sx + 11, y + 11), fill=t.accent, outline=(255, 255, 255), width=3)
    (px, _) = B(0.5)
    end_y = B(u_tail)[1]                                   # Höhe des Bogens an Heck und Nase
    p.img = sk.draw_airliner_side(p.img, px, end_y - 6, 220, 0, flip=rueck)   # Rumpfmitte liegt ~6 px unter dem Ankerpunkt
    p.d = ImageDraw.Draw(p.img)

def frame(cfg, now, title, subtitle, theme, seed, richtung=None, title2=None):
    th = THEMES[theme]
    p = Painter(cfg)
    img, planes = body(th, seed, richtung == "rueck")
    deco = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
    header(deco, th, seed)
    img.paste(deco, (0, 0), deco)
    p.img = img
    p.d = ImageDraw.Draw(p.img)
    for x_, y_, a_, sc_ in planes:
        p.plane(x_, y_, int(44 * sc_), a_, (255, 255, 255))
    if richtung is None:
        sk._route_marks(p)
    else:
        route_marks_dir(p, richtung == "rueck")
    ftt = p.fit(title, "extrabold", 112, W - 2 * PAD)
    ty = 212 + OFF - (12 if title2 else 0)
    p.d.text((W / 2 + 3, ty + 3), title, font=ftt, fill=(0, 0, 0), anchor="mm")
    p.d.text((W / 2, ty), title, font=ftt, fill=(255, 255, 255), anchor="mm")
    dy = 0
    if title2:                                             # zweite, goldene Titelzeile (z. B. „PRO PERSON“)
        f2 = p.font("extrabold", 58)
        p.d.text((W / 2 + 3, ty + 81), title2, font=f2, fill=(0, 0, 0), anchor="mm")
        p.d.text((W / 2, ty + 78), title2, font=f2, fill=GOLD, anchor="mm")
        dy = 50
    chk = f"Preise bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr"
    p.d.text((W / 2, 292 + OFF - 4 + dy), chk, font=p.fit(chk, "bold", 30, W - 2 * PAD - 8), fill=(232, 238, 246), anchor="mm")
    p.d.text((W / 2, 336 + OFF - 6 + dy), subtitle, font=p.fit(subtitle, "bold", 27, W - 2 * PAD - 8), fill=(205, 215, 232), anchor="mm")
    return p


def glass(p, top, h, outline):
    x0, y0, x1, y1 = int(PAD), int(top), int(W - PAD), int(top + h)
    reg = p.img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(14)).convert("RGBA")
    reg.alpha_composite(Image.new("RGBA", reg.size, (10, 18, 40, 175)))
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, reg.width - 1, reg.height - 1), 22, fill=255)
    p.img.paste(reg.convert("RGB"), (x0, y0), m)
    p.d = ImageDraw.Draw(p.img)
    p.d.rounded_rectangle((PAD, top, W - PAD, top + h), 22, outline=outline, width=4)


def pill(p, x, y, text):
    f = p.font("extrabold", 32)
    w = p.tw(text, f) + 40
    p.d.rounded_rectangle((x + 3, y + 3, x + w + 3, y + 55), 26, fill=(0, 0, 0))
    p.d.rounded_rectangle((x, y, x + w, y + 52), 26, fill=GOLD, outline=(255, 255, 255), width=3)
    p.d.text((x + 20, y + 26), text, font=f, fill=(40, 28, 6), anchor="lm")


def flight_line(p, x, y, f, rueck):
    p.d.ellipse((x, y - 19, x + 38, y + 19), fill=p.t.accent)
    p.plane(x + 19, y, 15, 198 if rueck else -18, (255, 255, 255))
    rt = "Rückflug · Nador → Frankfurt-Hahn" if rueck else "Hinflug · Frankfurt-Hahn → Nador"
    p.d.text((x + 52, y - 20), rt, font=p.font("bold", 22), fill=(178, 194, 214), anchor="lm")
    dt = f"{WOCHENTAGE[f.day.weekday()][:2]}, {f.day:%d.%m.%Y} · {f.departure}"
    fdt = p.font("bold", 29)
    p.d.text((x + 52, y + 14), dt, font=fdt, fill=(235, 242, 250), anchor="lm")
    return x + 52 + p.tw(dt, fdt)


def cards_area(n, gap=14, y0=410):
    y1 = 1688
    return y0, (y1 - y0 - gap * (n - 1)) / n, gap


def render_familie(cfg, now, f, rueck, theme, seed):
    title = "GÜNSTIGSTER RÜCKFLUG FÜR FAMILIEN" if rueck else "GÜNSTIGSTER HINFLUG FÜR FAMILIEN"
    sub = ("Nador → Frankfurt-Hahn" if rueck else "Frankfurt-Hahn → Nador") + \
        f" · billigster Flug der nächsten {sk.N_MONATE} Monate · Gesamtpreis für 2 bis 6 Personen"
    p = frame(cfg, now, title, sub, theme, seed, "rueck" if rueck else "hin")
    y0, h, gap = cards_area(5)
    for i, n in enumerate(range(2, 7)):
        top = y0 + i * (h + gap)
        glass(p, top, h, (120, 140, 170))
        pill(p, PAD + 26, top + 22, f"{n} Personen")
        flight_line(p, PAD + 26, top + h * 0.68, f, rueck)
        p.d.text((W - PAD - 26, top + h / 2 - 14), fmt_price(round(f.price * n, 2)), font=p.font("extrabold", 62),
                 fill=GOLD, anchor="rm")
        p.d.text((W - PAD - 26, top + h / 2 + 38), f"{n} × {fmt_price(f.price)}", font=p.font("bold", 24),
                 fill=(190, 205, 225), anchor="rm")
    sk._footer(p, "Gesamtpreis = Preis pro Person × Personen (Basic-Tarif) · Buchung nur auf ryanair.com")
    return p.img


def render_kombi_familie(cfg, now, o, r, theme, seed):
    nights = (r.day - o.day).days
    pp = o.price + r.price
    p = frame(cfg, now, "GÜNSTIGSTES HIN & ZURÜCK FÜR FAMILIEN",
              f"Billigste Kombination Hin- und Rückflug · {nights} Nächte in Nador · Gesamtpreis für 2 bis 6 Personen", theme, seed)
    y0, h, gap = cards_area(5)
    for i, n in enumerate(range(2, 7)):
        top = y0 + i * (h + gap)
        glass(p, top, h, (120, 140, 170))
        pill(p, PAD + 26, top + 18, f"{n} Personen")
        p.d.text((PAD + 26 + p.tw(f"{n} Personen", p.font("extrabold", 32)) + 60, top + 44),
                 f"{nights} Nächte", font=p.font("bold", 26), fill=(235, 242, 250), anchor="lm")
        x = PAD + 26
        for k, (f, rueck) in enumerate(((o, False), (r, True))):
            yy = top + h * 0.56 + k * h * 0.27
            p.d.ellipse((x, yy - 15, x + 30, yy + 15), fill=p.t.accent)
            p.plane(x + 15, yy, 12, 198 if rueck else -18, (255, 255, 255))
            dt = f"{'Rück' if rueck else 'Hin'}: {WOCHENTAGE[f.day.weekday()][:2]}, {f.day:%d.%m.%Y} · {f.departure}"
            p.d.text((x + 42, yy), dt, font=p.font("bold", 25), fill=(235, 242, 250), anchor="lm")
        p.d.text((W - PAD - 26, top + h / 2 - 14), fmt_price(round(pp * n, 2)), font=p.font("extrabold", 62),
                 fill=GOLD, anchor="rm")
        p.d.text((W - PAD - 26, top + h / 2 + 38), f"{n} × {fmt_price(pp)} hin & zurück", font=p.font("bold", 23),
                 fill=(190, 205, 225), anchor="rm")
    sk._footer(p)
    return p.img


def render_top5(cfg, now, fares, rueck, theme, seed):
    title = "TOP 5 GÜNSTIGSTE RÜCKFLÜGE" if rueck else "TOP 5 GÜNSTIGSTE HINFLÜGE"
    sub = ("Die billigsten Rückflüge Nador → Frankfurt-Hahn" if rueck else
           "Die billigsten Hinflüge Frankfurt-Hahn → Nador") + f" · alle Flüge der nächsten {sk.N_MONATE} Monate verglichen"
    p = frame(cfg, now, title, sub, theme, seed, "rueck" if rueck else "hin", title2="PRO PERSON")
    fpath = str(cfg.fonts_dir / "Inter-ExtraBold.ttf")
    y0, h, gap = cards_area(5, y0=460)
    for i, f in enumerate(fares[:5]):
        top = y0 + i * (h + gap)
        col = sk.MEDALS[i + 1][1] if i < 3 else (70, 90, 118)
        glass(p, top, h, col)
        sk._rank_badge(p, PAD + 60, top + h / 2 + 4, 34, i + 1, fpath)
        flight_line(p, PAD + 118, top + h / 2, f, rueck)
        p.d.text((W - PAD - 26, top + h / 2 - 12), fmt_price(f.price), font=p.font("extrabold", 62),
                 fill=GOLD if i < 3 else (255, 255, 255), anchor="rm")
        p.d.text((W - PAD - 26, top + h / 2 + 38), "pro Person", font=p.font("bold", 23), fill=(190, 205, 225), anchor="rm")
    sk._footer(p, "Preise pro Person (Basic-Tarif) · nur Hin- oder Rückflug · Buchung nur auf ryanair.com")
    return p.img


def render_neue(cfg, snap, now):
    """Liefert die fünf Zusatz-Stories als Liste (name, Bild) in der freigegebenen Reihenfolge."""
    today = now.date()
    outs = sorted(sk._future(snap, cfg, cfg.route_out, today), key=lambda f: (f.price, f.day))
    rets = sorted(sk._future(snap, cfg, cfg.route_ret, today), key=lambda f: (f.price, f.day))
    pairs = [(o, r) for o in outs for r in rets if 3 <= (r.day - o.day).days <= 30]
    res = [("top5_guenstigste_hinfluege", render_top5(cfg, now, outs, False, "polar", 14)),
           ("top5_guenstigste_rueckfluege", render_top5(cfg, now, rets, True, "bernstein", 15)),
           ("familie_hinflug", render_familie(cfg, now, outs[0], False, "tuerkis", 11)),
           ("familie_rueckflug", render_familie(cfg, now, rets[0], True, "violett", 12))]
    if pairs:
        co, cr = min(pairs, key=lambda p_: (round(p_[0].price + p_[1].price, 2), p_[0].day))
        res.append(("familie_hin_und_zurueck", render_kombi_familie(cfg, now, co, cr, "koralle", 13)))
    return res
