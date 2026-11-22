"""Feed-Beiträge (Facebook + Instagram, 4:5 = 1080×1350): günstigster Hinflug und günstigster Rückflug.
Eigene Bilder – die Story-Bilder werden NICHT verändert. Gleicher Stil wie die Bestpreis-Stories.

Aufruf:  .venv/bin/python scripts/feed_bestpreis.py
Ausgabe: output/facebook_ahora/feed_bestpreis_<datum>/
         1_hinflug.png  1_hinflug_facebook.txt  1_hinflug_instagram.txt
         2_rueckflug.png 2_rueckflug_facebook.txt 2_rueckflug_instagram.txt
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(PROJ / "scripts"))
from flightdeals.config import load_config  # noqa: E402
from flightdeals.fetch import fetch_all  # noqa: E402
from flightdeals.render.common import Painter  # noqa: E402
from flightdeals.render.photo_alert import _cover, _photo  # noqa: E402
from flightdeals.texts import WOCHENTAGE, booking_link, edition_line, fmt_checked, fmt_price  # noqa: E402
import vorschau_story_kalender as v  # noqa: E402

W, H = 1080, 1350
GOLD = v.GOLD
lerp = v.lerp


def render_feed(cfg, best, now, rueck=False):
    p = Painter(cfg)
    t = p.t
    ph = cfg["photos"]
    pd_ = PROJ / "assets" / "photos"
    src_city, dst_city = ("Nador", "Frankfurt-Hahn") if rueck else ("Frankfurt-Hahn", "Nador")
    src_flag, dst_flag = ("MA", "DE") if rueck else ("DE", "MA")

    # Himmel (Abend) + Skylines (Abflugort links, Ziel rechts) + Flugzeuge
    HOR = 470
    bg = Image.new("RGBA", (W, H), (8, 14, 26, 255))
    sky = Image.new("RGBA", (W, HOR + 160), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sky)
    stops = [(0, (14, 22, 70)), (0.45, (92, 44, 130)), (0.78, (220, 92, 110)), (1.0, (255, 170, 90))]
    for y in range(sky.height):
        u = y / sky.height
        for (u0, c0), (u1, c1) in zip(stops, stops[1:]):
            if u0 <= u <= u1:
                sd.line((0, y, W, y), fill=(*lerp(c0, c1, (u - u0) / (u1 - u0)), 255))
                break
    glow = Image.new("RGBA", sky.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 340, HOR - 140, W / 2 + 340, HOR + 220), fill=(255, 210, 120, 150))
    sky.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    rnd = random.Random(12)
    sd = ImageDraw.Draw(sky)
    for _ in range(55):
        x, y = rnd.randint(0, W), rnd.randint(0, 240)
        sd.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(255, 255, 255, rnd.randint(90, 200)))
    bg.alpha_composite(sky, (0, 0))
    fra = _cover(_photo(str(pd_ / ph["origin_file"])), W // 2 + 80, H - HOR + 260, 0.55, 0.30).convert("RGBA")
    ndr = _cover(_photo(str(pd_ / ph["destination_file"])), W // 2 + 80, H - HOR + 260, 0.62, 0.42).convert("RGBA")
    left, right = (ndr, fra) if rueck else (fra, ndr)
    for img_, x_, side in ((left, 0, "l"), (right, W - right.width, "r")):
        m = Image.new("L", img_.size, 255)
        md = ImageDraw.Draw(m)
        for yy in range(260):
            md.line((0, yy, img_.width, yy), fill=int(255 * (yy / 260) ** 1.6))
        if side == "r":
            mm = Image.new("L", img_.size, 255)
            mmd = ImageDraw.Draw(mm)
            for xx in range(160):
                mmd.line((xx, 0, xx, img_.height), fill=int(255 * xx / 160))
            m = ImageChops.multiply(m, mm)
        lum = img_.convert("L").point(lambda v_: min(255, int(v_ * 3.2)))
        grad = Image.new("L", img_.size, 0)
        gd_ = ImageDraw.Draw(grad)
        for yy in range(img_.height):
            gd_.line((0, yy, img_.width, yy), fill=int(255 * min(1, max(0, (yy - 140) / 340))))
        lm = Image.composite(Image.new("L", img_.size, 255), lum, grad)
        img_.putalpha(ImageChops.multiply(m, lm))
        bg.alpha_composite(img_, (x_, HOR - 260))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for yy in range(HOR, H):
        od.line((0, yy, W, yy), fill=(6, 10, 24, int(min(130, max(0, (yy - HOR - 120) * 0.16)))))
    bg.alpha_composite(ov)
    planes_ = [(90, 370, -12, 0.6), (1010, 360, 12, 0.6)]
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pld = ImageDraw.Draw(pl)
    for x, y, ang, sc in planes_:
        a_ = math.radians(ang)
        L = 340 * sc
        for k in range(30):
            t0, t1 = k / 30, (k + 1) / 30
            pld.line((x - L * (1 - t0) * math.cos(a_), y - L * (1 - t0) * math.sin(a_),
                      x - L * (1 - t1) * math.cos(a_), y - L * (1 - t1) * math.sin(a_)),
                     fill=(255, 255, 255, int(14 + 120 * t1)), width=max(2, int(6 * sc * t1)))
    bg.alpha_composite(pl)
    p.img = bg.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    for x, y, ang, sc in planes_:
        p.plane(x, y, int(42 * sc), ang, (255, 255, 255))

    def shadow(xy, txt, font, fill, anchor="mm", off=3):
        p.d.text((xy[0] + off, xy[1] + off), txt, font=font, fill=(0, 0, 0), anchor=anchor)
        p.d.text(xy, txt, font=font, fill=fill, anchor=anchor)

    # Goldenes Ticket-Band
    lab = f"BESTPREIS · NÄCHSTE {v.N_MONATE} MONATE"
    fl = p.font("extrabold", 40)
    bw = p.tw(lab, fl) + 140
    x0, y0, x1, y1 = (W - bw) / 2, 44, (W + bw) / 2, 120
    p.d.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), 20, fill=(0, 0, 0))
    p.d.rounded_rectangle((x0, y0, x1, y1), 20, fill=GOLD, outline=(255, 255, 255), width=4)
    for cxn in (x0, x1):
        p.d.ellipse((cxn - 14, (y0 + y1) / 2 - 14, cxn + 14, (y0 + y1) / 2 + 14), fill=(16, 22, 70))
    for yy in range(int(y0) + 10, int(y1) - 6, 13):
        p.d.line((x0 + 90, yy, x0 + 90, yy + 6), fill=(150, 110, 20), width=3)
    p.plane(x0 + 48, (y0 + y1) / 2, 27, -20, (60, 40, 6))
    p.d.text((x0 + 112, (y0 + y1) / 2 + 2), lab, font=fl, fill=(40, 28, 6), anchor="lm")

    lines_ = ["DER GÜNSTIGSTE RÜCKFLUG", "NACH FRANKFURT-HAHN"] if rueck else ["DER GÜNSTIGSTE", "FLUG NACH NADOR"]
    ft = min((p.fit(l_, "extrabold", 84, W - 60) for l_ in lines_), key=lambda f_: f_.size)
    shadow((W / 2, 190), lines_[0], ft, (255, 255, 255))
    shadow((W / 2, 278), lines_[1], ft, (255, 255, 255))

    # Flugbogen mit Kondensstreifen, realistischem Flugzeug und Pfeil
    ya = 450
    v._contrail(p, (150, ya), (930, ya), 300, 0.5)
    fcity = p.font("extrabold", 38)
    p.flag(src_flag, 50, ya + 30, 30)
    shadow((110, ya + 46), src_city, fcity, (255, 255, 255), anchor="lm")
    tw_ = p.tw(dst_city, fcity)
    shadow((W - 50 - 52 - tw_, ya + 46), dst_city, fcity, (255, 255, 255), anchor="lm")
    p.flag(dst_flag, W - 50 - 42, ya + 30, 30)

    # Glas-Karte
    cx0, cy0, cx1, cy1 = 48, 560, W - 48, 1150
    reg = p.img.crop((cx0, cy0, cx1, cy1)).filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
    reg.alpha_composite(Image.new("RGBA", reg.size, (8, 14, 30, 130)))
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, reg.width - 1, reg.height - 1), 34, fill=255)
    p.img.paste(reg.convert("RGB"), (cx0, cy0), m)
    p.d = ImageDraw.Draw(p.img)
    p.d.rounded_rectangle((cx0, cy0, cx1, cy1), 34, outline=GOLD, width=5)
    shadow((W / 2, cy0 + 56), ("RÜCKFLUG" if rueck else "HINFLUG") + " · EINFACHE STRECKE, PRO PERSON",
           p.font("extrabold", 30), (210, 222, 238), off=2)
    shadow((W / 2, cy0 + 130), f"{WOCHENTAGE[best.day.weekday()]}, {best.day:%d.%m.%Y}", p.font("extrabold", 62), (255, 255, 255))
    shadow((W / 2, cy0 + 200), f"Abflug {best.departure} Uhr · {src_city} → {dst_city}", p.font("bold", 32), (225, 234, 245), off=2)
    price = fmt_price(best.price)
    fp = p.font("extrabold", 200)
    gl = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).text((W / 2, cy0 + 370), price, font=fp, fill=(34, 197, 94, 170), anchor="mm")
    base = p.img.convert("RGBA")
    base.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18)))
    p.img = base.convert("RGB")
    p.d = ImageDraw.Draw(p.img)
    p.d.text((W / 2, cy0 + 370), price, font=fp, fill=(60, 220, 120), anchor="mm")
    shadow((W / 2, cy0 + 530), "Basic-Tarif · nur 1 kleine Tasche (40×30×20 cm)", p.font("bold", 28), (220, 230, 242), off=2)

    chk = f"Preis bei Ryanair geprüft: {WOCHENTAGE[now.weekday()]}, {now:%d.%m.%Y} · {now:%H:%M} Uhr – kann sich jederzeit ändern."
    shadow((W / 2, 1196), chk, p.fit(chk, "bold", 26, W - 50), (255, 255, 255), off=2)
    p.d.text((W / 2, 1238), "Unabhängige Infoseite · keine Verbindung zu Ryanair · Buchung nur auf ryanair.com",
             font=p.font("bold", 21), fill=(220, 228, 240), anchor="mm")
    p.d.text((W / 2, 1322), cfg["photos"]["credit"], font=p.fit(cfg["photos"]["credit"], "bold", 15, W - 60),
             fill=(185, 196, 212), anchor="mm")
    return p.img


def texts(cfg, best, now, rueck):
    o, d = ("NDR", "HHN") if rueck else ("HHN", "NDR")
    route = "🇲🇦 Nador → 🇩🇪 Frankfurt-Hahn" if rueck else "🇩🇪 Frankfurt-Hahn → 🇲🇦 Nador"
    head = "Der günstigste Rückflug nach Frankfurt-Hahn" if rueck else "Der günstigste Flug nach Nador"
    icon = "🛬" if rueck else "🛫"
    pg = cfg["page"]

    def build(platform):
        fb = platform == "facebook"
        link = f"\n🔗 {booking_link(o, d, best.day)}" if fb else ""
        return f"""{edition_line(now)}

✈️ {head}: {route} schon ab {fmt_price(best.price)}!
🕒 Preis bei Ryanair {fmt_checked(now)} – kann sich im Laufe des Tages jederzeit ändern.

{pg['stories_hint'] if fb else pg['instagram_stories_hint']}

{icon} {WOCHENTAGE[best.day.weekday()]}, {best.day:%d.%m.%Y} · Abflug {best.departure} Uhr · {fmt_price(best.price)} pro Person{link}

👉 Buchung nur über die offizielle Ryanair-Seite: ryanair.com

🧳 {cfg['fare']['baggage_note']}

{pg['like_cta']}

ℹ️ {pg['disclaimer']} Wir verkaufen keine Tickets – gebucht wird ausschließlich auf ryanair.com.

{pg['hashtags'] if fb else pg['instagram_hashtags']}
"""
    return build("facebook"), build("instagram")


def main():
    cfg = load_config()
    cfg["route"]["months_ahead"] = v.N_MONATE
    now = cfg.now()
    snap = fetch_all(cfg, now)
    if any(not m.ok for m in snap.months.values()):
        sys.exit("Preisabfrage unvollständig – keine Beiträge (keine alten Preise zeigen).")
    today = now.date()
    out = PROJ / "output" / "facebook_ahora" / f"feed_bestpreis_{now:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    for idx, (rueck, name) in enumerate(((False, "hinflug"), (True, "rueckflug")), 1):
        route = cfg.route_ret if rueck else cfg.route_out
        best = min((f for f in snap.fares(route) if f.day >= today), key=lambda f: (f.price, f.day))
        render_feed(cfg, best, now, rueck).save(out / f"{idx}_{name}.png")
        fb, ig = texts(cfg, best, now, rueck)
        (out / f"{idx}_{name}_facebook.txt").write_text(fb, encoding="utf-8")
        (out / f"{idx}_{name}_instagram.txt").write_text(ig, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
