# servidor-mcp

Servidor MCP para que las IAs (Claude Code, Claude Desktop, Cursor, VS Code…) trabajen
en tus servidores Linux por SSH, **sin darles tu contraseña** y sin instalar nada en el
servidor.

```
Tú:   srv-mcp on dev             → escribes la contraseña → sesión SSH abierta (8h)
IA:   ejecutar_comando(...)      → usa esa sesión abierta, sin contraseña
Tú:   srv-mcp off dev            → la IA pierde el acceso al instante
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

## Antes de empezar (lo hace el administrador)

1. **Dar acceso al repositorio:** en GitHub → Settings → Collaborators → invitar a la persona.
2. **Crear su propio usuario SSH** en cada servidor (no compartan usuarios: así la
   bitácora y los permisos son de cada quien y se puede revocar a uno sin afectar a otros).
3. Opcional, para que pueda leer logs de servicios (`journalctl`), en cada servidor:
   `sudo usermod -aG systemd-journal <usuario>`

## Guía paso a paso (cada persona, en su Mac o Linux)

Requisitos: Python 3.11+, OpenSSH, [GitHub CLI](https://cli.github.com) con sesión
iniciada (`gh auth login`) y acceso al repositorio. Los comandos funcionan desde
cualquier carpeta.

### 1. Instalar

```bash
gh repo clone Daniel-Riv/servidor-mcp ~/servidor-mcp && ~/servidor-mcp/instalar.sh
```

El instalador crea `.venv` con las dependencias, deja el comando `srv-mcp` en `~/bin`
(y lo agrega al PATH) e instala la skill `/access-server` para Claude Code.
**Abre una terminal nueva** al terminar. Comprueba con `srv-mcp`: debe mostrar la ayuda.

### 2. Registrar cada servidor

```bash
srv-mcp setup
```

Hace estas preguntas (escribe la respuesta y Enter):

| Pregunta | Qué responder |
|---|---|
| Nombre corto | Un alias sin espacios, ej. `principal`, `dev`, `prod` |
| IP o dominio | La dirección del servidor |
| Usuario SSH | **Tu** usuario en ese servidor |
| Puerto SSH | Enter si es 22 |
| ¿Se entra pasando por otro servidor? | Enter si entras directo desde tu Mac. Si primero hay que entrar a otro servidor, escribe el alias de ese (debe estar registrado antes) |
| ¿Solo lectura? | `s` para que la IA no pueda hacer cambios (recomendado en producción), `n` si puede |

Ejemplo con un servidor principal y dos máquinas internas (dev y prod) a las que se
llega desde él:

```
Tu Mac ──▶ principal (IP pública) ──▶ dev  (IP interna)
                                  └──▶ prod (IP interna)
```

| Servidor | IP | ¿Pasando por otro? | ¿Solo lectura? |
|---|---|---|---|
| `principal` | IP pública | Enter (directo) | `n` |
| `dev` | IP interna | `principal` | `n` |
| `prod` | IP interna | `principal` | `s` |

Registra primero el principal, luego los demás. Revisa con `srv-mcp list`.

### 3. Abrir la sesión

```bash
srv-mcp on dev
```

- La primera vez pregunta `Are you sure you want to continue connecting (yes/no)?` → `yes`.
- Pide tu contraseña. **Mientras la escribes no se ve nada**, es normal; Enter al final.
- Si el servidor pasa por otro, pide primero la contraseña de ese (si no estaba abierto).
- La sesión dura 8 horas. `srv-mcp status` muestra cuáles están abiertas (●).

Comprueba que funciona **sin pedir contraseña**:

```bash
srv-mcp run dev "hostname && uptime"
```

### 4. Usarlo con Claude Code

En una **sesión nueva** de Claude:

```
/access-server revisa el estado de dev
```

Claude solo toca servidores cuando escribes `/access-server`. Cada comando te lo muestra
antes de ejecutarlo; los cambios los consulta primero. Al terminar:

```bash
srv-mcp log dev     # qué ejecutó la IA
srv-mcp off dev     # cortar el acceso
```

### Actualizar

```bash
cd ~/servidor-mcp && git pull && ./instalar.sh
```

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `command not found: srv-mcp` | La terminal se abrió antes de instalar. Abre una nueva (o usa `~/bin/srv-mcp`). |
| `Permission denied (publickey,password)` | La sesión no está abierta o expiró: `srv-mcp on <servidor>`. |
| `Could not resolve hostname <nombre>` | Ese alias no existe; revisa `srv-mcp list` (usa el nombre exacto que registraste). |
| `srv-mcp setup` "se queda quieto" | Está esperando tu respuesta: escríbela en la terminal y Enter. |
| `journalctl` muestra `-- No entries --` | Tu usuario no está en el grupo `systemd-journal` (ver "Antes de empezar"). |
| La IA dice "está en modo 'lectura'" | Ese servidor es solo lectura; se cambia en `~/.srv-mcp/config.toml`. |
| `/access-server` no aparece en Claude | Abre una sesión nueva; si sigue sin aparecer, vuelve a correr `./instalar.sh`. |
| `sudo` falla | No es interactivo: corre ese comando tú mismo, o configura `NOPASSWD` para él. |

## Otras IAs (Claude Desktop, Cursor…): servidor MCP

La skill `/access-server` usa `srv-mcp run/estado/logs/leer/escribir`, con las mismas
reglas y bitácora que el servidor MCP. Si prefieres que Claude Code pueda usarlo sin `/`,
instala con `./instalar.sh --mcp`.

Para otros clientes, el comando del servidor es la ruta absoluta a `.venv/bin/servidor-mcp`.

En el archivo de configuración MCP del cliente:
```json
{
  "mcpServers": {
    "servidor": { "command": "/ruta/a/servidor-mcp/.venv/bin/servidor-mcp" }
  }
}
```
- Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Cursor: `~/.cursor/mcp.json`

## Referencia de comandos

```bash
srv-mcp setup             # registrar un servidor
srv-mcp list              # servidores registrados
srv-mcp on <servidor>     # abrir sesión (pide contraseña)
srv-mcp status            # qué sesiones están abiertas
srv-mcp log <servidor>    # qué ejecutaron las IAs
srv-mcp off <servidor>    # cerrar sesión
srv-mcp run <servidor> "comando"   # ejecutar a mano con las mismas reglas
```

Para quitar un servidor, borra su bloque (`# srv-mcp: <alias>` … `# srv-mcp: fin <alias>`)
de `~/.ssh/config` y su sección en `~/.srv-mcp/config.toml`, si tiene.

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
