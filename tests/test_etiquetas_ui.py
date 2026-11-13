"""
tests/test_etiquetas_ui.py
==========================
Nombres de pantalla de los conceptos del EERR (diccionario ETIQUETAS_CONCEPTO
de docs/app.js). Las claves internas (JSON, Python) no cambian: solo cambia
el texto que se muestra.

  - el diccionario cubre exactamente los 32 conceptos de estructura_eerr y
    trae los nombres acordados (tabla de referencia de este archivo);
  - cada fila del EERR general, de Lineas (Acumulado y Detalle, con la marca
    †) y los selectores y el grafico de cascada de Graficos muestran el
    nombre del diccionario, tambien con el drill abierto;
  - ninguna etiqueta visible conserva las siglas o abreviaturas anteriores;
  - los nombres largos no rompen la columna de conceptos (1440 y 390 px):
    no se desbordan ni se montan sobre los numeros. Capturas fuera del repo.

Requisitos: Playwright + Chromium (si faltan, se salta).
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _panel_ui import DOCS, Panel, chromium, servidor_docs   # noqa: E402

DAT = json.loads((DOCS / "datos_eerr.json").read_text(encoding="utf-8"))
CONCEPTOS = [c for c, _, _ in DAT["estructura_eerr"]]
TOTAL = "Total consolidado"

# Nombre a mostrar de cada concepto (clave interna -> pantalla). Fuente:
# filas del PPTO V2 / EERR de la V8 / mapeo_clasif; "Depreciación y
# Amortización" por decision del usuario. Los que no cambian, igual.
CAMBIAN = {
    "GPBE Directos":             "Gastos por Beneficios a los Empleados Directos",
    "GPBE Indirectos":           "Gastos por Beneficios a los Empleados Indirectos",
    "GPBE Total":                "Gastos por Beneficios a los Empleados Total",
    "OGPN Directos":             "Otros Gastos por Naturaleza Directos",
    "OGPN Indirectos":           "Otros Gastos por Naturaleza Indirectos",
    "OGPN Total":                "Otros Gastos por Naturaleza Total",
    "Provisión Obsolescencias":  "Provisión Obsolescencias Inventarios",
    "Depreciación":              "Depreciación y Amortización",
    "Resultado antes Impuestos": "Resultado antes de Impuestos",
}
ESPERADO = {c: CAMBIAN.get(c, c) for c in CONCEPTOS}

# Restos de abreviaturas que no deben verse en ninguna etiqueta de concepto
PROHIBIDO = re.compile(r"\bGPBE\b|\bOGPN\b|antes Impuestos|^Depreciación$|Obsolescencias$")

JS_FILAS = """(sel) => [...document.querySelectorAll(sel)].map(tr => ({
  c: tr.dataset.c || null,
  // texto de la celda sin el boton de drill (+/−)
  texto: (() => { const td = tr.cells[0].cloneNode(true);
                  td.querySelectorAll('.dd-btn, .dd-sp').forEach(e => e.remove());
                  return td.textContent.replace(/\\s+/g, ' ').trim(); })(),
  marca: !!tr.cells[0].querySelector('.lin-rep'),
}))"""

# Mide la columna de conceptos: que el texto no se salga de su celda ni se
# monte sobre la primera celda de numeros, y que si se parte en varias
# lineas quede dentro de la celda (alto suficiente, sin cortar).
JS_MEDIR = """(sel) => [...document.querySelectorAll(sel)].map(tr => {
  const td = tr.cells[0], v = tr.cells[1];
  const R = td.getBoundingClientRect(), V = v.getBoundingClientRect();
  const rango = document.createRange(); rango.selectNodeContents(td);
  const T = rango.getBoundingClientRect();
  // lineas del nombre: alturas distintas de los rectangulos de sus textos
  const rects = [...td.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim())
    .flatMap(n => { const r = document.createRange(); r.selectNodeContents(n); return [...r.getClientRects()]; });
  const lineas = rects.map(r => Math.round(r.top));
  return {
    // sangria colgante: todas las lineas del nombre empiezan en la misma x
    sangria: rects.length ? Math.max(...rects.map(r => Math.abs(r.left - rects[0].left))) : 0,
    texto: td.innerText.trim(),
    desborde: td.scrollWidth - td.clientWidth,
    choque: R.right - V.left,
    textoFuera: Math.max(T.right - R.right, R.left - T.left, T.bottom - R.bottom, R.top - T.top),
    lineas: new Set(lineas).size,
  };
})"""


@pytest.fixture(scope="module")
def url_panel():
    with servidor_docs() as url:
        yield url


@pytest.fixture(scope="module")
def navegador():
    with chromium() as b:
        yield b


@pytest.fixture()
def panel(navegador, url_panel):
    p = Panel(navegador, url_panel)
    yield p
    p.cerrar()


def _lineas(p):
    p.abrir("lineas")
    p.page.wait_for_selector("#lin-tbody tr[data-c]")


def _detalle(p, opcion):
    p.page.click('#sel-vista-lin .sel-btn[data-vista="detalle"]')
    p.page.select_option("#sel-linea-lin", label=opcion)
    p.page.wait_for_selector("#lin-tbody tr[data-c]")


# ── Diccionario ────────────────────────────────────────────────────────────

class TestDiccionario:

    def test_cubre_los_32_conceptos_con_los_nombres_acordados(self, panel):
        dic = panel.page.evaluate("ETIQUETAS_CONCEPTO")
        assert list(dic) == CONCEPTOS
        assert dic == ESPERADO

    def test_ningun_nombre_conserva_abreviaturas(self):
        assert [n for n in ESPERADO.values() if PROHIBIDO.search(n)] == []
        assert "EBITDA Directo" in ESPERADO.values()          # EBITDA queda como sigla

    def test_los_json_siguen_con_las_claves_internas(self):
        assert "Depreciación" in DAT["real"]["Consolidado"]["1"]
        assert "GPBE Directos" in DAT["ppto"]["Consolidado"]["1"]
        lin = json.loads((DOCS / "datos_lineas.json").read_text(encoding="utf-8"))
        assert "Resultado antes Impuestos" in lin["lineas_ppto"]["MMQ"]["1"]


# ── Pantallas ──────────────────────────────────────────────────────────────

def _filas_eerr(p):
    return p.page.evaluate(JS_FILAS, "#eerr-tbody tr.row-sub, #eerr-tbody tr.row-pct, #eerr-tbody tr.row-norm")


class TestPantallas:

    def test_eerr_general_filas_y_drill(self, panel):
        filas = _filas_eerr(panel)
        assert [f["texto"] for f in filas] == [ESPERADO[c] for c in CONCEPTOS]
        # con drill abierto (empresa y linea) las filas de concepto siguen igual
        panel.page.click('#eerr-tbody .dd-btn[data-c="GPBE Indirectos"][data-n="1"]')
        panel.page.click('#eerr-tbody .dd-btn[data-c="GPBE Indirectos"][data-n="2"]')
        assert panel.page.locator("#eerr-tbody tr.row-lin").count() > 0
        filas = _filas_eerr(panel)
        assert [f["texto"] for f in filas] == [ESPERADO[c] for c in CONCEPTOS]
        assert panel.errores_consola == []

    def test_lineas_acumulado(self, panel):
        _lineas(panel)
        filas = panel.page.evaluate(JS_FILAS, "#lin-tbody tr[data-c]")
        assert [f["c"] for f in filas] == CONCEPTOS
        assert all(f["texto"] == ESPERADO[f["c"]] and not f["marca"] for f in filas)

    @pytest.mark.parametrize("opcion", ["Incardia", TOTAL])
    def test_lineas_detalle_con_marca(self, panel, opcion):
        _lineas(panel)
        _detalle(panel, opcion)
        panel.page.click('#lin-tbody tr[data-c="Depreciación"] .dd-btn')     # drill abierto
        filas = panel.page.evaluate(JS_FILAS, "#lin-tbody tr[data-c]")
        assert [f["c"] for f in filas] == CONCEPTOS
        for f in filas:
            esp = ESPERADO[f["c"]] + (" †" if f["marca"] else "")
            assert f["texto"] == esp, f
        con_marca = {f["c"] for f in filas if f["marca"]}
        assert ("Depreciación" in con_marca) == (opcion != TOTAL)
        assert panel.errores_consola == []

    def test_graficos(self, panel):
        panel.abrir("graficos")
        panel.page.wait_for_function("!!Chart.getChart(document.getElementById('g-cW'))")
        sel = lambda i: panel.page.evaluate(
            f"[...document.querySelectorAll('#{i} option')].map(o => [o.value, o.textContent])")
        assert sel("g-conc") == [[c, ESPERADO[c]] for c in CONCEPTOS]
        assert sel("g-d-conc") == [[c, ESPERADO[c]] for c in CONCEPTOS if not c.startswith("%")]
        wf = panel.page.evaluate("Chart.getChart(document.getElementById('g-cW')).data.labels")
        assert wf == [ESPERADO[c] for c in ["Ingresos", "Costo de ventas", "Margen Bruto", "GPBE Total",
                                            "OGPN Total", "EBITDA Directo", "Gastos Adicionales",
                                            "EBITDA Empresa"]]

    def test_no_queda_ninguna_abreviatura_visible(self, panel):
        textos = [f["texto"] for f in _filas_eerr(panel)]
        _lineas(panel)
        _detalle(panel, "MMQ")
        textos += [f["texto"].rstrip(" †") for f in panel.page.evaluate(JS_FILAS, "#lin-tbody tr[data-c]")]
        assert [t for t in textos if PROHIBIDO.search(t)] == []


# ── Diseno: los nombres largos no rompen la columna ────────────────────────

ALTO_EERR = ("document.getElementById('hdr').offsetHeight"
             " + document.getElementById('tbl-cont').scrollHeight + 60")
ALTO_LIN = ("document.getElementById('hdr').offsetHeight"
            " + document.getElementById('lin-periodo').offsetHeight"
            " + document.getElementById('lin-cont').scrollHeight")


@pytest.mark.parametrize("ancho, alto, disp", [(1440, 900, "escritorio_1440"), (390, 780, "celular_390")])
@pytest.mark.parametrize("hoja", ["eerr", "lineas_detalle"])
def test_columna_de_conceptos_no_se_rompe(navegador, url_panel, ancho, alto, disp, hoja):
    p = Panel(navegador, url_panel, ancho=ancho, alto=alto)
    try:
        if hoja == "eerr":
            sel, alto_js = "#eerr-tbody tr", ALTO_EERR
        else:
            _lineas(p)
            _detalle(p, "Incardia")
            p.page.click("#btn-vard-lin")
            p.page.click("#btn-varpct-lin")
            sel, alto_js = "#lin-tbody tr[data-c]", ALTO_LIN
        medidas = p.page.evaluate(JS_MEDIR, sel)
        assert len(medidas) == 32
        malos = [m for m in medidas if m["desborde"] > 0 or m["choque"] > 0.5 or m["textoFuera"] > 0.5
                 or m["sangria"] > 0.5]
        assert malos == [], malos
        # los nombres que se parten en dos lineas: a lo sumo dos y ordenados
        assert max(m["lineas"] for m in medidas) <= 2, [m for m in medidas if m["lineas"] > 2]
        partidos = [m["texto"] for m in medidas if m["lineas"] > 1]
        print(f"\n{hoja} {disp}: en dos lineas -> {partidos}")
        ruta = p.captura_completa(f"etiquetas_{hoja}_{disp}.png", alto_js)
        assert ruta.stat().st_size > 10_000
        print(f"Captura: {ruta}")
        assert p.errores_consola == []
    finally:
        p.cerrar()
