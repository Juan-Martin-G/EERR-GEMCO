"""
tests/test_lineas_detalle_ui.py
===============================
Tests de las dos vistas de la hoja "Lineas" en el navegador (Playwright):

  - "Acumulado por linea": una columna por linea + Total (la vista de
    siempre; es la que se abre por defecto).
  - "Detalle por linea": una linea (o "Total consolidado"), una columna por
    mes seleccionado + "Total periodo".

Lo que se lee de la pantalla se compara con sumas hechas aqui desde
docs/datos_lineas.json y docs/datos_eerr.json, no con el codigo del panel.

Requisitos y carpeta de capturas: ver tests/_panel_ui.py.
"""

import json

import pytest

from _panel_ui import DOCS, Panel, chromium, servidor_docs

JSON_PANEL = DOCS / "datos_eerr.json"
JSON_LINEAS = DOCS / "datos_lineas.json"
if not JSON_PANEL.exists() or not JSON_LINEAS.exists():
    pytest.skip("Faltan los JSON de docs/. Correr generar_datos.py", allow_module_level=True)

DAT = json.loads(JSON_PANEL.read_text(encoding="utf-8"))
LIN = json.loads(JSON_LINEAS.read_text(encoding="utf-8"))

ESTRUCTURA = DAT["estructura_eerr"]                      # [concepto, nivel, tipo]
CONCEPTOS = [c for c, _, _ in ESTRUCTURA]
CONCEPTOS_VALOR = [c for c, _, t in ESTRUCTURA if t != "porcentaje"]
PCT_NR = {"% Margen": "Margen Bruto", "% EBITDA": "EBITDA Directo",
          "% EBITDA Empresa": "EBITDA Empresa"}
MESES_REAL = DAT["meta"]["meses_con_real"]
ABR = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul",
       8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

LINEAS = list(LIN["lineas_real"])
TOTAL = "Total consolidado"
OPCIONES = LINEAS + [TOTAL]                               # las 10 del desplegable
PRORRATEADOS = set(LIN["lineas_centros_prorrateados"])

# Selecciones de meses de la prueba 2: una contigua y una no contigua.
SELECCIONES = {
    "Ene–Sep": [m for m in range(1, 10) if m in MESES_REAL],
    "Feb, Abr, Sep": [m for m in (2, 4, 9) if m in MESES_REAL],
}
CONCEPTOS_DRILL = ["Ingresos", "GPBE Indirectos", "Costo Financiero"]

NOTA_FIJA = ("Los centros 601–611, 206 y 104 se prorratean con porcentajes fijos. "
             "MMQ se muestra ponderado por el factor de participación (0,75 / 0,875). "
             "La depreciación de cada línea es la contable; no incluye la reasignación "
             "de D&A de gestión del Excel.")

ALTO_HOJA = ("document.getElementById('hdr').offsetHeight"
             " + document.getElementById('lin-periodo').offsetHeight"
             " + document.getElementById('lin-cont').scrollHeight")


# ── Referencia calculada desde el JSON ─────────────────────────────────────

def bloque(opcion):
    return LIN["lineas_total_real"] if opcion == TOTAL else LIN["lineas_real"][opcion]


def lineas_de(opcion):
    return LINEAS if opcion == TOTAL else [opcion]


def suma(opcion, concepto, meses):
    return sum(bloque(opcion)[str(m)][concepto] for m in meses)


def texto_pct(numerador, ingresos):
    if not ingresos:
        return "-"
    return f"{numerador / ingresos * 100:.1f}".replace(".", ",") + "%"


def esperado(opcion, concepto, meses):
    """Lo que debe mostrar una celda: entero en pesos, o texto si es porcentaje."""
    if concepto in PCT_NR:
        return texto_pct(suma(opcion, PCT_NR[concepto], meses), suma(opcion, "Ingresos", meses))
    return suma(opcion, concepto, meses)


def periodo_txt(meses):
    if len(meses) == 1:
        return ABR[meses[0]]
    if all(b == a + 1 for a, b in zip(meses, meses[1:])):
        return f"{ABR[meses[0]]}–{ABR[meses[-1]]}"
    return ", ".join(ABR[m] for m in meses)


def etiqueta_centro(clave):
    return LIN["lineas_centros"][clave] + (" (prorrateo)" if clave in PRORRATEADOS else "")


def drill_esperado(opcion, concepto, meses):
    """etiqueta de centro -> [valor por mes..., total periodo]; None donde el
    centro no aporta ese mes. Solo centros con valor en algun mes."""
    por_mes = []
    for m in meses:
        acum = {}
        for l in lineas_de(opcion):
            for k, v in LIN["lineas_drill_real"][concepto][l][str(m)].items():
                acum[k] = acum.get(k, 0) + v
        por_mes.append({k: v for k, v in acum.items() if v != 0})
    out = {}
    for k in {k for d in por_mes for k in d}:
        vals = [d.get(k) for d in por_mes]
        out[etiqueta_centro(k)] = vals + ([sum(v or 0 for v in vals)] if len(meses) > 1 else [])
    return out


# ── Lectura de la pantalla ─────────────────────────────────────────────────

def num(texto):
    """'(1.234.567)' -> -1234567 ; '1.234,5' -> 1234.5 ; '-' o '' -> None."""
    t = texto.strip()
    if t in ("", "-"):
        return None
    signo = -1 if t.startswith("(") else 1
    t = t.strip("()").replace(".", "")
    return signo * (float(t.replace(",", ".")) if "," in t else int(t))


class Lineas(Panel):
    """Panel con la hoja Lineas abierta."""

    def __init__(self, navegador, url, **kw):
        super().__init__(navegador, url, **kw)
        self.abrir("lineas")
        self.page.wait_for_selector("#lin-tbl", state="visible")

    def vista(self, cual):                       # "acum" | "detalle"
        self.page.click(f'#sel-vista-lin .sel-btn[data-vista="{cual}"]')

    def linea(self, opcion):
        self.page.select_option("#sel-linea-lin", label=opcion)

    def meses(self, meses):
        self.page.click("#btn-lin-limpiar")
        for m in meses:
            self.page.click(f'#sel-meses-lin .sel-btn[data-mes="{m}"]')

    def desplegar(self, concepto):
        self.page.click(f'#lin-tbody tr[data-c="{concepto}"] .dd-btn')

    def leer(self):
        """Tabla en pantalla: cabecera, filas de concepto, drill y control."""
        t = self.page.evaluate("""() => ({
          cab: [...document.querySelectorAll('#lin-thead th')].map(th => th.innerText.trim()),
          filasCab: document.querySelectorAll('#lin-thead tr').length,
          filas: [...document.querySelectorAll('#lin-tbody tr')].map(tr => ({
            c: tr.dataset.c || null, drill: tr.dataset.drill || null, id: tr.id || null,
            etiqueta: tr.querySelector('td.td-c').innerText.trim(),
            celdas: [...tr.querySelectorAll('td.td-v')].map(td => td.innerText.trim()),
            rojo: !!tr.querySelector('.rt-var-bad'),
          })),
        })""")
        t["conceptos"] = {f["c"]: f["celdas"] for f in t["filas"] if f["c"]}
        t["orden"] = [f["c"] for f in t["filas"] if f["c"]]
        t["control"] = next((f for f in t["filas"] if f["id"] == "lin-control"), None)
        t["drill"] = {}
        for f in t["filas"]:
            if f["drill"]:
                t["drill"].setdefault(f["drill"], {})[f["etiqueta"]] = [num(x) for x in f["celdas"]]
        return t

    def estado(self):
        return self.page.evaluate("""() => ({
          vista: document.querySelector('#sel-vista-lin .sel-btn.active')?.dataset.vista,
          vistasActivas: document.querySelectorAll('#sel-vista-lin .sel-btn.active').length,
          botones: [...document.querySelectorAll('#sel-vista-lin .sel-btn')].map(b => b.innerText.trim()),
          selectorVisible: document.getElementById('sel-linea-grp').offsetParent !== null,
          linea: document.getElementById('sel-linea-lin').selectedOptions[0]?.textContent ?? null,
          opciones: [...document.getElementById('sel-linea-lin').options].map(o => o.textContent),
          meses: [...document.querySelectorAll('#sel-meses-lin .sel-btn.active')].map(b => +b.dataset.mes),
          mm: document.getElementById('btn-mm-lin').classList.contains('active'),
          tablaVisible: document.getElementById('lin-tbl').offsetParent !== null,
          mensaje: document.getElementById('lin-msg').offsetParent !== null
                     ? document.getElementById('lin-msg').innerText.trim() : null,
          periodo: document.getElementById('lin-periodo').innerText.replace(/\\s+/g, ' ').trim(),
          nota: document.getElementById('lin-nota').offsetParent !== null
                  ? document.getElementById('lin-nota').innerText.replace(/\\s+/g, ' ').trim() : null,
          desplegados: [...document.querySelectorAll('#lin-tbody tr[data-c] .dd-btn')]
                         .filter(b => b.innerText.trim() !== '+').map(b => b.dataset.c),
        })""")


def comparar_tabla(tabla, columnas, contexto):
    """columnas: lista de (opcion, meses), una por columna de valores."""
    malos = []
    for c in CONCEPTOS:
        celdas = tabla["conceptos"].get(c)
        if celdas is None or len(celdas) != len(columnas):
            malos.append(f"{c}: {None if celdas is None else len(celdas)} celdas")
            continue
        for texto, (opcion, meses) in zip(celdas, columnas):
            esp = esperado(opcion, c, meses)
            visto = texto if c in PCT_NR else num(texto)
            if visto != esp:
                malos.append(f"{c} [{opcion} {periodo_txt(meses)}]: {texto!r} != {esp!r}")
    assert tabla["orden"] == CONCEPTOS, f"{contexto}: filas u orden distintos"
    assert not malos, f"{contexto}: {len(malos)} celdas distintas, p. ej. {malos[:4]}"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def url_panel():
    with servidor_docs() as url:
        yield url


@pytest.fixture(scope="module")
def navegador():
    with chromium() as browser:
        yield browser


@pytest.fixture()
def hoja(navegador, url_panel):
    """Hoja Lineas recien abierta (una por test)."""
    p = Lineas(navegador, url_panel)
    yield p
    assert p.errores_consola == [], p.errores_consola
    assert p.fallidas == [], p.fallidas
    p.cerrar()


@pytest.fixture(scope="module")
def lecturas(navegador, url_panel):
    """
    Lee una vez todo lo que usan las pruebas 2 y 3, para cada seleccion de
    meses: la vista Acumulado y el Detalle de las 10 opciones.
      lecturas[sel] = {"acum": tabla, "detalle": {opcion: (tabla, estado)}}
    """
    p = Lineas(navegador, url_panel)
    out = {}
    for sel, meses in SELECCIONES.items():
        p.meses(meses)
        p.vista("acum")
        out[sel] = {"acum": p.leer(), "detalle": {}}
        p.vista("detalle")
        for opcion in OPCIONES:
            p.linea(opcion)
            out[sel]["detalle"][opcion] = (p.leer(), p.estado())
    out["errores"] = list(p.errores_consola) + list(p.fallidas)
    out["descargas"] = p.descargas("datos_lineas.json")
    p.cerrar()
    return out


# ── 1) Vista por defecto = Acumulado, sin cambios ──────────────────────────

class TestVistaPorDefecto:

    def test_abre_en_acumulado(self, hoja):
        e = hoja.estado()
        assert e["botones"] == ["Acumulado por línea", "Detalle por línea"]
        assert e["vista"] == "acum" and e["vistasActivas"] == 1
        assert not e["selectorVisible"]              # el desplegable es solo del Detalle
        assert e["meses"] == MESES_REAL              # todos los meses con Real
        assert e["periodo"] == f"PERÍODO {periodo_txt(MESES_REAL)}"
        assert "Línea" not in e["periodo"]
        assert e["nota"] == (f"Período: {periodo_txt(MESES_REAL)} (suma de los "
                             f"{len(MESES_REAL)} meses seleccionados). {NOTA_FIJA}")

    def test_valores_identicos_al_json(self, hoja):
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + LINEAS + ["Total"]
        assert t["filasCab"] == 1
        comparar_tabla(t, [(l, MESES_REAL) for l in LINEAS] + [(TOTAL, MESES_REAL)],
                       "Acumulado, todos los meses")
        control = t["control"]["celdas"]
        assert control[:-1] == [""] * len(LINEAS) and num(control[-1]) == 0
        assert not t["control"]["rojo"]

    def test_acumulado_con_otros_meses_y_drill(self, hoja):
        """La vista de siempre con una seleccion no contigua y un concepto
        desplegado: mismas cifras y mismo drill que antes."""
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.desplegar("GPBE Indirectos")
        t = hoja.leer()
        comparar_tabla(t, [(l, meses) for l in LINEAS] + [(TOTAL, meses)], "Acumulado, Feb+Abr+Sep")
        esp = {}
        for i, l in enumerate(LINEAS):
            for etiqueta, vals in drill_esperado(l, "GPBE Indirectos", meses).items():
                if vals[-1]:
                    esp.setdefault(etiqueta, [None] * len(LINEAS))[i] = vals[-1]
        esp = {k: v + [sum(x or 0 for x in v)] for k, v in esp.items()}
        assert t["drill"]["GPBE Indirectos"] == esp


# ── 2) Detalle: las 10 opciones x 2 selecciones de meses ───────────────────

CASOS = [(sel, opcion) for sel in SELECCIONES for opcion in OPCIONES]


class TestDetalle:

    def test_desplegable_con_las_10_opciones(self, lecturas):
        _, estado = lecturas["Ene–Sep"]["detalle"][LINEAS[0]]
        assert estado["opciones"] == OPCIONES and len(OPCIONES) == 10
        assert estado["selectorVisible"]

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_encabezado(self, lecturas, sel, opcion):
        tabla, _ = lecturas[sel]["detalle"][opcion]
        assert tabla["cab"] == ["Concepto"] + [ABR[m] for m in SELECCIONES[sel]] + ["Total período"]
        assert tabla["filasCab"] == 1

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_cada_celda_igual_al_json(self, lecturas, sel, opcion):
        """Todas las filas (29 conceptos y 3 porcentajes), todas las columnas."""
        meses = SELECCIONES[sel]
        tabla, _ = lecturas[sel]["detalle"][opcion]
        comparar_tabla(tabla, [(opcion, [m]) for m in meses] + [(opcion, meses)],
                       f"Detalle {opcion}, {sel}")

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_total_periodo_es_la_suma_y_calza_con_acumulado(self, lecturas, sel, opcion):
        tabla, _ = lecturas[sel]["detalle"][opcion]
        acum = lecturas[sel]["acum"]["conceptos"]
        col = len(LINEAS) if opcion == TOTAL else LINEAS.index(opcion)
        for c in CONCEPTOS:
            celdas = tabla["conceptos"][c]
            if c in PCT_NR:
                # los porcentajes no se suman: salen de los totales de la columna
                assert celdas[-1] == acum[c][col], f"{c}: {celdas[-1]} vs Acumulado {acum[c][col]}"
                continue
            total = num(celdas[-1])
            assert total == sum(num(x) for x in celdas[:-1]), f"{c}: Total período no es la suma"
            assert total == num(acum[c][col]), f"{c}: Total período distinto del Acumulado"

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_periodo_y_nota_indican_la_linea(self, lecturas, sel, opcion):
        meses = SELECCIONES[sel]
        _, estado = lecturas[sel]["detalle"][opcion]
        assert estado["linea"] == opcion
        assert estado["periodo"] == f"PERÍODO {periodo_txt(meses)} · LÍNEA {opcion}"
        assert estado["nota"] == (
            f"Línea: {opcion}. Período: {periodo_txt(meses)} (una columna por mes; «Total período» "
            f"es la suma de los {len(meses)} meses seleccionados). {NOTA_FIJA}")

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_fila_de_control(self, lecturas, sel, opcion):
        """Solo tiene sentido en "Total consolidado": ahi va en 0 en cada mes."""
        tabla, _ = lecturas[sel]["detalle"][opcion]
        if opcion == TOTAL:
            assert [num(x) for x in tabla["control"]["celdas"]] == [0] * (len(SELECCIONES[sel]) + 1)
            assert not tabla["control"]["rojo"]
        else:
            assert tabla["control"] is None

    # 3) Conservacion
    @pytest.mark.parametrize("sel", SELECCIONES)
    def test_suma_de_las_9_lineas_igual_total_consolidado(self, lecturas, sel):
        total, _ = lecturas[sel]["detalle"][TOTAL]
        n_cols = len(SELECCIONES[sel]) + 1
        for c in CONCEPTOS_VALOR:
            for j in range(n_cols):
                suma_lineas = sum(num(lecturas[sel]["detalle"][l][0]["conceptos"][c][j]) for l in LINEAS)
                assert suma_lineas == num(total["conceptos"][c][j]), f"{c}, columna {j}"

    def test_sin_errores_y_una_sola_descarga(self, lecturas):
        assert lecturas["errores"] == []
        assert lecturas["descargas"] == 1


# ── 4) Drill por centro de origen ──────────────────────────────────────────

class TestDrill:

    @pytest.mark.parametrize("opcion", ["Incardia", "MMQ", "TECSERVICE", "Equipos Esterilización", TOTAL])
    @pytest.mark.parametrize("sel", SELECCIONES)
    def test_centros_suman_la_fila_padre_y_calzan_con_el_json(self, hoja, sel, opcion):
        meses = SELECCIONES[sel]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.linea(opcion)
        for c in CONCEPTOS_DRILL:
            hoja.desplegar(c)
        t = hoja.leer()
        assert sorted(hoja.estado()["desplegados"]) == sorted(CONCEPTOS_DRILL)
        for c in CONCEPTOS_DRILL:
            visto = t["drill"].get(c, {})
            assert visto == drill_esperado(opcion, c, meses), f"{c}: drill distinto del JSON"
            padre = [num(x) for x in t["conceptos"][c]]
            for j in range(len(meses) + 1):
                suma_centros = sum(v[j] or 0 for v in visto.values())
                assert abs(suma_centros - padre[j]) <= 1, f"{c}, columna {j}: {suma_centros} vs {padre[j]}"

    def test_etiqueta_prorrateo(self, hoja):
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.desplegar("GPBE Indirectos")
        etiquetas = list(hoja.leer()["drill"]["GPBE Indirectos"])
        assert etiquetas and all(e.endswith(" (prorrateo)") for e in etiquetas)   # todo llega por prorrateo
        hoja.desplegar("Ingresos")
        etiquetas = list(hoja.leer()["drill"]["Ingresos"])
        assert etiquetas[0] == "Incardia"                                         # su propio diario, primero
        # lleva "(prorrateo)" exactamente lo que el JSON marca como centro prorrateado
        con_marca = {e for e in etiquetas if e.endswith(" (prorrateo)")}
        prorrateados = {etiqueta_centro(k) for k in PRORRATEADOS}
        assert con_marca == set(etiquetas) & prorrateados
        assert con_marca and con_marca != set(etiquetas)

    def test_total_consolidado_igual_al_drill_del_acumulado(self, hoja):
        """El drill de "Total consolidado" es el de la columna Total de la
        vista Acumulado, abierto mes a mes."""
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.desplegar("GPBE Indirectos")
        acum = {k: v[-1] for k, v in hoja.leer()["drill"]["GPBE Indirectos"].items()}
        hoja.vista("detalle")
        hoja.linea(TOTAL)
        detalle = hoja.leer()["drill"]["GPBE Indirectos"]
        assert {k: v[-1] for k, v in detalle.items() if v[-1]} == {k: v for k, v in acum.items() if v}
        assert all(len(v) == len(meses) + 1 for v in detalle.values())


# ── 5) Cambiar de vista conserva el estado ─────────────────────────────────

class TestEstado:

    def test_meses_linea_escala_y_desplegados_se_conservan(self, hoja):
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.linea("TECSERVICE")
        hoja.page.click("#btn-mm-lin")
        hoja.desplegar("Costo Financiero")
        antes = hoja.leer()

        hoja.vista("acum")
        e = hoja.estado()
        assert (e["vista"], e["meses"], e["mm"], e["desplegados"]) == ("acum", meses, True, ["Costo Financiero"])
        assert not e["selectorVisible"]
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + LINEAS + ["Total"]
        assert "," in t["conceptos"]["Ingresos"][-1]            # sigue en MM$ (1 decimal)

        hoja.vista("detalle")
        e = hoja.estado()
        assert (e["vista"], e["linea"], e["meses"], e["mm"]) == ("detalle", "TECSERVICE", meses, True)
        assert e["desplegados"] == ["Costo Financiero"] and e["selectorVisible"]
        assert hoja.leer() == antes                              # misma tabla que antes de salir

        # ... y tambien al salir de la hoja y volver
        hoja.abrir("eerr")
        hoja.abrir("lineas")
        e = hoja.estado()
        assert (e["vista"], e["linea"], e["meses"], e["mm"]) == ("detalle", "TECSERVICE", meses, True)
        assert hoja.leer() == antes

    def test_escala_mm_en_el_detalle(self, hoja):
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.page.click("#btn-mm-lin")
        celdas = hoja.leer()["conceptos"]["Ingresos"]
        for texto, ms in zip(celdas, [[m] for m in meses] + [meses]):
            assert abs(num(texto) - suma("Incardia", "Ingresos", ms) / 1e6) <= 0.05

    def test_cambiar_meses_actualiza_la_vista_activa(self, hoja):
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.page.click('#sel-meses-lin .sel-btn[data-mes="1"]')       # quita enero
        meses = [m for m in MESES_REAL if m != 1]
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + [ABR[m] for m in meses] + ["Total período"]
        comparar_tabla(t, [("Incardia", [m]) for m in meses] + [("Incardia", meses)], "sin enero")
        hoja.page.click("#btn-lin-todos")
        assert hoja.leer()["cab"] == ["Concepto"] + [ABR[m] for m in MESES_REAL] + ["Total período"]


# ── 6) Un solo mes y ningun mes ────────────────────────────────────────────

class TestCasosBorde:

    @pytest.mark.parametrize("opcion", ["Incardia", TOTAL])
    def test_un_solo_mes_sin_total_periodo(self, hoja, opcion):
        hoja.meses([3])
        hoja.vista("detalle")
        hoja.linea(opcion)
        hoja.desplegar("Ingresos")
        t = hoja.leer()
        assert t["cab"] == ["Concepto", "Mar"]
        comparar_tabla(t, [(opcion, [3])], f"Detalle {opcion}, solo marzo")
        assert t["drill"]["Ingresos"] == drill_esperado(opcion, "Ingresos", [3])
        e = hoja.estado()
        assert e["periodo"] == f"PERÍODO Mar · LÍNEA {opcion}"
        assert e["nota"] == f"Línea: {opcion}. Período: Mar. {NOTA_FIJA}"

    def test_sin_meses_aviso_en_las_dos_vistas(self, hoja):
        hoja.vista("detalle")
        hoja.page.click("#btn-lin-limpiar")
        for vista in ("detalle", "acum", "detalle"):
            hoja.vista(vista)
            e = hoja.estado()
            assert e["mensaje"] == "Selecciona al menos un mes."
            assert not e["tablaVisible"] and e["nota"] is None
            assert "ningún mes seleccionado" in e["periodo"]
        hoja.linea("MMQ")                                   # elegir linea sin meses no rompe nada
        hoja.page.click("#btn-lin-todos")
        t = hoja.leer()
        assert hoja.estado()["tablaVisible"]
        comparar_tabla(t, [("MMQ", [m]) for m in MESES_REAL] + [("MMQ", MESES_REAL)], "tras Todos")


# ── Las demas hojas ────────────────────────────────────────────────────────

class TestRestoDelPanel:

    def test_otras_hojas_siguen_igual(self, hoja):
        hoja.vista("detalle")
        page = hoja.page
        hoja.abrir("eerr")
        assert page.locator("#eerr-tbody tr").count() == 32
        assert page.locator("#sel-eerr-ctrl").is_visible()
        assert not page.locator("#sel-lineas-ctrl").is_visible()
        hoja.abrir("curvas")
        page.wait_for_selector("#cj-grid canvas")
        assert page.locator("#cj-grid canvas").count() == 9
        hoja.abrir("graficos")
        assert page.evaluate("!!Chart.getChart(document.getElementById('g-cM'))")
        hoja.abrir("ratios")
        assert page.locator("#rt-tbody tr").count() > 0
        assert hoja.descargas("datos_lineas.json") == 1


# ── 7) Celular y capturas ──────────────────────────────────────────────────

def _preparar(p, vista):
    if vista == "detalle":
        p.vista("detalle")
        p.linea("Incardia")
        p.desplegar("GPBE Indirectos")


class TestCelularYCapturas:

    @pytest.mark.parametrize("vista", ["acum", "detalle"])
    def test_celular_390_no_rompe_el_diseno(self, navegador, url_panel, vista):
        p = Lineas(navegador, url_panel, ancho=390, alto=780)
        try:
            _preparar(p, vista)
            m = p.page.evaluate("""() => {
              const R = e => e.getBoundingClientRect();
              const visibles = [...document.querySelectorAll(
                  '#sel-lineas-ctrl .sel-btn, #sel-lineas-ctrl select, #sel-lineas-ctrl .sel-lbl')]
                .filter(e => e.offsetParent !== null);
              const cont = document.getElementById('lin-cont');
              return {
                anchoPagina: document.documentElement.scrollWidth, ventana: window.innerWidth,
                fuera: visibles.filter(e => R(e).left < 0 || R(e).right > window.innerWidth + 0.5)
                               .map(e => e.innerText || e.id),
                controles: visibles.length,
                tablaAncho: cont.scrollWidth, contAncho: cont.clientWidth,
                contAlto: cont.clientHeight,
              };
            }""")
            assert m["anchoPagina"] <= m["ventana"], "la pagina no debe deslizarse hacia el lado"
            assert m["fuera"] == [], f"controles fuera de la pantalla: {m['fuera']}"
            assert m["tablaAncho"] > m["contAncho"]             # la tabla se desliza dentro de su caja
            assert m["contAlto"] > 250                          # y queda espacio para verla
            p.page.evaluate("document.getElementById('lin-cont').scrollTo(160, 0)")
            assert p.page.evaluate("document.getElementById('lin-cont').scrollLeft") > 0
            p.page.evaluate("document.getElementById('lin-cont').scrollTo(0, 0)")
            ruta = p.captura_completa(f"lineas_{'acumulado' if vista == 'acum' else 'detalle'}_celular_390.png",
                                      ALTO_HOJA)
            assert ruta.stat().st_size > 10_000
            print(f"\nCaptura: {ruta}")
            assert p.errores_consola == []
        finally:
            p.cerrar()

    @pytest.mark.parametrize("vista", ["acum", "detalle"])
    def test_captura_escritorio_1440(self, navegador, url_panel, vista):
        p = Lineas(navegador, url_panel, ancho=1440, alto=900)
        try:
            _preparar(p, vista)
            # los controles caben en una sola fila
            tops = p.page.evaluate("""() => [...document.querySelectorAll('#sel-lineas-ctrl > .sel-grp')]
                .filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top))""")
            assert max(tops) - min(tops) <= 6, f"controles en mas de una fila: {tops}"
            ruta = p.captura_completa(f"lineas_{'acumulado' if vista == 'acum' else 'detalle'}_escritorio_1440.png",
                                      ALTO_HOJA)
            assert ruta.stat().st_size > 10_000
            print(f"\nCaptura: {ruta}")
            assert p.errores_consola == []
        finally:
            p.cerrar()
