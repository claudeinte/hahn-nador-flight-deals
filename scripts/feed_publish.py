"""Veröffentlicht die Feed-Beiträge „günstigster Hinflug“ und „günstigster Rückflug“ (4:5) auf Facebook und Instagram –
nur wenn sich der günstigste Flug (Datum oder Preis) seit dem letzten Beitrag geändert hat. Erst Hinflug, 5 Minuten
später Rückflug. Protokoll: data/feed_veroeffentlicht.json (pro Richtung und Plattform), dadurch keine Doppelten.
Nur offizielle Meta Graph API: FB  POST /{page}/photos (source + message);  IG  /{ig}/media (image_url, caption) → media_publish.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stories_publish import _call, wait_url  # noqa: E402

PROJ = Path(__file__).resolve().parents[1]
STATE = PROJ / "data" / "feed_veroeffentlicht.json"


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
    ap.add_argument("--pause", type=int, default=300, help="Sekunden zwischen Hin- und Rückflug-Beitrag")
    a = ap.parse_args()
    d = Path(a.ordner)
    info = json.loads((d / "feed_info.json").read_text())
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    fehler, gepostet = [], 0
    for name in ("hinflug", "rueckflug"):
        x = info[name]
        key = f"{x['tag']}|{x['preis']:.2f}"
        for plat in ("facebook", "instagram"):
            last = st.get(name, {}).get(plat, {}).get("key")
            if last == key:
                print(f"{name}/{plat}: unverändert ({key}) – kein neuer Beitrag")
                continue
            if a.modus == "test":
                print(f"TEST {name}/{plat}: würde veröffentlichen ({key}, vorher {last})")
                continue
            if name == "rueckflug" and gepostet == 1:          # Hinflug wurde gerade gepostet → 5 Min. warten (einmal)
                print(f"Warte {a.pause} s vor dem Rückflug-Beitrag …")
                time.sleep(a.pause)
                gepostet = -1
            text = (d / f"{x['datei']}_{plat}.txt").read_text(encoding="utf-8")
            try:
                if plat == "facebook":
                    pid = post_facebook(d / f"{x['datei']}.png", text)
                else:
                    pid = post_instagram(a.base_url.rstrip("/") + f"/{x['datei']}.jpg", text)
                st.setdefault(name, {})[plat] = {"key": key, "id": pid, "zeit": datetime.now().isoformat(timespec="seconds")}
                STATE.parent.mkdir(parents=True, exist_ok=True)
                STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")
                print(f"✅ {name}/{plat} veröffentlicht ({key})")
                if name == "hinflug":
                    gepostet = 1
            except Exception as e:
                fehler.append(f"{name}/{plat}: {e}")
                print(f"❌ {name}/{plat}: {e}")
    if fehler:
        sys.exit("Fehler: " + " | ".join(fehler))


if __name__ == "__main__":
    main()
