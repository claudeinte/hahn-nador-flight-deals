"""Simulación del flujo diario (.github/workflows/stories.yml) con respuestas ficticias.

Lee el workflow REAL: evalúa cada condición `if:` igual que GitHub Actions y ejecuta los mismos comandos
`run:` (paso.sh, scripts de Python, guardar_estado.sh, lauf_bericht.py) en una copia temporal del proyecto.
Solo se sustituyen las partes externas (ver sim_wrapper.py): API de Ryanair, API de Meta, GitHub.
El email de aviso lo envía GitHub cuando la ejecución termina "Failed" → aquí: ejecución fallida + informe.
Nada se publica, no se envía ningún email y el repositorio real no se toca.

Uso:  .venv/bin/python tests/simulacion/simular.py [escenario …]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

PROJ = Path(__file__).resolve().parents[2]
WRAPPER = Path(__file__).resolve().parent / "sim_wrapper.py"
REALPY = sys.executable
HOY = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")

ESCENARIOS = {
    "1_todo_bien": {},
    "2_story_recuperada": {"ig_story": {"05_top5_guenstigste_rueckfluege.jpg": 1, "14_kalender_2027-01.jpg": 2}},
    "3_story_falla_3_veces": {"ig_story": {"15_kalender_2027-02.jpg": "siempre"}},
    "4_api_ryanair_caida": {"api_caida": True},
    "5a_post_instagram_falla": {"ig_feed": "siempre"},
    "5b_guardado_falla": {"_guardado_falla": True},
}


# ---------------------------------------------------------------- expresiones de GitHub Actions
def traducir(e):
    e = e.strip()
    if e.startswith("${{"):
        e = e[3:-2].strip()
    e = re.sub(r"steps\.(\w+)\.outputs\.(\w+)", r"OUT('\1','\2')", e)
    e = re.sub(r"steps\.(\w+)\.outcome", r"OC('\1')", e)
    e = re.sub(r"secrets\.(\w+)", r"SEC('\1')", e)
    e = re.sub(r"needs\.(\w+)\.result", r"NEEDS('\1')", e)
    e = re.sub(r"github\.(\w+)", r"GH('\1')", e)
    e = e.replace("inputs.modus", "MODUS").replace("toJSON(steps)", "TOJSON()").replace("hashFiles", "HF")
    e = e.replace("&&", " and ").replace("||", " or ")
    e = re.sub(r"!(?!=)", " not ", e)
    return e


class Job:
    def __init__(self, ws, env_base, ctx):
        self.ws, self.env_base, self.ctx = ws, env_base, ctx
        self.steps = {}            # id → {"outcome", "conclusion", "outputs"}
        self.fallo = False
        self.log = []

    def ns(self):
        return {
            "OUT": lambda i, k: self.steps.get(i, {}).get("outputs", {}).get(k, ""),
            "OC": lambda i: self.steps.get(i, {}).get("outcome", ""),
            "SEC": lambda k: self.ctx["secrets"].get(k, ""),
            "NEEDS": lambda j: self.ctx["needs"].get(j, ""),
            "GH": lambda k: self.ctx["github"][k],
            "MODUS": self.ctx["modus"],
            "TOJSON": lambda: json.dumps(self.steps),
            "HF": lambda p: "hash" if (self.ws / p).exists() else "",
            "always": lambda: True, "cancelled": lambda: False,
            "success": lambda: not self.fallo, "failure": lambda: self.fallo,
        }

    def evaluar(self, expr):
        return eval(traducir(expr), {}, self.ns())

    def sustituir(self, texto):
        return re.sub(r"\$\{\{(.*?)\}\}", lambda m: str(self.evaluar(m.group(1))), str(texto))

    def condicion(self, cond):
        if cond is None:
            return not self.fallo
        c = str(cond)
        if not re.search(r"\b(always|cancelled|failure|success)\(", c):
            c = f"success() && ({c[3:-2] if c.strip().startswith('${{') else c})"
        return bool(self.evaluar(c))

    def ejecutar(self, steps, override):
        for st in steps:
            sid, nombre = st.get("id"), st.get("name") or st.get("uses") or st.get("id")
            if not self.condicion(st.get("if")):
                if sid:
                    self.steps[sid] = {"outcome": "skipped", "conclusion": "skipped", "outputs": {}}
                self.log.append(f"   ⏭  {nombre}  (omitido por su condición)")
                continue
            if sid in override:
                ok, outputs = override[sid](self), {}
            elif "uses" in st:
                ok, outputs = True, {}                     # checkout / setup-python / artifacts → no aplica en local
            else:
                ok, outputs = self.run(st)
            if sid:
                self.steps[sid] = {"outcome": "success" if ok else "failure",
                                   "conclusion": "success" if ok else "failure", "outputs": outputs}
            self.fallo |= not ok
            self.log.append(f"   {'✅' if ok else '❌'} {nombre}")

    def run(self, st):
        out_file = self.ws / ".gh_output"
        out_file.write_text("")
        env = dict(self.env_base)
        env.update({k: self.sustituir(v) for k, v in self.ctx["job_env"].items()})
        env.update({k: self.sustituir(v) for k, v in (st.get("env") or {}).items()})
        env["GITHUB_OUTPUT"] = str(out_file)
        env["GITHUB_WORKSPACE"] = str(self.ws)
        env["GITHUB_STEP_SUMMARY"] = str(self.ws / ".gh_summary.md")
        script = self.sustituir(st["run"])
        p = subprocess.run(["bash", "-e", "-c", script], cwd=self.ws, env=env, capture_output=True, text=True)
        (self.ws / "sim_logs").mkdir(exist_ok=True)
        with open(self.ws / "sim_logs" / f"{st.get('id') or 'x'}.log", "a") as f:
            f.write(p.stdout + p.stderr)
        outs = dict(line.split("=", 1) for line in out_file.read_text().splitlines() if "=" in line)
        return p.returncode == 0, outs


# ---------------------------------------------------------------- preparar copia del proyecto
def preparar(tmp, reglas):
    ws = tmp / "repo"
    shutil.copytree(PROJ, ws, ignore=shutil.ignore_patterns(".venv", "output", "public", ".git", "__pycache__",
                                                            ".pytest_cache", "sim_logs"))
    p = ws / "data" / "stories_veroeffentlicht.json"          # hoy aún no publicado
    st = json.loads(p.read_text()) if p.exists() else {}
    st.pop(HOY, None)
    p.write_text(json.dumps(st, indent=1))
    p = ws / "data" / "feed_rotation.json"
    rot = json.loads(p.read_text())
    if (rot.get("heute") or {}).get("tag") == HOY:
        rot["heute"] = {"tag": (datetime.fromisoformat(HOY) - timedelta(days=1)).strftime("%Y-%m-%d"),
                        "schritt": rot["heute"]["schritt"], "erledigt": [], "fertig": True}
    p.write_text(json.dumps(rot, indent=1))
    g = lambda *a, cwd=ws: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    g("config", "user.email", "sim@example.invalid")
    g("config", "user.name", "sim")
    g("add", "-A")
    g("commit", "-qm", "sim")
    g("init", "-q", "--bare", str(tmp / "remote.git"), cwd=tmp)
    g("remote", "add", "origin", str(tmp / "remote.git"))
    g("push", "-q", "-u", "origin", "main")
    if reglas.get("_guardado_falla"):
        g("remote", "set-url", "origin", str(tmp / "no_existe.git"))
    bin_ = tmp / "bin"
    bin_.mkdir()
    shim = bin_ / "python"
    shim.write_text(f'#!/bin/bash\nexec "{REALPY}" "{WRAPPER}" "$@"\n')
    shim.chmod(0o755)
    state = tmp / "sim_state.json"
    state.write_text(json.dumps({"reglas": reglas, "intentos": [], "contenedores": {}, "fotos": {}, "emails": [],
                                 "publicado": {"ig_story": [], "fb_story": [], "ig_feed": [], "fb_feed": []}}))
    return ws, bin_, state


def simular(nombre, reglas):
    tmp = Path(tempfile.mkdtemp(prefix=f"sim_{nombre}_"))
    ws, bin_, state = preparar(tmp, reglas)
    wf = yaml.safe_load((ws / ".github/workflows/stories.yml").read_text())
    env_base = {k: v for k, v in os.environ.items() if not k.startswith(("FACEBOOK", "INSTAGRAM", "GMAIL"))}
    env_base.update({"PATH": f"{bin_}:{os.environ['PATH']}", "SIM_STATE": str(state), "GUARDAR_PAUSA": "0",
                     "TZ": "Europe/Berlin"})
    github = {"workspace": str(ws), "repository": "simulacion/hahn-nador-flight-deals",
              "server_url": "https://github.com", "run_id": "999000111", "run_number": "1"}
    secrets = {"FACEBOOK_PAGE_ACCESS_TOKEN": "token-ficticio", "FACEBOOK_PAGE_ID": "111", "INSTAGRAM_USER_ID": "222",
               "GITHUB_TOKEN": "x"}
    ctx = {"github": github, "secrets": secrets, "modus": "veroeffentlichen", "needs": {},
           "job_env": wf["jobs"]["stories"].get("env", {})}

    def subir(job):                               # no se sube nada a GitHub; las URLs se simulan
        return True

    job = Job(ws, env_base, ctx)
    job.ejecutar(wf["jobs"]["stories"]["steps"], {"deps": lambda j: True, "subir": subir})
    ctx2 = dict(ctx, needs={"stories": "failure" if job.fallo else "success"}, job_env=wf["jobs"]["aviso"].get("env", {}))
    aviso = Job(ws, env_base, ctx2)
    aviso.ejecutar(wf["jobs"]["aviso"]["steps"], {})
    s = json.loads(state.read_text())
    lauf = ws / "output" / "lauf"
    # GitHub envía UN email cuando la ejecución termina "Failed" (algún job falló); contenido = informe del aviso
    ejecucion_fallida = job.fallo or aviso.fallo
    aviso_json = json.loads((lauf / "aviso.json").read_text()) if (lauf / "aviso.json").exists() else None
    s["emails"] = [aviso_json] if ejecucion_fallida else []
    s["coherente"] = ejecucion_fallida == (aviso_json is not None) and aviso.fallo == (aviso_json is not None)
    resumen = ws / ".gh_summary.md"
    s["resumen"] = resumen.read_text() if resumen.exists() else ""
    leer = lambda n: json.loads((lauf / n).read_text()) if (lauf / n).exists() else None
    return {"tmp": tmp, "log": job.log, "aviso_log": aviso.log, "estado": s, "stories": leer("stories.json"),
            "feed": leer("feed.json"), "guardado": leer("guardado.json"), "api": leer("api_fehler.json"),
            "pasos": job.steps, "remote": tmp / "remote.git"}


# ---------------------------------------------------------------- comprobaciones por escenario
def comprobar(nombre, r):
    s, st, fd, gd = r["estado"], r["stories"], r["feed"], r["guardado"]
    pub, emails = s["publicado"], s["emails"]
    n = st["anzahl"] if st else 0
    chk = []

    def c(desc, ok):
        chk.append((desc, bool(ok)))

    def feed_ok(plat):
        return fd and all(v["estado"] == "publicado" for k, v in fd["beitraege"].items() if k.endswith(plat)) \
            and any(k.endswith(plat) for k in fd["beitraege"])

    if nombre == "1_todo_bien":
        c(f"Stories Instagram {len(pub['ig_story'])}/{n}", n and len(pub["ig_story"]) == n)
        c(f"Stories Facebook {len(pub['fb_story'])}/{n}", n and len(pub["fb_story"]) == n)
        c("Post del día publicado en Facebook", feed_ok("/facebook"))
        c("Post del día publicado en Instagram", feed_ok("/instagram"))
        c(f"Guardado ejecutado ({gd and gd['estado']})", gd and gd["estado"] == "ok")
        c("Ningún email", len(emails) == 0)
    elif nombre == "2_story_recuperada":
        for story, esperado in (("05_top5_guenstigste_rueckfluege.jpg", 2), ("14_kalender_2027-01.jpg", 3)):
            k = s["intentos"].count(f"ig_story:{story}")
            c(f"{story}: falló y se publicó en el intento {k}", k == esperado and story in pub["ig_story"])
        c(f"Stories Instagram {len(pub['ig_story'])}/{n} (el flujo continuó)", n and len(pub["ig_story"]) == n)
        c(f"Stories Facebook {len(pub['fb_story'])}/{n}", n and len(pub["fb_story"]) == n)
        c("Registradas como recuperadas", st and len(st["instagram"]["recuperadas"]) == 2)
        c("Post del día publicado en Facebook e Instagram", feed_ok("/facebook") and feed_ok("/instagram"))
        c(f"Guardado ejecutado ({gd and gd['estado']})", gd and gd["estado"] == "ok")
        c("Ningún email", len(emails) == 0)
    elif nombre == "3_story_falla_3_veces":
        story = "15_kalender_2027-02.jpg"
        c(f"{story}: exactamente 3 intentos", s["intentos"].count(f"ig_story:{story}") == 3)
        c(f"Las demás stories se intentaron: Instagram {len(pub['ig_story'])}/{n} (falta solo la 15)",
          n and len(pub["ig_story"]) == n - 1 and story not in pub["ig_story"])
        c(f"Stories Facebook {len(pub['fb_story'])}/{n}", n and len(pub["fb_story"]) == n)
        c("Post del día publicado en Facebook", feed_ok("/facebook"))
        c("Post del día publicado en Instagram", feed_ok("/instagram"))
        c(f"Guardado de lo completado ({gd and gd['estado']})", gd and gd["estado"] == "ok")
        c("Exactamente 1 email", len(emails) == 1)
        c("El email nombra la story, la plataforma y el error",
          emails and story in emails[0]["cuerpo"] and "Instagram" in emails[0]["cuerpo"]
          and "does not exist" in emails[0]["cuerpo"])
    elif nombre == "4_api_ryanair_caida":
        c("Se intentó consultar la API de Ryanair", s.get("llamadas_ryanair", 0) > 0)
        c("Ninguna llamada de publicación a Facebook/Instagram",
          not s["intentos"] and not any(pub.values()))
        c("Stories y post omitidos (sin resultados de publicación)", st is None and fd is None)
        c(f"Guardado ejecutado ({gd and gd['estado']})", gd is not None)
        c("Exactamente 1 email", len(emails) == 1)
        c("El email indica la hora del fallo de la API y lo omitido",
          emails and "API de Ryanair" in emails[0]["cuerpo"] and r["api"]["zeit"] in emails[0]["cuerpo"]
          and "omitido" in emails[0]["cuerpo"])
    elif nombre == "5a_post_instagram_falla":
        c(f"Stories Instagram {len(pub['ig_story'])}/{n} y Facebook {len(pub['fb_story'])}/{n}",
          n and len(pub["ig_story"]) == n and len(pub["fb_story"]) == n)
        c("Post del día publicado en Facebook (el paso continuó)", feed_ok("/facebook"))
        c("Post del día NO publicado en Instagram", not pub["ig_feed"])
        c(f"Guardado ejecutado ({gd and gd['estado']})", gd and gd["estado"] == "ok")
        c("Exactamente 1 email", len(emails) == 1)
        c("El email nombra Instagram y el post", emails and "Publicar el post del día" in emails[0]["cuerpo"]
          and "Plataforma: Instagram" in emails[0]["cuerpo"])
    elif nombre == "5b_guardado_falla":
        c(f"Stories Instagram {len(pub['ig_story'])}/{n} y Facebook {len(pub['fb_story'])}/{n}",
          n and len(pub["ig_story"]) == n and len(pub["fb_story"]) == n)
        c("Post del día publicado en Facebook e Instagram", feed_ok("/facebook") and feed_ok("/instagram"))
        c("Guardado registrado como fallido", gd and gd["estado"] == "fallido")
        c("Exactamente 1 email", len(emails) == 1)
        c("El email nombra el guardado", emails and "Guardar estado en el repositorio" in emails[0]["cuerpo"])
    c("Ejecución 'Failed' (= email de GitHub) solo si hay aviso, y viceversa", s["coherente"])
    if emails:
        c("Informe completo en la página de la ejecución (resumen)", emails[0]["cuerpo"].strip()[:40] in s["resumen"])
    return chk


def main():
    nombres = sys.argv[1:] or list(ESCENARIOS)
    total_ok = True
    for nombre in nombres:
        print(f"\n=== Escenario {nombre} ===")
        r = simular(nombre, ESCENARIOS[nombre])
        print("\n".join(r["log"]))
        print("   — job aviso —")
        print("\n".join(r["aviso_log"]))
        for desc, ok in comprobar(nombre, r):
            total_ok &= ok
            print(f"   {'PASA ' if ok else 'FALLA'}  {desc}")
        for i, e in enumerate(r["estado"]["emails"], 1):
            print(f"\n   ✉️  Ejecución 'Failed' → GitHub enviaría 1 email · informe en la página — {e['asunto']}\n")
            print("\n".join("      " + x for x in e["cuerpo"].splitlines()))
        out = PROJ / "output" / "simulacion" / nombre
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        (out / "resultado.json").write_text(json.dumps({k: v for k, v in r.items() if k not in ("tmp", "remote")},
                                                       indent=1, ensure_ascii=False, default=str))
        shutil.rmtree(r["tmp"], ignore_errors=True)
    print("\nRESULTADO:", "todas las comprobaciones pasan" if total_ok else "HAY COMPROBACIONES QUE FALLAN")
    sys.exit(0 if total_ok else 1)


if __name__ == "__main__":
    main()
