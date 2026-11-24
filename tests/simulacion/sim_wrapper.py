"""Ejecuta un script del proyecto con respuestas FICTICIAS (para tests/simulacion/simular.py).

Sustituye (solo dentro de este proceso):
  - API de Ryanair      → precios inventados, o "no responde" (escenario api_caida)
  - API de Meta (FB/IG) → respuestas inventadas; fallos programados por escenario; nada se publica de verdad
  - Gmail (SMTP)        → el email se guarda en el estado de la simulación, no se envía
  - time.sleep          → sin esperas
Estado y reglas: archivo JSON en $SIM_STATE.
Uso (lo hace el falso "python" del PATH): sim_wrapper.py <script.py | -c código> [args…]
"""
import io
import json
import os
import random
import re
import runpy
import smtplib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

STATE = os.environ["SIM_STATE"]


def _load():
    with open(STATE) as f:
        return json.load(f)


def _save(s):
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


class _Resp:
    def __init__(self, data=b"", status=200):
        self._d, self.status = data, status

    def read(self, *a):
        return self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(url, code, msg, sub=None):
    body = json.dumps({"error": {"message": msg, "code": code, "error_subcode": sub}}).encode()
    return urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(body))


def _regla(s, clave, nombre):
    """True → este intento debe fallar. Reglas: {"ig_story": {"15_x.jpg": 2 | "siempre"}, "ig_feed": "siempre", …}"""
    r = s["reglas"].get(clave)
    if r is None:
        return False
    if isinstance(r, dict):
        r = r.get(nombre)
        if r is None:
            return False
        if r == "siempre":
            return True
        if r > 0:
            s["reglas"][clave][nombre] = r - 1
            return True
        return False
    return r == "siempre"


def _ryanair(url):
    s = _load()
    s["llamadas_ryanair"] = s.get("llamadas_ryanair", 0) + 1
    _save(s)
    if s["reglas"].get("api_caida"):
        raise urllib.error.URLError("timed out (simulación: la API de Ryanair no responde)")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    m = date.fromisoformat(q["outboundMonthOfDate"][0])
    route = url.split("oneWayFares/")[1].split("/cheapestPerDay")[0].replace("/", "-")
    rnd = random.Random(f"{route}{m}")
    fares, d = [], m
    while d.month == m.month:
        if rnd.random() < 0.6:
            v = rnd.choice([15.99, 19.99, 24.99, 29.99, 34.99, 39.99, 49.99, 59.99, 79.99, 99.99])
            fares.append({"day": d.isoformat(), "price": {"value": v, "currencyCode": "EUR"},
                          "departureDate": f"{d}T10:15:00", "arrivalDate": f"{d}T13:05:00",
                          "unavailable": False, "soldOut": False})
        else:
            fares.append({"day": d.isoformat(), "price": None, "unavailable": True, "soldOut": False})
        d += timedelta(days=1)
    return _Resp(json.dumps({"outbound": {"fares": fares}}).encode())


def _meta(req):
    url = req.full_url
    path = urllib.parse.urlparse(url).path.split("/", 2)[2]          # nach /v27.0/
    method = req.get_method()
    s = _load()
    s["n"] = s.get("n", 0) + 1
    n = s["n"]
    try:
        if method == "GET":
            return _Resp(json.dumps({"status_code": "FINISHED"}).encode())
        raw = req.data or b""
        if path.endswith("/media"):                                     # Instagram: Container
            f = dict(urllib.parse.parse_qsl(raw.decode()))
            name = f["image_url"].rsplit("/", 1)[1]
            kind = "ig_story" if f.get("media_type") == "STORIES" else "ig_feed"
            s["intentos"].append(f"{kind}:{name}")
            if _regla(s, kind, name):
                raise _http_error(url, 24, "The requested resource does not exist", 2207006)
            s["contenedores"][f"c{n}"] = [kind, name]
            return _Resp(json.dumps({"id": f"c{n}"}).encode())
        if path.endswith("/media_publish"):
            f = dict(urllib.parse.parse_qsl(raw.decode()))
            kind, name = s["contenedores"][f["creation_id"]]
            s["publicado"][kind].append(name)
            return _Resp(json.dumps({"id": f"ig{n}"}).encode())
        if path.endswith("/photos"):                                    # Facebook: Foto (Story-Vorstufe oder Post)
            name = re.search(rb'filename="([^"]+)"', raw).group(1).decode()
            kind = "fb_story" if b'name="published"' in raw else "fb_feed"
            s["intentos"].append(f"{kind}:{name}")
            if _regla(s, kind, name):
                raise _http_error(url, 100, "Simulación: error de Facebook al subir la foto", 0)
            if kind == "fb_feed":
                s["publicado"]["fb_feed"].append(name)
            s["fotos"][f"ph{n}"] = name
            return _Resp(json.dumps({"id": f"ph{n}", "post_id": f"post{n}"}).encode())
        if path.endswith("/photo_stories"):
            f = dict(urllib.parse.parse_qsl(raw.decode()))
            s["publicado"]["fb_story"].append(s["fotos"][f["photo_id"]])
            return _Resp(json.dumps({"success": True}).encode())
        raise RuntimeError(f"Simulación: llamada Meta no prevista {method} {path}")
    finally:
        _save(s)


def fake_urlopen(req, *a, **kw):
    url = req if isinstance(req, str) else req.full_url
    if "ryanair.com" in url:
        return _ryanair(url)
    if "graph.facebook.com" in url:
        return _meta(req)
    if "raw.githubusercontent.com" in url:
        return _Resp(b"", 200)
    raise RuntimeError(f"Simulación: acceso a red no permitido: {url}")


class FakeSMTP:
    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        pass

    def send_message(self, m):
        s = _load()
        s["emails"].append({"asunto": m["Subject"], "para": m["To"], "cuerpo": m.get_content()})
        _save(s)


urllib.request.urlopen = fake_urlopen
smtplib.SMTP_SSL = FakeSMTP
smtplib.SMTP = FakeSMTP
time.sleep = lambda *_: None

args = sys.argv[1:]
if args and args[0] == "-c":
    sys.argv = ["-c"] + args[2:]
    exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
elif args and args[0] == "-":
    sys.argv = ["-"] + args[1:]
    exec(compile(sys.stdin.read(), "<stdin>", "exec"), {"__name__": "__main__"})
else:
    script = os.path.abspath(args[0])
    sys.argv = args
    sys.path.insert(0, os.path.dirname(script))
    runpy.run_path(script, run_name="__main__")
