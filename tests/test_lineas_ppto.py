"""
tests/test_lineas_ppto.py
=========================
Tests del presupuesto por concepto y linea de la vista "Detalle por linea"
(hoja Lineas): bloque lineas_ppto de docs/datos_lineas.json, que genera
generar_datos.py con calculo/ppto_lineas.py.

  lineas_ppto[linea]["1".."12"][concepto] = pesos enteros

Las 8 lineas con presupuesto (Consumibles Dental no tiene). El Total
consolidado no esta en el bloque: es ppto.Consolidado de datos_eerr.json.

Casi todos leen solo los JSON; los que necesitan data/raw/PPTO_V2.xlsx se
saltan si el archivo no esta.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from calculo import ppto_lineas as PL                       # noqa: E402

RAIZ = Path(__file__).parent.parent
JSON_PANEL = RAIZ / "docs" / "datos_eerr.json"
JSON_LINEAS = RAIZ / "docs" / "datos_lineas.json"
EXCEL_PPTO = RAIZ / "data" / "raw" / "PPTO_V2.xlsx"

MESES = [str(m) for m in range(1, 13)]
LINEAS = [
    "MMQ", "Incardia",
    "Equipos Esterilización", "Consumibles Esterilización",
    "Equipos Endoscopía", "Consumibles Endoscopía",
    "Equipos Dental", "TECSERVICE",
]
SIN_PPTO = "Consumibles Dental"
RESULTADO = "Resultado del Ejercicio"
MILLON = 1_000_000


def _leer(ruta):
    if not ruta.exists():
        pytest.skip(f"No existe {ruta}. Correr generar_datos.py")
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def datos():
    return _leer(JSON_PANEL)


@pytest.fixture(scope="module")
def lineas_json():
    return _leer(JSON_LINEAS)


@pytest.fixture(scope="module")
def ppto(lineas_json):
    if "lineas_ppto" not in lineas_json:
        pytest.fail("docs/datos_lineas.json no tiene el bloque lineas_ppto. Correr generar_datos.py")
    return lineas_json["lineas_ppto"]


@pytest.fixture(scope="module")
def conceptos(datos):
    """Los 29 conceptos en pesos de la tabla Lineas (sin porcentajes)."""
    return [c for c, _, t in datos["estructura_eerr"] if t != "porcentaje"]


def _requiere_excel():
    if not EXCEL_PPTO.exists():
        pytest.skip(f"No existe {EXCEL_PPTO}")


# ── Estructura ─────────────────────────────────────────────────────────────

class TestEstructura:

    def test_lineas(self, ppto, lineas_json):
        assert list(ppto) == LINEAS
        assert SIN_PPTO not in ppto
        # mismas lineas que el Real, menos la que no tiene presupuesto
        assert [l for l in lineas_json["lineas_real"] if l != SIN_PPTO] == LINEAS

    def test_meses_y_conceptos(self, ppto, conceptos):
        assert len(conceptos) == 29
        for linea in LINEAS:
            assert list(ppto[linea]) == MESES, linea
            for mes in MESES:
                assert list(ppto[linea][mes]) == conceptos, f"{linea} mes {mes}"

    def test_pesos_enteros(self, ppto):
        for linea in LINEAS:
            for mes in MESES:
                for c, v in ppto[linea][mes].items():
                    assert isinstance(v, int) and not isinstance(v, bool), f"{linea} {mes} {c}: {v!r}"

    def test_sin_total_en_el_bloque(self, ppto):
        """El Total consolidado sale de ppto.Consolidado de datos_eerr.json."""
        assert not any(k.lower().startswith("total") for k in ppto)


# ── Cuadratura ─────────────────────────────────────────────────────────────

class TestCuadratura:

    def test_suma_lineas_igual_consolidado_exacto(self, ppto, datos, conceptos):
        for mes in MESES:
            for c in conceptos:
                suma = sum(ppto[l][mes][c] for l in LINEAS)
                assert suma == datos["ppto"]["Consolidado"][mes][c], f"{c}, mes {mes}"

    def test_resultado_igual_a_curvas_j(self, ppto, lineas_json):
        cj = lineas_json["curvas_j"]["lineas"]
        for linea in LINEAS:
            for i, mes in enumerate(MESES):
                dif = ppto[linea][mes][RESULTADO] - cj[linea]["ppto_mensual"][i]
                assert abs(dif) <= 1, f"{linea} mes {mes}: {dif} pesos"

    def test_subtotales_coherentes(self, ppto):
        """Los subtotales del bloque son la suma de sus partes (tolerancia de
        redondeo: cada parte se redondea por separado)."""
        partes = {
            "Margen Bruto": ["Ingresos", "Costo de ventas"],
            "GPBE Total": ["GPBE Directos", "GPBE Indirectos"],
            "OGPN Total": ["OGPN Directos", "OGPN Indirectos"],
            "Subtotal GAV": ["GPBE Total", "OGPN Total"],
            "Resultado del Ejercicio": ["Resultado antes Impuestos", "Impuesto a la Renta"],
        }
        for linea in LINEAS:
            for mes in MESES:
                v = ppto[linea][mes]
                for total, ps in partes.items():
                    assert abs(v[total] - sum(v[p] for p in ps)) <= 3, f"{linea} {mes} {total}"


# ── Valores de referencia (acumulado Ene–Sep, verificacion del 13-nov) ─────

def _acum(ppto, linea, conceptos, meses=range(1, 10)):
    return sum(ppto[linea][str(m)][c] for c in conceptos for m in meses)


GAV_DIRECTOS = ["GPBE Directos", "OGPN Directos"]
REFERENCIAS = [   # (linea, conceptos sumados, M$)
    ("Incardia", GAV_DIRECTOS, -91.9),
    ("TECSERVICE", GAV_DIRECTOS, -853.2),
    ("Equipos Endoscopía", GAV_DIRECTOS, -172.6),
    ("Equipos Esterilización", ["Subtotal GAV"], -383.4),
    ("Equipos Esterilización", [RESULTADO], 126.1),
]


class TestReferencias:
    """Presupuesto PPTO V2 acumulado a septiembre. Si cambia el PPTO V2, estos
    valores cambian legitimamente y hay que actualizarlos."""

    @pytest.mark.parametrize("linea, cs, esperado", REFERENCIAS)
    def test_linea(self, ppto, linea, cs, esperado):
        obtenido = _acum(ppto, linea, cs) / MILLON
        assert abs(obtenido - esperado) <= 0.05, f"{linea} {cs}: {obtenido:.2f} vs {esperado}"

    def test_resultado_total(self, ppto, datos):
        lineas = sum(_acum(ppto, l, [RESULTADO]) for l in LINEAS) / MILLON
        consolidado = sum(datos["ppto"]["Consolidado"][str(m)][RESULTADO] for m in range(1, 10)) / MILLON
        assert abs(lineas - 629.9) <= 0.05 and abs(consolidado - 629.9) <= 0.05


# ── Contra el Excel ────────────────────────────────────────────────────────

class TestExcel:

    def test_cada_linea_igual_a_sus_hojas(self, ppto):
        _requiere_excel()
        hojas = PL.leer_hojas(str(EXCEL_PPTO))
        for linea in LINEAS:
            for mes in MESES:
                for c, v in ppto[linea][mes].items():
                    assert abs(v - hojas[linea][mes][c]) <= 0.5 * MILLON, f"{linea} {mes} {c}"

    def test_json_al_dia_con_el_excel(self, ppto):
        """El bloque es el que hoy sale del Excel (sin redondear, a 2 pesos).
        Si falla, regenerar con generar_datos.py."""
        _requiere_excel()
        import generar_datos as G
        from transformacion.presupuesto import cargar_presupuesto_completo
        claves = {c: G.KEY_PPTO[c] for c in G.CONCEPTOS_VALOR}
        exactos = PL.presupuesto_exacto(cargar_presupuesto_completo(str(EXCEL_PPTO)), claves)
        for linea in LINEAS:
            for mes in MESES:
                for c, v in ppto[linea][mes].items():
                    assert abs(v - exactos[linea][mes][c]) <= 2, f"{linea} {mes} {c}"


# ── Controles de la generacion ─────────────────────────────────────────────

class TestControles:

    @pytest.fixture()
    def insumos(self, ppto, datos, lineas_json):
        return dict(lineas_ppto=copy.deepcopy(ppto), ppto_consolidado=datos["ppto"]["Consolidado"],
                    curvas_j=lineas_json["curvas_j"], hojas=None)

    def test_pasan_con_los_datos_publicados(self, insumos):
        dif = PL.controlar_lineas_ppto(**insumos)
        assert dif["suma_vs_consolidado"] == 0
        assert dif["resultado_vs_curvas"] <= 1
        print(f"\nControles (pesos): {dif}")

    def test_aborta_si_la_suma_no_es_exacta(self, insumos):
        insumos["lineas_ppto"]["MMQ"]["3"]["Ingresos"] += 1
        with pytest.raises(ValueError, match="'Ingresos', mes 3"):
            PL.controlar_lineas_ppto(**insumos)

    def test_aborta_si_el_resultado_no_calza_con_curvas_j(self, insumos):
        # se mueve el Resultado entre dos lineas: la suma sigue exacta
        insumos["lineas_ppto"]["MMQ"]["5"][RESULTADO] += 5
        insumos["lineas_ppto"]["Incardia"]["5"][RESULTADO] -= 5
        with pytest.raises(ValueError, match="curvas J"):
            PL.controlar_lineas_ppto(**insumos)

    def test_aborta_si_una_linea_no_calza_con_sus_hojas(self, insumos):
        hojas = {l: {m: dict(v) for m, v in insumos["lineas_ppto"][l].items()} for l in LINEAS}
        hojas["TECSERVICE"]["7"]["Depreciación"] -= MILLON
        insumos["hojas"] = hojas
        with pytest.raises(ValueError, match="Depreciación' de TECSERVICE, mes 7"):
            PL.controlar_lineas_ppto(**insumos)

    def test_aborta_si_falta_una_linea(self, insumos):
        del insumos["lineas_ppto"]["Equipos Dental"]
        with pytest.raises(ValueError, match="faltan las lineas"):
            PL.controlar_lineas_ppto(**insumos)

    def test_cobertura_detecta_una_linea_nueva(self):
        """Una fila del presupuesto que no cae en ninguna linea aborta."""
        import pandas as pd
        full = pd.DataFrame([
            {"Nivel": "Linea", "Empresa_Comercial": "MMQ", "Linea_Negocio": "MMQ", "Monto_Presupuesto": 1.0},
            {"Nivel": "Linea", "Empresa_Comercial": "GEMCO", "Linea_Negocio": "Equipos Médicos", "Monto_Presupuesto": 2.0},
        ])
        with pytest.raises(ValueError, match="no caen en exactamente una linea"):
            PL._controlar_cobertura(full)
