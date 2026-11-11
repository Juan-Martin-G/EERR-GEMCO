"""
tests/test_curvas_j_ui.py
=========================
Tests de la hoja "Curvas J" en el navegador (Playwright, Chromium sin
ventana). Levantan un servidor local sobre docs/ y abren panel.html.

Comparan lo que dibuja el panel (datasets de Chart.js, subtitulos y
tooltips) con los acumulados recalculados en Python desde el JSON
(tests/_curvas_j_ref.py), no con el codigo del panel.

Requisitos (si faltan, los tests se saltan):
    pip install playwright
    playwright install chromium
y acceso a internet, porque el panel carga Chart.js desde cdnjs.

Capturas de pantalla: se guardan FUERA del repo, en la carpeta de la
variable de entorno EERR_CAPTURAS o, si no esta, en
<carpeta temporal del sistema>/eerr_capturas_curvas_j.
"""

import functools
import os
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright no esta instalado")
from playwright.sync_api import Error as PlaywrightError, sync_playwright  # noqa: E402

from _curvas_j_ref import (                                              # noqa: E402
    ABR, DOCS, LINEAS, MILLON, ORDEN, TOTAL, acumulados, leer_curvas_j,
    lineas_tooltip, subtitulo, texto_m,
)

TOL_GRAFICO = 0.05   # M$

MESES_NOMBRE = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

IDS = {
    TOTAL: "curva-total-gemco",
    "MMQ": "curva-mmq",
    "Incardia": "curva-incardia",
    "TECSERVICE": "curva-tecservice",
    "Equipos Esterilización": "curva-equipos-esterilizacion",
    "Consumibles Esterilización": "curva-consumibles-esterilizacion",
    "Equipos Endoscopía": "curva-equipos-endoscopia",
    "Consumibles Endoscopía": "curva-consumibles-endoscopia",
    "Equipos Dental": "curva-equipos-dental",
}

CAPTURAS = Path(os.environ.get("EERR_CAPTURAS")
                or Path(tempfile.gettempdir()) / "eerr_capturas_curvas_j")


# ── Servidor y navegador ───────────────────────────────────────────────────

class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def url_panel():
    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(DOCS)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/panel.html"
    srv.shutdown()


@pytest.fixture(scope="module")
def navegador():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as e:
            pytest.skip(f"No se pudo abrir Chromium (playwright install chromium): {e}")
        yield browser
        browser.close()


class Panel:
    """Una pestaña del panel ya autenticada, con registro de errores y
    peticiones."""

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
            pytest.skip("Chart.js no cargo (sin acceso a cdnjs): no se puede probar la hoja")

    def descargas_lineas(self):
        return sum(u.endswith("datos_lineas.json") for u in self.pedidos)

    def abrir(self, hoja):
        self.page.click(f'.nav-btn[data-hoja="{hoja}"]')

    def abrir_curvas(self):
        self.abrir("curvas")
        self.page.wait_for_selector("#cj-grid canvas")

    def graficos(self):
        """Lo que hay en pantalla, en el orden del DOM."""
        return self.page.evaluate("""() =>
          [...document.querySelectorAll('#cj-grid .cj-card')].map(card => {
            const canvas = card.querySelector('canvas');
            const ch = Chart.getChart(canvas);
            return {
              id: canvas.id,
              linea: card.dataset.linea,
              titulo: card.querySelector('.cj-tit').textContent,
              subtitulo: card.querySelector('.cj-sub').textContent,
              destacado: card.classList.contains('cj-total'),
              borde: getComputedStyle(card).borderTopWidth,
              etiquetas: ch.data.labels,
              series: Object.fromEntries(ch.data.datasets.map(d => [d.label, d.data])),
              guiones: Object.fromEntries(ch.data.datasets.map(d => [d.label, (d.borderDash || []).length > 0])),
              yMin: ch.scales.y.min, yMax: ch.scales.y.max,
              ticksY: ch.scales.y.ticks.map(t => t.value),
              ancho: canvas.getBoundingClientRect().width,
              alto: canvas.getBoundingClientRect().height,
            };
          })""")

    def tooltip(self, canvas_id, i):
        """Pasa el mouse por el mes de indice i y retorna el tooltip."""
        self.page.locator(f"#{canvas_id}").scroll_into_view_if_needed()
        pos = self.page.evaluate("""([id, i]) => {
            const c = document.getElementById(id), ch = Chart.getChart(c);
            const r = c.getBoundingClientRect();
            const p = ch.getDatasetMeta(1).data[i];   // Presupuesto: tiene los 12 meses
            return {x: r.left + p.x, y: r.top + r.height / 2};
          }""", [canvas_id, i])
        self.page.mouse.move(pos["x"] - 3, pos["y"] - 3)
        self.page.mouse.move(pos["x"], pos["y"])
        self.page.wait_for_function(
            "id => { const t = Chart.getChart(document.getElementById(id)).tooltip;"
            "        return t && t.opacity > 0 && t.title.length > 0; }", arg=canvas_id)
        return self.page.evaluate("""id => {
            const t = Chart.getChart(document.getElementById(id)).tooltip;
            return {titulo: t.title, lineas: t.beforeBody,
                    cuerpo: t.body.flatMap(b => b.lines)};
          }""", canvas_id)

    def cerrar(self):
        self.ctx.close()


@pytest.fixture(scope="module")
def curvas():
    return leer_curvas_j()


@pytest.fixture(scope="module")
def panel(navegador, url_panel):
    """Panel con la hoja Curvas J abierta (compartido por los tests de lectura)."""
    p = Panel(navegador, url_panel)
    p.abrir_curvas()
    yield p
    p.cerrar()


@pytest.fixture(scope="module")
def graficos(panel):
    return {g["linea"]: g for g in panel.graficos()}


# ── La hoja ────────────────────────────────────────────────────────────────

class TestHoja:

    def test_pestana_despues_de_lineas(self, panel):
        hojas = panel.page.eval_on_selector_all(
            ".nav-btn", "bs => bs.map(b => b.dataset.hoja)")
        assert hojas == ["eerr", "graficos", "ratios", "lineas", "curvas"]
        assert "Curvas J" in panel.page.inner_text('.nav-btn[data-hoja="curvas"]')
        assert panel.page.locator('.nav-btn[data-hoja="curvas"].active').count() == 1

    def test_nueve_graficos_total_primero(self, panel):
        gs = panel.graficos()
        assert [g["linea"] for g in gs] == ORDEN
        assert [g["id"] for g in gs] == [IDS[l] for l in ORDEN]
        assert [g["titulo"] for g in gs] == ORDEN
        assert panel.page.locator("#cj-grid canvas").count() == 9

    def test_total_destacado(self, panel):
        gs = panel.graficos()
        assert [g["destacado"] for g in gs] == [True] + [False] * 8
        assert gs[0]["borde"] == "2px" and gs[1]["borde"] == "1px"

    def test_sin_selectores_en_la_hoja(self, panel):
        assert not panel.page.locator("#sel-row").is_visible()
        assert panel.page.locator("#view-curvas button, #view-curvas select").count() == 0

    def test_graficos_con_tamano(self, panel):
        for g in panel.graficos():
            assert g["ancho"] > 200 and g["alto"] > 150, g["id"]

    def test_nota_al_pie(self, panel, curvas):
        nota = panel.page.inner_text("#cj-nota")
        excl = sum(curvas["excluido"]["Consumibles Dental"]["real_mensual"])
        assert nota.startswith("Resultado del Ejercicio acumulado, en M$. Presupuesto: PPTO V2")
        assert "TECSERVICE = TECSERVICE + SS + Reas + Trazabilidad" in nota
        assert "la brecha por línea incluye diferencias de reparto (el Total no se ve afectado)" in nota
        assert "MMQ real ponderado por participación (0,75 / 0,875)" in nota
        mes = MESES_NOMBRE[int(curvas["ultimo_mes_real"]) - 1]
        assert ("Total GEMCO = suma de las 8 líneas; excluye Consumibles Dental (sin presupuesto; "
                f"Real acumulado a {mes}: {texto_m(excl)} M$).") in nota
        assert nota.endswith("'n/a' si el presupuesto acumulado es ≤ 0.")

    def test_sin_errores_ni_peticiones_fallidas(self, panel):
        """Va al final de la clase: cubre todo lo anterior."""
        assert panel.errores_consola == []
        assert panel.fallidas == []
        assert panel.descargas_lineas() == 1


# ── Los datos dibujados ────────────────────────────────────────────────────

class TestSeries:

    @pytest.mark.parametrize("linea", ORDEN)
    def test_eje_x_son_los_12_meses(self, graficos, linea):
        assert graficos[linea]["etiquetas"] == ABR

    @pytest.mark.parametrize("linea", ORDEN)
    def test_presupuesto_12_puntos_y_real_hasta_el_ultimo_mes(self, graficos, curvas, linea):
        series = graficos[linea]["series"]
        assert set(series) == {"Real", "Presupuesto"}
        assert len(series["Presupuesto"]) == 12
        assert len(series["Real"]) == int(curvas["ultimo_mes_real"])
        assert all(v is not None for v in series["Real"])

    @pytest.mark.parametrize("linea", ORDEN)
    def test_valores_igual_a_los_acumulados_de_python(self, graficos, curvas, linea):
        ac = acumulados(curvas)[linea]
        series = graficos[linea]["series"]
        for nombre, clave in (("Presupuesto", "ppto"), ("Real", "real")):
            for i, (dibujado, esperado) in enumerate(zip(series[nombre], ac[clave])):
                assert abs(dibujado - esperado / MILLON) <= TOL_GRAFICO, (
                    f"{linea} {nombre} {ABR[i]}: grafico {dibujado} vs {esperado / MILLON}")

    @pytest.mark.parametrize("linea", ORDEN)
    def test_presupuesto_discontinuo_y_real_solido(self, graficos, linea):
        assert graficos[linea]["guiones"] == {"Real": False, "Presupuesto": True}

    @pytest.mark.parametrize("linea", ORDEN)
    def test_linea_de_cero_en_el_eje(self, graficos, linea):
        g = graficos[linea]
        assert g["yMin"] <= 0 <= g["yMax"]
        assert 0 in g["ticksY"]

    @pytest.mark.parametrize("linea", ORDEN)
    def test_subtitulo(self, graficos, curvas, linea):
        assert graficos[linea]["subtitulo"] == subtitulo(curvas, linea)

    def test_ejes_y_propios(self, graficos):
        """Cada grafico escala a sus datos: no comparten el eje Y."""
        assert len({(g["yMin"], g["yMax"]) for g in graficos.values()}) > 1


# ── Tooltip ────────────────────────────────────────────────────────────────

class TestTooltip:

    @pytest.mark.parametrize("linea", ["Incardia", TOTAL])
    def test_octubre(self, panel, curvas, linea):
        if int(curvas["ultimo_mes_real"]) < 10:
            pytest.skip("El JSON no tiene Real hasta octubre")
        tip = panel.tooltip(IDS[linea], 9)
        assert tip["titulo"] == ["Octubre"]
        assert tip["lineas"] == lineas_tooltip(curvas, linea, 9)
        assert tip["cuerpo"] == []          # todo el texto va en las lineas de arriba
        texto = "\n".join(tip["lineas"])
        for etiqueta in ("Real del mes:", "Ppto del mes:", "Real acum:", "Ppto acum:",
                         "Brecha acum:", "Cumplimiento:"):
            assert etiqueta in texto

    def test_valores_del_cierre_de_octubre(self, panel, curvas):
        """Textos exactos con el cierre de octubre 2026 (ver la advertencia
        de TestReferenciaCierreOctubre en test_curvas_j.py)."""
        if curvas["ultimo_mes_real"] != "10":
            pytest.skip("Referencia valida solo con Real hasta octubre")
        tip = "\n".join(panel.tooltip(IDS["Incardia"], 9)["lineas"])
        assert "Real acum: 107,5 M$" in tip and "Ppto acum: 179,0 M$" in tip
        assert "Brecha acum: −71,4 M$" in tip and "Cumplimiento: 60%" in tip
        tip = "\n".join(panel.tooltip(IDS[TOTAL], 9)["lineas"])
        assert "Real acum: −379,6 M$" in tip and "Ppto acum: 752,0 M$" in tip
        assert "Brecha acum: −1.131,6 M$" in tip and "Cumplimiento: −50%" in tip

    def test_na_si_el_presupuesto_acumulado_no_es_positivo(self, panel, curvas):
        ac = acumulados(curvas)["MMQ"]
        n = int(curvas["ultimo_mes_real"])
        i = next((k for k in reversed(range(n)) if ac["ppto"][k] <= 0), None)
        assert i is not None, "MMQ ya no tiene un mes con presupuesto acumulado <= 0"
        tip = panel.tooltip(IDS["MMQ"], i)
        assert tip["lineas"] == lineas_tooltip(curvas, "MMQ", i)
        assert tip["lineas"][-1] == "Cumplimiento: n/a"

    def test_mes_sin_real_solo_muestra_presupuesto(self, panel, curvas):
        n = int(curvas["ultimo_mes_real"])
        if n == 12:
            pytest.skip("Todos los meses tienen Real")
        tip = panel.tooltip(IDS[TOTAL], 11)
        assert tip["titulo"] == ["Diciembre"]
        assert tip["lineas"] == lineas_tooltip(curvas, TOTAL, 11)
        assert len(tip["lineas"]) == 2
        assert not any("Real" in t or "Brecha" in t or "Cumplimiento" in t for t in tip["lineas"])


# ── El resto del panel ─────────────────────────────────────────────────────

class TestRestoDelPanel:

    def test_eerr_y_lineas_siguen_funcionando_y_una_sola_descarga(self, navegador, url_panel):
        p = Panel(navegador, url_panel)
        try:
            page = p.page
            assert page.locator("#eerr-tbody tr").count() == 32
            assert page.locator("#sel-row").is_visible()
            assert p.descargas_lineas() == 0            # carga diferida

            p.abrir("lineas")
            page.wait_for_selector("#lin-tbl", state="visible")
            assert page.locator("#lin-tbody tr[data-c]").count() == 32
            assert page.locator("#sel-lineas-ctrl").is_visible()
            assert p.descargas_lineas() == 1

            p.abrir_curvas()
            assert page.locator("#cj-grid canvas").count() == 9
            assert not page.locator("#lin-tbl").is_visible()
            assert p.descargas_lineas() == 1            # no se descarga de nuevo

            p.abrir("lineas")
            assert page.locator("#lin-tbl").is_visible()
            assert page.locator("#sel-lineas-ctrl").is_visible()

            p.abrir("graficos")
            assert page.evaluate("!!Chart.getChart(document.getElementById('g-cM'))")
            assert page.locator("#sel-grp-meses").is_visible()

            p.abrir("ratios")
            assert page.locator("#rt-tbody tr").count() > 0

            p.abrir("eerr")
            assert page.locator("#eerr-tbl").is_visible()
            assert page.locator("#sel-eerr-ctrl").is_visible()
            assert page.locator("#sel-grp-empresa").is_visible()
            assert not page.locator("#view-curvas").is_visible()

            p.abrir_curvas()                            # reabrir: se redibuja, sin duplicar
            assert page.locator("#cj-grid canvas").count() == 9
            assert p.descargas_lineas() == 1
            assert p.errores_consola == [] and p.fallidas == []
        finally:
            p.cerrar()

    def test_curvas_primero_y_despues_lineas_una_sola_descarga(self, navegador, url_panel):
        p = Panel(navegador, url_panel)
        try:
            p.abrir_curvas()
            assert p.descargas_lineas() == 1
            p.abrir("lineas")
            p.page.wait_for_selector("#lin-tbl", state="visible")
            assert p.page.locator("#lin-tbody tr[data-c]").count() == 32
            assert p.descargas_lineas() == 1
            assert p.errores_consola == [] and p.fallidas == []
        finally:
            p.cerrar()

    def test_mensaje_si_falla_la_descarga(self, navegador, url_panel):
        p = Panel(navegador, url_panel)
        try:
            p.ctx.route("**/datos_lineas.json", lambda r: r.fulfill(status=404, body="no"))
            p.abrir("curvas")
            p.page.wait_for_selector("#cj-msg.err")
            assert "No se pudieron cargar los datos de la hoja Curvas J" in p.page.inner_text("#cj-msg")
            assert p.page.locator("#cj-grid canvas").count() == 0
            p.abrir("eerr")
            assert p.page.locator("#eerr-tbody tr").count() == 32
        finally:
            p.cerrar()

    def test_mensaje_si_el_json_no_trae_curvas(self, navegador, url_panel):
        """Un datos_lineas.json anterior (sin curvas_j) no rompe el panel."""
        import json
        from _curvas_j_ref import JSON_LINEAS, leer_json
        viejo = {k: v for k, v in leer_json(JSON_LINEAS).items() if k != "curvas_j"}
        p = Panel(navegador, url_panel)
        try:
            p.ctx.route("**/datos_lineas.json", lambda r: r.fulfill(
                status=200, content_type="application/json", body=json.dumps(viejo)))
            p.abrir("curvas")
            p.page.wait_for_selector("#cj-msg.err")
            assert "no trae las curvas J" in p.page.inner_text("#cj-msg")
            p.abrir("lineas")
            p.page.wait_for_selector("#lin-tbl", state="visible")
            assert p.errores_consola == []
        finally:
            p.cerrar()


# ── Cuadricula y capturas ──────────────────────────────────────────────────

def _columnas(page):
    return page.evaluate(
        "getComputedStyle(document.getElementById('cj-grid')).gridTemplateColumns.split(' ').length")


def _captura_completa(p, ancho, nombre):
    """Captura la hoja entera: agranda la ventana al alto del contenido."""
    alto = p.page.evaluate(
        "document.getElementById('hdr').offsetHeight + document.getElementById('view-curvas').scrollHeight")
    p.page.set_viewport_size({"width": ancho, "height": alto + 2})
    p.page.wait_for_timeout(300)
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    ruta = CAPTURAS / nombre
    p.page.screenshot(path=str(ruta))
    return ruta


class TestCuadriculaYCapturas:

    @pytest.mark.parametrize("ancho, columnas, nombre", [
        (1440, 3, "curvas_j_escritorio_1440.png"),
        (800, 2, None),
        (390, 1, "curvas_j_celular_390.png"),
    ])
    def test_columnas_y_captura(self, navegador, url_panel, ancho, columnas, nombre):
        p = Panel(navegador, url_panel, ancho=ancho, alto=900)
        try:
            p.abrir_curvas()
            assert _columnas(p.page) == columnas
            sin_scroll_horizontal = p.page.evaluate(
                "document.getElementById('view-curvas').scrollWidth <= "
                "document.getElementById('view-curvas').clientWidth")
            assert sin_scroll_horizontal
            if nombre:
                ruta = _captura_completa(p, ancho, nombre)
                assert ruta.stat().st_size > 10_000
                assert p.page.locator("#cj-grid canvas").count() == 9
                print(f"\nCaptura: {ruta}")
            assert p.errores_consola == []
        finally:
            p.cerrar()
