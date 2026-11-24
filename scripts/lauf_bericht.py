"""Email de aviso al terminar la ejecución diaria (último paso, se ejecuta siempre).

Reglas (pedidas por el usuario, 24.11.2026):
  - Todo bien → NO se envía email.
  - Una story falla y se publica en el 2.º o 3.º intento → recuperada, no cuenta como fallo.
  - La API de Ryanair falló → no se publicó nada; un email indicando que se omitió la publicación.
  - Cualquier otro fallo → UN solo email al final: fecha y hora, paso, plataforma, error, estado final
    de las stories, del post en cada plataforma y del guardado, y el enlace a la ejecución de GitHub Actions.

Lee los archivos de output/lauf/ (ver scripts/lauf_estado.py).
El email lo envía GitHub mismo (deseo del usuario: su dirección no se guarda en ningún sitio): si hay un fallo,
este paso escribe el informe en la página de la ejecución (resumen + anotación) y termina con error → la ejecución
queda "Failed" y GitHub manda su email de aviso a la cuenta que la inició (claudeinte). Todo bien → sin error,
sin email. Requisito: en github.com/settings/notifications → "Actions": Email activado y
"Only notify for failed workflows".
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lauf_estado as le  # noqa: E402

PASOS = {  # id del paso en stories.yml → nombre legible
    "checkout": "Descargar el código",
    "python": "Preparar Python",
    "deps": "Instalar dependencias",
    "tag": "Fecha y protección contra duplicados",
    "bilder": "Consultar precios y crear las stories",
    "jpeg": "Convertir stories a JPEG",
    "feed_bilder": "Crear imágenes del post (mejor precio)",
    "rotacion": "Preparar el post del día (rotación)",
    "subir": "Subir imágenes (branch stories)",
    "stories": "Publicar stories",
    "feed": "Publicar el post del día",
    "guardar": "Guardar estado en el repositorio",
}
PLAT = {"instagram": "Instagram", "facebook": "Facebook"}


def _txt_fallo(id_):
    f = le.leer(f"{id_}.fallo.json") or {}
    lin = [x for x in f.get("ultimas_lineas", []) if x.strip()]
    err = next((x for x in reversed(lin) if any(w in x for w in ("Error", "Fehler", "error", "❌", "Traceback"))), None)
    return f.get("zeit"), (err or (lin[-1] if lin else "El paso terminó con error (ver registro)")).strip()


def analizar(pasos, run_url, job_result, ahora):
    """Devuelve (tipo, asunto, cuerpo) o None si todo salió bien."""
    api = le.leer("api_fehler.json")
    stories = le.leer("stories.json")
    feed = le.leer("feed.json")
    guard = le.leer("guardado.json")
    out = lambda i: (pasos or {}).get(i, {}).get("outcome")        # success / failure / skipped / cancelled / None
    fecha = ahora[:10]
    problemas = []                                               # (zeit, paso, plataforma, error)

    # ---------- estado final (para cualquier email) ----------
    def estado_stories():
        if api:
            return ["No se publicó ninguna story (omitido por el fallo de la API de Ryanair)."]
        if (pasos or {}).get("tag", {}).get("outputs", {}).get("fertig") == "ja":
            return ["Ya estaban publicadas todas antes hoy (no se volvieron a publicar)."]
        if not stories:
            motivo = {"skipped": "el paso no se ejecutó porque falló un paso anterior",
                      "failure": "el paso falló antes de publicar", None: "el paso no llegó a ejecutarse"}
            return [f"No se publicaron ({motivo.get(out('stories'), out('stories'))})."]
        r = []
        for p in ("instagram", "facebook"):
            s = stories[p]
            t = f"{PLAT[p]}: {s.get('total', len(s['publicadas']) + len(s['ya_publicadas']))}/{stories['anzahl']} publicadas"
            if s["recuperadas"]:
                t += " · recuperadas: " + ", ".join(f"{x['story']} (intento {x['versuch']})" for x in s["recuperadas"])
            if s["fallidas"]:
                t += " · fallidas tras 3 intentos: " + ", ".join(x["story"] for x in s["fallidas"])
            r.append(t)
        return r

    def estado_feed():
        if api:
            return ["Facebook: no publicado (omitido por el fallo de la API)",
                    "Instagram: no publicado (omitido por el fallo de la API)"]
        if feed is None:
            motivo = {"skipped": "el paso no se ejecutó porque falló un paso anterior",
                      "failure": "el paso falló antes de publicar", None: "el paso no llegó a ejecutarse"}
            return [f"No publicado ({motivo.get(out('feed'), out('feed'))})."]
        if feed.get("estado") == "ya_publicado_hoy":
            return ["Ya estaba publicado antes hoy."]
        r = []
        for p in ("facebook", "instagram"):
            xs = {k.split("/")[0]: v for k, v in feed["beitraege"].items() if k.endswith("/" + p)}
            if not xs:
                r.append(f"{PLAT[p]}: no publicado")
                continue
            r.append(f"{PLAT[p]}: " + ", ".join(
                f"{n} → {'publicado' if v['estado'] in ('publicado', 'ya_publicado') else 'FALLÓ'}" for n, v in xs.items()))
        return r

    def estado_guardado():
        if guard:
            return {"ok": "Guardado correctamente.", "sin_cambios": "Nada nuevo que guardar.",
                    "fallido": "FALLÓ (ver el error arriba)."}.get(guard["estado"], guard["estado"])
        return "No se ejecutó." if out("guardar") in (None, "skipped") else f"Estado: {out('guardar')}"

    def cuerpo(cabecera, problemas):
        lin = [cabecera, ""]
        for z, paso, plat, err in problemas:
            err = " ".join(x.strip() for x in str(err).splitlines() if x.strip())[:600]
            lin += [f"• Fecha y hora: {z}", f"  Paso: {paso}", f"  Plataforma: {plat}", f"  Error: {err}", ""]
        lin += ["ESTADO FINAL", "Stories:"] + [f"  - {x}" for x in estado_stories()]
        lin += ["Post del día:"] + [f"  - {x}" for x in estado_feed()]
        lin += [f"Guardado: {estado_guardado()}", "", f"Ejecución en GitHub Actions: {run_url}"]
        return "\n".join(lin) + "\n"

    # ---------- 1) fallo de la API de Ryanair ----------
    if api:
        fx = api.get("fehler", [])
        err = (f"{len(fx)} consulta(s) de precios fallaron. Primer error: {fx[0]}" if fx else "sin detalle")[:600]
        problemas.append((api["zeit"], "Consultar precios (API de Ryanair)", "—", err))
        if guard and guard.get("estado") == "fallido":
            problemas.append((guard["zeit"], PASOS["guardar"], "—", guard.get("detalle", "")))
        cab = ("La API de Ryanair no respondió o devolvió un error, así que hoy NO se publicó nada: "
               "ni las stories ni el post del día, ni en Facebook ni en Instagram.")
        return ("api", f"⚠️ {fecha}: publicación omitida – fallo de la API de Ryanair", cuerpo(cab, problemas))

    # ---------- 2) cualquier otro fallo ----------
    if pasos is None:
        problemas.append((ahora, "Ejecución completa", "—",
                          f"La ejecución terminó de forma inesperada (resultado: {job_result}); no hay registro de pasos."))
    for id_, nombre in PASOS.items():
        if out(id_) != "failure" or id_ in ("stories", "feed", "guardar"):
            continue
        z, e = _txt_fallo(id_)
        problemas.append((z or ahora, nombre, "—", e))
    if stories:
        for p in ("instagram", "facebook"):
            for x in stories[p]["fallidas"]:
                problemas.append((x["zeit"], f"{PASOS['stories']} ({x['story']}, 3 intentos)", PLAT[p], x["error"]))
    elif out("stories") == "failure":
        z, e = _txt_fallo("stories")
        problemas.append((z or ahora, PASOS["stories"], "Instagram y Facebook", e))
    if feed:
        for k, v in feed.get("beitraege", {}).items():
            if v["estado"] == "fallido":
                n, p = k.split("/")
                problemas.append((v["zeit"], f"{PASOS['feed']} ({n})", PLAT[p], v["error"]))
    elif out("feed") == "failure":
        z, e = _txt_fallo("feed")
        problemas.append((z or ahora, PASOS["feed"], "Instagram y Facebook", e))
    if guard and guard["estado"] == "fallido":
        problemas.append((guard["zeit"], PASOS["guardar"], "—", guard.get("detalle", "")))
    elif out("guardar") == "failure":
        z, e = _txt_fallo("guardar")
        problemas.append((z or ahora, PASOS["guardar"], "—", e))
    if job_result == "cancelled" and pasos is not None:
        problemas.append((ahora, "Ejecución completa", "—", "La ejecución fue cancelada o superó el tiempo máximo."))

    if not problemas:
        return None
    problemas.sort(key=lambda x: x[0])
    cab = f"La ejecución diaria del {fecha} terminó con {len(problemas)} fallo(s):"
    return ("fallo", f"⚠️ {fecha}: fallo en la publicación diaria ({problemas[0][1]})", cuerpo(cab, problemas))


def main():
    pasos = le.leer("pasos.json")
    if pasos and "_ilegible" in pasos:
        pasos = None
    run_url = os.environ.get("RUN_URL", "(sin enlace)")
    res = analizar(pasos, run_url, os.environ.get("JOB_RESULT", ""), le.ahora())
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if res is None:
        print("Todo terminó bien – no hay aviso.")
        if resumen:
            Path(resumen).write_text("✅ Todo terminó bien – sin aviso.\n", encoding="utf-8")
        return
    tipo, asunto, cuerpo = res
    print(f"{asunto}\n\n{cuerpo}")
    le.escribir("aviso.json", {"tipo": tipo, "asunto": asunto, "cuerpo": cuerpo})
    if resumen:                                   # informe completo en la página de la ejecución
        Path(resumen).write_text(f"## {asunto}\n\n```\n{cuerpo}```\n", encoding="utf-8")
    corto = cuerpo.split("ESTADO FINAL")[0].strip().replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::error title={asunto.replace(':', ' -').replace(',', ' ')}::{corto}")
    sys.exit(1)                                   # ejecución "Failed" → GitHub envía su email de aviso


if __name__ == "__main__":
    main()
