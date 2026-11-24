"""Veröffentlicht die Tages-Stories (output/stories/<datum>/01…NN) als STORIES auf Instagram und Facebook.

Nur offizielle Meta Graph API (v27.0):
  Instagram: POST /{ig-id}/media (image_url, media_type=STORIES) → Status prüfen → POST /{ig-id}/media_publish
  Facebook:  POST /{page-id}/photos (published=false, Datei) → POST /{page-id}/photo_stories (photo_id)
Instagram braucht eine öffentliche JPEG-Adresse (STORY_BASE_URL, z. B. raw.githubusercontent.com/…/stories/<datum>/).

Sicherheit:
  - --modus test: nur prüfen/vorbereiten, NICHTS veröffentlichen
  - bereits Veröffentlichtes steht in data/stories_veroeffentlicht.json → keine Doppelten (auch bei erneutem Start)
  - jede Story bis zu 3 Versuche; scheitert sie dreimal, geht es mit der nächsten weiter
  - Ergebnis (veröffentlicht / wiederhergestellt / gescheitert) → output/lauf/stories.json (für den Email-Bericht)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lauf_estado  # noqa: E402

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
                         f"Content-Type: {'image/png' if file_path.suffix == '.png' else 'image/jpeg'}\r\n\r\n").encode() + file_path.read_bytes() + f"\r\n--{b}--\r\n".encode()
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


def _ig_story(ig, url, name):
    c = _call("POST", f"{ig}/media", {"image_url": url, "media_type": "STORIES"}, tries=1)
    cid = c["id"]
    time.sleep(5)
    for _ in range(36):                                       # max. 3 Minuten warten
        s = _call("GET", cid, {"fields": "status_code"}).get("status_code")
        if s == "FINISHED":
            break
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {name}: {s}")
        time.sleep(5)
    else:
        raise RuntimeError(f"Container {name}: Zeitüberschreitung")
    _call("POST", f"{ig}/media_publish", {"creation_id": cid}, tries=1)


VERSUCHE = 3


def _mit_versuchen(fn, name, plat, erg):
    """Führt fn() bis zu 3× aus (die POSTs darin selbst ohne Wiederholung → höchstens 3 Versuche pro Story). Ergebnis wird in erg[plat] notiert. True = veröffentlicht."""
    for versuch in range(1, VERSUCHE + 1):
        try:
            fn()
            erg[plat]["publicadas"].append(name)
            if versuch > 1:
                erg[plat]["recuperadas"].append({"story": name, "versuch": versuch})
                print(f"  ✅ {plat}-Story {name} (wiederhergestellt im Versuch {versuch})")
            else:
                print(f"  ✅ {plat}-Story {name}")
            return True
        except Exception as e:
            print(f"  ⚠️ {plat} {name}, Versuch {versuch}/{VERSUCHE}: {e}")
            if versuch == VERSUCHE:
                erg[plat]["fallidas"].append({"story": name, "error": str(e), "zeit": lauf_estado.ahora()})
                print(f"  ❌ {plat} {name}: nach {VERSUCHE} Versuchen gescheitert – weiter mit der nächsten Story")
                return False
            time.sleep(20 * versuch)


def publish_instagram(files, base_url, st_day, erg, bilder_online=True):
    ig = os.environ.get("INSTAGRAM_USER_ID", "").strip()
    done = st_day.setdefault("instagram", [])
    for f in files:
        if f.name in done:
            erg["instagram"]["ya_publicadas"].append(f.name)
            continue
        url = base_url.rstrip("/") + "/" + f.name

        def eine():
            if not bilder_online:
                raise RuntimeError("Bilder nicht öffentlich bereitgestellt (Schritt 'Bilder öffentlich bereitstellen' fehlgeschlagen)")
            if not wait_url(url):
                raise RuntimeError(f"Bild nicht öffentlich erreichbar: {url}")
            _ig_story(ig, url, f.name)

        if _mit_versuchen(eine, f.name, "instagram", erg):
            done.append(f.name)
        yield
        time.sleep(3)


def publish_facebook(files, st_day, erg, png_dir=None):
    page = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
    done = st_day.setdefault("facebook", [])
    for f in files:
        if f.name in done:
            erg["facebook"]["ya_publicadas"].append(f.name)
            continue
        src = (Path(png_dir) / (f.stem + ".png")) if png_dir else f      # Facebook: verlustfreies PNG → schärfer
        if not src.exists():
            src = f

        def eine():
            ph = _call("POST", f"{page}/photos", {"published": "false"}, file_path=src, tries=1)
            _call("POST", f"{page}/photo_stories", {"photo_id": ph["id"]}, tries=1)

        if _mit_versuchen(eine, f.name, "facebook", erg):
            done.append(f.name)
        yield
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordner", required=True, help="Ordner mit den JPEGs (01_….jpg … 10_….jpg)")
    ap.add_argument("--datum", required=True)
    ap.add_argument("--modus", choices=["test", "veroeffentlichen"], default="test")
    ap.add_argument("--base-url", default=os.environ.get("STORY_BASE_URL", ""))
    ap.add_argument("--png-ordner", default="", help="Original-PNGs für Facebook (schärfer als JPEG)")
    ap.add_argument("--anzahl", type=int, default=14, help="erwartete Anzahl Stories")
    a = ap.parse_args()
    files = sorted(f for f in Path(a.ordner).glob("[0-9][0-9]_*.jpg") if not f.name.startswith("00_"))
    anz_file = Path(a.png_ordner or a.ordner) / "anzahl.txt"
    if anz_file.exists():
        a.anzahl = int(anz_file.read_text().strip())
    if len(files) != a.anzahl:
        sys.exit(f"Erwartet {a.anzahl} Story-Bilder, gefunden {len(files)} – nichts veröffentlicht.")
    print("Stories:", ", ".join(f.name for f in files))
    if a.modus == "test":
        print("TESTMODUS: nichts veröffentlicht.")
        return
    st = load_state()
    day = st.setdefault(a.datum, {})
    erg = {"datum": a.datum, "anzahl": a.anzahl,
           **{p: {"publicadas": [], "recuperadas": [], "fallidas": [], "ya_publicadas": []} for p in ("instagram", "facebook")}}
    bilder_online = os.environ.get("BILDER_ONLINE", "ja") == "ja"
    for plat, gen in (("instagram", lambda: publish_instagram(files, a.base_url, day, erg, bilder_online)),
                      ("facebook", lambda: publish_facebook(files, day, erg, a.png_ordner or None))):
        try:
            for _ in gen():
                save_state(st)                                # nach jeder Story sichern
                lauf_estado.escribir("stories.json", erg)
        except Exception as e:                                # unerwarteter Fehler außerhalb einer Story
            erg[plat]["fallidas"].append({"story": "(alle übrigen)", "error": str(e), "zeit": lauf_estado.ahora()})
            print(f"  ❌ {plat}: {e}")
        save_state(st)
    for plat in ("instagram", "facebook"):
        erg[plat]["total"] = len(day.get(plat, []))
    lauf_estado.escribir("stories.json", erg)
    print(f"Instagram {erg['instagram']['total']}/{a.anzahl} · Facebook {erg['facebook']['total']}/{a.anzahl}")
    fehler = [f"{p} {x['story']}: {x['error']}" for p in ("instagram", "facebook") for x in erg[p]["fallidas"]]
    if not fehler:
        day["komplett"] = True
        save_state(st)
    else:
        sys.exit("Fehler: " + " | ".join(fehler))


if __name__ == "__main__":
    main()
