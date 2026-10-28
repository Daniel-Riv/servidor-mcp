"""Las mismas herramientas del servidor MCP como comandos de terminal (srv-mcp run/estado/…).

Las usa la skill de Claude Code: mismas reglas de permisos y misma bitácora.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from mcp.server.mcpserver.exceptions import ToolError

from . import server


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="srv-mcp")
    sub = p.add_subparsers(dest="accion", required=True)

    run = sub.add_parser("run", help="Ejecuta un comando de shell")
    run.add_argument("servidor")
    run.add_argument("comando")
    run.add_argument("--timeout", type=int)

    estado = sub.add_parser("estado", help="Resumen de salud del servidor")
    estado.add_argument("servidor")

    logs = sub.add_parser("logs", help="Últimas líneas de logs")
    logs.add_argument("servidor")
    logs.add_argument("tipo", choices=["servicio", "docker", "archivo", "sistema"])
    logs.add_argument("nombre", nargs="?", default="")
    logs.add_argument("-n", "--lineas", type=int, default=100)
    logs.add_argument("--filtro", default="")
    logs.add_argument("--desde", default="")

    leer = sub.add_parser("leer", help="Lee un archivo")
    leer.add_argument("servidor")
    leer.add_argument("ruta")
    leer.add_argument("-n", "--lineas", type=int, default=300)
    leer.add_argument("--final", action="store_true", help="Últimas líneas en vez de las primeras")

    escribir = sub.add_parser("escribir", help="Escribe un archivo con el contenido de stdin")
    escribir.add_argument("servidor")
    escribir.add_argument("ruta")
    escribir.add_argument("--sin-respaldo", action="store_true")
    return p


async def _ejecutar(a: argparse.Namespace) -> str:
    if a.accion == "run":
        return await server.ejecutar_comando(a.servidor, a.comando, a.timeout)
    if a.accion == "estado":
        return await server.estado_sistema(a.servidor)
    if a.accion == "logs":
        return await server.ver_logs(a.servidor, a.tipo, a.nombre, a.lineas, a.filtro, a.desde)
    if a.accion == "leer":
        return await server.leer_archivo(a.servidor, a.ruta, a.lineas, a.final)
    return await server.escribir_archivo(a.servidor, a.ruta, sys.stdin.read(), not a.sin_respaldo)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        print(asyncio.run(_ejecutar(args)))
    except (ToolError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
