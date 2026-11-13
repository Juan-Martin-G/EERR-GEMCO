"""
tests/test_lineas_json.py
=========================
Tests del EERR por Linea de Negocio que consume la hoja "Lineas" del
panel. Los datos estan en docs/datos_lineas.json (los genera
generar_datos.py, aparte del JSON principal docs/datos_eerr.json):

  lineas_real        linea -> periodo -> {concepto: valor}
  lineas_total_real  periodo -> {concepto: valor}
  lineas_drill_real  concepto -> linea -> periodo -> {clave centro: valor}
  lineas_centros     {clave centro: etiqueta}
  lineas_prorrateo   {linea: pct}
  lineas_centros_prorrateados  [clave centro, ...]

Solo leen los JSON (no necesitan el Excel): validan que lo publicado sea
coherente consigo mismo.
  - Suma de las lineas == consolidado del JSON principal, por periodo y concepto.
  - Suma del drill por centro == valor de la linea.
  - El JSON principal no cambio respecto del anterior.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
JSON_PANEL = RAIZ / "docs" / "datos_eerr.json"
JSON_LINEAS = RAIZ / "docs" / "datos_lineas.json"
FUENTES = [RAIZ / "data" / "raw" / "v8.xlsx", RAIZ / "data" / "raw" / "PPTO_V2.xlsx"]

TOLERANCIA = 1  # pesos

ACUMULADO = "Acumulado"
PERIODOS = [str(m) for m in range(1, 13)] + [ACUMULADO]

LINEAS = [
    "MMQ", "Incardia",
    "Equipos Esterilización", "Consumibles Esterilización",
    "Equipos Endoscopía", "Consumibles Endoscopía",
    "Equipos Dental", "Consumibles Dental",
    "TECSERVICE",
]

BLOQUES_LINEAS = {
    "lineas_real", "lineas_total_real", "lineas_drill_real", "lineas_centros",
    "lineas_prorrateo", "lineas_centros_prorrateados",
    "curvas_j",   # hoja "Curvas J": ver tests/test_curvas_j.py
    "lineas_ppto",  # presupuesto de la vista Detalle: ver tests/test_lineas_ppto.py
}


# ── Fixtures y helpers ─────────────────────────────────────────────────────

def _leer(ruta):
    if not ruta.exists():
        pytest.skip(f"No existe {ruta}. Correr generar_datos.py")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def datos():
    """JSON principal del panel (consolidado y empresas)."""
    return _leer(JSON_PANEL)


@pytest.fixture(scope="module")
def lineas():
    """JSON de la hoja "Lineas"."""
    return _leer(JSON_LINEAS)


def _conceptos_valor(datos):
    """Los 29 conceptos en pesos (todos menos los porcentajes)."""
    return [c for c, _, tipo in datos["estructura_eerr"] if tipo != "porcentaje"]


def _consolidado(datos, periodo, concepto):
    """Valor consolidado del JSON principal. No guarda el acumulado: es la
    suma de los meses con Real (igual que el panel)."""
    cons = datos["real"]["Consolidado"]
    if periodo == ACUMULADO:
        return sum(cons[str(m)][concepto] for m in datos["meta"]["meses_con_real"])
    return cons[periodo][concepto]


# ── Estructura ─────────────────────────────────────────────────────────────

class TestEstructura:

    def test_estan_los_bloques(self, lineas):
        assert set(lineas) == BLOQUES_LINEAS

    def test_json_principal_sin_bloques_de_lineas(self, datos):
        """Los bloques de lineas viven solo en datos_lineas.json."""
        assert not (BLOQUES_LINEAS & set(datos))

    def test_lineas(self, lineas):
        """Las 9 lineas, en orden. Una linea extra "Sin asignar" significa
        que hay un centro de costo sin regla en centro_linea.csv."""
        assert list(lineas["lineas_real"]) == LINEAS

    def test_periodos_y_conceptos_igual_que_el_grid(self, datos, lineas):
        claves_grid = list(datos["real"]["Consolidado"]["1"])
        for linea, por_periodo in lineas["lineas_real"].items():
            assert list(por_periodo) == PERIODOS, linea
            for periodo, valores in por_periodo.items():
                assert list(valores) == claves_grid, (linea, periodo)
        assert list(lineas["lineas_total_real"]) == PERIODOS
        for periodo, valores in lineas["lineas_total_real"].items():
            assert list(valores) == claves_grid, periodo

    def test_drill_cubre_todo(self, datos, lineas):
        drill = lineas["lineas_drill_real"]
        assert list(drill) == _conceptos_valor(datos)
        for concepto, por_linea in drill.items():
            assert list(por_linea) == LINEAS, concepto
            for linea, por_periodo in por_linea.items():
                assert list(por_periodo) == PERIODOS, (concepto, linea)

    def test_centros_del_drill_tienen_etiqueta(self, lineas):
        centros = lineas["lineas_centros"]
        usados = {
            centro
            for por_linea in lineas["lineas_drill_real"].values()
            for por_periodo in por_linea.values()
            for por_centro in por_periodo.values()
            for centro in por_centro
        }
        assert usados <= set(centros), sorted(usados - set(centros))

    def test_valores_enteros(self, datos, lineas):
        """Mismo redondeo que el resto del panel: pesos enteros."""
        for concepto in _conceptos_valor(datos):
            for linea in LINEAS:
                for periodo in PERIODOS:
                    assert isinstance(
                        lineas["lineas_real"][linea][periodo][concepto], int
                    ), (linea, periodo, concepto)

    def test_prorrateo(self, lineas):
        """Porcentajes de las 9 lineas, suman 100%; los centros marcados
        como prorrateados existen en el catalogo si aparecen en el drill."""
        prorrateo = lineas["lineas_prorrateo"]
        assert list(prorrateo) == LINEAS
        assert round(sum(prorrateo.values()), 10) == 1.0
        prorrateados = lineas["lineas_centros_prorrateados"]
        assert prorrateados and all(isinstance(c, str) for c in prorrateados)

    def test_centro_prorrateado_reparte_con_los_porcentajes(self, datos, lineas):
        """Un centro prorrateado aporta a cada linea segun su porcentaje
        (se revisa el de mayor monto en el Acumulado; la tolerancia cubre
        el redondeo a pesos de cada mes)."""
        tolerancia = 2 * len(datos["meta"]["meses_con_real"])
        prorrateo = lineas["lineas_prorrateo"]
        prorrateados = set(lineas["lineas_centros_prorrateados"])
        drill = lineas["lineas_drill_real"]["OGPN Indirectos"]
        por_centro = {}
        for linea in LINEAS:
            for centro, v in drill[linea][ACUMULADO].items():
                if centro in prorrateados:
                    por_centro.setdefault(centro, {})[linea] = v
        assert por_centro, "No hay centros prorrateados en OGPN Indirectos"
        centro, reparto = max(por_centro.items(),
                              key=lambda kv: abs(sum(kv[1].values())))
        total = sum(reparto.values())
        for linea in LINEAS:
            esperado = total * prorrateo[linea]
            assert abs(reparto.get(linea, 0) - esperado) <= tolerancia, (centro, linea)


# ── Cuadratura ─────────────────────────────────────────────────────────────

class TestCuadratura:

    @pytest.mark.parametrize("periodo", PERIODOS)
    def test_suma_lineas_igual_consolidado(self, datos, lineas, periodo):
        diferencias = []
        for concepto in _conceptos_valor(datos):
            suma = sum(lineas["lineas_real"][l][periodo][concepto] for l in LINEAS)
            cons = _consolidado(datos, periodo, concepto)
            if abs(suma - cons) > TOLERANCIA:
                diferencias.append(
                    f"  {concepto} | {periodo} | consolidado={cons:,} | "
                    f"suma lineas={suma:,} | diferencia={suma - cons:,}"
                )
        assert not diferencias, (
            "La suma de las lineas no calza con el consolidado del JSON:\n"
            + "\n".join(diferencias)
        )

    @pytest.mark.parametrize("periodo", PERIODOS)
    def test_total_lineas_igual_consolidado(self, datos, lineas, periodo):
        total = lineas["lineas_total_real"][periodo]
        for concepto in _conceptos_valor(datos):
            suma = sum(lineas["lineas_real"][l][periodo][concepto] for l in LINEAS)
            assert total[concepto] == suma, (periodo, concepto)
            assert abs(total[concepto] - _consolidado(datos, periodo, concepto)) \
                <= TOLERANCIA, (periodo, concepto)

    @pytest.mark.parametrize("linea", LINEAS)
    def test_suma_drill_igual_linea(self, datos, lineas, linea):
        diferencias = []
        for concepto in _conceptos_valor(datos):
            for periodo in PERIODOS:
                valor = lineas["lineas_real"][linea][periodo][concepto]
                suma = sum(lineas["lineas_drill_real"][concepto][linea][periodo].values())
                if abs(suma - valor) > TOLERANCIA:
                    diferencias.append(
                        f"  {concepto} | {periodo} | linea={valor:,} | "
                        f"suma centros={suma:,} | diferencia={suma - valor:,}"
                    )
        assert not diferencias, (
            f"El drill por centro no suma el valor de la linea '{linea}':\n"
            + "\n".join(diferencias)
        )

    @pytest.mark.parametrize("linea", LINEAS)
    def test_acumulado_es_la_suma_de_los_meses(self, datos, lineas, linea):
        meses = [str(m) for m in datos["meta"]["meses_con_real"]]
        por_periodo = lineas["lineas_real"][linea]
        for concepto in _conceptos_valor(datos):
            assert por_periodo[ACUMULADO][concepto] == sum(
                por_periodo[m][concepto] for m in meses
            ), concepto

    def test_linea_mmq_va_ponderada(self, datos, lineas):
        """El diario MMQ dentro de la linea MMQ lleva el factor de
        participacion, igual que el bloque MMQ ponderado del grid (y no el
        100% de mmq_100_real). Tolerancia 2 pesos: son dos redondeos."""
        drill = lineas["lineas_drill_real"]["Ingresos"]["MMQ"]
        comparados = 0
        for mes in datos["meta"]["meses_con_real"]:
            ponderado = datos["real"]["MMQ"][str(mes)]["Ingresos"]
            al_100 = datos["mmq_100_real"][str(mes)]["Ingresos"]
            if ponderado == al_100:
                continue
            assert abs(drill[str(mes)].get("MMQ", 0) - ponderado) <= 2, mes
            comparados += 1
        assert comparados > 0


# ── El JSON principal no cambia ────────────────────────────────────────────

def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, check=True
    ).stdout


def _json_anterior():
    """
    JSON principal anterior contra el cual comparar. Por defecto es el del
    ultimo commit (git HEAD); se puede indicar otro archivo con la
    variable de entorno EERR_JSON_ANTERIOR.
    """
    ruta = os.environ.get("EERR_JSON_ANTERIOR")
    if ruta:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    try:
        fecha_commit = int(_git("log", "-1", "--format=%ct", "--",
                                "docs/datos_eerr.json").strip() or 0)
        contenido = _git("show", "HEAD:docs/datos_eerr.json")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("No se pudo leer docs/datos_eerr.json del ultimo commit (git).")
    # Si los datos fuente cambiaron despues del ultimo commit, es normal
    # que las cifras sean distintas: la comparacion no aplica.
    if any(f.exists() and f.stat().st_mtime > fecha_commit for f in FUENTES):
        pytest.skip("Los datos fuente (data/raw) son mas nuevos que el ultimo "
                    "commit del JSON: la comparacion con el JSON anterior no aplica.")
    return json.loads(contenido.decode("utf-8"))


class TestBloquesAnteriores:

    def test_bloques_anteriores_identicos(self, datos):
        """El EERR por linea no cambia ninguna cifra de los bloques que ya
        consumia el panel: el JSON principal es igual al anterior."""
        anterior = _json_anterior()
        bloques = [b for b in anterior if b not in BLOQUES_LINEAS]
        assert bloques, "El JSON anterior no tiene bloques que comparar"
        distintos = [b for b in bloques if datos.get(b) != anterior[b]]
        assert not distintos, f"Bloques que cambiaron respecto del JSON anterior: {distintos}"
