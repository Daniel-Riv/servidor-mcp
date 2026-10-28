"""Configuración del usuario: ~/.srv-mcp/config.toml (o la ruta en SRV_MCP_CONFIG)."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(os.environ.get("SRV_MCP_HOME", Path.home() / ".srv-mcp"))

# En modo "lectura" se rechaza cualquier comando que coincida con estos patrones.
# Es una red de seguridad contra errores de la IA, no un límite de seguridad:
# alguien decidido puede escribir un comando que no coincida.
PATRONES_ESCRITURA = [
    r"\brm\b", r"\brmdir\b", r"\bmv\b", r"\bcp\b", r"\bdd\b", r"\bmkfs", r"\btruncate\b",
    r"\bchmod\b", r"\bchown\b", r"\bln\b", r"\btouch\b", r"\bmkdir\b",
    r"\bsed\b.*\s-i", r"\btee\b", r"(?<![0-9&])>(?!&)", r">>",
    r"\b(apt|apt-get|dpkg|snap|pip|pip3|npm|yarn)\b\s+(install|remove|purge|upgrade|update|uninstall|i\b)",
    r"\bsystemctl\s+(start|stop|restart|reload|enable|disable|mask|kill)",
    r"\bservice\s+\S+\s+(start|stop|restart|reload)",
    r"\bdocker(\s+compose|-compose)?\s+.*\b(rm|rmi|stop|start|restart|kill|down|up|run|exec|prune|pull|build|create)\b",
    r"\b(reboot|shutdown|poweroff|halt)\b", r"\bkill(all)?\b", r"\bpkill\b",
    r"\b(useradd|userdel|usermod|passwd|groupadd|visudo|crontab)\b",
    r"\b(ufw|iptables|nft)\b", r"\bgit\s+(push|pull|reset|checkout|commit|merge|rebase|clean)\b",
    r"\b(nano|vim?|vi|emacs)\b",
]


MODOS = ("completo", "lectura")


@dataclass
class Config:
    modo: str = "completo"  # "completo" | "lectura"
    bloqueados: list[str] = field(default_factory=list)  # regex, aplican en cualquier modo
    # Ajustes por servidor: {"prod": {"modo": "lectura", "bloqueados": [...]}}
    servidores: dict[str, dict] = field(default_factory=dict)
    timeout: int = 120
    max_salida: int = 30_000
    ssh: str = "ssh"
    ssh_config: Path = Path.home() / ".ssh" / "config"
    logs: Path = BASE_DIR / "logs"

    def modo_de(self, servidor: str) -> str:
        return self.servidores.get(servidor, {}).get("modo", self.modo)

    def motivo_bloqueo(self, comando: str, servidor: str) -> str | None:
        """Devuelve por qué se rechaza el comando, o None si está permitido."""
        propios = self.servidores.get(servidor, {}).get("bloqueados", [])
        for patron in [*self.bloqueados, *propios]:
            if re.search(patron, comando):
                return f"bloqueado por la regla '{patron}' de la configuración"
        if self.modo_de(servidor) == "lectura":
            for patron in PATRONES_ESCRITURA:
                if re.search(patron, comando):
                    return f"'{servidor}' está en modo 'lectura' y el comando parece modificar el servidor"
        return None


def cargar() -> Config:
    ruta = Path(os.environ.get("SRV_MCP_CONFIG", BASE_DIR / "config.toml"))
    datos = tomllib.loads(ruta.read_text()) if ruta.exists() else {}
    cfg = Config(
        modo=datos.get("modo", "completo"),
        bloqueados=list(datos.get("bloqueados", [])),
        servidores=dict(datos.get("servidores", {})),
        timeout=int(datos.get("timeout", 120)),
        max_salida=int(datos.get("max_salida", 30_000)),
        ssh=os.environ.get("SRV_MCP_SSH", "ssh"),
        ssh_config=Path(os.environ.get("SRV_MCP_SSH_CONFIG", Path.home() / ".ssh" / "config")),
        logs=BASE_DIR / "logs",
    )
    modos = [cfg.modo, *(s.get("modo", cfg.modo) for s in cfg.servidores.values())]
    if invalidos := [m for m in modos if m not in MODOS]:
        raise ValueError(f"modo inválido en {ruta}: '{invalidos[0]}' (usa 'completo' o 'lectura')")
    for patron in [*cfg.bloqueados, *(p for s in cfg.servidores.values() for p in s.get("bloqueados", []))]:
        re.compile(patron)
    return cfg
