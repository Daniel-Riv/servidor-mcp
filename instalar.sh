#!/usr/bin/env bash
# Instala (o actualiza) servidor-mcp para el usuario actual. Se puede correr varias veces.
#
#   ./instalar.sh          srv-mcp + skill /access-server para Claude Code
#   ./instalar.sh --mcp    además registra el servidor MCP en Claude Code
#                          (Claude podrá usarlo sin que escribas /access-server)
set -euo pipefail

PROYECTO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SKILLS="$HOME/.claude/skills"
CON_MCP=false
[[ "${1:-}" == "--mcp" ]] && CON_MCP=true

paso() { printf '\n→ %s\n' "$1"; }

paso "Buscando Python 3.11 o superior"
PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY=$(command -v "$c"); break
  fi
done
[[ -n "$PY" ]] || { echo "No encontré Python 3.11+. Instálalo (macOS: brew install python) y vuelve a correr." >&2; exit 1; }
echo "  $PY ($("$PY" --version))"

paso "Instalando dependencias en $PROYECTO/.venv"
[[ -x "$PROYECTO/.venv/bin/python" ]] || "$PY" -m venv "$PROYECTO/.venv"
"$PROYECTO/.venv/bin/python" -m pip install -q --disable-pip-version-check -e "$PROYECTO"
chmod +x "$PROYECTO/bin/srv-mcp"

paso "Comando srv-mcp en ~/bin"
mkdir -p "$HOME/bin"
ln -sf "$PROYECTO/bin/srv-mcp" "$HOME/bin/srv-mcp"
case "$(basename "${SHELL:-zsh}")" in
  bash) RC="$HOME/.bashrc" ;;
  *)    RC="$HOME/.zshrc" ;;
esac
if ! grep -qs 'HOME/bin:\$PATH' "$RC"; then
  printf '\n# srv-mcp y otros scripts personales\nexport PATH="$HOME/bin:$PATH"\n' >> "$RC"
  echo "  Agregué ~/bin al PATH en $RC (abre una terminal nueva para que aplique)"
fi

paso "Skill /access-server para Claude Code"
mkdir -p "$SKILLS"
# Quita enlaces de nombres anteriores de la skill (apuntan a .../skill[s]/access-server-*).
for viejo in "$SKILLS"/access-server-*; do
  [[ -L "$viejo" && "$(readlink "$viejo")" == */skill*/access-server-* ]] && rm "$viejo" && echo "  Quité el nombre anterior: $(basename "$viejo")"
done
ln -sfn "$PROYECTO/skills/access-server" "$SKILLS/access-server"

if $CON_MCP; then
  paso "Servidor MCP en Claude Code"
  if command -v claude >/dev/null; then
    claude mcp remove servidor --scope user >/dev/null 2>&1 || true
    claude mcp add servidor --scope user -- "$PROYECTO/.venv/bin/servidor-mcp"
  else
    echo "  No encontré el comando 'claude'. Para otros clientes usa: $PROYECTO/.venv/bin/servidor-mcp"
  fi
fi

cat <<EOF

✓ Instalado.

Siguientes pasos (en una terminal nueva):
  srv-mcp setup            registra cada servidor (uno por vez)
  srv-mcp on <servidor>    abre la sesión con tu contraseña
  En Claude:  /access-server revisa el estado de <servidor>
EOF
