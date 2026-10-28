# servidor-mcp

Servidor MCP para que las IAs (Claude Code, Claude Desktop, Cursor, VS Code…) trabajen
en tus servidores Linux por SSH, **sin darles tu contraseña** y sin instalar nada en el
servidor.

```
Tú:   srv-mcp on tecon-prod      → escribes la contraseña → sesión SSH abierta (8h)
IA:   ejecutar_comando(...)      → usa esa sesión abierta, sin contraseña
Tú:   srv-mcp off tecon-prod     → la IA pierde el acceso al instante
```

## Herramientas que recibe la IA

| Herramienta         | Qué hace                                                        |
|---------------------|-----------------------------------------------------------------|
| `listar_servidores` | Servidores registrados y si su sesión está abierta              |
| `estado_sistema`    | Carga, memoria, disco, top procesos, servicios caídos, Docker   |
| `ver_logs`          | journalctl de un servicio, `docker logs`, un archivo o el sistema; con filtro |
| `leer_archivo`      | Primeras o últimas N líneas de un archivo                       |
| `escribir_archivo`  | Crea/reemplaza un archivo, con respaldo `.bak.<fecha>` automático |
| `ejecutar_comando`  | Cualquier comando de shell (no interactivo)                     |

Cada llamada aparece en tu cliente de IA con el comando exacto, y queda en la bitácora
`~/.srv-mcp/logs/<servidor>.log` (`srv-mcp log <servidor>`).

## Instalación (cada persona, en su Mac o Linux)

Requisitos: Python 3.11+ y OpenSSH.

```bash
cd servidor-mcp
python3 -m venv .venv && .venv/bin/pip install -e .
mkdir -p ~/bin && ln -sf "$PWD/bin/srv-mcp" ~/bin/srv-mcp
```

Si `~/bin` no está en tu PATH, agrega a `~/.zshrc`: `export PATH="$HOME/bin:$PATH"`

### Conectarlo a tu IA

El comando del servidor es la ruta absoluta a `.venv/bin/servidor-mcp`.

**Claude Code**
```bash
claude mcp add servidor --scope user -- "$PWD/.venv/bin/servidor-mcp"
```

**Claude Desktop / Cursor / otros** (archivo de configuración MCP del cliente):
```json
{
  "mcpServers": {
    "servidor": { "command": "/ruta/a/servidor-mcp/.venv/bin/servidor-mcp" }
  }
}
```
- Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Cursor: `~/.cursor/mcp.json`

### Claude Code solo con `/access-server-dan` (alternativa al MCP)

Si prefieres que Claude Code toque servidores **solo cuando tú lo pidas** con `/`, no
registres el MCP ahí y usa la skill incluida, que ejecuta con el mismo motor
(`srv-mcp run/estado/logs/leer/escribir`, mismas reglas y bitácora):

```bash
mkdir -p ~/.claude/skills && ln -sf "$PWD/skill/access-server-dan" ~/.claude/skills/access-server-dan
claude mcp remove servidor --scope user   # si lo habías agregado
```

Uso: `/access-server-dan revisa los logs de nginx en prod`

## Servidores detrás de otro (dev/prod por salto)

`srv-mcp setup` pregunta si se entra pasando por otro servidor ya registrado y configura
`ProxyJump`. Cada uno tiene su propio usuario y contraseña:

```bash
srv-mcp on prod    # pide la contraseña del salto (si no está abierta) y luego la de prod
```

## Uso diario

```bash
srv-mcp setup             # una vez por servidor: alias, host, usuario, puerto
srv-mcp on tecon-prod     # antes de pedirle algo a la IA
srv-mcp status            # qué sesiones están abiertas
srv-mcp log tecon-prod    # qué ejecutaron las IAs
srv-mcp off tecon-prod    # al terminar
```

## Permisos (`~/.srv-mcp/config.toml`)

Por defecto todo está permitido. Cada usuario lo cambia en su archivo
(ver [config.ejemplo.toml](config.ejemplo.toml)):

```toml
modo = "lectura"                       # "completo" (defecto) o "lectura"
bloqueados = ['\breboot\b', 'rm -rf']  # regex que se rechazan siempre
timeout = 120                          # segundos por comando

[servidores."prod"]                    # ajustes por servidor (setup lo crea si eliges solo lectura)
modo = "lectura"
bloqueados = ['virsh destroy']
```

Los cambios aplican en la siguiente llamada; no hay que reiniciar nada.

El modo "lectura" rechaza comandos que parecen modificar el servidor (rm, mv,
`systemctl restart`, `apt install`, `docker stop/rm/down`, redirecciones `>`…). Es una
red de seguridad contra errores de la IA, **no un límite de seguridad**. El límite real es
el usuario SSH: para acceso realmente restringido, crea en el servidor un usuario sin
sudo y regístralo con `srv-mcp setup`.

## Seguridad

- La contraseña solo la escribes tú en tu terminal; queda un socket local en
  `~/.ssh/cm/` que solo tu usuario del Mac puede usar.
- Solo se aceptan servidores registrados con `srv-mcp setup`.
- Mientras la sesión esté abierta, la IA puede hacer lo que tu usuario SSH pueda
  hacer. Ciérrala con `srv-mcp off` al terminar.
- `sudo` con contraseña no funciona (no es interactivo). Para permitir comandos
  concretos, configura `NOPASSWD` solo para ellos en el servidor.

## Desarrollo

```bash
.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest
```
Las pruebas usan un ssh falso (`tests/fake_ssh`) que ejecuta en local.
