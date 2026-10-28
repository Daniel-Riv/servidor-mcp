import asyncio
from pathlib import Path

import pytest
from mcp import Client

from servidor_mcp import config
from servidor_mcp.server import mcp

AQUI = Path(__file__).parent


@pytest.fixture(autouse=True)
def entorno(tmp_path, monkeypatch):
    ssh_config = tmp_path / "ssh_config"
    ssh_config.write_text(
        "# srv-mcp: web\nHost web\n  HostName 10.0.0.1\n# srv-mcp: fin web\n\n"
        "# srv-mcp: cerrado\nHost cerrado\n  HostName 10.0.0.2\n# srv-mcp: fin cerrado\n\n"
        "# srv-mcp: caido\nHost caido\n  HostName 10.0.0.3\n# srv-mcp: fin caido\n\n"
        "Host otro\n  HostName 10.0.0.9\n"
    )
    abiertas = tmp_path / "abiertas"
    abiertas.mkdir()
    (abiertas / "web").touch()
    (abiertas / "caido").touch()
    monkeypatch.setenv("SRV_MCP_SSH", str(AQUI / "fake_ssh"))
    monkeypatch.setenv("SRV_MCP_SSH_CONFIG", str(ssh_config))
    monkeypatch.setenv("SRV_MCP_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("FAKE_SSH_OPEN", str(abiertas))
    monkeypatch.setattr(config, "cargar", _cargar_en(tmp_path, config.cargar))
    return tmp_path


def _cargar_en(tmp_path, original):
    def cargar():
        cfg = original()
        cfg.logs = tmp_path / "logs"
        return cfg
    return cargar


def llamar(nombre, args=None):
    async def _():
        async with Client(mcp) as c:
            r = await c.call_tool(nombre, args or {})
            return r.is_error, "\n".join(b.text for b in r.content)
    return asyncio.run(_())


def test_lista_solo_servidores_registrados_con_estado():
    err, txt = llamar("listar_servidores")
    assert not err
    assert "web: sesión abierta" in txt
    assert "cerrado: sesión cerrada" in txt
    assert "otro" not in txt


def test_ejecuta_y_devuelve_codigo_stdout_stderr():
    err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": "echo hola; echo mal >&2; exit 3"})
    assert not err
    assert "[código de salida: 3]" in txt
    assert "hola" in txt
    assert "--- stderr ---\nmal" in txt


def test_escribe_bitacora(entorno):
    llamar("ejecutar_comando", {"servidor": "web", "comando": "echo uno"})
    log = (entorno / "logs" / "web.log").read_text()
    assert "\t0\techo uno" in log


def test_servidor_no_registrado_falla():
    err, txt = llamar("ejecutar_comando", {"servidor": "otro", "comando": "ls"})
    assert err and "no registrado" in txt


def test_sesion_cerrada_pide_srv_mcp_on():
    err, txt = llamar("ejecutar_comando", {"servidor": "cerrado", "comando": "ls"})
    assert err and "srv-mcp on cerrado" in txt


def test_error_de_conexion_se_reporta():
    err, txt = llamar("ejecutar_comando", {"servidor": "caido", "comando": "ls"})
    assert err and "Connection refused" in txt


def test_timeout_cancela():
    err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": "sleep 5", "timeout_segundos": 1})
    assert not err and "tiempo agotado" in txt


def test_modo_lectura_bloquea_cambios_y_permite_lectura(entorno):
    (entorno / "config.toml").write_text('modo = "lectura"\n')
    for cmd in ["rm -rf /tmp/x", "systemctl restart nginx", "echo a > f", "docker compose down",
                "sudo apt install -y htop", "docker restart n8n"]:
        err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": cmd})
        assert err and "modo 'lectura'" in txt, cmd
    for cmd in ["ls -la /", "df -h 2>&1", "docker ps -a", "systemctl status nginx", "grep -r x . 2>/dev/null"]:
        err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": cmd})
        assert "modo 'lectura'" not in txt, cmd
    err, txt = llamar("escribir_archivo", {"servidor": "web", "ruta": str(entorno / "a.txt"), "contenido": "x"})
    assert err and "lectura" in txt


def test_bloqueados_personalizados_aplican_en_modo_completo(entorno):
    (entorno / "config.toml").write_text("bloqueados = ['\\breboot\\b']\n")
    err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": "sudo reboot"})
    assert err and "reboot" in txt
    err, _ = llamar("ejecutar_comando", {"servidor": "web", "comando": "rm -f /nonexistent-x"})
    assert not err


def test_modo_lectura_por_servidor(entorno):
    (entorno / "config.toml").write_text('[servidores."caido"]\nmodo = "lectura"\n')
    err, txt = llamar("ejecutar_comando", {"servidor": "caido", "comando": "systemctl restart nginx"})
    assert err and "'caido' está en modo 'lectura'" in txt
    err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": "rm -f /nonexistent-x"})
    assert not err, txt
    err, txt = llamar("listar_servidores")
    assert "web: sesión abierta, modo completo" in txt and "caido: sesión abierta, modo lectura" in txt


def test_bloqueados_por_servidor(entorno):
    (entorno / "config.toml").write_text('[servidores."web"]\nbloqueados = ["virsh destroy"]\n')
    err, txt = llamar("ejecutar_comando", {"servidor": "web", "comando": "virsh destroy vm1"})
    assert err and "virsh destroy" in txt


def test_cli_usa_las_mismas_reglas(entorno, capsys):
    from servidor_mcp import cli
    (entorno / "config.toml").write_text('[servidores."web"]\nmodo = "lectura"\n')
    assert cli.main(["run", "web", "echo hola"]) == 0
    assert "hola" in capsys.readouterr().out
    assert cli.main(["run", "web", "rm -rf /tmp/x"]) == 1
    assert "modo 'lectura'" in capsys.readouterr().err
    assert cli.main(["logs", "web", "docker"]) == 1
    assert (entorno / "logs" / "web.log").read_text().count("echo hola") == 1


def test_leer_y_escribir_archivo_con_respaldo(entorno):
    ruta = entorno / "conf con espacio.txt"
    ruta.write_text("viejo\n")
    err, txt = llamar("escribir_archivo", {"servidor": "web", "ruta": str(ruta), "contenido": "línea 'uno'\n$HOME\n"})
    assert not err, txt
    assert ruta.read_text() == "línea 'uno'\n$HOME\n"
    respaldos = list(entorno.glob("conf con espacio.txt.bak.*"))
    assert len(respaldos) == 1 and respaldos[0].read_text() == "viejo\n"
    err, txt = llamar("leer_archivo", {"servidor": "web", "ruta": str(ruta)})
    assert not err and "línea 'uno'" in txt


def test_ver_logs_de_archivo_con_filtro(entorno):
    log = entorno / "app.log"
    log.write_text("ok\nERROR uno\nok\nerror dos\n")
    err, txt = llamar("ver_logs", {"servidor": "web", "tipo": "archivo", "nombre": str(log), "filtro": "error"})
    assert not err
    assert "ERROR uno" in txt and "error dos" in txt and "\nok" not in txt


def test_ver_logs_requiere_nombre():
    err, txt = llamar("ver_logs", {"servidor": "web", "tipo": "docker"})
    assert err and "falta 'nombre'" in txt


def test_estado_sistema_responde():
    err, txt = llamar("estado_sistema", {"servidor": "web"})
    assert not err
    assert "== Disco ==" in txt and "== Docker ==" in txt
