"""Servidor MCP: herramientas para que cualquier IA trabaje en los servidores del usuario."""

from __future__ import annotations

import base64
import shlex
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import config, ssh

INSTRUCCIONES = """\
Acceso a los servidores Linux del usuario por SSH.

- Empieza con listar_servidores para ver los alias y si la sesión está abierta.
- Si una sesión está cerrada, NO pidas contraseñas: dile al usuario que corra
  `srv-mcp on <alias>` en su terminal y espera.
- Prefiere las herramientas específicas (estado_sistema, ver_logs, leer_archivo)
  antes que ejecutar_comando: son más claras para el usuario.
- Antes de cualquier cambio (reiniciar, instalar, borrar, editar archivos, docker
  stop/rm/down, firewall, usuarios) explica qué vas a hacer y pide confirmación.
- `sudo` sin contraseña configurada falla en modo no interactivo; si pasa, dile al
  usuario que lo ejecute él.
- Limita salidas largas (tail, head, --no-pager, grep).
"""

mcp = MCPServer("servidor-mcp", instructions=INSTRUCCIONES)

LECTURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
ESCRITURA = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


def _validar(cfg: config.Config, servidor: str) -> None:
    registrados = ssh.servidores(cfg)
    if servidor not in registrados:
        lista = ", ".join(registrados) or "ninguno (el usuario debe correr `srv-mcp setup`)"
        raise ToolError(f"Servidor '{servidor}' no registrado. Disponibles: {lista}")


def _recortar(texto: str, maximo: int) -> str:
    if len(texto) <= maximo:
        return texto
    return f"[… {len(texto) - maximo} caracteres omitidos del inicio …]\n" + texto[-maximo:]


def _formatear(cfg: config.Config, comando: str, r: ssh.Resultado) -> str:
    partes = [f"$ {comando}"]
    if r.tiempo_agotado:
        partes.append("[tiempo agotado: el comando se canceló]")
    else:
        partes.append(f"[código de salida: {r.codigo}]")
    if r.stdout:
        partes.append(_recortar(r.stdout.rstrip(), cfg.max_salida))
    if r.stderr.strip():
        partes.append("--- stderr ---\n" + _recortar(r.stderr.rstrip(), cfg.max_salida // 3))
    return "\n".join(partes)


async def _correr(servidor: str, comando: str, timeout: int | None = None, verificar: bool = True) -> str:
    cfg = config.cargar()
    _validar(cfg, servidor)
    if verificar and (motivo := cfg.motivo_bloqueo(comando)):
        raise ToolError(f"Comando rechazado: {motivo}. Comando: {comando}")
    try:
        r = await ssh.ejecutar(cfg, servidor, comando, timeout)
    except ssh.SesionCerrada as e:
        raise ToolError(str(e)) from None
    if r.codigo == 255 and not r.stdout:
        raise ToolError(f"Falló la conexión SSH a '{servidor}': {r.stderr.strip()}")
    return _formatear(cfg, comando, r)


@mcp.tool(annotations=LECTURA)
async def listar_servidores() -> str:
    """Lista los servidores registrados y si su sesión SSH está abierta."""
    cfg = config.cargar()
    registrados = ssh.servidores(cfg)
    if not registrados:
        return "No hay servidores registrados. El usuario debe correr `srv-mcp setup`."
    lineas = [f"Modo: {cfg.modo}"]
    for alias in registrados:
        abierta = await ssh.sesion_abierta(cfg, alias)
        lineas.append(f"- {alias}: {'sesión abierta' if abierta else 'sesión cerrada (srv-mcp on ' + alias + ')'}")
    return "\n".join(lineas)


@mcp.tool(annotations=ESCRITURA)
async def ejecutar_comando(servidor: str, comando: str, timeout_segundos: int | None = None) -> str:
    """Ejecuta un comando de shell en el servidor y devuelve código de salida, stdout y stderr.

    No es interactivo: comandos que piden datos (contraseñas, confirmaciones, editores)
    fallan o se cancelan al agotar el tiempo. Usa flags como -y o --no-pager.
    """
    return await _correr(servidor, comando, timeout_segundos)


@mcp.tool(annotations=LECTURA)
async def estado_sistema(servidor: str) -> str:
    """Resumen de salud: uptime/carga, memoria, disco, procesos que más consumen,
    servicios systemd caídos y contenedores Docker."""
    script = (
        "echo '== Sistema =='; uname -srn; uptime; "
        "echo; echo '== Memoria =='; free -h; "
        "echo; echo '== Disco =='; df -h -x tmpfs -x devtmpfs -x squashfs -x overlay; "
        "echo; echo '== Top CPU =='; ps -eo pid,user,%cpu,%mem,etime,comm --sort=-%cpu | head -n 8; "
        "echo; echo '== Top memoria =='; ps -eo pid,user,%cpu,%mem,etime,comm --sort=-%mem | head -n 8; "
        "echo; echo '== Servicios con fallo =='; systemctl --failed --no-legend --no-pager 2>/dev/null || echo 'systemd no disponible'; "
        "echo; echo '== Docker =='; "
        "if command -v docker >/dev/null; then "
        "docker ps -a --format 'table {{.Names}}\\t{{.Status}}\\t{{.Image}}' 2>&1 | head -n 40; "
        "else echo 'docker no instalado'; fi"
    )
    return await _correr(servidor, script, verificar=False)


@mcp.tool(annotations=LECTURA)
async def ver_logs(
    servidor: str,
    tipo: Literal["servicio", "docker", "archivo", "sistema"],
    nombre: str = "",
    lineas: int = 100,
    filtro: str = "",
    desde: str = "",
) -> str:
    """Últimas líneas de logs.

    tipo: "servicio" (unidad systemd, ej. nginx), "docker" (nombre del contenedor),
    "archivo" (ruta, ej. /var/log/nginx/error.log) o "sistema" (journal completo).
    filtro: texto o regex para grep -iE. desde: solo para servicio/sistema/docker,
    ej. "1 hour ago" o "2026-10-28 08:00" (docker usa formato como "1h").
    """
    n = max(1, min(int(lineas), 2000))
    q = shlex.quote
    if tipo in ("servicio", "docker", "archivo") and not nombre:
        raise ToolError(f"Para tipo '{tipo}' falta 'nombre'.")
    if tipo == "servicio":
        cmd = f"journalctl -u {q(nombre)} --no-pager -n {n}" + (f" --since {q(desde)}" if desde else "")
    elif tipo == "sistema":
        cmd = f"journalctl --no-pager -n {n}" + (f" --since {q(desde)}" if desde else "")
    elif tipo == "docker":
        cmd = f"docker logs --tail {n}" + (f" --since {q(desde)}" if desde else "") + f" {q(nombre)} 2>&1"
    else:
        cmd = f"tail -n {n} {q(nombre)}"
    if filtro:
        cmd += f" | grep -iE {q(filtro)}"
    return await _correr(servidor, cmd, verificar=False)


@mcp.tool(annotations=LECTURA)
async def leer_archivo(servidor: str, ruta: str, lineas: int = 300, desde_el_final: bool = False) -> str:
    """Lee un archivo de texto del servidor (las primeras o últimas N líneas)."""
    n = max(1, min(int(lineas), 5000))
    cmd = f"{'tail' if desde_el_final else 'head'} -n {n} {shlex.quote(ruta)}"
    return await _correr(servidor, cmd, verificar=False)


@mcp.tool(annotations=ESCRITURA)
async def escribir_archivo(servidor: str, ruta: str, contenido: str, respaldo: bool = True) -> str:
    """Crea o reemplaza un archivo de texto en el servidor.

    Si el archivo existe y respaldo=True, primero lo copia a <ruta>.bak.<fecha>.
    No usa sudo: solo funciona en rutas donde el usuario SSH puede escribir.
    """
    cfg = config.cargar()
    if cfg.modo == "lectura":
        raise ToolError("Comando rechazado: el servidor MCP está en modo 'lectura'.")
    datos = base64.b64encode(contenido.encode()).decode()
    if len(datos) > 100_000:
        raise ToolError("Contenido demasiado grande (máx. ~75 KB).")
    q = shlex.quote(ruta)
    cmd = (
        (f'[ -f {q} ] && cp -p {q} {q}.bak.$(date +%Y%m%d-%H%M%S); ' if respaldo else "")
        + f"echo {datos} | base64 -d > {q} && echo \"escrito: $(wc -c < {q}) bytes\""
    )
    return await _correr(servidor, cmd, verificar=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
