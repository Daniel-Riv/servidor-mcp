---
name: access-server-dan
description: Trabajar en los servidores Linux del usuario por SSH con srv-mcp.
disable-model-invocation: true
argument-hint: "[servidor] qué revisar o hacer"
---

# Acceso a servidores (srv-mcp)

Pedido del usuario: $ARGUMENTS

Trabajas en servidores reales por SSH con el comando `srv-mcp` (en el PATH del usuario).
La conexión la abre el usuario con su contraseña; tú nunca la ves ni la pides.

## Primer paso, siempre

```bash
srv-mcp status
```
Muestra los servidores y si su sesión está abierta. Si el servidor que necesitas está
**cerrado**, detente y pide al usuario que corra en su terminal `srv-mcp on <alias>`
(es interactivo, tú no puedes). Si el pedido no dice en qué servidor, pregunta.

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
