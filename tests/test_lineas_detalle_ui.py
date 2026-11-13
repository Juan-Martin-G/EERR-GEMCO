"""
tests/test_lineas_detalle_ui.py
===============================
Tests de las dos vistas de la hoja "Lineas" en el navegador (Playwright):

  - "Acumulado por linea": una columna por linea + Total, solo Real (la
    vista de siempre; es la que se abre por defecto).
  - "Detalle por linea": una linea (o "Total consolidado"), Real vs
    Presupuesto como en la hoja EERR: por cada mes seleccionado
    Real | Ppto | [Var $] | [Var %], luego "Total periodo" (si hay mas de
    un mes) y "Ppto Anual".

Lo que se lee de la pantalla se compara con sumas y formatos calculados
aqui desde docs/datos_lineas.json y docs/datos_eerr.json, no con el codigo
del panel. Tambien se revisa la hoja EERR general (columnas de variacion,
que comparten formato con el Detalle).

Requisitos y carpeta de capturas: ver tests/_panel_ui.py.
"""

import json
import re

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
ANIO = list(range(1, 13))

LINEAS = list(LIN["lineas_real"])
TOTAL = "Total consolidado"
OPCIONES = LINEAS + [TOTAL]                               # las 10 del desplegable
SIN_PPTO = "Consumibles Dental"
PRORRATEADOS = set(LIN["lineas_centros_prorrateados"])
LPPTO = LIN.get("lineas_ppto", {})
PPTO_CONS = DAT["ppto"]["Consolidado"]

# Selecciones de meses: una contigua y una no contigua.
SELECCIONES = {
    "Ene–Sep": [m for m in range(1, 10) if m in MESES_REAL],
    "Feb, Abr, Sep": [m for m in (2, 4, 9) if m in MESES_REAL],
}
CONCEPTOS_DRILL = ["Ingresos", "GPBE Indirectos", "Costo Financiero"]

# Conceptos con marca "†" en el Detalle de una linea (no en Total consolidado).
MARCADOS = {
    "GPBE Indirectos", "GPBE Total", "OGPN Indirectos", "OGPN Total",
    "Subtotal GAV", "EBITDA Directo", "% EBITDA",
    "Finiquitos", "Provisión Habilitación Oficinas", "Gastos Adicionales",
    "EBITDA Empresa", "% EBITDA Empresa", "Depreciación", "Resultado Operacional",
    "Costo Financiero", "Diferencia de Cambio", "Resultado No Operacional",
    "Resultado antes Impuestos", "Impuesto a la Renta", "Resultado del Ejercicio",
}
TEXTO_MARCA = "Comparación por línea afectada por distinto criterio de reparto entre Real y Presupuesto"

NOTA_FIJA = ("Los centros 601–611, 206 y 104 se prorratean con porcentajes fijos. "
             "MMQ se muestra ponderado por el factor de participación (0,75 / 0,875). "
             "La depreciación de cada línea es la contable; no incluye la reasignación "
             "de D&A de gestión del Excel.")
NOTA_PPTO = ("Presupuesto: PPTO V2. † El Real prorratea los centros comunes con porcentajes fijos "
             "y el presupuesto reparte los costos compartidos con su propio criterio; en esas filas "
             "la variación por línea mezcla gestión y reparto (el Total consolidado no se ve "
             "afectado). El presupuesto de MMQ es el de la hoja P&L MMQ, sin factor de "
             "participación. Las filas de centro de origen no tienen presupuesto. Consumibles "
             "Dental no tiene presupuesto.")

ALTO_HOJA = ("document.getElementById('hdr').offsetHeight"
             " + document.getElementById('lin-periodo').offsetHeight"
             " + document.getElementById('lin-cont').scrollHeight")


# ── Referencia calculada desde el JSON ─────────────────────────────────────

def bloque(opcion):
    """Real: {mes: {concepto: valor}}."""
    return LIN["lineas_total_real"] if opcion == TOTAL else LIN["lineas_real"][opcion]


def bloque_p(opcion):
    """Presupuesto: {mes: {concepto: valor}}, o None si la linea no tiene."""
    return PPTO_CONS if opcion == TOTAL else LPPTO.get(opcion)


def lineas_de(opcion):
    return LINEAS if opcion == TOTAL else [opcion]


def suma_b(b, concepto, meses):
    return None if b is None else sum(b[str(m)][concepto] for m in meses)


def suma(opcion, concepto, meses):
    return suma_b(bloque(opcion), concepto, meses)


def miles(n):
    return f"{abs(round(n)):,}".replace(",", ".")


def texto_pesos(v):
    if v is None:
        return "-"
    return f"({miles(v)})" if v < 0 else miles(v)


def texto_pct(numerador, ingresos):
    if numerador is None or not ingresos:
        return "-"
    return f"{numerador / ingresos * 100:.1f}".replace(".", ",") + "%"


def texto_var_d(r, p):
    """Var $ del panel: "+1.234" / "(1.234)"; "-" si falta un valor."""
    if r is None or p is None:
        return "-"
    d = r - p
    return f"({miles(d)})" if d < 0 else f"+{miles(d)}"


def texto_var_p(r, p):
    """Var % del panel: (Real - Ppto) / |Ppto|, 1 decimal con COMA; "-" si el Ppto es 0."""
    if r is None or p is None or p == 0:
        return "-"
    pct = (r - p) / abs(p) * 100
    return ("+" if pct >= 0 else "") + f"{pct:.1f}".replace(".", ",") + "%"


def celda(b_real, b_ppto, concepto, tipo, meses):
    """Texto esperado de una celda (escala en pesos), mismas reglas que la hoja EERR."""
    def R(k):
        return suma_b(b_real, k, meses)

    def P(k):
        return suma_b(b_ppto, k, meses)

    def PA(k):
        return suma_b(b_ppto, k, ANIO)

    if concepto in PCT_NR:
        if tipo in ("Var $", "Var %"):
            return "-"
        get = R if tipo == "Real" else PA if tipo == "Ppto Anual" else P
        return texto_pct(get(PCT_NR[concepto]), get("Ingresos"))
    if tipo == "Ppto Anual":
        return texto_pesos(PA(concepto))
    r, p = R(concepto), P(concepto)
    return {"Real": texto_pesos(r), "Ppto": texto_pesos(p),
            "Var $": texto_var_d(r, p), "Var %": texto_var_p(r, p)}[tipo]


def esperado(opcion, concepto, meses):
    """Vista Acumulado: entero en pesos, o texto si es porcentaje."""
    if concepto in PCT_NR:
        return texto_pct(suma(opcion, PCT_NR[concepto], meses), suma(opcion, "Ingresos", meses))
    return suma(opcion, concepto, meses)


def tipos(var):
    return ["Real", "Ppto"] + (["Var $", "Var %"] if var else [])


def columnas_esperadas(meses, var):
    """[(grupo, tipo, meses de la columna)] de la vista Detalle."""
    cols = [(ABR[m], t, [m]) for m in meses for t in tipos(var)]
    if len(meses) > 1:
        cols += [("Total período", t, meses) for t in tipos(var)]
    return cols + [(None, "Ppto Anual", meses)]


def periodo_txt(meses):
    if len(meses) == 1:
        return ABR[meses[0]]
    if all(b == a + 1 for a, b in zip(meses, meses[1:])):
        return f"{ABR[meses[0]]}–{ABR[meses[-1]]}"
    return ", ".join(ABR[m] for m in meses)


def nota_detalle(opcion, meses):
    n = len(meses)
    periodo = (f"Período: {periodo_txt(meses)}." if n == 1 else
               f"Período: {periodo_txt(meses)} (columnas por mes; «Total período» es la suma "
               f"de los {n} meses seleccionados).")
    return f"Línea: {opcion}. {periodo} {NOTA_FIJA} {NOTA_PPTO}"


def etiqueta_centro(clave):
    return LIN["lineas_centros"][clave] + (" (prorrateo)" if clave in PRORRATEADOS else "")


def drill_esperado(opcion, concepto, meses):
    """etiqueta de centro -> [Real por mes..., Real del total periodo]; None
    donde el centro no aporta ese mes. Solo centros con valor en algun mes."""
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
    t = t.strip("()+").replace(".", "")
    return signo * (float(t.replace(",", ".")) if "," in t else int(t))


JS_LEER = """(tbl) => {
  const t = document.getElementById(tbl);
  const filasCab = [...t.tHead.rows];
  // (grupo, tipo) de cada columna de valores, a partir del encabezado
  const columnas = [];
  if (filasCab.length === 1) {
    [...filasCab[0].cells].slice(1).forEach(th => columnas.push([null, th.innerText.trim()]));
  } else {
    const subs = [...filasCab[1].cells].map(th => th.innerText.trim());
    let j = 0;
    [...filasCab[0].cells].slice(1).forEach(th => {
      if (th.rowSpan === 2) columnas.push([null, th.innerText.trim()]);
      else for (let k = 0; k < th.colSpan; k++) columnas.push([th.innerText.trim(), subs[j++]]);
    });
  }
  return {
    cab: [...t.tHead.querySelectorAll('th')].map(th => th.innerText.trim()),
    filasCab: filasCab.length,
    columnas,
    filas: [...t.tBodies[0].rows].map(tr => ({
      c: tr.dataset.c || null, drill: tr.dataset.drill || null, id: tr.id || null,
      etiqueta: tr.cells[0].innerText.trim(),
      marca: tr.cells[0].querySelector('.lin-rep')?.title ?? null,
      celdas: [...tr.querySelectorAll('td.td-v')].map(td => td.innerText.trim()),
      rojo: !!tr.querySelector('.rt-var-bad'),
    })),
  };
}"""


def armar(t):
    t["conceptos"] = {f["c"]: f["celdas"] for f in t["filas"] if f["c"]}
    t["orden"] = [f["c"] for f in t["filas"] if f["c"]]
    t["marcas"] = {f["c"]: f["marca"] for f in t["filas"] if f["c"] and f["marca"]}
    t["control"] = next((f for f in t["filas"] if f["id"] == "lin-control"), None)
    t["drill"] = {}
    for f in t["filas"]:
        if f["drill"]:
            t["drill"].setdefault(f["drill"], {})[f["etiqueta"]] = f["celdas"]
    return t


def indices(tabla, tipo):
    return [i for i, (_, t) in enumerate(tabla["columnas"]) if t == tipo]


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

    def variaciones(self):
        """Enciende Var $ y Var % desde la fila de controles de la hoja."""
        self.page.click("#btn-vard-lin")
        self.page.click("#btn-varpct-lin")

    def desplegar(self, concepto):
        self.page.click(f'#lin-tbody tr[data-c="{concepto}"] .dd-btn')

    def leer(self):
        return armar(self.page.evaluate(JS_LEER, "lin-tbl"))

    def estado(self):
        return self.page.evaluate("""() => {
          const vis = id => document.getElementById(id).offsetParent !== null;
          return {
            vista: document.querySelector('#sel-vista-lin .sel-btn.active')?.dataset.vista,
            vistasActivas: document.querySelectorAll('#sel-vista-lin .sel-btn.active').length,
            botones: [...document.querySelectorAll('#sel-vista-lin .sel-btn')].map(b => b.innerText.trim()),
            selectorVisible: vis('sel-linea-grp'),
            varVisible: vis('sel-var-lin'),
            varD: document.getElementById('btn-vard-lin').classList.contains('active'),
            varPct: document.getElementById('btn-varpct-lin').classList.contains('active'),
            linea: document.getElementById('sel-linea-lin').selectedOptions[0]?.textContent ?? null,
            opciones: [...document.getElementById('sel-linea-lin').options].map(o => o.textContent),
            meses: [...document.querySelectorAll('#sel-meses-lin .sel-btn.active')].map(b => +b.dataset.mes),
            mm: document.getElementById('btn-mm-lin').classList.contains('active'),
            tablaVisible: vis('lin-tbl'),
            mensaje: vis('lin-msg') ? document.getElementById('lin-msg').innerText.trim() : null,
            periodo: document.getElementById('lin-periodo').innerText.replace(/\\s+/g, ' ').trim(),
            nota: vis('lin-nota')
                    ? document.getElementById('lin-nota').innerText.replace(/\\s+/g, ' ').trim() : null,
            desplegados: [...document.querySelectorAll('#lin-tbody tr[data-c] .dd-btn')]
                           .filter(b => b.innerText.trim() !== '+').map(b => b.dataset.c),
          };
        }""")


def comparar_tabla(tabla, columnas, contexto):
    """Vista Acumulado. columnas: lista de (opcion, meses), una por columna."""
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


def comparar_detalle(tabla, opcion, meses, var, contexto):
    """Vista Detalle: encabezado y CADA celda (texto exacto) contra el JSON."""
    cols = columnas_esperadas(meses, var)
    assert tabla["columnas"] == [[g, t] for g, t, _ in cols], f"{contexto}: encabezado"
    assert tabla["filasCab"] == 2
    assert tabla["orden"] == CONCEPTOS, f"{contexto}: filas u orden distintos"
    malos = []
    for c in CONCEPTOS:
        for texto, (g, t, ms) in zip(tabla["conceptos"][c], cols):
            esp = celda(bloque(opcion), bloque_p(opcion), c, t, ms)
            if texto != esp:
                malos.append(f"{c} [{g} {t}]: {texto!r} != {esp!r}")
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
    Lee una vez lo que usan las pruebas del Detalle, para cada seleccion de
    meses, con Var $ y Var % ENCENDIDOS: la vista Acumulado y el Detalle de
    las 10 opciones.
      lecturas[sel] = {"acum": tabla, "detalle": {opcion: (tabla, estado)}}
    """
    p = Lineas(navegador, url_panel)
    p.vista("detalle")
    p.variaciones()
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


CASOS = [(sel, opcion) for sel in SELECCIONES for opcion in OPCIONES]


# ── Datos ──────────────────────────────────────────────────────────────────

def test_el_json_trae_el_presupuesto_por_linea():
    assert set(LPPTO) == set(LINEAS) - {SIN_PPTO}


# ── 1) Vista por defecto = Acumulado, sin cambios ──────────────────────────

class TestVistaPorDefecto:

    def test_abre_en_acumulado(self, hoja):
        e = hoja.estado()
        assert e["botones"] == ["Acumulado por línea", "Detalle por línea"]
        assert e["vista"] == "acum" and e["vistasActivas"] == 1
        assert not e["selectorVisible"] and not e["varVisible"]   # solo del Detalle
        assert e["meses"] == MESES_REAL                            # todos los meses con Real
        assert e["periodo"] == f"PERÍODO {periodo_txt(MESES_REAL)}"
        assert e["nota"] == (f"Período: {periodo_txt(MESES_REAL)} (suma de los "
                             f"{len(MESES_REAL)} meses seleccionados). {NOTA_FIJA}")

    def test_valores_identicos_al_json(self, hoja):
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + LINEAS + ["Total"]
        assert t["filasCab"] == 1
        assert t["marcas"] == {}
        comparar_tabla(t, [(l, MESES_REAL) for l in LINEAS] + [(TOTAL, MESES_REAL)],
                       "Acumulado, todos los meses")
        control = t["control"]["celdas"]
        assert control[:-1] == [""] * len(LINEAS) and num(control[-1]) == 0
        assert not t["control"]["rojo"]

    def test_variaciones_encendidas_no_cambian_el_acumulado(self, hoja):
        hoja.vista("detalle")
        hoja.variaciones()
        hoja.vista("acum")
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + LINEAS + ["Total"]
        comparar_tabla(t, [(l, MESES_REAL) for l in LINEAS] + [(TOTAL, MESES_REAL)], "Acumulado con Var")

    def test_acumulado_con_otros_meses_y_drill(self, hoja):
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
        visto = {k: [num(x) for x in v] for k, v in t["drill"]["GPBE Indirectos"].items()}
        assert visto == esp


# ── 2) Detalle: Real y Ppto, las 10 opciones x 2 selecciones ──────────────

class TestDetalle:

    def test_desplegable_con_las_10_opciones(self, lecturas):
        _, estado = lecturas["Ene–Sep"]["detalle"][LINEAS[0]]
        assert estado["opciones"] == OPCIONES and len(OPCIONES) == 10
        assert estado["selectorVisible"] and estado["varVisible"]
        assert estado["varD"] and estado["varPct"]

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_cada_celda_igual_al_json(self, lecturas, sel, opcion):
        """Las 32 filas y todas las columnas: Real, Ppto, Var $, Var % de cada
        mes y del Total periodo, y Ppto Anual (texto exacto)."""
        tabla, _ = lecturas[sel]["detalle"][opcion]
        comparar_detalle(tabla, opcion, SELECCIONES[sel], True, f"Detalle {opcion}, {sel}")

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_total_periodo_es_la_suma_y_calza_con_acumulado(self, lecturas, sel, opcion):
        tabla, _ = lecturas[sel]["detalle"][opcion]
        acum = lecturas[sel]["acum"]["conceptos"]
        col = len(LINEAS) if opcion == TOTAL else LINEAS.index(opcion)
        ir, ip = indices(tabla, "Real"), indices(tabla, "Ppto")
        for c in CONCEPTOS:
            celdas = tabla["conceptos"][c]
            if c in PCT_NR:
                # los porcentajes no se suman: salen de los totales de la columna
                assert celdas[ir[-1]] == acum[c][col], f"{c}: {celdas[ir[-1]]} vs Acumulado {acum[c][col]}"
                continue
            real = [num(celdas[i]) for i in ir]
            assert real[-1] == sum(real[:-1]), f"{c}: Total período Real no es la suma"
            assert real[-1] == num(acum[c][col]), f"{c}: Total período distinto del Acumulado"
            ppto = [num(celdas[i]) for i in ip]
            if opcion == SIN_PPTO:
                assert ppto == [None] * len(ppto)
            else:
                assert ppto[-1] == sum(ppto[:-1]), f"{c}: Total período Ppto no es la suma"

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_ppto_anual_es_la_suma_de_los_12_meses(self, lecturas, sel, opcion):
        tabla, _ = lecturas[sel]["detalle"][opcion]
        ia = indices(tabla, "Ppto Anual")
        assert ia == [len(tabla["columnas"]) - 1]          # ultima columna
        for c in CONCEPTOS_VALOR:
            visto = num(tabla["conceptos"][c][ia[0]])
            assert visto == suma_b(bloque_p(opcion), c, ANIO), c

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_filas_de_porcentaje_sin_variacion(self, lecturas, sel, opcion):
        tabla, _ = lecturas[sel]["detalle"][opcion]
        iv = indices(tabla, "Var $") + indices(tabla, "Var %")
        for c in PCT_NR:
            assert {tabla["conceptos"][c][i] for i in iv} == {"-"}, c

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_periodo_y_nota(self, lecturas, sel, opcion):
        meses = SELECCIONES[sel]
        _, estado = lecturas[sel]["detalle"][opcion]
        assert estado["linea"] == opcion
        assert estado["periodo"] == f"PERÍODO {periodo_txt(meses)} · LÍNEA {opcion}"
        assert estado["nota"] == nota_detalle(opcion, meses)

    @pytest.mark.parametrize("sel, opcion", CASOS)
    def test_fila_de_control(self, lecturas, sel, opcion):
        """Solo en "Total consolidado": 0 en el Real de cada mes y del total."""
        tabla, _ = lecturas[sel]["detalle"][opcion]
        if opcion != TOTAL:
            assert tabla["control"] is None
            return
        ir = set(indices(tabla, "Real"))
        celdas = tabla["control"]["celdas"]
        assert [num(celdas[i]) for i in sorted(ir)] == [0] * len(ir)
        assert all(x == "" for i, x in enumerate(celdas) if i not in ir)
        assert not tabla["control"]["rojo"]

    # 3) Conservacion
    @pytest.mark.parametrize("sel", SELECCIONES)
    def test_suma_de_las_lineas_igual_total_consolidado(self, lecturas, sel):
        total, _ = lecturas[sel]["detalle"][TOTAL]
        for tipo in ("Real", "Ppto", "Ppto Anual"):
            for j in indices(total, tipo):
                for c in CONCEPTOS_VALOR:
                    partes = [num(lecturas[sel]["detalle"][l][0]["conceptos"][c][j]) for l in LINEAS]
                    suma_l = sum(v for v in partes if v is not None)    # Consumibles Dental: "-" en Ppto
                    assert suma_l == num(total["conceptos"][c][j]), f"{tipo} {c}, columna {j}"

    def test_sin_errores_y_una_sola_descarga(self, lecturas):
        assert lecturas["errores"] == []
        assert lecturas["descargas"] == 1


# ── Columnas de variacion ──────────────────────────────────────────────────

class TestVariaciones:

    def test_apagadas_por_defecto(self, hoja):
        hoja.vista("detalle")
        hoja.meses([1, 2])
        e = hoja.estado()
        assert e["varVisible"] and not e["varD"] and not e["varPct"]
        t = hoja.leer()
        comparar_detalle(t, LINEAS[0], [1, 2], False, "Var apagadas")
        assert [g for g, _ in t["columnas"]] == ["Ene", "Ene", "Feb", "Feb", "Total período",
                                                 "Total período", None]

    def test_cada_boton_por_separado(self, hoja):
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.meses([3])
        hoja.page.click("#btn-varpct-lin")
        assert [t for _, t in hoja.leer()["columnas"]] == ["Real", "Ppto", "Var %", "Ppto Anual"]
        hoja.page.click("#btn-vard-lin")
        assert [t for _, t in hoja.leer()["columnas"]] == ["Real", "Ppto", "Var $", "Var %", "Ppto Anual"]
        hoja.page.click("#btn-varpct-lin")
        assert [t for _, t in hoja.leer()["columnas"]] == ["Real", "Ppto", "Var $", "Ppto Anual"]

    def test_comparten_estado_con_la_hoja_eerr(self, hoja):
        hoja.vista("detalle")
        hoja.page.click("#btn-vard-lin")
        hoja.abrir("eerr")
        assert hoja.page.locator("#btn-vard.active").count() == 1
        assert hoja.page.locator("#btn-varpct.active").count() == 0
        hoja.page.click("#btn-varpct")
        hoja.abrir("lineas")
        e = hoja.estado()
        assert e["varD"] and e["varPct"]

    def test_var_porcentaje_con_coma_y_ppto_cero(self, lecturas):
        """Var % usa coma decimal; con Ppto 0 muestra "-" (y Var $ el Real)."""
        tabla, _ = lecturas["Ene–Sep"]["detalle"]["Incardia"]
        ivp = indices(tabla, "Var %")
        textos = [tabla["conceptos"][c][i] for c in CONCEPTOS_VALOR for i in ivp]
        con_valor = [x for x in textos if x != "-"]
        assert con_valor and all(re.fullmatch(r"[+-]\d+,\d%", x) for x in con_valor), con_valor[:5]
        # Multas de Incardia: presupuesto 0 todo el año
        ip, ivd = indices(tabla, "Ppto"), indices(tabla, "Var $")
        multas = tabla["conceptos"]["Multas"]
        assert {multas[i] for i in ip} == {"0"}
        assert {multas[i] for i in ivp} == {"-"}
        for i_ppto, i_var in zip(ip, ivd):
            real = multas[i_ppto - 1]
            assert multas[i_var] == (f"+{real}" if not real.startswith("(") else real)


# ── Consumibles Dental (sin presupuesto) ───────────────────────────────────

class TestSinPresupuesto:

    @pytest.mark.parametrize("sel", SELECCIONES)
    def test_ppto_var_y_ppto_anual_con_guion(self, lecturas, sel):
        tabla, _ = lecturas[sel]["detalle"][SIN_PPTO]
        no_real = [i for i, (_, t) in enumerate(tabla["columnas"]) if t != "Real"]
        for c in CONCEPTOS:
            assert {tabla["conceptos"][c][i] for i in no_real} == {"-"}, c
        # el Real si esta
        ir = indices(tabla, "Real")
        assert num(tabla["conceptos"]["Ingresos"][ir[-1]]) == suma(SIN_PPTO, "Ingresos", SELECCIONES[sel])


# ── Marca de reparto (†) ───────────────────────────────────────────────────

class TestMarcaReparto:

    @pytest.mark.parametrize("opcion", [l for l in LINEAS])
    def test_en_los_conceptos_listados_de_cada_linea(self, lecturas, opcion):
        tabla, _ = lecturas["Ene–Sep"]["detalle"][opcion]
        assert set(tabla["marcas"]) == MARCADOS
        assert set(tabla["marcas"].values()) == {TEXTO_MARCA}
        for c in MARCADOS:
            fila = next(f for f in tabla["filas"] if f["c"] == c)
            assert fila["etiqueta"].endswith("†"), c

    def test_no_aparece_en_total_consolidado(self, lecturas):
        tabla, _ = lecturas["Ene–Sep"]["detalle"][TOTAL]
        assert tabla["marcas"] == {}
        assert not any("†" in f["etiqueta"] for f in tabla["filas"])

    def test_no_aparece_en_acumulado(self, lecturas):
        assert lecturas["Ene–Sep"]["acum"]["marcas"] == {}


# ── 4) Drill por centro de origen ──────────────────────────────────────────

class TestDrill:

    @pytest.mark.parametrize("opcion", ["Incardia", "MMQ", "TECSERVICE", "Equipos Esterilización", TOTAL])
    @pytest.mark.parametrize("sel", SELECCIONES)
    def test_centros_solo_real_y_suman_la_fila_padre(self, hoja, sel, opcion):
        meses = SELECCIONES[sel]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.variaciones()
        hoja.linea(opcion)
        for c in CONCEPTOS_DRILL:
            hoja.desplegar(c)
        t = hoja.leer()
        assert sorted(hoja.estado()["desplegados"]) == sorted(CONCEPTOS_DRILL)
        ir = indices(t, "Real")
        for c in CONCEPTOS_DRILL:
            filas = t["drill"].get(c, {})
            # Ppto, Var y Ppto Anual en blanco en las filas de centro
            for etiqueta, celdas in filas.items():
                assert all(x == "" for i, x in enumerate(celdas) if i not in ir), f"{c} / {etiqueta}"
            visto = {k: [num(v[i]) for i in ir] for k, v in filas.items()}
            assert visto == drill_esperado(opcion, c, meses), f"{c}: drill distinto del JSON"
            padre = [num(t["conceptos"][c][i]) for i in ir]
            for j in range(len(ir)):
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
        con_marca = {e for e in etiquetas if e.endswith(" (prorrateo)")}
        assert con_marca == set(etiquetas) & {etiqueta_centro(k) for k in PRORRATEADOS}
        assert con_marca and con_marca != set(etiquetas)

    def test_total_consolidado_igual_al_drill_del_acumulado(self, hoja):
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.desplegar("GPBE Indirectos")
        acum = {k: num(v[-1]) for k, v in hoja.leer()["drill"]["GPBE Indirectos"].items()}
        hoja.vista("detalle")
        hoja.linea(TOTAL)
        t = hoja.leer()
        i_total = indices(t, "Real")[-1]
        detalle = {k: num(v[i_total]) for k, v in t["drill"]["GPBE Indirectos"].items()}
        assert {k: v for k, v in detalle.items() if v} == {k: v for k, v in acum.items() if v}


# ── 5) Cambiar de vista conserva el estado ─────────────────────────────────

class TestEstado:

    def test_meses_linea_escala_var_y_desplegados_se_conservan(self, hoja):
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.linea("TECSERVICE")
        hoja.variaciones()
        hoja.page.click("#btn-mm-lin")
        hoja.desplegar("Costo Financiero")
        antes = hoja.leer()

        hoja.vista("acum")
        e = hoja.estado()
        assert (e["vista"], e["meses"], e["mm"], e["desplegados"]) == ("acum", meses, True, ["Costo Financiero"])
        assert not e["selectorVisible"] and not e["varVisible"]
        t = hoja.leer()
        assert t["cab"] == ["Concepto"] + LINEAS + ["Total"]
        assert "," in t["conceptos"]["Ingresos"][-1]            # sigue en MM$ (1 decimal)

        hoja.vista("detalle")
        e = hoja.estado()
        assert (e["vista"], e["linea"], e["meses"], e["mm"], e["varD"], e["varPct"]) == \
               ("detalle", "TECSERVICE", meses, True, True, True)
        assert e["desplegados"] == ["Costo Financiero"] and e["selectorVisible"]
        assert hoja.leer() == antes                              # misma tabla que antes de salir

        hoja.abrir("eerr")
        hoja.abrir("lineas")
        assert hoja.leer() == antes

    def test_escala_mm_en_el_detalle(self, hoja):
        meses = SELECCIONES["Feb, Abr, Sep"]
        hoja.meses(meses)
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.page.click("#btn-mm-lin")
        t = hoja.leer()
        celdas = t["conceptos"]["Ingresos"]
        for tipo, b in (("Real", bloque("Incardia")), ("Ppto", bloque_p("Incardia"))):
            for i, ms in zip(indices(t, tipo), [[m] for m in meses] + [meses]):
                assert abs(num(celdas[i]) - suma_b(b, "Ingresos", ms) / 1e6) <= 0.05
        ia = indices(t, "Ppto Anual")[0]
        assert abs(num(celdas[ia]) - suma_b(bloque_p("Incardia"), "Ingresos", ANIO) / 1e6) <= 0.05

    def test_cambiar_meses_actualiza_la_vista_activa(self, hoja):
        hoja.vista("detalle")
        hoja.linea("Incardia")
        hoja.page.click('#sel-meses-lin .sel-btn[data-mes="1"]')       # quita enero
        meses = [m for m in MESES_REAL if m != 1]
        comparar_detalle(hoja.leer(), "Incardia", meses, False, "sin enero")
        hoja.page.click("#btn-lin-todos")
        comparar_detalle(hoja.leer(), "Incardia", MESES_REAL, False, "todos")


# ── 6) Un solo mes y ningun mes ────────────────────────────────────────────

class TestCasosBorde:

    @pytest.mark.parametrize("opcion", ["Incardia", SIN_PPTO, TOTAL])
    def test_un_solo_mes_sin_total_periodo(self, hoja, opcion):
        hoja.meses([3])
        hoja.vista("detalle")
        hoja.variaciones()
        hoja.linea(opcion)
        hoja.desplegar("Ingresos")
        t = hoja.leer()
        assert t["columnas"] == [["Mar", "Real"], ["Mar", "Ppto"], ["Mar", "Var $"], ["Mar", "Var %"],
                                 [None, "Ppto Anual"]]
        comparar_detalle(t, opcion, [3], True, f"Detalle {opcion}, solo marzo")
        visto = {k: [num(v[0])] for k, v in t["drill"]["Ingresos"].items()}
        assert visto == drill_esperado(opcion, "Ingresos", [3])
        e = hoja.estado()
        assert e["periodo"] == f"PERÍODO Mar · LÍNEA {opcion}"
        assert e["nota"] == nota_detalle(opcion, [3])

    def test_sin_meses_aviso_en_las_dos_vistas(self, hoja):
        hoja.vista("detalle")
        hoja.variaciones()
        hoja.page.click("#btn-lin-limpiar")
        for vista in ("detalle", "acum", "detalle"):
            hoja.vista(vista)
            e = hoja.estado()
            assert e["mensaje"] == "Selecciona al menos un mes."
            assert not e["tablaVisible"] and e["nota"] is None
            assert "ningún mes seleccionado" in e["periodo"]
        hoja.linea("MMQ")
        hoja.page.click("#btn-lin-todos")
        assert hoja.estado()["tablaVisible"]
        comparar_detalle(hoja.leer(), "MMQ", MESES_REAL, True, "tras Todos")


# ── 7) Hoja EERR general y demas hojas ─────────────────────────────────────

class TestEerrGeneral:
    """La hoja EERR usa las mismas funciones de celda que el Detalle. Con Var $
    y Var % encendidos, cada celda de las filas principales (Consolidado,
    meses por defecto) coincide con el JSON, y Var % va con coma decimal."""

    def test_valores_y_var_porcentaje_con_coma(self, hoja):
        page = hoja.page
        hoja.abrir("eerr")
        page.click("#btn-vard")
        page.click("#btn-varpct")
        meses = [int(b) for b in page.eval_on_selector_all(
            "#sel-meses .sel-btn.active", "bs => bs.map(b => b.dataset.mes)")]
        t = armar(page.evaluate(JS_LEER, "eerr-tbl"))
        filas = [f for f in t["filas"]]
        assert len(filas) == len(CONCEPTOS)
        cols = [(ABR[m], ty, [m]) for m in meses for ty in tipos(True)]
        cols += [("Acumulado", ty, meses) for ty in tipos(True)] + [("Acumulado", "Ppto Anual", meses)]
        assert t["columnas"] == [[g, ty] for g, ty, _ in cols]
        real, ppto = DAT["real"]["Consolidado"], DAT["ppto"]["Consolidado"]
        malos = []
        for c, f in zip(CONCEPTOS, filas):
            for texto, (g, ty, ms) in zip(f["celdas"], cols):
                esp = celda(real, ppto, c, ty, ms)
                if texto != esp:
                    malos.append(f"{c} [{g} {ty}]: {texto!r} != {esp!r}")
        assert not malos, f"{len(malos)} celdas distintas, p. ej. {malos[:4]}"
        var_pct = [f["celdas"][i] for f in filas for i, (_, ty) in enumerate(t["columnas"]) if ty == "Var %"]
        con_valor = [x for x in var_pct if x != "-"]
        assert con_valor and all(re.fullmatch(r"[+-]\d+,\d%", x) for x in con_valor), con_valor[:5]

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


# ── Celular y capturas ─────────────────────────────────────────────────────

def _preparar(p, vista):
    if vista == "detalle":
        p.vista("detalle")
        p.variaciones()
        p.linea("Incardia")
        p.desplegar("GPBE Indirectos")


JS_ENCABEZADO = """() => {
  const t = document.getElementById('lin-tbl');
  const cont = document.getElementById('lin-cont').getBoundingClientRect();
  const [f1, f2] = t.tHead.rows;
  const cuerpo = [...t.tBodies[0].rows[0].cells].slice(1);
  // columnas de la 2a fila del encabezado = columnas con grupo
  const conGrupo = [];
  let j = 0;
  [...f1.cells].slice(1).forEach(th => {
    if (th.rowSpan === 2) { j++; return; }
    for (let k = 0; k < th.colSpan; k++) conGrupo.push(j++);
  });
  const R = e => e.getBoundingClientRect();
  const subs = [...f2.cells];
  return {
    f1Arriba: Math.round(R(f1.cells[1]).top - cont.top),
    f2BajoF1: Math.round(R(subs[0]).top - R(f1.cells[1]).bottom),
    desalineadas: subs.filter((th, i) => Math.abs(R(th).left - R(cuerpo[conGrupo[i]]).left) > 0.5
                                       || Math.abs(R(th).width - R(cuerpo[conGrupo[i]]).width) > 0.5).length,
    alturasF2: [...new Set(subs.map(th => Math.round(R(th).height)))],
  };
}"""


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
                tablaAncho: cont.scrollWidth, contAncho: cont.clientWidth,
                contAlto: cont.clientHeight,
              };
            }""")
            assert m["anchoPagina"] <= m["ventana"], "la pagina no debe deslizarse hacia el lado"
            assert m["fuera"] == [], f"controles fuera de la pantalla: {m['fuera']}"
            assert m["tablaAncho"] > m["contAncho"]             # la tabla se desliza dentro de su caja
            assert m["contAlto"] > 150                          # y queda espacio para verla
            if vista == "detalle":
                # encabezado de dos filas: pegado arriba, 2a fila bajo la 1a y
                # alineado con las columnas, tambien con la tabla desplazada
                for x, y in ((0, 0), (900, 400)):
                    p.page.evaluate(f"document.getElementById('lin-cont').scrollTo({x}, {y})")
                    p.page.wait_for_timeout(100)
                    enc = p.page.evaluate(JS_ENCABEZADO)
                    assert enc["f1Arriba"] in (0, 1) and enc["f2BajoF1"] == 0, enc
                    assert enc["desalineadas"] == 0 and len(enc["alturasF2"]) == 1, enc
            p.page.evaluate("document.getElementById('lin-cont').scrollTo(0, 0)")
            ruta = p.captura_completa(f"lineas_{'acumulado' if vista == 'acum' else 'detalle_ppto'}_celular_390.png",
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
            if vista == "detalle":
                enc = p.page.evaluate(JS_ENCABEZADO)
                assert enc["f2BajoF1"] == 0 and enc["desalineadas"] == 0, enc
            ruta = p.captura_completa(f"lineas_{'acumulado' if vista == 'acum' else 'detalle_ppto'}_escritorio_1440.png",
                                      ALTO_HOJA)
            assert ruta.stat().st_size > 10_000
            print(f"\nCaptura: {ruta}")
            assert p.errores_consola == []
        finally:
            p.cerrar()
