#!/usr/bin/env bash
# Prepara el post del día (rotación de 7 días). No publica nada.
# Uso: bash scripts/rotacion_paso.sh <fecha YYYY-MM-DD>
set -e
D="$1"
FERTIG=$(python -c "import json,pathlib; p=pathlib.Path('data/feed_rotation.json'); h=(json.loads(p.read_text()) if p.exists() else {}).get('heute') or {}; print('ja' if h.get('tag')=='$D' and h.get('fertig') else 'nein')")
if [ "$FERTIG" = "ja" ]; then echo "Feed heute schon veröffentlicht."; exit 0; fi
[ -d "output/stories/$D" ] || python scripts/vorschau_story_kalender.py --alle
python scripts/feed_rotation.py --story-ordner "output/stories/$D" --out "public/$D"
