#!/usr/bin/env bash
# Hook SessionStart del plugin: crea/actualiza el entorno de Python en la carpeta de datos
# del plugin (sobrevive a actualizaciones). Solo reinstala cuando cambia la versión del plugin.
#   preparar.sh <CLAUDE_PLUGIN_ROOT> <CLAUDE_PLUGIN_DATA>
set -euo pipefail

RAIZ=${1:?falta CLAUDE_PLUGIN_ROOT}
DATOS=${2:?falta CLAUDE_PLUGIN_DATA}
VENV="$DATOS/venv"
SELLO="$DATOS/instalado-desde"

chmod +x "$RAIZ/bin/srv-mcp" 2>/dev/null || true
# Ruta fija para la terminal del usuario (la carpeta del plugin cambia con cada versión).
mkdir -p "$DATOS"
ln -sfn "$RAIZ/bin/srv-mcp" "$DATOS/srv-mcp"
[[ -x "$VENV/bin/python" && "$(cat "$SELLO" 2>/dev/null)" == "$RAIZ" ]] && exit 0

PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY=$(command -v "$c"); break
  fi
done
if [[ -z "$PY" ]]; then
  echo "servidor-mcp: necesita Python 3.11 o superior (macOS: brew install python)." >&2
  exit 0 # no bloquear la sesión
fi

[[ -x "$VENV/bin/python" ]] || "$PY" -m venv "$VENV"
# Instalación normal (no editable): la carpeta del plugin cambia con cada versión.
"$VENV/bin/python" -m pip install -q --disable-pip-version-check --upgrade "$RAIZ" >&2
echo "$RAIZ" > "$SELLO"
