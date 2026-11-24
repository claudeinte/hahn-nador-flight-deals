#!/usr/bin/env bash
# Guarda en el repositorio lo que se haya completado (precios, protocolo de stories y posts).
# Escribe el resultado en output/lauf/guardado.json (o $LAUF_DIR) y termina con error si no se pudo guardar.
# Antes, un push fallido podía pasar desapercibido; ahora se detecta y se informa.
set -u
LAUF="${LAUF_DIR:-output/lauf}"
PAUSA="${GUARDAR_PAUSA:-5}"
mkdir -p "$LAUF"

resultado() {   # resultado <estado> <detalle>
  python3 - "$LAUF/guardado.json" "$1" "$2" <<'EOF'
import json, sys
from datetime import datetime
from zoneinfo import ZoneInfo
p, estado, detalle = sys.argv[1:4]
json.dump({"estado": estado, "detalle": detalle[-1500:],
           "zeit": datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")},
          open(p, "w"), indent=1, ensure_ascii=False)
EOF
}

for f in data/snapshots data/stories_veroeffentlicht.json data/feed_veroeffentlicht.json data/feed_rotation.json; do
  [ -e "$f" ] && git add "$f"
done

if git diff --cached --quiet; then
  resultado sin_cambios "Nada nuevo que guardar."
  echo "Nada nuevo que guardar."
  exit 0
fi

if ! out=$(git commit -qm "Stories/Preise $(date +'%Y-%m-%d %H:%M')" 2>&1); then
  resultado fallido "git commit: $out"
  echo "❌ git commit: $out"
  exit 1
fi

for i in 1 2 3; do
  if out=$(git pull -q --rebase 2>&1 && git push -q 2>&1); then
    resultado ok "Guardado (intento $i)."
    echo "✅ Guardado (intento $i)."
    exit 0
  fi
  echo "⚠️ Guardar, intento $i/3: $out"
  sleep "$PAUSA"
done

resultado fallido "git pull/push tras 3 intentos: $out"
echo "❌ No se pudo guardar: $out"
exit 1
