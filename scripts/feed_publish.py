"""Veröffentlicht die Feed-Beiträge (4:5) des heutigen Rotations-Schritts auf Facebook und Instagram
(Plan: <ordner>/feed_plan.json aus scripts/feed_rotation.py; Kreis siehe dort). Zwischen zwei Beiträgen 5 Minuten Pause.
Stand/Protokoll: data/feed_rotation.json – pro Tag wird festgehalten, welcher Beitrag auf welcher Plattform schon
veröffentlicht ist (kein Doppelpost bei erneutem Lauf). Erst wenn alle Beiträge des Tages draußen sind, rückt der
Kreis einen Schritt weiter. Nur offizielle Meta Graph API: FB  POST /{page}/photos (source + message);
IG  /{ig}/media (image_url, caption) → media_publish.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stories_publish import _call, wait_url  # noqa: E402

PROJ = Path(__file__).resolve().parents[1]
ROT = PROJ / "data" / "feed_rotation.json"


def post_facebook(png, text):
    page = os.environ["FACEBOOK_PAGE_ID"].strip()
    r = _call("POST", f"{page}/photos", {"message": text}, file_path=png)
    return r.get("post_id") or r.get("id")


def post_instagram(url, text):
    ig = os.environ["INSTAGRAM_USER_ID"].strip()
    if not wait_url(url):
        raise RuntimeError(f"Bild nicht öffentlich erreichbar: {url}")
    cid = _call("POST", f"{ig}/media", {"image_url": url, "caption": text})["id"]
    for _ in range(36):
        st = _call("GET", cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram-Container {st}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram-Container: Zeitüberschreitung")
    return _call("POST", f"{ig}/media_publish", {"creation_id": cid}).get("id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordner", required=True)
    ap.add_argument("--base-url", default=os.environ.get("STORY_BASE_URL", ""))
    ap.add_argument("--modus", choices=["test", "veroeffentlichen"], default="test")
    ap.add_argument("--pause", type=int, default=300, help="Sekunden zwischen zwei Beiträgen")
    a = ap.parse_args()
    d = Path(a.ordner)
    if not (d / "feed_plan.json").exists():
        print("Kein feed_plan.json – heute kein Feed-Beitrag (schon erledigt).")
        return
    plan = json.loads((d / "feed_plan.json").read_text())
    st = json.loads(ROT.read_text()) if ROT.exists() else {"naechster_schritt": 0, "heute": {}}
    h = st.get("heute") or {}
    if h.get("tag") != plan["datum"]:
        h = {"tag": plan["datum"], "schritt": plan["schritt"], "erledigt": [], "fertig": False}
    print(f"Feed-Rotation {plan['datum']}: Tag {plan['tag_im_kreis']} von 7 {plan.get('hinweis') or ''}")
    if h.get("fertig"):
        print("Heute schon alles veröffentlicht – nichts zu tun.")
        return
    fehler, letzter_post = [], None
    for x in plan["beitraege"]:
        for plat in ("facebook", "instagram"):
            k = f"{x['name']}/{plat}"
            if k in h["erledigt"]:
                print(f"{k}: heute schon veröffentlicht – übersprungen")
                continue
            if a.modus == "test":
                print(f"TEST {k}: würde veröffentlichen ({x['datei']})")
                continue
            if letzter_post and letzter_post != x["name"]:      # 5 Min. Pause zwischen verschiedenen Beiträgen
                print(f"Warte {a.pause} s …")
                time.sleep(a.pause)
            text = (d / f"{x['datei']}_{plat}.txt").read_text(encoding="utf-8")
            try:
                if plat == "facebook":
                    pid = post_facebook(d / f"{x['datei']}.png", text)
                else:
                    pid = post_instagram(a.base_url.rstrip("/") + f"/{x['datei']}.jpg", text)
                h["erledigt"].append(k)
                h.setdefault("ids", {})[k] = pid
                letzter_post = x["name"]
                print(f"✅ {k} veröffentlicht")
            except Exception as e:
                fehler.append(f"{k}: {e}")
                print(f"❌ {k}: {e}")
            st["heute"] = h
            ROT.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")
    if a.modus == "test":
        return
    if not fehler:
        h["fertig"] = True
        st["heute"] = h
        st["naechster_schritt"] = (plan["schritt"] + 1) % 7
        ROT.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")
        print(f"Fertig – morgen Tag {st['naechster_schritt'] + 1} von 7")
    else:
        sys.exit("Fehler: " + " | ".join(fehler))


if __name__ == "__main__":
    main()
