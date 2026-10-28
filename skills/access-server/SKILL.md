---
name: access-server
description: Trabajar en los servidores Linux del usuario por SSH con srv-mcp (estado, logs, archivos, comandos).
disable-model-invocation: true
argument-hint: "[servidor] qué revisar o hacer"
---

# Acceso a servidores (srv-mcp)

Pedido del usuario: $ARGUMENTS

Trabajas en servidores reales por SSH con el comando `srv-mcp`.
La conexión la abre el usuario con su contraseña; tú nunca la ves ni la pides.

Ruta del comando: si `srv-mcp` responde "command not found", usa
`${CLAUDE_PLUGIN_ROOT}/bin/srv-mcp` (instalado como plugin) o `~/bin/srv-mcp`
(instalado con instalar.sh; úsala también si la ruta anterior aparece con `${` sin
reemplazar).

## Primer paso, siempre

```bash
srv-mcp status
```
Muestra los servidores y si su sesión está abierta.

Comandos para la terminal del usuario: si en su terminal no existe `srv-mcp`, dale la ruta
fija del plugin, `~/.claude/plugins/data/servidor-mcp-servidor-mcp/srv-mcp` (verifica que
exista con `ls`), y sugiérele una vez crear el atajo:
`mkdir -p ~/bin && ln -sf ~/.claude/plugins/data/servidor-mcp-servidor-mcp/srv-mcp ~/bin/srv-mcp`.

- **No hay servidores registrados:** el usuario debe registrarlos en su terminal (es
  interactivo, tú no puedes) con `srv-mcp setup`. Explícale que pregunta alias, IP,
  usuario, puerto, si se entra pasando por otro servidor y si es solo lectura.
- **El servidor está cerrado:** pide al usuario que corra en su terminal
  `srv-mcp on <alias>` y espera.
- Si el pedido no dice en qué servidor, pregunta.

## Herramientas

Usa solo estos comandos para tocar servidores, nunca `ssh` directo: aplican los permisos
de cada servidor (prod es solo lectura) y registran todo en la bitácora.

| Para                         | Comando                                                              |
|------------------------------|----------------------------------------------------------------------|
| Salud general                | `srv-mcp estado <alias>`                                             |
| Logs de un servicio systemd  | `srv-mcp logs <alias> servicio nginx -n 200 --filtro error`          |
| Logs de un contenedor        | `srv-mcp logs <alias> docker <contenedor> -n 200 --desde 1h`         |
| Logs de un archivo           | `srv-mcp logs <alias> archivo /var/log/syslog -n 200`                |
| Journal del sistema          | `srv-mcp logs <alias> sistema --desde "1 hour ago"`                  |
| Leer un archivo              | `srv-mcp leer <alias> /etc/nginx/nginx.conf` (`--final` = últimas líneas) |
| Cualquier comando            | `srv-mcp run <alias> "comando"` (`--timeout 300` si tarda)           |
| Escribir un archivo          | `srv-mcp escribir <alias> /ruta <<'EOF'` … `EOF` (respalda el anterior) |

Los comandos no son interactivos: usa `-y`, `--no-pager`, `| tail -n 200`. `sudo` con
contraseña falla; si hace falta, dale al usuario el comando para que lo corra él.

## Reglas

- Antes de cualquier cambio (reiniciar, instalar, borrar, editar, `docker stop/rm/down`,
  firewall, usuarios, VMs con `virsh`) explica qué harás y espera un "sí" explícito.
- Si `srv-mcp` rechaza un comando por modo "lectura", no intentes rodearlo: díselo al
  usuario. El modo se cambia en `~/.srv-mcp/config.toml`.
- Antes de editar un archivo, léelo; `escribir` guarda un respaldo `.bak.<fecha>`.
- Resume lo encontrado en lenguaje claro: qué está mal, evidencia (líneas de log) y
  qué propones.
- Al terminar, recuerda que puede cortar el acceso con `srv-mcp off <alias>`.
