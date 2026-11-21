"""Nur LESENDER Verbindungstest zu Meta (veröffentlicht nichts).
Prüft: Token gehört zur Seite, Instagram-Konto erreichbar, Veröffentlichungs-Kontingent, Token-Rechte/Ablauf.
Gibt nie den Token aus."""
import json, os, sys, urllib.parse, urllib.request

V = "v27.0"
TOKEN = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"].strip()
PAGE = os.environ["FACEBOOK_PAGE_ID"].strip()
IG = os.environ["INSTAGRAM_USER_ID"].strip()

def get(path, **params):
    params["access_token"] = TOKEN
    url = f"https://graph.facebook.com/{V}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return True, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
        except Exception:
            err = {"message": str(e)}
        return False, {"code": err.get("code"), "type": err.get("type"), "message": err.get("message")}

ok_all = True
def show(title, ok, data):
    global ok_all
    ok_all &= ok
    print(("✅ " if ok else "❌ ") + title + ": " + json.dumps(data, ensure_ascii=False))

ok, d = get("me", fields="id,name")
show("Token gehört zu", ok, d)
if ok and d.get("id") != PAGE:
    print("❌ Das ist KEIN Seiten-Token der Seite " + PAGE + " (vermutlich Nutzer-Token).")
    ok_all = False
show("Instagram-Konto", *get(IG, fields="id,username,name"))
show("Veröffentlichungs-Kontingent Instagram", *get(f"{IG}/content_publishing_limit", fields="config,quota_usage"))
ok, d = get("debug_token", input_token=TOKEN)
if ok:
    x = d.get("data", {})
    exp = x.get("expires_at")
    show("Token-Info", True, {"typ": x.get("type"), "gültig": x.get("is_valid"),
                              "läuft_ab": "nie" if exp in (0, None) else exp,
                              "rechte": sorted(x.get("scopes", []))})
    need = {"pages_manage_posts", "pages_read_engagement", "pages_show_list", "instagram_basic", "instagram_content_publish"}
    missing = need - set(x.get("scopes", []))
    if missing:
        print("❌ Fehlende Rechte: " + ", ".join(sorted(missing)))
        ok_all = False
else:
    show("Token-Info", False, d)
print("ERGEBNIS: " + ("alles in Ordnung" if ok_all else "Problem gefunden"))
sys.exit(0 if ok_all else 1)
