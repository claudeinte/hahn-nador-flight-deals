"""Estado de la ejecución diaria (para el email de aviso).

Cada paso deja aquí un pequeño JSON (output/lauf/ o LAUF_DIR):
  api_fehler.json  – la API de Ryanair falló → no se publica nada
  stories.json     – resultado de las stories por plataforma (publicadas, recuperadas, fallidas)
  feed.json        – resultado del post del día por plataforma
  guardado.json    – resultado del paso de guardado (git commit/push)
  pasos.json       – resultado de cada paso del workflow (lo escribe GitHub Actions)
scripts/lauf_bericht.py lee estos archivos y decide si hay que enviar un email.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJ = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")


def lauf_dir() -> Path:
    d = Path(os.environ.get("LAUF_DIR") or PROJ / "output" / "lauf")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ahora() -> str:
    return datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M:%S")


def escribir(nombre: str, data) -> None:
    (lauf_dir() / nombre).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def leer(nombre: str):
    p = lauf_dir() / nombre
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                       # archivo roto → se informa, no se ignora
        return {"_ilegible": str(e)}


def api_fehler(skript: str, fehler: list[str]) -> None:
    """La API de Ryanair no dio datos completos: se anota y el workflow no publica nada."""
    escribir("api_fehler.json", {"zeit": ahora(), "skript": skript, "fehler": fehler})
