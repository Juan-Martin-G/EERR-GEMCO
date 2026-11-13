"""
tests/_panel_ui.py
==================
Piezas comunes de los tests de interfaz del panel (Playwright, Chromium sin
ventana): servidor local sobre docs/, una pestaña del panel ya autenticada
con registro de errores, y la carpeta de capturas.

Requisitos (si faltan, los tests que lo usan se saltan):
    pip install playwright
    playwright install chromium
y acceso a internet, porque el panel carga Chart.js desde cdnjs.

Capturas de pantalla: se guardan FUERA del repo, en la carpeta de la
variable de entorno EERR_CAPTURAS o, si no esta, en
<carpeta temporal del sistema>/EERR_CAPTURAS.
"""

import functools
import os
import tempfile
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright no esta instalado")
from playwright.sync_api import Error as PlaywrightError, sync_playwright  # noqa: E402

RAIZ = Path(__file__).parent.parent
DOCS = RAIZ / "docs"


def carpeta_capturas():
    carpeta = Path(os.environ.get("EERR_CAPTURAS")
                   or Path(tempfile.gettempdir()) / "EERR_CAPTURAS")
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def servidor_docs():
    """Sirve docs/ en un puerto libre y entrega la URL de panel.html."""
    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(DOCS)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/panel.html"
    finally:
        srv.shutdown()


@contextmanager
def chromium():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as e:
            pytest.skip(f"No se pudo abrir Chromium (playwright install chromium): {e}")
        try:
            yield browser
        finally:
            browser.close()


class Panel:
    """Una pestaña del panel ya autenticada, con registro de errores de
    consola, peticiones fallidas y peticiones hechas."""

    def __init__(self, navegador, url, ancho=1440, alto=900):
        self.ctx = navegador.new_context(viewport={"width": ancho, "height": alto})
        self.ctx.add_init_script("sessionStorage.setItem('eerr_auth','true')")
        self.page = self.ctx.new_page()
        self.errores_consola, self.fallidas, self.pedidos = [], [], []
        self.page.on("console", lambda m: self.errores_consola.append(m.text)
                     if m.type == "error" else None)
        self.page.on("pageerror", lambda e: self.errores_consola.append(f"pageerror: {e}"))
        self.page.on("requestfailed", lambda r: self.fallidas.append(r.url))
        self.page.on("response", lambda r: self.fallidas.append(f"{r.status} {r.url}")
                     if r.status >= 400 else None)
        self.page.on("request", lambda r: self.pedidos.append(r.url))
        self.page.goto(url)
        self.page.wait_for_selector("#app", state="visible")
        if not self.page.evaluate("typeof Chart !== 'undefined'"):
            self.cerrar()
            pytest.skip("Chart.js no cargo (sin acceso a cdnjs): no se puede probar el panel")

    def abrir(self, hoja):
        self.page.click(f'.nav-btn[data-hoja="{hoja}"]')

    def descargas(self, archivo):
        return sum(u.endswith(archivo) for u in self.pedidos)

    def captura_completa(self, nombre, alto_js):
        """Captura la hoja entera: agranda la ventana al alto que entrega la
        expresion JavaScript `alto_js` (el contenido tiene scroll propio)."""
        ancho = self.page.viewport_size["width"]
        alto = self.page.evaluate(alto_js)
        self.page.set_viewport_size({"width": ancho, "height": int(alto) + 2})
        self.page.wait_for_timeout(300)
        ruta = carpeta_capturas() / nombre
        self.page.screenshot(path=str(ruta))
        return ruta

    def cerrar(self):
        self.ctx.close()
