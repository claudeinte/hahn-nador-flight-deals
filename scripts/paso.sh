#!/usr/bin/env bash
# Ejecuta un paso del workflow y guarda su registro en output/lauf/<id>.log.
# Si el paso falla, escribe output/lauf/<id>.fallo.json (hora, código, últimas líneas) para el email de aviso.
# Uso: bash scripts/paso.sh <id> <comando> [argumentos…]   – el código de salida del comando se conserva.
set -o pipefail
id="$1"; shift
LAUF="${LAUF_DIR:-output/lauf}"
mkdir -p "$LAUF"
"$@" 2>&1 | tee "$LAUF/$id.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then
  python3 - "$LAUF/$id.fallo.json" "$rc" "$LAUF/$id.log" <<'EOF'
import json, sys
from datetime import datetime
from zoneinfo import ZoneInfo
p, rc, log = sys.argv[1:4]
lines = [l for l in open(log, encoding="utf-8", errors="replace").read().splitlines() if l.strip()]
json.dump({"zeit": datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S"),
           "codigo": int(rc), "ultimas_lineas": lines[-12:]}, open(p, "w"), indent=1, ensure_ascii=False)
EOF
fi
exit "$rc"
