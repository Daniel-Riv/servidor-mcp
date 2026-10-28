"""Ejecución de comandos por SSH reutilizando la sesión que abre el usuario (srv-mcp on)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime

from .config import Config


class SesionCerrada(Exception):
    pass


@dataclass
class Resultado:
    codigo: int
    stdout: str
    stderr: str
    tiempo_agotado: bool = False


def servidores(cfg: Config) -> list[str]:
    """Alias registrados con `srv-mcp setup` (bloques marcados en ~/.ssh/config)."""
    if not cfg.ssh_config.exists():
        return []
    return re.findall(r"^# srv-mcp: (?!fin )(\S+)\s*\nHost \1\b", cfg.ssh_config.read_text(), re.M)


async def _correr(*args: str, timeout: float) -> Resultado:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
        agotado = False
    except TimeoutError:
        proc.kill()
        out, err = await proc.communicate()
        agotado = True
    return Resultado(
        codigo=proc.returncode if proc.returncode is not None else -1,
        stdout=out.decode(errors="replace"),
        stderr=err.decode(errors="replace"),
        tiempo_agotado=agotado,
    )


async def sesion_abierta(cfg: Config, alias: str) -> bool:
    r = await _correr(cfg.ssh, "-F", str(cfg.ssh_config), "-O", "check", alias, timeout=10)
    return r.codigo == 0


async def ejecutar(cfg: Config, alias: str, comando: str, timeout: int | None = None) -> Resultado:
    if not await sesion_abierta(cfg, alias):
        raise SesionCerrada(
            f"La sesión SSH de '{alias}' está cerrada. Pide al usuario que corra en su terminal: "
            f"srv-mcp on {alias}"
        )
    r = await _correr(
        cfg.ssh, "-F", str(cfg.ssh_config),
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        alias, comando,
        timeout=timeout or cfg.timeout,
    )
    _bitacora(cfg, alias, comando, r)
    return r


def _bitacora(cfg: Config, alias: str, comando: str, r: Resultado) -> None:
    cfg.logs.mkdir(parents=True, exist_ok=True)
    estado = "timeout" if r.tiempo_agotado else str(r.codigo)
    linea = comando.replace("\n", "\\n")
    with open(cfg.logs / f"{alias}.log", "a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{estado}\t{linea}\n")
