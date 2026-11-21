"""Veröffentlicht die Tages-Stories (output/stories/<datum>/01…NN) als STORIES auf Instagram und Facebook.

Nur offizielle Meta Graph API (v27.0):
  Instagram: POST /{ig-id}/media (image_url, media_type=STORIES) → Status prüfen → POST /{ig-id}/media_publish
  Facebook:  POST /{page-id}/photos (published=false, Datei) → POST /{page-id}/photo_stories (photo_id)
Instagram braucht eine öffentliche JPEG-Adresse (STORY_BASE_URL, z. B. raw.githubusercontent.com/…/stories/<datum>/).

Sicherheit:
  - --modus test: nur prüfen/vorbereiten, NICHTS veröffentlichen
  - bereits Veröffentlichtes steht in data/stories_veroeffentlicht.json → keine Doppelten (auch bei erneutem Start)
  - Wiederholungen bei Fehlern; Reihenfolge bleibt erhalten (bricht pro Plattform beim ersten endgültigen Fehler ab)
  - Token wird nie ausgegeben
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
V = "v27.0"
STATE = PROJ / "data" / "stories_veroeffentlicht.json"


def _call(method, path, fields=None, file_path=None, tries=3):
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"].strip()
    url = f"https://graph.facebook.com/{V}/{path}"
    fields = dict(fields or {}, access_token=token)
    last = None
    for i in range(tries):
        try:
            if method == "GET":
                req = urllib.request.Request(url + "?" + urllib.parse.urlencode(fields))
            elif file_path:
                b = uuid.uuid4().hex
                body = bytearray()
                for k, v in fields.items():
                    body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                body += (f"--{b}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"{file_path.name}\"\r\n"
                         f"Content-Type: image/jpeg\r\n\r\n").encode() + file_path.read_bytes() + f"\r\n--{b}--\r\n".encode()
                req = urllib.request.Request(url, data=bytes(body), method="POST",
                                             headers={"Content-Type": f"multipart/form-data; boundary={b}"})
            else:
                req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST")
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                err = json.load(e).get("error", {})
            except Exception:
                err = {}
            last = f"HTTP {e.code}: {err.get('message', '')} (code {err.get('code')}, sub {err.get('error_subcode')})"
            if e.code < 500 and err.get("code") not in (1, 2, 4, 17, 32, 341, 9007):   # dauerhafte Fehler nicht wiederholen
                break
        except Exception as e:  # Netzwerk
            last = repr(e)
        time.sleep(5 * (i + 1))
    raise RuntimeError(last)


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")


def wait_url(url, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def publish_instagram(files, base_url, st_day):
    ig = os.environ["INSTAGRAM_USER_ID"].strip()
    done = st_day.setdefault("instagram", [])
    for f in files:
        if f.name in done:
            print(f"  Instagram: {f.name} schon veröffentlicht – übersprungen")
            continue
        url = base_url.rstrip("/") + "/" + f.name
        if not wait_url(url):
            raise RuntimeError(f"Bild nicht öffentlich erreichbar: {url}")
        c = _call("POST", f"{ig}/media", {"image_url": url, "media_type": "STORIES"})
        cid = c["id"]
        for _ in range(36):                                   # max. 3 Minuten warten
            s = _call("GET", cid, {"fields": "status_code"}).get("status_code")
            if s == "FINISHED":
                break
            if s in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {f.name}: {s}")
            time.sleep(5)
        else:
            raise RuntimeError(f"Container {f.name}: Zeitüberschreitung")
        _call("POST", f"{ig}/media_publish", {"creation_id": cid})
        done.append(f.name)
        print(f"  ✅ Instagram-Story {f.name}")
        yield
        time.sleep(3)


def publish_facebook(files, st_day):
    page = os.environ["FACEBOOK_PAGE_ID"].strip()
    done = st_day.setdefault("facebook", [])
    for f in files:
        if f.name in done:
            print(f"  Facebook: {f.name} schon veröffentlicht – übersprungen")
            continue
        ph = _call("POST", f"{page}/photos", {"published": "false"}, file_path=f)
        _call("POST", f"{page}/photo_stories", {"photo_id": ph["id"]})
        done.append(f.name)
        print(f"  ✅ Facebook-Story {f.name}")
        yield
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordner", required=True, help="Ordner mit den JPEGs (01_….jpg … 10_….jpg)")
    ap.add_argument("--datum", required=True)
    ap.add_argument("--modus", choices=["test", "veroeffentlichen"], default="test")
    ap.add_argument("--base-url", default=os.environ.get("STORY_BASE_URL", ""))
    ap.add_argument("--anzahl", type=int, default=12, help="erwartete Anzahl Stories (1 Übersicht + Monate)")
    a = ap.parse_args()
    files = sorted(f for f in Path(a.ordner).glob("[0-9][0-9]_*.jpg") if not f.name.startswith("00_"))
    if len(files) != a.anzahl:
        sys.exit(f"Erwartet {a.anzahl} Story-Bilder, gefunden {len(files)} – nichts veröffentlicht.")
    print("Stories:", ", ".join(f.name for f in files))
    if a.modus == "test":
        print("TESTMODUS: nichts veröffentlicht.")
        return
    st = load_state()
    day = st.setdefault(a.datum, {})
    fehler = []
    for name, gen in (("Instagram", lambda: publish_instagram(files, a.base_url, day)),
                      ("Facebook", lambda: publish_facebook(files, day))):
        try:
            for _ in gen():
                save_state(st)                                # nach jeder Story sichern
        except Exception as e:
            fehler.append(f"{name}: {e}")
            print(f"  ❌ {name}: {e}")
        save_state(st)
    print(f"Instagram {len(day.get('instagram', []))}/{a.anzahl} · Facebook {len(day.get('facebook', []))}/{a.anzahl}")
    if fehler:
        sys.exit("Fehler: " + " | ".join(fehler))


if __name__ == "__main__":
    main()
