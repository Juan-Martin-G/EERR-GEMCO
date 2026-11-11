"""
tests/test_lineas.py
====================
Tests del EERR por Linea de Negocio (transformacion/lineas.py).

Validacion principal - CONSERVACION: para cada mes y cada concepto del
EERR, la suma de todas las lineas debe ser igual al EERR consolidado
(tolerancia 1 peso), y la linea "Sin asignar" debe ser 0.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transformacion.diarios import (
    cargar_mapeo_clasif, limpiar_incardia, limpiar_mmq,
    limpiar_tecservice, limpiar_gemco, consolidar
)
from transformacion.lineas import (
    asignar_lineas, cargar_centro_linea, cargar_prorrateo,
    centros_sin_regla, lineas_reporte, PRORRATEO, SIN_ASIGNAR,
)
from calculo.eerr import calcular_eerr

EXCEL_V8 = Path(__file__).parent.parent / "data" / "raw" / "v8.xlsx"

TOLERANCIA = 1  # pesos

# None = acumulado
PERIODOS = [None] + list(range(1, 13))


def _nombre_periodo(mes):
    return "Acumulado" if mes is None else f"mes {mes}"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def base_consolidada():
    if not EXCEL_V8.exists():
        pytest.skip(f"Excel V8 no encontrado en {EXCEL_V8}. "
                    "Copiar el archivo y renombrarlo a v8.xlsx")
    mapeo = cargar_mapeo_clasif()
    hojas = pd.read_excel(EXCEL_V8, sheet_name=[
        "Diario GEMCO", "Diario Incardia", "Diario MMQ", "Diario Tecservice",
    ])
    return consolidar(
        limpiar_gemco(hojas["Diario GEMCO"]),
        limpiar_incardia(hojas["Diario Incardia"], mapeo),
        limpiar_mmq(hojas["Diario MMQ"], mapeo),
        limpiar_tecservice(hojas["Diario Tecservice"], mapeo),
    )


@pytest.fixture(scope="module")
def base_expandida(base_consolidada):
    return asignar_lineas(base_consolidada)


def _base_sintetica():
    """Mini base con un centro directo, uno prorrateado, uno sin regla y
    una fila de cada diario propio."""
    return pd.DataFrame({
        "Fecha": pd.to_datetime(["2026-01-15"] * 6),
        "Cuenta_Int": [410101, 610101, 610101, 410101, 410101, 410101],
        "Cargo/abono (ML)": [-1000.0, 10000.0, 500.0, 300.0, 400.0, 200.0],
        "Nombre en EERR": [
            "Ingresos de actividades ordinarias",
            "Otros gastos por naturaleza",
            "Otros gastos por naturaleza",
            "Ingresos de actividades ordinarias",
            "Ingresos de actividades ordinarias",
            "Ingresos de actividades ordinarias",
        ],
        "Empresa": ["GEMCO", "GEMCO", "GEMCO", "Incardia", "MMQ", "Tecservice"],
        "Empresa_Comercial": ["GEMCO", "Soporte Indirecto", "GEMCO",
                              "Incardia", "MMQ", "Tecservice"],
        "Linea_Negocio": ["Equipos Esterilización", "Finanzas y Contabilidad",
                          "Sin clasificar", "Soporte Indirecto",
                          "Soporte Indirecto", "SS Nueva Empresa"],
        "GAV": ["GAV DIRECTO", "GAV INDIRECTO", "GAV DIRECTO", None, None, None],
        "Nombre Unidad": ["E. Esterilización", "Finanzas y Contabilidad",
                          "Centro nuevo", None, None, None],
        "Cod_Unidad": pd.array([101, 601, 999, pd.NA, pd.NA, pd.NA], dtype="Int64"),
    })


# ── Reglas (CSV) ───────────────────────────────────────────────────────────

class TestReglas:

    def test_prorrateo_suma_100(self):
        prorrateo = cargar_prorrateo()
        assert round(sum(prorrateo.values()), 10) == 1.0
        assert all(p >= 0 for p in prorrateo.values())

    def test_prorrateo_que_no_suma_100_lanza_error(self, tmp_path):
        malo = tmp_path / "prorrateo_lineas.csv"
        malo.write_text("linea,pct\nMMQ,0.5000\nIncardia,0.4999\n",
                        encoding="utf-8")
        with pytest.raises(ValueError, match="sumar 1.0000"):
            cargar_prorrateo(malo)

    def test_lineas_del_prorrateo_existen(self):
        """Toda linea del prorrateo es una linea de reporte real (sin
        errores de tipeo/tildes respecto de centro_linea.csv)."""
        assert set(cargar_prorrateo()) <= set(lineas_reporte())

    def test_centro_duplicado_lanza_error(self, tmp_path):
        malo = tmp_path / "centro_linea.csv"
        malo.write_text("cod_unidad,linea_reporte\n101,A\n101,B\n",
                        encoding="utf-8")
        with pytest.raises(ValueError, match="duplicado"):
            cargar_centro_linea(malo)


# ── asignar_lineas (unitarios, sin Excel) ──────────────────────────────────

class TestAsignarLineasSintetico:

    def test_no_modifica_el_df_original(self):
        df = _base_sintetica()
        copia = df.copy(deep=True)
        asignar_lineas(df)
        pd.testing.assert_frame_equal(df, copia)

    def test_fila_directa(self):
        exp = asignar_lineas(_base_sintetica())
        f = exp[exp["Cod_Unidad"] == 101]
        assert len(f) == 1
        assert f["Linea_Reporte"].iloc[0] == "Equipos Esterilización"
        assert f["Centro_Origen"].iloc[0] == "E. Esterilización"
        assert f["Cargo/abono (ML)"].iloc[0] == -1000.0

    def test_prorrateo_explota_por_linea(self):
        prorrateo = cargar_prorrateo()
        exp = asignar_lineas(_base_sintetica())
        f = exp[exp["Cod_Unidad"] == 601]
        esperadas = {l for l, p in prorrateo.items() if p > 0}
        assert set(f["Linea_Reporte"]) == esperadas
        assert PRORRATEO not in set(exp["Linea_Reporte"])
        assert (f["Centro_Origen"] == "Finanzas y Contabilidad").all()
        assert f["Cargo/abono (ML)"].sum() == pytest.approx(10000.0, abs=1e-6)
        for _, fila in f.iterrows():
            assert fila["Cargo/abono (ML)"] == pytest.approx(
                10000.0 * prorrateo[fila["Linea_Reporte"]], abs=1e-6)
        # No cambia la empresa comercial ni el GAV de las filas repartidas
        assert (f["Empresa_Comercial"] == "Soporte Indirecto").all()
        assert (f["GAV"] == "GAV INDIRECTO").all()

    def test_diarios_propios(self):
        exp = asignar_lineas(_base_sintetica())
        for empresa, linea in [("Incardia", "Incardia"), ("MMQ", "MMQ"),
                               ("Tecservice", "TECSERVICE")]:
            f = exp[exp["Empresa"] == empresa]
            assert len(f) == 1
            assert f["Linea_Reporte"].iloc[0] == linea
            assert f["Centro_Origen"].iloc[0] == empresa

    def test_centro_sin_regla_va_a_sin_asignar(self):
        df = _base_sintetica()
        exp = asignar_lineas(df)
        f = exp[exp["Cod_Unidad"] == 999]
        assert f["Linea_Reporte"].tolist() == [SIN_ASIGNAR]
        assert centros_sin_regla(df)["Cod_Unidad"].tolist() == [999]

    def test_monto_total_se_conserva(self):
        df = _base_sintetica()
        exp = asignar_lineas(df)
        assert exp["Cargo/abono (ML)"].sum() == pytest.approx(
            df["Cargo/abono (ML)"].sum(), abs=1e-6)

    def test_lineas_requiere_base_expandida(self):
        with pytest.raises(ValueError, match="Linea_Reporte"):
            calcular_eerr(_base_sintetica(), lineas=["MMQ"])


# ── Validacion principal sobre los datos reales ────────────────────────────

class TestConservacion:
    """Suma de todas las lineas == EERR consolidado, por mes y concepto."""

    @pytest.mark.parametrize("mes", PERIODOS, ids=_nombre_periodo)
    def test_suma_lineas_igual_consolidado(self, base_consolidada,
                                           base_expandida, mes):
        consolidado = calcular_eerr(base_consolidada, mes=mes)
        # Todas las lineas presentes en la base (incluye "Sin asignar" si
        # existiera): asi ninguna fila queda fuera de la suma.
        lineas = sorted(base_expandida["Linea_Reporte"].unique())
        por_linea = {l: calcular_eerr(base_expandida, mes=mes, lineas=[l])
                     for l in lineas}

        diferencias = []
        for concepto, valor in consolidado.items():
            suma = sum(r[concepto] for r in por_linea.values())
            dif = suma - valor
            if abs(dif) > TOLERANCIA:
                diferencias.append(
                    f"  {concepto} | {_nombre_periodo(mes)} | "
                    f"consolidado={valor:,.0f} | suma lineas={suma:,.0f} | "
                    f"diferencia={dif:,.2f}"
                )
        assert not diferencias, (
            "La suma de las lineas no calza con el consolidado:\n"
            + "\n".join(diferencias)
        )

    @pytest.mark.parametrize("mes", PERIODOS, ids=_nombre_periodo)
    def test_sin_asignar_es_cero(self, base_expandida, mes):
        r = calcular_eerr(base_expandida, mes=mes, lineas=[SIN_ASIGNAR])
        no_cero = {c: v for c, v in r.items() if abs(v) > TOLERANCIA}
        assert not no_cero, (
            f"'{SIN_ASIGNAR}' tiene montos en {_nombre_periodo(mes)}: {no_cero}"
        )

    @pytest.mark.parametrize("mes", PERIODOS, ids=_nombre_periodo)
    def test_sin_parametro_lineas_no_cambia_nada(self, base_consolidada,
                                                 base_expandida, mes):
        """calcular_eerr sin 'lineas' sobre la base expandida da lo mismo
        que el consolidado de siempre."""
        consolidado = calcular_eerr(base_consolidada, mes=mes)
        assert calcular_eerr(base_consolidada, mes=mes, lineas=None) == consolidado
        sin_filtro = calcular_eerr(base_expandida, mes=mes)
        for concepto, valor in consolidado.items():
            assert sin_filtro[concepto] == pytest.approx(valor, abs=TOLERANCIA), concepto


class TestCobertura:

    def test_ningun_cod_unidad_sin_regla(self, base_consolidada):
        """Si aparece un centro de costo nuevo en el Diario GEMCO, hay que
        agregarlo a data/rules/centro_linea.csv."""
        faltan = centros_sin_regla(base_consolidada)
        assert faltan.empty, (
            "Centros de costo sin regla en data/rules/centro_linea.csv:\n"
            + faltan.to_string(index=False)
        )

    def test_sin_filas_sin_asignar(self, base_expandida):
        n = int((base_expandida["Linea_Reporte"] == SIN_ASIGNAR).sum())
        assert n == 0, f"Hay {n} filas en '{SIN_ASIGNAR}'"

    def test_solo_lineas_conocidas(self, base_expandida):
        conocidas = set(lineas_reporte()) | {SIN_ASIGNAR}
        assert set(base_expandida["Linea_Reporte"].unique()) <= conocidas

    def test_cod_unidad_es_entero_en_gemco(self, base_consolidada):
        gemco = base_consolidada[base_consolidada["Empresa"] == "GEMCO"]
        assert str(gemco["Cod_Unidad"].dtype) == "Int64"
        assert gemco["Cod_Unidad"].notna().all()

    def test_gemco_en_linea_mmq_e_incardia_no_cambia_empresa(self, base_expandida):
        """Las filas del Diario GEMCO asignadas a las lineas MMQ / Incardia
        siguen siendo de GEMCO: no reciben el factor de participacion MMQ."""
        f = base_expandida[
            (base_expandida["Empresa"] == "GEMCO") &
            (base_expandida["Linea_Reporte"].isin(["MMQ", "Incardia"]))
        ]
        assert not f["Empresa_Comercial"].isin(["MMQ", "Incardia"]).any()
