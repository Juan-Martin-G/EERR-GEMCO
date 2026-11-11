"""
tests/test_curvas_j.py
======================
Tests de los datos de la hoja "Curvas J" del panel: bloque curvas_j de
docs/datos_lineas.json (lo genera generar_datos.py con calculo/curvas_j.py).

  curvas_j.lineas[linea] = {ppto_mensual: [12], real_mensual: [n]}  (pesos)

Resultado del Ejercicio mensual por linea, Presupuesto (PPTO V2) y Real
(lineas_real). Total GEMCO = suma de las 8 lineas. Los acumulados no estan
en el JSON: los calcula el panel, y aqui se recalculan aparte
(tests/_curvas_j_ref.py) para compararlos con los graficos en
tests/test_curvas_j_ui.py.

Casi todos leen solo los JSON. Los que necesitan data/raw/PPTO_V2.xlsx se
saltan si el archivo no esta.
"""

import copy
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from calculo import curvas_j as cj_mod                        # noqa: E402
from _curvas_j_ref import (                                   # noqa: E402
    ABR, CONCEPTO, EXCEL_PPTO, EXCLUIDA, JSON_LINEAS, JSON_PANEL, LINEAS,
    MILLON, ORDEN, TOTAL, acumulados, acumular, leer_curvas_j, leer_json,
)

MESES = [str(m) for m in range(1, 13)]

TOL_ANUAL = 0.05 * MILLON        # presupuesto anual vs reporte validado
TOL_PPTO_CONSOLIDADO = 0.5 * MILLON
TOL_REAL_CONSOLIDADO = 10        # pesos por mes (control 1e-iii)
TOL_CIERRE = 0.1 * MILLON        # referencias del cierre de octubre


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def datos():
    return leer_json(JSON_PANEL)


@pytest.fixture(scope="module")
def lineas_json():
    return leer_json(JSON_LINEAS)


@pytest.fixture(scope="module")
def curvas():
    return leer_curvas_j()


@pytest.fixture(scope="module")
def acum(curvas):
    return acumulados(curvas)


def _requiere_excel():
    if not EXCEL_PPTO.exists():
        pytest.skip(f"No existe {EXCEL_PPTO}")


# ── 1) Estructura ──────────────────────────────────────────────────────────

class TestEstructura:

    def test_orden_y_lineas(self, curvas):
        assert curvas["orden"] == ORDEN
        assert len(curvas["orden"]) == 9
        assert set(curvas["lineas"]) == set(ORDEN)

    def test_meses_con_la_clave_de_lineas_real(self, curvas, lineas_json):
        assert curvas["meses"] == MESES
        for linea in LINEAS:
            assert set(MESES) <= set(lineas_json["lineas_real"][linea])

    def test_ultimo_mes_real(self, curvas, datos):
        assert curvas["ultimo_mes_real"] == str(max(datos["meta"]["meses_con_real"]))

    @pytest.mark.parametrize("linea", ORDEN)
    def test_largo_de_las_series(self, curvas, linea):
        bloque = curvas["lineas"][linea]
        assert set(bloque) == {"ppto_mensual", "real_mensual"}
        assert len(bloque["ppto_mensual"]) == 12
        assert len(bloque["real_mensual"]) == int(curvas["ultimo_mes_real"])

    def test_solo_valores_mensuales_en_pesos_enteros(self, curvas):
        """Mismo tipo de dato que lineas_real: pesos enteros, sin acumulados."""
        for bloque in curvas["lineas"].values():
            for serie in bloque.values():
                assert all(isinstance(v, int) and not isinstance(v, bool) for v in serie)

    def test_excluido_y_fuente(self, curvas):
        assert set(curvas["excluido"]) == {EXCLUIDA}
        assert set(curvas["excluido"][EXCLUIDA]) == {"real_mensual"}
        assert len(curvas["excluido"][EXCLUIDA]["real_mensual"]) == int(curvas["ultimo_mes_real"])
        assert EXCLUIDA not in curvas["lineas"]
        assert curvas["fuente"] == "PPTO V2 (fila Resultado del ejercicio Empresa)"

    def test_claves_del_bloque(self, curvas):
        assert set(curvas) == {"meses", "ultimo_mes_real", "orden", "lineas",
                               "excluido", "fuente"}


# ── 2) Presupuesto vs el reporte validado ──────────────────────────────────

PPTO_ANUAL_VALIDADO = {     # M$, verificacion contra el PPTO V2
    "MMQ": 13.2, "Incardia": 207.2, "TECSERVICE": 175.5,
    "Equipos Esterilización": 160.8, "Consumibles Esterilización": 83.7,
    "Equipos Endoscopía": 333.5, "Consumibles Endoscopía": 13.9,
    "Equipos Dental": 42.1, TOTAL: 1029.9,
}


class TestPresupuesto:

    @pytest.mark.parametrize("linea, anual", PPTO_ANUAL_VALIDADO.items())
    def test_total_anual_validado(self, curvas, linea, anual):
        obtenido = sum(curvas["lineas"][linea]["ppto_mensual"])
        assert abs(obtenido - anual * MILLON) <= TOL_ANUAL, (
            f"Presupuesto anual {linea}: {obtenido / MILLON:.2f} M vs {anual} M")

    def test_total_es_la_suma_de_las_8_lineas(self, curvas):
        for i in range(12):
            suma = sum(curvas["lineas"][l]["ppto_mensual"][i] for l in LINEAS)
            assert curvas["lineas"][TOTAL]["ppto_mensual"][i] == suma, f"mes {i + 1}"

    # 3) Suma de las 8 lineas = presupuesto consolidado (calcular_eerr_ppto)
    def test_suma_lineas_igual_consolidado_del_panel(self, curvas, datos):
        """Contra el bloque ppto.Consolidado del JSON (que es la salida de
        calcular_eerr_ppto): no necesita el Excel."""
        for i, mes in enumerate(MESES):
            dif = (curvas["lineas"][TOTAL]["ppto_mensual"][i]
                   - datos["ppto"]["Consolidado"][mes][CONCEPTO])
            assert abs(dif) <= TOL_PPTO_CONSOLIDADO, f"mes {mes}: diferencia {dif:,}"

    def test_suma_lineas_igual_calcular_eerr_ppto(self, curvas):
        """Lo mismo, llamando a calcular_eerr_ppto sobre el Excel."""
        _requiere_excel()
        from transformacion.presupuesto import cargar_presupuesto_completo, MESES as NOMBRES
        from calculo.eerr_presupuesto import calcular_eerr_ppto
        full = cargar_presupuesto_completo(str(EXCEL_PPTO))
        for i, nombre in enumerate(NOMBRES):
            consolidado = calcular_eerr_ppto(full, nombre)[CONCEPTO]
            dif = curvas["lineas"][TOTAL]["ppto_mensual"][i] - consolidado
            assert abs(dif) <= TOL_PPTO_CONSOLIDADO, f"{nombre}: diferencia {dif:,.0f}"

    def test_json_al_dia_con_el_excel(self, curvas):
        """El presupuesto del JSON es el que hoy se lee del Excel, y
        TECSERVICE calza con 'TECSERVICE Consolidado'. Si falla, regenerar."""
        _requiere_excel()
        ppto = cj_mod.leer_presupuesto(str(EXCEL_PPTO))
        for linea in LINEAS:
            assert curvas["lineas"][linea]["ppto_mensual"] == ppto["lineas"][linea], (
                f"{linea}: el JSON no coincide con PPTO_V2.xlsx. Correr generar_datos.py")
        anual_tec = sum(ppto["lineas"]["TECSERVICE"])
        assert abs(anual_tec - ppto["tecservice_consolidado"]) <= TOL_PPTO_CONSOLIDADO


# ── 4) Real ────────────────────────────────────────────────────────────────

class TestReal:

    @pytest.mark.parametrize("linea", LINEAS)
    def test_real_igual_a_lineas_real(self, curvas, lineas_json, linea):
        n = int(curvas["ultimo_mes_real"])
        esperado = [lineas_json["lineas_real"][linea][str(m)][CONCEPTO] for m in range(1, n + 1)]
        assert curvas["lineas"][linea]["real_mensual"] == esperado

    def test_excluida_igual_a_lineas_real(self, curvas, lineas_json):
        n = int(curvas["ultimo_mes_real"])
        esperado = [lineas_json["lineas_real"][EXCLUIDA][str(m)][CONCEPTO] for m in range(1, n + 1)]
        assert curvas["excluido"][EXCLUIDA]["real_mensual"] == esperado

    def test_total_es_la_suma_de_las_8_lineas(self, curvas):
        for i in range(int(curvas["ultimo_mes_real"])):
            suma = sum(curvas["lineas"][l]["real_mensual"][i] for l in LINEAS)
            assert curvas["lineas"][TOTAL]["real_mensual"][i] == suma, f"mes {i + 1}"

    def test_8_lineas_mas_excluida_igual_consolidado(self, curvas, datos):
        """Total GEMCO + Consumibles Dental = Resultado del Ejercicio Real
        consolidado del panel (tolerancia del control 1e-iii)."""
        peor = 0
        for i in range(int(curvas["ultimo_mes_real"])):
            mes = curvas["meses"][i]
            suma = (curvas["lineas"][TOTAL]["real_mensual"][i]
                    + curvas["excluido"][EXCLUIDA]["real_mensual"][i])
            dif = suma - datos["real"]["Consolidado"][mes][CONCEPTO]
            peor = max(peor, abs(dif))
            assert abs(dif) <= TOL_REAL_CONSOLIDADO, f"mes {mes}: diferencia {dif:,}"
        print(f"\nReal 8 lineas + {EXCLUIDA} vs consolidado: diferencia maxima {peor} pesos")


# ── 5) Referencias del cierre de octubre ───────────────────────────────────

# (linea, mes) -> Real acumulado en M$, segun el cierre de octubre 2026.
CIERRE_OCTUBRE = {
    (TOTAL, 9): -668.3, (TOTAL, 10): -379.6,
    ("Incardia", 10): 107.5, ("TECSERVICE", 10): 65.2,
    ("Equipos Esterilización", 10): -263.9, ("Equipos Dental", 10): -105.1,
    ("MMQ", 10): -42.1, ("Consumibles Endoscopía", 10): -90.6,
    ("Consumibles Esterilización", 10): -14.1, ("Equipos Endoscopía", 10): -36.6,
}


class TestReferenciaCierreOctubre:
    """
    Valores de referencia de meses YA CERRADOS (Real acumulado a septiembre y
    octubre de 2026). Solo aplican mientras esos meses no cambien: si se
    reexpresa un mes pasado (ajustes contables posteriores al cierre), estos
    tests pueden fallar LEGITIMAMENTE y hay que actualizar CIERRE_OCTUBRE.
    """

    @pytest.mark.parametrize("linea, mes", CIERRE_OCTUBRE)
    def test_real_acumulado(self, curvas, acum, linea, mes):
        if int(curvas["ultimo_mes_real"]) < mes:
            pytest.skip(f"El JSON no tiene Real hasta {ABR[mes - 1]}")
        esperado = CIERRE_OCTUBRE[(linea, mes)]
        obtenido = acum[linea]["real"][mes - 1]
        assert abs(obtenido - esperado * MILLON) <= TOL_CIERRE, (
            f"Real acumulado {linea} a {ABR[mes - 1]}: {obtenido / MILLON:.1f} M vs "
            f"{esperado} M del cierre de octubre. Si se reexpreso un mes ya "
            "cerrado, actualizar CIERRE_OCTUBRE.")


# ── 6) Acumulados recalculados aparte ──────────────────────────────────────

class TestAcumulados:
    """Los acumulados no vienen en el JSON. Se recalculan aqui desde los
    mensuales (tests/_curvas_j_ref.py); test_curvas_j_ui.py compara estos
    mismos valores con los que dibuja el panel."""

    @pytest.mark.parametrize("linea", ORDEN)
    def test_acumulado_cierra_con_la_suma(self, curvas, acum, linea):
        bloque = curvas["lineas"][linea]
        for serie, clave in (("ppto", "ppto_mensual"), ("real", "real_mensual")):
            ac = acum[linea][serie]
            assert len(ac) == len(bloque[clave])
            assert ac[0] == bloque[clave][0]
            assert ac[-1] == sum(bloque[clave])
            assert all(ac[i] - ac[i - 1] == bloque[clave][i] for i in range(1, len(ac)))

    def test_total_acumulado_es_la_suma_de_las_lineas(self, acum):
        for serie in ("ppto", "real"):
            for i in range(len(acum[TOTAL][serie])):
                assert acum[TOTAL][serie][i] == sum(acum[l][serie][i] for l in LINEAS)

    def test_presupuesto_acumulado_a_diciembre(self, acum):
        assert abs(acum[TOTAL]["ppto"][11] - 1029.9 * MILLON) <= 0.1 * MILLON

    def test_acumular(self):
        assert acumular([1, -3, 5]) == [1, -2, 3]


# ── Lectura del Excel: la fila se ubica por su etiqueta ────────────────────

def _libro(tmp_path, filas):
    """Libro de una hoja 'P&L X' con encabezado de meses y las filas dadas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P&L X"
    ws.append([None, "PLAN ESTRATEGICO 2026"])
    ws.append([None, "ESTADO RESULTADO", "X"] + cj_mod.MESES_PPTO + ["TOTAL 2026"])
    for fila in filas:
        ws.append(fila)
    ruta = tmp_path / "ppto.xlsx"
    wb.save(ruta)
    return openpyxl.load_workbook(ruta, read_only=True, data_only=True)


class TestLecturaExcel:

    FILA = [None, "Resultado del ejercicio Empresa", 78.0] + [float(m) for m in range(1, 13)] + [78.0]

    def test_ubica_la_fila_por_etiqueta(self, tmp_path):
        wb = _libro(tmp_path, [
            [None, "Resultado antes de impuestos", 0] + [9.0] * 12,
            [None, "Impuesto a la renta", 0] + [9.0] * 12,
            [None, None],
            self.FILA,
            [None, "Resultado Ejercicio Empresa S/Ingresos", 0] + [0.5] * 12,
        ])
        assert cj_mod._resultado_hoja(wb, "P&L X") == [float(m) for m in range(1, 13)]

    def test_falla_si_no_esta_la_etiqueta(self, tmp_path):
        wb = _libro(tmp_path, [[None, "Resultado antes de impuestos", 0] + [9.0] * 12])
        with pytest.raises(ValueError, match="esta 0 veces"):
            cj_mod._resultado_hoja(wb, "P&L X")

    def test_falla_si_la_etiqueta_esta_repetida(self, tmp_path):
        wb = _libro(tmp_path, [self.FILA, self.FILA])
        with pytest.raises(ValueError, match="esta 2 veces"):
            cj_mod._resultado_hoja(wb, "P&L X")

    def test_falla_si_falta_un_valor(self, tmp_path):
        fila = list(self.FILA)
        fila[5] = None
        wb = _libro(tmp_path, [fila])
        with pytest.raises(ValueError, match="no tiene un numero"):
            cj_mod._resultado_hoja(wb, "P&L X")

    def test_falla_si_no_esta_la_hoja(self, tmp_path):
        wb = _libro(tmp_path, [self.FILA])
        with pytest.raises(ValueError, match="no tiene la hoja"):
            cj_mod._resultado_hoja(wb, "P&L Inexistente")


# ── Controles de la generacion ─────────────────────────────────────────────

class TestControles:

    @pytest.fixture()
    def insumos(self, curvas, datos):
        return dict(
            curvas_j=copy.deepcopy(curvas),
            ppto_consolidado={m: datos["ppto"]["Consolidado"][m][CONCEPTO] for m in MESES},
            tecservice_consolidado=sum(curvas["lineas"]["TECSERVICE"]["ppto_mensual"]),
            real_consolidado={m: datos["real"]["Consolidado"][m][CONCEPTO] for m in MESES},
        )

    def test_pasan_con_los_datos_publicados(self, insumos):
        dif = cj_mod.controlar_curvas_j(**insumos)
        assert dif["ppto_vs_consolidado"] <= TOL_PPTO_CONSOLIDADO
        assert dif["tecservice_vs_pln"] == 0
        assert dif["real_vs_consolidado"] <= TOL_REAL_CONSOLIDADO
        print(f"\nControles (pesos): {dif}")

    def test_aborta_si_el_presupuesto_no_calza_con_el_consolidado(self, insumos):
        insumos["curvas_j"]["lineas"][TOTAL]["ppto_mensual"][3] += MILLON
        with pytest.raises(ValueError, match="presupuesto consolidado en el mes 4"):
            cj_mod.controlar_curvas_j(**insumos)

    def test_aborta_si_tecservice_no_calza(self, insumos):
        insumos["tecservice_consolidado"] += MILLON
        with pytest.raises(ValueError, match="TECSERVICE"):
            cj_mod.controlar_curvas_j(**insumos)

    def test_aborta_si_el_real_no_calza_con_el_consolidado(self, insumos):
        insumos["curvas_j"]["excluido"][EXCLUIDA]["real_mensual"][1] += 11
        with pytest.raises(ValueError, match="consolidado en el mes 2"):
            cj_mod.controlar_curvas_j(**insumos)
