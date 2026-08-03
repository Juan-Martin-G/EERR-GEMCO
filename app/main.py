import sys
from pathlib import Path

import pandas as pd
import json
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent.parent))

from calculo.eerr import calcular_eerr
from calculo.eerr_presupuesto import calcular_eerr_ppto
from transformacion.diarios import (
    cargar_mapeo_clasif,
    consolidar,
    limpiar_gemco,
    limpiar_incardia,
    limpiar_mmq,
    limpiar_tecservice,
)
from transformacion.presupuesto import cargar_presupuesto_completo

EXCEL_PATH = Path(__file__).parent.parent / "data" / "raw" / "V8.xlsx"
PPTO_PATH  = Path(__file__).parent.parent / "data" / "raw" / "PPTO_V2.xlsx"

TODOS_LOS_MESES = [
    ("Ene", "Enero",       1),
    ("Feb", "Febrero",     2),
    ("Mar", "Marzo",       3),
    ("Abr", "Abril",       4),
    ("May", "Mayo",        5),
    ("Jun", "Junio",       6),
    ("Jul", "Julio",       7),
    ("Ago", "Agosto",      8),
    ("Sep", "Septiembre",  9),
    ("Oct", "Octubre",    10),
    ("Nov", "Noviembre",  11),
    ("Dic", "Diciembre",  12),
]

MESES_CON_DATOS    = {1, 2, 3, 4, 5}
MESES_NUM_A_NOMBRE = {num: nombre for _, nombre, num in TODOS_LOS_MESES}
EMPRESAS           = ["GEMCO", "Incardia", "MMQ", "Tecservice"]

ESTRUCTURA_EERR = [
    ("Ingresos",                        0, False),
    ("Costo de ventas",                 0, False),
    ("Margen Bruto",                    0, True),
    ("% Margen",                        0, False),
    ("GPBE Directos",                   1, False),
    ("GPBE Indirectos",                 1, False),
    ("GPBE Total",                      1, True),
    ("OGPN Directos",                   1, False),
    ("OGPN Indirectos",                 1, False),
    ("OGPN Total",                      1, True),
    ("Subtotal GAV",                    0, True),
    ("EBITDA Directo",                  0, True),
    ("% EBITDA",                        0, False),
    ("Finiquitos",                      1, False),
    ("Multas",                          1, False),
    ("Provisión Obsolescencias",        1, False),
    ("Provisión Incobrables",           1, False),
    ("Provisión Habilitación Oficinas", 1, False),
    ("Gastos Adicionales",              0, True),
    ("EBITDA Empresa",                  0, True),
    ("% EBITDA Empresa",                0, False),
    ("Depreciación",                    0, False),
    ("Resultado Operacional",           0, True),
    ("Otros Ingresos por Función",      1, False),
    ("Ingreso Financiero",              1, False),
    ("Costo Financiero",                1, False),
    ("Otros Gastos por Función",        1, False),
    ("Diferencia de Cambio",            1, False),
    ("Resultado No Operacional",        0, True),
    ("Resultado antes Impuestos",       0, True),
    ("Impuesto a la Renta",             0, False),
    ("Resultado del Ejercicio",         0, True),
]

MAPEO_CONCEPTO_PPTO = {
    "Ingresos":                        "Ingresos",
    "Costo de ventas":                 "Costo de Ventas",
    "Margen Bruto":                    "Margen Bruto",
    "GPBE Directos":                   "GPBE Directos",
    "GPBE Indirectos":                 "GPBE Indirectos",
    "GPBE Total":                      "GPBE Total",
    "OGPN Directos":                   "OGPN Directos",
    "OGPN Indirectos":                 "OGPN Indirectos",
    "OGPN Total":                      "OGPN Total",
    "Subtotal GAV":                    "Subtotal",
    "EBITDA Directo":                  "EBITDA Directo",
    "Finiquitos":                      "Finiquitos",
    "Multas":                          "Multas",
    "Provisión Obsolescencias":        "Prov Obsolescencias",
    "Provisión Incobrables":           "Prov Incobrables",
    "Provisión Habilitación Oficinas": "Prov Habilitacion",
    "Gastos Adicionales":              "Gastos Adicionales",
    "EBITDA Empresa":                  "EBITDA Empresa",
    "Depreciación":                    "Depreciacion",
    "Resultado Operacional":           "Resultado Operacional",
    "Otros Ingresos por Función":      "Otros Ingresos Funcion",
    "Ingreso Financiero":              "Ingreso Financiero",
    "Costo Financiero":                "Costo Financiero",
    "Otros Gastos por Función":        "Otros Gastos Funcion",
    "Diferencia de Cambio":            "Diferencia Cambio",
    "Resultado No Operacional":        "Resultado No Operacional",
    "Resultado antes Impuestos":       "Resultado Antes Impuestos",
    "Impuesto a la Renta":             "Impuesto Renta",
    "Resultado del Ejercicio":         "Resultado del Ejercicio",
}

NOMBRES_LARGOS = {
    "GPBE Directos":   "Gastos por Beneficios a los Empleados Directos",
    "GPBE Indirectos": "Gastos por Beneficios a los Empleados Indirectos",
    "GPBE Total":      "Gastos por Beneficios a los Empleados Total",
    "OGPN Directos":   "Otros Gastos por Naturaleza Directos",
    "OGPN Indirectos": "Otros Gastos por Naturaleza Indirectos",
    "OGPN Total":      "Otros Gastos por Naturaleza Total",
}

_INDENT = " " * 4

_SUBTOTALES = {
    (_INDENT * nivel) + clave
    for clave, nivel, es_sub in ESTRUCTURA_EERR
    if es_sub
}

# Factor de participación MMQ
_FACTOR_MMQ = {m: 0.75 for m in range(1, 4)}
_FACTOR_MMQ.update({m: 0.875 for m in range(4, 13)})

# Display empresa → Empresa_Comercial values
_EC_POR_EMP = {
    "GEMCO":      frozenset({"GEMCO", "Soporte Indirecto", "Ajustes Contables"}),
    "Incardia":   frozenset({"Incardia"}),
    "MMQ":        frozenset({"MMQ"}),
    "Tecservice": frozenset({"Tecservice"}),
}

# Drill-down specs para Real: EERR concept key → {c: nombre_en_eerr, optional filters}
_DRILL_DOWN = {
    "Ingresos":                     {"c": "Ingresos de actividades ordinarias"},
    "Costo de ventas":              {"c": "Costo de ventas"},
    "GPBE Directos":                {"c": "Gastos por beneficios a los empleados", "gav": "GAV DIRECTO"},
    "GPBE Indirectos":              {"c": "Gastos por beneficios a los empleados", "gav": "GAV INDIRECTO"},
    "OGPN Directos":                {"c": "Otros gastos por naturaleza", "ogpn_d": True},
    "OGPN Indirectos":              {"c": "Otros gastos por naturaleza", "ogpn_i": True},
    "Finiquitos":                   {"c": "Finiquitos", "excl_sc": True},
    "Multas":                       {"c": "Multas"},
    "Provisión Obsolescencias":     {"c": "Provisión Obsolescencias Inventarios"},
    "Provisión Incobrables":        {"c": "Provisión Incobrales"},
    "Provisión Habilitación Oficinas": {"c": "Provisión Habilitación Oficinas"},
    "Depreciación":                 {"c": "Gastos por depreciación y amortización"},
    "Otros Ingresos por Función":   {"c": "Otros Ingresos por Función"},
    "Ingreso Financiero":           {"c": "Ingreso Financiero"},
    "Costo Financiero":             {"c": "Costo financiero", "excl_nc": True},
    "Otros Gastos por Función":     {"c": "Otros gastos por función"},
    "Diferencia de Cambio":         {"c": "Diferencia de cambio"},
}

# Drill-down specs para Presupuesto: concept key → (Concepto_Padre, GAV|None)
_DRILL_DOWN_PPTO = {
    "Ingresos":                     ("Ingresos de actividades ordinarias", None),
    "Costo de ventas":              ("Costo de ventas", None),
    "GPBE Directos":                ("Gastos por beneficios a los empleados", "GAV DIRECTO"),
    "GPBE Indirectos":              ("Gastos por beneficios a los empleados", "GAV INDIRECTO"),
    "OGPN Directos":                ("Otros gastos por naturaleza", "GAV DIRECTO"),
    "OGPN Indirectos":              ("Otros gastos por naturaleza", "GAV INDIRECTO"),
    "Finiquitos":                   ("Finiquitos", None),
    "Multas":                       ("Multas", None),
    "Provisión Obsolescencias":     ("Provisión Obsolescencias Inventarios", None),
    "Provisión Incobrables":        ("Provisión Incobrales", None),
    "Provisión Habilitación Oficinas": ("Provisión Habilitación Oficinas", None),
    "Depreciación":                 ("Gastos por depreciación y amortización", None),
    "Otros Ingresos por Función":   ("Otros ingresos por función", None),
    "Ingreso Financiero":           ("Ingreso financiero", None),
    "Costo Financiero":             ("Costo financiero", None),
    "Otros Gastos por Función":     ("Otros gastos por función", None),
    "Diferencia de Cambio":         ("Diferencia de cambio", None),
}

PROPORCIONES_IND_GEMCO = {
    "Equipos Esterilización":     0.405631,
    "Consumibles Esterilización": 0.068991,
    "Equipos Dental":             0.053527,
    "Equipos Endoscopía":         0.396068,
    "Consumibles Endoscopía":     0.075782,
}

# Nombre en EERR y GAV para cada concepto indirecto prorrateable
_EERR_INDIRECTOS = {
    "GPBE Indirectos": ("Gastos por beneficios a los empleados", "GAV INDIRECTO"),
    "OGPN Indirectos": ("Otros gastos por naturaleza",           "GAV INDIRECTO"),
}

# Filas de porcentaje derivado (no tienen transacciones propias ni drill-down)
_FILAS_PCT = {"% Margen", "% EBITDA", "% EBITDA Empresa"}
_PCT_NUMERADOR = {
    "% Margen":         "Margen Bruto",
    "% EBITDA":         "EBITDA Directo",
    "% EBITDA Empresa": "EBITDA Empresa",
}

# ── Colores paleta gráficos ────────────────────────────────────────────────
_COL_REAL  = "#2c5f7c"
_COL_PPTO  = "#7fb3c8"
_COL_POS   = "#4a9e8c"
_COL_NEG   = "#d97b5f"
_COL_EMP   = {"GEMCO": "#2c5f7c", "Incardia": "#4a9e8c", "MMQ": "#8c6a2c", "Tecservice": "#7f8c9c"}


def empresa_visible(ec: str) -> str:
    if ec in ("GEMCO", "Soporte Indirecto", "Ajustes Contables"):
        return "GEMCO"
    return ec


def _aplicar_spec_mask(df: pd.DataFrame, spec: dict) -> pd.Series:
    mask = df["Nombre en EERR"] == spec["c"]
    if "gav" in spec:
        mask = mask & (df["GAV"] == spec["gav"])
    if spec.get("ogpn_d"):
        mask = mask & (
            (df["GAV"] == "GAV DIRECTO") |
            df["Empresa_Comercial"].isin({"Incardia", "MMQ", "Tecservice"})
        )
    if spec.get("ogpn_i"):
        mask = mask & (
            (df["GAV"] == "GAV INDIRECTO") &
            df["Empresa_Comercial"].isin({"GEMCO", "Soporte Indirecto", "Ajustes Contables"})
        )
    if spec.get("excl_sc"):
        mask = mask & (df["Linea_Negocio"] != "Sin clasificar")
    if spec.get("excl_nc"):
        mask = mask & (df["GAV"] != "No corresponde")
    return mask


def _suma_con_factor(sub: pd.DataFrame, factor_mmq_activo: bool = True) -> float:
    if sub.empty:
        return 0.0
    es_mmq = sub["Empresa_Comercial"] == "MMQ"
    total  = sub.loc[~es_mmq, "Cargo/abono (ML)"].sum()
    if es_mmq.any():
        mmq = sub[es_mmq].copy()
        if factor_mmq_activo:
            mmq["_f"] = mmq["Fecha"].dt.month.map(_FACTOR_MMQ)
            total += (mmq["Cargo/abono (ML)"] * mmq["_f"]).sum()
        else:
            total += mmq["Cargo/abono (ML)"].sum()
    return total


@st.cache_data
def cargar_base() -> pd.DataFrame:
    mapeo = cargar_mapeo_clasif()
    df_g = limpiar_gemco(pd.read_excel(EXCEL_PATH, sheet_name="Diario GEMCO"))
    df_i = limpiar_incardia(pd.read_excel(EXCEL_PATH, sheet_name="Diario Incardia"), mapeo)
    df_m = limpiar_mmq(pd.read_excel(EXCEL_PATH, sheet_name="Diario MMQ"), mapeo)
    df_t = limpiar_tecservice(pd.read_excel(EXCEL_PATH, sheet_name="Diario Tecservice"), mapeo)
    return consolidar(df_g, df_i, df_m, df_t)


@st.cache_data
def cargar_ppto():
    try:
        return cargar_presupuesto_completo(str(PPTO_PATH))
    except Exception:
        return None


@st.cache_data
def _agg_empresa(base: pd.DataFrame, clave: str, mes: int,
                 factor_mmq_activo: bool = True) -> dict:
    """Returns {empresa_display: valor_clp} (presentation sign × -1)."""
    spec = _DRILL_DOWN[clave]
    mask = _aplicar_spec_mask(base, spec) & (base["Fecha"].dt.month == mes)
    sub  = base[mask].copy()
    if sub.empty:
        return {}
    sub["_emp"] = sub["Empresa_Comercial"].map(empresa_visible)
    return {
        emp_vis: _suma_con_factor(grp, factor_mmq_activo) * -1
        for emp_vis, grp in sub.groupby("_emp")
    }


@st.cache_data
def _agg_linea(base: pd.DataFrame, clave: str, empresa_display: str, mes: int,
               factor_mmq_activo: bool = True) -> dict:
    """Returns {linea: valor_clp} sorted by |val| desc (presentation sign × -1)."""
    spec   = _DRILL_DOWN[clave]
    ec_set = _EC_POR_EMP.get(empresa_display, frozenset({empresa_display}))
    mask   = _aplicar_spec_mask(base, spec) & base["Empresa_Comercial"].isin(ec_set)
    mask   = mask & (base["Fecha"].dt.month == mes)
    sub    = base[mask].copy()
    if sub.empty:
        return {}
    result = {
        linea: _suma_con_factor(grp, factor_mmq_activo) * -1
        for linea, grp in sub.groupby("Linea_Negocio")
    }
    return dict(sorted(result.items(), key=lambda x: abs(x[1]), reverse=True))


@st.cache_data
def _linea_indirectos_gemco(base: pd.DataFrame, clave: str, meses_tuple: tuple) -> dict:
    """
    Para GPBE/OGPN Indirectos de GEMCO: reparte el total GAV Indirecto real
    entre las 5 líneas de negocio según PROPORCIONES_IND_GEMCO.
    Resultado consistente con emp_vals["GEMCO"] para los mismos meses.
    """
    nombre_eerr, gav = _EERR_INDIRECTOS[clave]
    mask = (
        (base["Nombre en EERR"] == nombre_eerr)
        & (base["GAV"] == gav)
        & base["Empresa_Comercial"].isin({"GEMCO", "Soporte Indirecto", "Ajustes Contables"})
        & base["Fecha"].dt.month.isin(meses_tuple)
    )
    total = base[mask]["Cargo/abono (ML)"].sum() * -1
    resultado = {linea: total * prop for linea, prop in PROPORCIONES_IND_GEMCO.items()}
    return dict(sorted(resultado.items(), key=lambda x: abs(x[1]), reverse=True))


@st.cache_data
def _ppto_empresa(df_ppto: pd.DataFrame, clave: str,
                  mes_nombre: str, empresas_tuple: tuple) -> dict:
    """Returns {empresa_display: valor_clp} from presupuesto (presentation sign)."""
    concepto_padre, gav = _DRILL_DOWN_PPTO[clave]
    m = (
        (df_ppto["Mes"] == mes_nombre)
        & (df_ppto["Nivel"] == "Linea")
        & (df_ppto["Concepto_Padre"] == concepto_padre)
        & (df_ppto["Empresa_Comercial"].isin(empresas_tuple))
    )
    if gav is not None:
        m = m & (df_ppto["GAV"] == gav)
    resultado = {}
    for emp in empresas_tuple:
        sub = df_ppto[m & (df_ppto["Empresa_Comercial"] == emp)]
        resultado[emp] = sub["Monto_Presupuesto"].sum() * 1e6
    return resultado


@st.cache_data
def _ppto_linea(df_ppto: pd.DataFrame, clave: str,
                mes_nombre: str, empresa: str) -> dict:
    """Returns {linea: valor_clp} sorted by |val| desc from presupuesto."""
    concepto_padre, gav = _DRILL_DOWN_PPTO[clave]
    m = (
        (df_ppto["Mes"] == mes_nombre)
        & (df_ppto["Nivel"] == "Linea")
        & (df_ppto["Concepto_Padre"] == concepto_padre)
        & (df_ppto["Empresa_Comercial"] == empresa)
    )
    if gav is not None:
        m = m & (df_ppto["GAV"] == gav)
    sub = df_ppto[m]
    if sub.empty:
        return {}
    agregado = sub.groupby("Linea_Negocio")["Monto_Presupuesto"].sum() * 1e6
    return dict(agregado.sort_values(key=abs, ascending=False))


@st.cache_data
def _eerr_empresa_acum(base: pd.DataFrame, empresa: str, meses_tuple: tuple) -> dict:
    """Acumulado EERR para una empresa sobre los meses dados (para graficos)."""
    acum: dict = {}
    for mes in meses_tuple:
        if mes in MESES_CON_DATOS:
            d = calcular_eerr(base, mes=mes, empresas=[empresa])
            for k, v in d.items():
                acum[k] = acum.get(k, 0.0) + v
    return acum


@st.cache_data
def _precalcular_graficos(base: pd.DataFrame, df_ppto) -> str:
    """Pre-calcula todos los datos EERR para el componente Chart.js. Cacheado."""
    meses_cfg = [(abr, nombre, num) for abr, nombre, num in TODOS_LOS_MESES]
    emp_configs = [
        ("Consolidado", None),
        ("GEMCO",       ["GEMCO"]),
        ("Incardia",    ["Incardia"]),
        ("MMQ",         ["MMQ"]),
        ("Tecservice",  ["Tecservice"]),
    ]
    datos: dict = {}
    for emp_label, emp_list in emp_configs:
        real_x: dict = {}
        for _, _, num in meses_cfg:
            if num in MESES_CON_DATOS:
                kw = {} if emp_list is None else {"empresas": emp_list}
                real_x[num] = calcular_eerr(base, mes=num, **kw)
        ppto_x: dict = {}
        if df_ppto is not None:
            for _, nombre_mes, num in meses_cfg:
                if emp_list is None:
                    ppto_x[num] = calcular_eerr_ppto(df_ppto, nombre_mes)
                else:
                    ppto_x[num] = calcular_eerr_ppto(
                        df_ppto, nombre_mes, empresa=emp_list[0]
                    )
        emp_data: dict = {}
        for clave, _, _ in ESTRUCTURA_EERR:
            real_arr, ppto_arr = [], []
            for _, _, num in meses_cfg:
                d = real_x.get(num)
                if d is None:
                    real_arr.append(None)
                elif clave in _FILAS_PCT:
                    nk = _PCT_NUMERADOR[clave]
                    ing = d.get("Ingresos", 0.0)
                    real_arr.append(
                        round(d.get(nk, 0.0) / ing * 100, 2) if ing else None
                    )
                else:
                    v = d.get(clave)
                    real_arr.append(round(v) if v is not None else None)
                p = ppto_x.get(num)
                if p is None:
                    ppto_arr.append(None)
                elif clave in _FILAS_PCT:
                    nk = _PCT_NUMERADOR[clave]
                    cn = MAPEO_CONCEPTO_PPTO.get(nk)
                    ci = MAPEO_CONCEPTO_PPTO.get("Ingresos")
                    ing_p = p.get(ci, 0.0) if ci else 0.0
                    ppto_arr.append(
                        round(p.get(cn, 0.0) / ing_p * 100, 2)
                        if (cn and ing_p)
                        else None
                    )
                else:
                    cp = MAPEO_CONCEPTO_PPTO.get(clave)
                    v = p.get(cp) if cp else None
                    ppto_arr.append(round(v) if v is not None else None)
            emp_data[clave] = {"real": real_arr, "ppto": ppto_arr}
        datos[emp_label] = emp_data
    lineas: dict = {}
    meses_r = tuple(sorted(MESES_CON_DATOS))
    for clave in _DRILL_DOWN:
        lineas[clave] = {}
        for emp_label, emp_list in emp_configs[1:]:
            is_solo_mmq = (emp_label == "MMQ")
            fm = not is_solo_mmq
            emp_lins: dict = {}
            for num in meses_r:
                is_prorr = (clave in _EERR_INDIRECTOS and emp_label == "GEMCO")
                vals = (
                    _linea_indirectos_gemco(base, clave, (num,))
                    if is_prorr
                    else _agg_linea(base, clave, emp_label, num, fm)
                )
                for linea, v in vals.items():
                    emp_lins[linea] = emp_lins.get(linea, 0.0) + v
            lineas[clave][emp_label] = emp_lins
        cons: dict = {}
        for ek in ["GEMCO", "Incardia", "MMQ", "Tecservice"]:
            for linea, v in lineas[clave].get(ek, {}).items():
                cons[linea] = cons.get(linea, 0.0) + v
        lineas[clave]["Consolidado"] = cons
    abrevs = [abr for abr, _, _ in TODOS_LOS_MESES]
    payload = {
        "abrev":           abrevs,
        "meses_con_datos": sorted(list(MESES_CON_DATOS)),
        "empresas":        ["Consolidado", "GEMCO", "Incardia", "MMQ", "Tecservice"],
        "conceptos":       [c for c, _, _ in ESTRUCTURA_EERR],
        "conceptos_pct":   list(_FILAS_PCT),
        "conceptos_drill": list(_DRILL_DOWN.keys()),
        "tiene_ppto":      df_ppto is not None,
        "datos":           datos,
        "lineas":          lineas,
    }
    return json.dumps(payload, ensure_ascii=False, default=float)


def _fmt(v, mm: bool = False) -> str:
    if mm:
        m = v / 1_000_000
        s = f"{abs(m):.1f}".replace(".", ",")
        return f"({s})" if v < 0 else s
    if v < 0:
        return f"({abs(int(v)):,})".replace(",", ".")
    return f"{int(v):,}".replace(",", ".")


def _fmt_var_pesos(real, ppto, mm: bool = False) -> str:
    if real is None or ppto is None or ppto == 0:
        return "-"
    var = real - ppto
    if mm:
        m = var / 1_000_000
        s = f"{abs(m):.1f}".replace(".", ",")
        return f"({s})" if var < 0 else f"+{s}"
    if var < 0:
        return f"({abs(int(var)):,})".replace(",", ".")
    return f"+{int(var):,}".replace(",", ".")


def _fmt_var_pct(real, ppto) -> str:
    if real is None or ppto is None or ppto == 0:
        return "-"
    pct   = (real - ppto) / abs(ppto) * 100
    signo = "+" if pct >= 0 else ""
    return f"{signo}{pct:.1f}%"


def _calc_pct_val(num_v, ing_v) -> str:
    """Ratio row: numerador / ingresos * 100, formato chileno (coma decimal)."""
    if num_v is None or ing_v is None or ing_v == 0:
        return "-"
    return f"{num_v / ing_v * 100:.1f}".replace(".", ",") + "%"


def _val_str(clave, nombre, num, tipo, resultados_real, resultados_ppto,
             mm: bool = False) -> str:
    real = (
        round(resultados_real[nombre].get(clave, 0.0))
        if nombre in resultados_real else None
    )
    clave_ppto = MAPEO_CONCEPTO_PPTO.get(clave)
    ppto_dict  = resultados_ppto.get(nombre, {})
    ppto = (
        round(ppto_dict[clave_ppto])
        if (clave_ppto and clave_ppto in ppto_dict) else None
    )
    if tipo == "Real":
        return _fmt(real, mm) if real is not None else "-"
    if tipo == "Ppto":
        return _fmt(ppto, mm) if ppto is not None else "-"
    if tipo == "Var $":
        return _fmt_var_pesos(real, ppto, mm)
    return _fmt_var_pct(real, ppto)


# ── App ────────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="EERR GEMCO", page_icon="📊")
st.title("EERR Consolidado 2026")

st.markdown("""
<style>
/* ── Tipografía base ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"], [data-testid="stApp"] {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}

/* ── Etiquetas de grupo de selectores ───────────────────────── */
.sel-label {
    font-size: 11px !important;
    color: #888888 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
    margin: 0 0 5px 0 !important;
    padding: 0 !important;
    line-height: 1.2;
}

/* ── Botones de selector (Meses, Empresa, Variación, Nav) ────── */
button[kind="secondary"],
button[data-testid="stBaseButton-secondary"] {
    background: #fafafa !important;
    color: #444444 !important;
    border: 1px solid #d0d0d0 !important;
    border-radius: 6px !important;
    height: 38px !important;
    min-height: 38px !important;
    font-weight: normal !important;
    transition: all 0.15s ease !important;
}
button[kind="secondary"]:hover,
button[data-testid="stBaseButton-secondary"]:hover {
    background: #f0f0f0 !important;
    border-color: #b0b0b0 !important;
    color: #444444 !important;
}
button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: #2c5f7c !important;
    color: #ffffff !important;
    border: 1px solid #2c5f7c !important;
    border-radius: 6px !important;
    height: 38px !important;
    min-height: 38px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: #245070 !important;
    border-color: #245070 !important;
}

/* ── Celda base de la tabla EERR ─────────────────────────────── */
.eerr-header {
    font-size: 0.74rem;
    font-weight: 700;
    color: #344054;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 2px solid #344054;
    padding: 4px 4px 7px 4px;
    margin-bottom: 2px;
}
.eerr-cell {
    padding: 5px 4px;
    border-bottom: 1px solid #ebebeb;
    font-size: 0.84rem;
    line-height: 1.35;
    color: #1a1a2e;
}
.eerr-alt {
    background-color: #f9fafb;
}
.eerr-sub {
    font-weight: 700;
    border-top: 2px solid #b0b0b0;
    border-bottom: 1px solid #b0b0b0;
    background-color: #f0f2f5 !important;
    color: #1a1a2e;
}
.eerr-pct {
    font-style: italic;
    font-size: 0.80rem;
    color: #556070;
}

/* ── Filas drill-down ────────────────────────────────────────── */
.eerr-drill-emp {
    background-color: #f5f7fa;
    border-bottom: 1px solid #e8e8e8;
    font-size: 0.82rem;
    padding: 4px 4px 4px 12px;
    color: #445566;
}
.eerr-drill-lin {
    background-color: #eff1f5;
    border-bottom: 1px solid #e4e4e4;
    font-size: 0.78rem;
    padding: 3px 4px 3px 24px;
    color: #667788;
}

/* ── Quitar margen extra entre elementos Streamlit ───────────── */
[data-testid="stVerticalBlock"] > [data-testid="element-container"] {
    margin-bottom: 0 !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: 6px !important;
}

/* ── HTML tabla EERR: sticky + scroll horizontal ─────────────── */
.eerr-wrap{overflow-x:auto;overflow-y:clip;border:1px solid #e2e4e8;border-radius:4px}
.eerr-tbl{border-collapse:collapse;white-space:nowrap;font-family:'Segoe UI',system-ui,sans-serif;font-size:.84rem;color:#1a1a2e}
.eerr-tbl th,.eerr-tbl td{padding:0 10px;border-bottom:1px solid #ebebeb;overflow:hidden}
.eerr-tbl thead tr{height:50px}
.eerr-tbl thead th{position:sticky;top:0;z-index:2;background:#f0f2f5;font-size:.74rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;text-align:right;border-bottom:2px solid #344054;white-space:nowrap;vertical-align:middle}
.eerr-tbl .sk{position:sticky;left:0;z-index:1}
.eerr-tbl thead th.sk{z-index:3;text-align:left;background:#f0f2f5;min-width:280px}
.eerr-tbl .concept{min-width:280px;text-align:left}
.eerr-tbl .val{min-width:120px;text-align:right;white-space:nowrap}
.eerr-tbl tbody tr{height:38px}
.eerr-tbl .ra td{background:#f9fafb}
.eerr-tbl .rs td{font-weight:700;border-top:2px solid #b0b0b0;border-bottom:1px solid #b0b0b0;background:#f0f2f5!important}
.eerr-tbl .rp td{font-style:italic;color:#556070;font-size:.80rem}
.eerr-tbl .re td{background:#f5f7fa;font-size:.82rem;color:#445566}
.eerr-tbl .rl td{background:#eff1f5;font-size:.78rem;color:#667788}

/* ── Layout 2 columnas dentro de col_tabla: botones | tabla HTML ─ */

/* col_btn: ancho fijo angosto */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child {
    flex: 0 0 42px !important;
    min-width: 42px !important;
    max-width: 42px !important;
}

/* col_tbl: ocupa el espacio restante */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:nth-child(2) {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}

/* Quitar gap vertical entre elementos de col_btn */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
> [data-testid="stVerticalBlock"] {
    gap: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

/* Contenedor stButton en col_btn: altura exacta de fila */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
[data-testid="stButton"] {
    height: 38px !important;
    min-height: 38px !important;
    max-height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* El <button> dentro de col_btn */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
[data-testid="stButton"] > button {
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    margin: 0 !important;
    font-weight: 700 !important;
    font-size: .78rem !important;
    line-height: 1 !important;
    width: 100% !important;
    color: #2c5f7c !important;
    background: #f2f4f7 !important;
    border: 1px solid #c0c8d0 !important;
    border-radius: 3px !important;
}
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
[data-testid="stButton"] > button:hover {
    background: #2c5f7c !important;
    color: #fff !important;
    border-color: #2c5f7c !important;
}

/* stMarkdown spacers en col_btn: sin márgenes extra */
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
[data-testid="stMarkdown"],
[data-testid="stColumn"]:last-child
[data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child
[data-testid="stMarkdownContainer"] {
    margin: 0 !important;
    padding: 0 !important;
}
/* ── Contenedor scroll compartido: col_btn + col_tbl se mueven juntos ─ */
[data-testid="stColumn"]:last-child [data-testid="stHorizontalBlock"] {
    max-height: 75vh !important;
    overflow-y: auto !important;
    align-items: flex-start !important;
    gap: 4px !important;
}
/* ── Divisor sutil entre controles y tabla ────────────────────── */
hr.sel-divider {
    border: none;
    border-top: 1px solid #eeeeee;
    margin: 14px 0 16px 0;
}
/* ── Espaciado entre filas de selectores ──────────────────────── */
[data-testid="stVerticalBlock"] > [data-testid="element-container"]:has(.sel-label) {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
/* ── Fila de meses: fila única, sin wrap, gap reducido ───────── */
/* Identificada unívocamente por tener 12 stColumn hijos          */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(12)) {
    flex-wrap: nowrap !important;
    gap: 3px !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(12))
button {
    font-size: 0.73rem !important;
    padding: 0 5px !important;
}

/* ── Gráficos: tarjetas de insight ──────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important;
    border: 1px solid #e8e8e8 !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
/* Restaura spacing entre elementos dentro de las tarjetas
   (anula el margin-bottom:0 global que aplica en el resto) */
[data-testid="stVerticalBlockBorderWrapper"]
[data-testid="stVerticalBlock"]
> [data-testid="element-container"] {
    margin-bottom: 4px !important;
}
/* Separador entre gráfico principal y grilla de insight */
hr.graf-divider {
    border: none;
    border-top: 1px solid #e8e8e8;
    margin: 8px 0 18px 0;
}
/* Subtítulo de sección "Gráficos de Insight" */
p.graf-insight-header {
    font-size: 11px;
    font-weight: 700;
    color: #aaaaaa;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 16px 0 !important;
}
/* Título dentro de cada tarjeta de gráfico */
p.graf-card-title {
    font-size: 15px;
    font-weight: 600;
    color: #2d3748;
    line-height: 1.3;
    margin: 0 0 6px 0 !important;
}
</style>
""", unsafe_allow_html=True)

if not EXCEL_PATH.exists():
    st.error(f"No se encontró el archivo Excel en: {EXCEL_PATH}")
    st.stop()

with st.spinner("Cargando datos..."):
    base    = cargar_base()
    df_ppto = cargar_ppto()

ppto_ok = df_ppto is not None
if not ppto_ok:
    st.warning("No se pudo cargar el Presupuesto, verifica que PPTO_V2.xlsx este en data/raw/")

# ── Estado de selectores (persistente entre reruns) ──────────────────────
if "hoja_activa"  not in st.session_state:
    st.session_state.hoja_activa  = "EERR"
if "sel_meses"    not in st.session_state:
    st.session_state.sel_meses    = set(MESES_CON_DATOS)
if "sel_empresas" not in st.session_state:
    st.session_state.sel_empresas = set(EMPRESAS)
if "sel_vistas"   not in st.session_state:
    st.session_state.sel_vistas   = set()
if "sel_millones" not in st.session_state:
    st.session_state.sel_millones = False

# ── Navegación superior (EERR / Gráficos) ────────────────────────────────
_nav_c, _ = st.columns([2, 8])
with _nav_c:
    _nb1, _nb2 = st.columns(2)
    with _nb1:
        if st.button("📊 EERR", key="nav_eerr",
                     type="primary" if st.session_state.hoja_activa == "EERR" else "secondary",
                     use_container_width=True):
            st.session_state.hoja_activa = "EERR"
            st.rerun()
    with _nb2:
        if st.button("📈 Gráficos", key="nav_graf",
                     type="primary" if st.session_state.hoja_activa == "Graficos" else "secondary",
                     use_container_width=True):
            st.session_state.hoja_activa = "Graficos"
            st.rerun()

# ── Selector de meses (compartido entre hojas) ────────────────────────────
st.markdown('<p class="sel-label">Meses</p>', unsafe_allow_html=True)
mes_cols = st.columns(12)
for col, (_, nombre, num) in zip(mes_cols, TODOS_LOS_MESES):
    with col:
        activo = num in st.session_state.sel_meses
        if st.button(nombre, key=f"mes_{num}",
                     type="primary" if activo else "secondary",
                     use_container_width=True):
            st.session_state.sel_meses.discard(num) if activo else st.session_state.sel_meses.add(num)
            st.rerun()

meses_activos = [
    (nombre, num) for _, nombre, num in TODOS_LOS_MESES
    if num in st.session_state.sel_meses
]
if not meses_activos:
    meses_activos = [(nombre, num) for _, nombre, num in TODOS_LOS_MESES]

# ── Selectores: empresa (compartido) + variación/escala (solo EERR) ──────
_ctl_emp, _ctl_vis, _ctl_mm, _ = st.columns([4, 2, 1, 3])

with _ctl_emp:
    st.markdown('<p class="sel-label">Empresa</p>', unsafe_allow_html=True)
    _emp_cols = st.columns(4)
    for _ec, _emp in zip(_emp_cols, EMPRESAS):
        with _ec:
            activo = _emp in st.session_state.sel_empresas
            if st.button(_emp, key=f"emp_{_emp}",
                         type="primary" if activo else "secondary",
                         use_container_width=True):
                st.session_state.sel_empresas.discard(_emp) if activo else st.session_state.sel_empresas.add(_emp)
                st.rerun()

if st.session_state.hoja_activa == "EERR":
    with _ctl_vis:
        st.markdown('<p class="sel-label">Variación</p>', unsafe_allow_html=True)
        _vis_cols = st.columns(2)
        with _vis_cols[0]:
            activo = "varp" in st.session_state.sel_vistas
            if st.button("Var $", key="v_varp",
                         type="primary" if activo else "secondary",
                         use_container_width=True,
                         disabled=not ppto_ok):
                st.session_state.sel_vistas.discard("varp") if activo else st.session_state.sel_vistas.add("varp")
                st.rerun()
        with _vis_cols[1]:
            activo = "varpct" in st.session_state.sel_vistas
            if st.button("Var %", key="v_varpct",
                         type="primary" if activo else "secondary",
                         use_container_width=True,
                         disabled=not ppto_ok):
                st.session_state.sel_vistas.discard("varpct") if activo else st.session_state.sel_vistas.add("varpct")
                st.rerun()
    with _ctl_mm:
        st.markdown('<p class="sel-label">Escala</p>', unsafe_allow_html=True)
        _activo_mm = st.session_state.sel_millones
        if st.button("MM$", key="v_millones_btn",
                     type="primary" if _activo_mm else "secondary",
                     use_container_width=True):
            st.session_state.sel_millones = not _activo_mm
            st.rerun()

v_varp     = "varp"   in st.session_state.sel_vistas
v_varpct   = "varpct" in st.session_state.sel_vistas
v_millones = st.session_state.sel_millones
v_real = True
v_ppto = ppto_ok

necesita_real = True
necesita_ppto = ppto_ok

empresas_seleccionadas = [e for e in EMPRESAS if e in st.session_state.sel_empresas]
empresas_efectivas = empresas_seleccionadas or list(EMPRESAS)

_n     = len(empresas_efectivas)
_todas = (_n == len(EMPRESAS))

kwargs_real = {} if _todas else {"empresas": empresas_efectivas}
if _todas:
    kwargs_ppto = {}
elif _n == 1:
    kwargs_ppto = {"empresa": empresas_efectivas[0]}
else:
    kwargs_ppto = {"empresas": empresas_efectivas}

if _todas:
    alcance = f"Consolidado ({len(EMPRESAS)} empresas)"
elif _n == 1:
    alcance = empresas_efectivas[0]
else:
    alcance = " + ".join(empresas_efectivas)

# ── Calcular resultados ────────────────────────────────────────────────────
resultados_real = {}
if necesita_real:
    for nombre, num in meses_activos:
        if num in MESES_CON_DATOS:
            resultados_real[nombre] = calcular_eerr(base, mes=num, **kwargs_real)

resultados_ppto = {}
if necesita_ppto:
    for nombre, num in meses_activos:
        resultados_ppto[nombre] = calcular_eerr_ppto(
            df_ppto, MESES_NUM_A_NOMBRE[num], **kwargs_ppto
        )

# ── Acumulado: suma directa de todos los meses seleccionados ──────────────
acum_real = {}
if necesita_real:
    for clave, _, _ in ESTRUCTURA_EERR:
        acum_real[clave] = round(sum(
            resultados_real.get(nombre, {}).get(clave, 0.0)
            for nombre, _ in meses_activos
        ))

acum_ppto = {}
if necesita_ppto:
    for clave, _, _ in ESTRUCTURA_EERR:
        clave_ppto = MAPEO_CONCEPTO_PPTO.get(clave)
        if clave_ppto:
            acum_ppto[clave] = round(sum(
                resultados_ppto.get(nombre, {}).get(clave_ppto, 0.0)
                for nombre, _ in meses_activos
            ))

# ── Base filtrada para drill-down ─────────────────────────────────────────
if _todas:
    base_drill = base
else:
    ec_drill = set()
    for e in empresas_efectivas:
        ec_drill.update(_EC_POR_EMP[e])
    base_drill = base[base["Empresa_Comercial"].isin(ec_drill)]

factor_mmq_activo = empresas_efectivas != ["MMQ"]

# ── Session state ─────────────────────────────────────────────────────────
if "expandido" not in st.session_state:
    st.session_state.expandido = {}

# ── Columnas de valor en orden ────────────────────────────────────────────
val_cols = []
for nombre, num in meses_activos:
    if v_real:   val_cols.append((nombre, num, "Real"))
    if v_ppto:   val_cols.append((nombre, num, "Ppto"))
    if v_varp:   val_cols.append((nombre, num, "Var $"))
    if v_varpct: val_cols.append((nombre, num, "Var %"))

if v_real:  val_cols.append(("Acumulado", None, "Real"))
if v_ppto:  val_cols.append(("Acumulado", None, "Ppto"))
if v_varp:  val_cols.append(("Acumulado", None, "Var $"))


def _cell_val(clave, nombre, num, tipo):
    if clave in _FILAS_PCT:
        if tipo in ("Var $", "Var %"):
            return "-"
        if num is None:
            src = acum_real if tipo == "Real" else acum_ppto
            return _calc_pct_val(src.get(_PCT_NUMERADOR[clave]), src.get("Ingresos"))
        if tipo == "Real":
            if nombre in resultados_real:
                d = resultados_real[nombre]
                return _calc_pct_val(
                    round(d.get(_PCT_NUMERADOR[clave], 0.0)),
                    round(d.get("Ingresos", 0.0)),
                )
            return "-"
        if nombre in resultados_ppto:
            p  = resultados_ppto[nombre]
            cn = MAPEO_CONCEPTO_PPTO.get(_PCT_NUMERADOR[clave])
            ci = MAPEO_CONCEPTO_PPTO.get("Ingresos")
            return _calc_pct_val(
                round(p.get(cn, 0.0)) if cn else None,
                round(p.get(ci, 0.0)) if ci else None,
            )
        return "-"
    if num is None:
        rv = acum_real.get(clave)
        pv = acum_ppto.get(clave)
        if tipo == "Real":  return _fmt(rv, v_millones) if rv is not None else "-"
        if tipo == "Ppto":  return _fmt(pv, v_millones) if pv is not None else "-"
        return _fmt_var_pesos(rv, pv, v_millones)
    return _val_str(clave, nombre, num, tipo, resultados_real, resultados_ppto, v_millones)


ROW_H    = 38
HEADER_H = 50


@st.fragment
def _tabla_eerr():
    rows = []

    for idx, (clave, nivel, es_sub) in enumerate(ESTRUCTURA_EERR):
        es_pct        = clave in _FILAS_PCT
        label         = NOMBRES_LARGOS.get(clave, clave)
        indent_html   = "&nbsp;" * (4 * nivel)
        es_expandible = (clave in _DRILL_DOWN) and not es_sub and not es_pct
        estado        = st.session_state.expandido.get(clave)
        expandido     = estado is not None

        if es_sub:
            tr_cls = "rs"; sk_bg = "#f0f2f5"
        elif es_pct:
            tr_cls = "rp" + (" ra" if idx % 2 else ""); sk_bg = "#f9fafb" if idx % 2 else "#ffffff"
        else:
            tr_cls = "ra" if idx % 2 else ""; sk_bg = "#f9fafb" if idx % 2 else "#ffffff"

        val_tds = "".join(
            f'<td class="val">{_cell_val(clave, nm, nu, tp)}</td>'
            for nm, nu, tp in val_cols
        )
        tr = (f'<tr class="{tr_cls}">'
              f'<td class="concept sk" style="background:{sk_bg}">{indent_html}{label}</td>'
              f'{val_tds}</tr>\n')

        rows.append({
            "tr": tr, "is_btn": es_expandible,
            "sym": ("−" if expandido else "+") if es_expandible else None,
            "key": f"btn_{clave}" if es_expandible else None,
            "rtype": "main", "clave": clave, "emp": None, "is_open": expandido,
        })

        if not (expandido and es_expandible):
            continue

        # ── Empresa drill-down ────────────────────────────────────────────
        emp_vh = {}
        for _, num, tipo in val_cols:
            if tipo == "Real" and num is not None and num in MESES_CON_DATOS and num not in emp_vh:
                emp_vh[num] = _agg_empresa(base_drill, clave, num, factor_mmq_activo)
        emp_vh[None] = {
            e_: sum(emp_vh.get(n, {}).get(e_, 0.0) for n in emp_vh if n is not None)
            for e_ in empresas_efectivas
        }
        ppto_evh = {}
        if clave in _DRILL_DOWN_PPTO and ppto_ok:
            etup = tuple(empresas_efectivas)
            need = {nu for _, nu, tp in val_cols if tp in ("Ppto", "Var $", "Var %") and nu is not None}
            for num in need:
                ppto_evh[num] = _ppto_empresa(df_ppto, clave, MESES_NUM_A_NOMBRE[num], etup)
            ppto_evh[None] = {
                e_: sum(ppto_evh.get(n, {}).get(e_, 0.0) for n in ppto_evh if n is not None)
                for e_ in empresas_efectivas
            }

        for emp in empresas_efectivas:
            linea_abierta = isinstance(estado, tuple) and estado[1] == emp
            etds = []
            for nm, nu, tp in val_cols:
                rv = round(emp_vh.get(nu, {}).get(emp, 0.0))   if nu in emp_vh   else None
                pv = round(ppto_evh.get(nu, {}).get(emp, 0.0)) if nu in ppto_evh else None
                if   tp == "Real":  v = _fmt(rv, v_millones)           if rv is not None else "-"
                elif tp == "Ppto":  v = _fmt(pv, v_millones)           if pv is not None else "-"
                elif tp == "Var $": v = _fmt_var_pesos(rv, pv, v_millones)
                else:               v = _fmt_var_pct(rv, pv)
                etds.append(f'<td class="val">{v}</td>')
            emp_tr = (f'<tr class="re">'
                      f'<td class="concept sk" style="background:#f5f7fa;padding-left:14px">↳ {emp}</td>'
                      f'{"".join(etds)}</tr>\n')
            rows.append({
                "tr": emp_tr, "is_btn": True,
                "sym": "−" if linea_abierta else "+",
                "key": f"btn_{clave}__{emp}",
                "rtype": "emp", "clave": clave, "emp": emp, "is_open": linea_abierta,
            })

            if not linea_abierta:
                continue

            # ── Linea drill-down ──────────────────────────────────────────
            lv_h   = {}
            _prorr = clave in _EERR_INDIRECTOS and emp == "GEMCO"
            for _, num, tipo in val_cols:
                if tipo == "Real" and num is not None and num in MESES_CON_DATOS and num not in lv_h:
                    lv_h[num] = (
                        _linea_indirectos_gemco(base_drill, clave, (num,))
                        if _prorr else
                        _agg_linea(base_drill, clave, emp, num, factor_mmq_activo)
                    )
            real_ms = [n for n in lv_h if n is not None]
            if _prorr:
                lv_h[None] = _linea_indirectos_gemco(base_drill, clave, tuple(real_ms)) if real_ms else {}
            else:
                all_lk: set = set()
                for n in real_ms: all_lk.update(lv_h[n].keys())
                lv_h[None] = {l: sum(lv_h[n].get(l, 0.0) for n in real_ms) for l in all_lk}

            plv_h = {}
            if clave in _DRILL_DOWN_PPTO and ppto_ok:
                needl = {nu for _, nu, tp in val_cols if tp in ("Ppto", "Var $", "Var %") and nu is not None}
                for num in needl:
                    plv_h[num] = _ppto_linea(df_ppto, clave, MESES_NUM_A_NOMBRE[num], emp)
                pms = [n for n in plv_h if n is not None]
                all_pl: set = set()
                for n in pms: all_pl.update(plv_h[n].keys())
                plv_h[None] = {l: sum(plv_h[n].get(l, 0.0) for n in pms) for l in all_pl}

            all_lin = set()
            for lv_dict in (lv_h, plv_h):
                for m, lv in lv_dict.items():
                    if m is not None: all_lin.update(lv.keys())

            sorted_lin = sorted(
                all_lin,
                key=lambda l: (
                    sum(abs(lv_h.get(m, {}).get(l, 0)) for m in lv_h if m is not None)
                    + sum(abs(plv_h.get(m, {}).get(l, 0)) for m in plv_h if m is not None)
                ),
                reverse=True,
            )

            for linea in sorted_lin:
                ltds = []
                for nm, nu, tp in val_cols:
                    rv = round(lv_h.get(nu, {}).get(linea, 0.0))  if nu in lv_h  else None
                    pv = round(plv_h.get(nu, {}).get(linea, 0.0)) if nu in plv_h else None
                    if   tp == "Real":  v = _fmt(rv, v_millones) if rv is not None else "-"
                    elif tp == "Ppto":  v = _fmt(pv, v_millones) if pv is not None else "-"
                    elif tp == "Var $": v = _fmt_var_pesos(rv, pv, v_millones)
                    else:               v = _fmt_var_pct(rv, pv)
                    ltds.append(f'<td class="val">{v}</td>')
                lin_tr = (f'<tr class="rl">'
                          f'<td class="concept sk" style="background:#eff1f5;padding-left:28px">· {linea}</td>'
                          f'{"".join(ltds)}</tr>\n')
                rows.append({
                    "tr": lin_tr, "is_btn": False, "sym": None, "key": None,
                    "rtype": "lin", "clave": None, "emp": None, "is_open": False,
                })

    # ── Render ────────────────────────────────────────────────────────────
    col_btn, col_tbl = st.columns([1, 22])

    with col_btn:
        st.markdown(
            f'<div id="eerr-btn-anchor" class="eerr-hdr-sp" style="height:{HEADER_H}px;margin:0;padding:0;display:block"></div>',
            unsafe_allow_html=True,
        )
        for row in rows:
            if row["is_btn"]:
                if st.button(row["sym"], key=row["key"], use_container_width=True):
                    clave   = row["clave"]
                    is_open = row["is_open"]
                    if row["rtype"] == "main":
                        st.session_state.expandido[clave] = None if is_open else "EMPRESA"
                    else:
                        st.session_state.expandido[clave] = (
                            "EMPRESA" if is_open else ("LINEA", row["emp"])
                        )
                    st.rerun()
            else:
                st.markdown(
                    f'<div class="eerr-row-sp" style="height:{ROW_H}px;margin:0;padding:0;display:block"></div>',
                    unsafe_allow_html=True,
                )

    with col_tbl:
        th_cells = ['<th class="sk concept">Concepto</th>']
        for nm, _, tp in val_cols:
            th_cells.append(f'<th class="val">{nm}<br>{tp}</th>')
        parts = [
            '<div class="eerr-wrap" id="eerr-table-wrap"><table class="eerr-tbl">',
            f'<thead><tr>{"".join(th_cells)}</tr></thead><tbody>',
        ]
        for row in rows:
            parts.append(row["tr"])
        parts.append('</tbody></table></div>')
        st.markdown("".join(parts), unsafe_allow_html=True)


# ── Gráficos Chart.js ─────────────────────────────────────────────────────

_GRAFICOS_HTML_TPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--az:#2c5f7c;--te:#4a9e8c;--rd:#d97b5f;--gy:#f5f7fb;--brd:#e2e4e8;--wh:#fff;--r:8px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--gy);color:#1a1a2e;font-size:13px;padding:4px 4px 28px}
.card{background:var(--wh);border:1px solid var(--brd);border-radius:var(--r);margin-bottom:16px;overflow:hidden}
.ch{padding:10px 14px;border-bottom:1px solid var(--brd);background:#f8f9fc;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ct{font-size:11px;font-weight:700;color:#4a5568;text-transform:uppercase;letter-spacing:.06em}
.cb{padding:14px}
.ctrl{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.lbl{font-size:10px;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.bg{display:flex;gap:4px;flex-wrap:wrap}
.btn{background:var(--wh);border:1px solid #d0d5dd;color:#555;font-size:11px;font-weight:600;padding:4px 10px;border-radius:20px;cursor:pointer;transition:all .12s;font-family:inherit}
.btn:hover{border-color:var(--az);color:var(--az)}
.btn.on{background:var(--az);color:#fff;border-color:var(--az)}
select.sl{border:1px solid #d0d5dd;border-radius:6px;padding:4px 8px;font-size:11px;font-family:inherit;color:#444;background:var(--wh);cursor:pointer;outline:none}
select.sl:focus{border-color:var(--az)}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.wrap{position:relative}
</style>
</head>
<body>

<div class="card">
  <div class="ch">
    <span class="ct">Real vs Presupuesto</span>
    <select class="sl" id="sc" style="min-width:190px"></select>
  </div>
  <div class="cb">
    <div class="ctrl">
      <span class="lbl">Empresa</span><div class="bg" id="eg"></div>
      <span class="lbl">Vista</span>
      <div class="bg">
        <button class="btn on" data-v="bar" onclick="setV(this)">Barras</button>
        <button class="btn" data-v="line" onclick="setV(this)">L\\u00edneas</button>
        <button class="btn" data-v="acum" onclick="setV(this)">Acumulado</button>
      </div>
      <span class="lbl">Series</span>
      <div class="bg">
        <button class="btn on" data-s="real" onclick="toggleS(this)">Real</button>
        <button class="btn" id="bp" data-s="ppto" onclick="toggleS(this)">Ppto</button>
      </div>
    </div>
    <div class="wrap" style="height:340px"><canvas id="cM"></canvas></div>
  </div>
</div>

<div class="g3">
  <div class="card">
    <div class="ch">
      <span class="ct" style="font-size:10px">Cascada EBITDA</span>
      <select class="sl" id="we" onchange="buildWF()" style="font-size:10px"></select>
      <select class="sl" id="wm" onchange="buildWF()" style="font-size:10px"></select>
    </div>
    <div class="cb" style="padding:10px">
      <div class="wrap" style="height:300px"><canvas id="cW"></canvas></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">
      <span class="ct" style="font-size:10px">Composici\\u00f3n por Empresa</span>
      <select class="sl" id="dc" onchange="buildD()" style="font-size:10px;max-width:130px"></select>
    </div>
    <div class="cb" style="padding:10px">
      <div class="wrap" style="height:300px"><canvas id="cD"></canvas></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">
      <span class="ct" style="font-size:10px">Ranking L\\u00edneas</span>
      <select class="sl" id="rc" onchange="buildR()" style="font-size:10px;max-width:100px"></select>
      <select class="sl" id="re" onchange="buildR()" style="font-size:10px"></select>
    </div>
    <div class="cb" style="padding:10px">
      <div class="wrap" style="height:300px"><canvas id="cR"></canvas></div>
    </div>
  </div>
</div>

<script>
const D=__DATOS__;
const CR='#2c5f7c',CP='#7fb3c8',CPs='#4a9e8c',CN='#d97b5f';
const CE={GEMCO:'#2c5f7c',Incardia:'#4a9e8c',MMQ:'#8c6a2c',Tecservice:'#7f8c9c',Consolidado:'#5577aa'};
Chart.defaults.font.family="'Segoe UI',system-ui,sans-serif";Chart.defaults.color='#718096';

let sE='Consolidado',sV='bar',sR=true,sP=D.tiene_ppto;
let cM=null,cW=null,cD=null,cR=null;

const fmm=v=>{if(v==null)return'—';const s=v<0?'(':'' ,e=v<0?')':'';return s+'MM$'+Math.abs(v/1e6).toFixed(1)+e;};
const fax=v=>{if(v==null)return'';const a=Math.abs(v);if(a>=1e9)return(v/1e9).toFixed(1)+'B';if(a>=1e6)return(v/1e6).toFixed(0)+'M';if(a>=1e3)return(v/1e3).toFixed(0)+'K';return v.toFixed(0);};
const cum=a=>{let s=0;return a.map(v=>{if(v!==null)s+=v;return v!==null?s:null;});};

function init(){
  const sc=document.getElementById('sc');
  D.conceptos.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sc.appendChild(o);});
  sc.addEventListener('change',buildM);

  const eg=document.getElementById('eg');
  D.empresas.forEach(e=>{
    const b=document.createElement('button');
    b.className='btn'+(e==='Consolidado'?' on':'');
    b.textContent=e==='Consolidado'?'Consol':e;b.dataset.e=e;
    b.onclick=()=>{document.querySelectorAll('#eg .btn').forEach(x=>x.classList.remove('on'));b.classList.add('on');sE=e;buildM();};
    eg.appendChild(b);
  });

  const bp=document.getElementById('bp');
  if(D.tiene_ppto){bp.classList.add('on');}
  else{bp.disabled=true;bp.style.opacity='0.4';}

  const we=document.getElementById('we');
  D.empresas.forEach(e=>{const o=document.createElement('option');o.value=e;o.textContent=e==='Consolidado'?'Consol':e;we.appendChild(o);});

  const wm=document.getElementById('wm');
  const lm=D.meses_con_datos[D.meses_con_datos.length-1];
  D.meses_con_datos.forEach(n=>{const o=document.createElement('option');o.value=n-1;o.textContent=D.abrev[n-1];if(n===lm)o.selected=true;wm.appendChild(o);});

  const dc=document.getElementById('dc');
  D.conceptos.filter(c=>!D.conceptos_pct.includes(c)).forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;dc.appendChild(o);});

  const rc=document.getElementById('rc'),re=document.getElementById('re');
  D.conceptos_drill.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;rc.appendChild(o);});
  D.empresas.forEach(e=>{const o=document.createElement('option');o.value=e;o.textContent=e==='Consolidado'?'Consol':e;re.appendChild(o);});
}

function setV(b){document.querySelectorAll('[data-v]').forEach(x=>x.classList.remove('on'));b.classList.add('on');sV=b.dataset.v;buildM();}
function toggleS(b){if(b.dataset.s==='real'){sR=!sR;b.classList.toggle('on',sR);}else{sP=!sP;b.classList.toggle('on',sP);}buildM();}

function buildM(){
  const c=document.getElementById('sc').value;
  const isPct=D.conceptos_pct.includes(c);
  const d=D.datos[sE][c];
  let ra=d.real.slice(),pa=d.ppto.slice();
  if(sV==='acum'){ra=cum(d.real);pa=cum(d.ppto);}
  const il=sV!=='bar';
  const ds=[];
  if(sR)ds.push({label:'Real',data:ra,backgroundColor:il?'rgba(44,95,124,.1)':CR,borderColor:CR,borderWidth:il?2:0,fill:il,tension:.3,pointRadius:il?4:0,borderRadius:il?0:4,spanGaps:true});
  if(sP&&D.tiene_ppto)ds.push({label:'Presupuesto',data:pa,backgroundColor:il?'rgba(127,179,200,.1)':CP,borderColor:CP,borderWidth:il?2:0,borderDash:il?[5,5]:undefined,fill:false,tension:.3,pointRadius:il?4:0,borderRadius:il?0:4,spanGaps:true});
  if(cM)cM.destroy();
  cM=new Chart(document.getElementById('cM'),{
    type:il?'line':'bar',data:{labels:D.abrev,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{position:'bottom',labels:{boxWidth:10,font:{size:11}}},
        tooltip:{callbacks:{label:ctx=>{const v=ctx.raw;if(v==null)return null;return' '+ctx.dataset.label+': '+(isPct?(v.toFixed(1)+'%'):fmm(v));}}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:11}}},y:{grid:{color:'#edf0f7'},ticks:{callback:v=>isPct?(v.toFixed(1)+'%'):fax(v),font:{size:11}}}}}
  });
}

function buildWF(){
  const emp=document.getElementById('we').value;
  const mi=parseInt(document.getElementById('wm').value);
  const cs=['Ingresos','Costo de ventas','Margen Bruto','Subtotal GAV','EBITDA Directo','Gastos Adicionales','EBITDA Empresa'];
  const ms=['rel','rel','tot','rel','tot','rel','tot'];
  const lb=['Ingresos','Costo VTA','Marg. Bruto','Subt. GAV','EBITDA Dir.','Gs. Adic.','EBITDA Emp.'];
  const bars=[],cols=[];let run=0;
  for(let i=0;i<cs.length;i++){
    const d2=D.datos[emp][cs[i]];const v=(d2&&d2.real[mi]!==null)?d2.real[mi]:0;
    if(ms[i]==='tot'){bars.push([0,v]);cols.push(CR);run=v;}
    else{const en=run+v;bars.push([Math.min(run,en),Math.max(run,en)]);cols.push(v>=0?CPs:CN);run=en;}
  }
  if(cW)cW.destroy();
  cW=new Chart(document.getElementById('cW'),{
    type:'bar',data:{labels:lb,datasets:[{data:bars,backgroundColor:cols,borderRadius:3,borderSkipped:false}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>{
        const i=ctx.dataIndex;
        const d3=D.datos[document.getElementById('we').value][cs[i]];
        const v=d3&&d3.real[parseInt(document.getElementById('wm').value)]!==null?d3.real[parseInt(document.getElementById('wm').value)]:0;
        return' '+lb[i]+': '+fmm(v);
      }}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:10},maxRotation:20}},y:{grid:{color:'#edf0f7'},ticks:{callback:fax,font:{size:10}}}}}
  });
}

function buildD(){
  const c=document.getElementById('dc').value;
  const emps=['GEMCO','Incardia','MMQ','Tecservice'];
  const vals=emps.map(e=>{const d=D.datos[e][c];if(!d)return 0;return D.meses_con_datos.reduce((s,n)=>s+(d.real[n-1]||0),0);});
  if(cD)cD.destroy();
  cD=new Chart(document.getElementById('cD'),{
    type:'bar',data:{labels:emps,datasets:[{data:vals,backgroundColor:emps.map(e=>CE[e]),borderRadius:4}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>' '+ctx.label+': '+fmm(ctx.raw)}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:10}}},y:{grid:{color:'#edf0f7'},ticks:{callback:fax,font:{size:10}}}}}
  });
}

function buildR(){
  const c=document.getElementById('rc').value,e=document.getElementById('re').value;
  const ld=(D.lineas[c]&&D.lineas[c][e])?D.lineas[c][e]:{};
  const en2=Object.entries(ld).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,15);
  const lb2=en2.map(([l])=>l.length>30?l.slice(0,29)+'\\u2026':l);
  const vl=en2.map(([,v])=>v);
  const cl=vl.map(v=>v>=0?CPs:CN);
  if(cR)cR.destroy();
  cR=new Chart(document.getElementById('cR'),{
    type:'bar',data:{labels:lb2,datasets:[{data:vl,backgroundColor:cl,borderRadius:3}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>' '+ctx.label+': '+fmm(ctx.raw)}}},
      scales:{x:{grid:{color:'#edf0f7'},ticks:{callback:fax,font:{size:10}}},y:{grid:{display:false},ticks:{font:{size:10}}}}}
  });
}

document.addEventListener('DOMContentLoaded',()=>{init();buildM();buildWF();buildD();buildR();});
</script>
</body>
</html>"""


def _graficos():
    json_str = _precalcular_graficos(base, df_ppto)
    json_str = json_str.replace("</script>", r"<\/script>")
    html = _GRAFICOS_HTML_TPL.replace("__DATOS__", json_str)
    components.html(html, height=960, scrolling=True)


# ── Renderizado condicional por hoja ──────────────────────────────────────
st.markdown('<hr class="sel-divider">', unsafe_allow_html=True)

if st.session_state.hoja_activa == "EERR":
    (col_tabla,) = st.columns(1)
    with col_tabla:
        st.subheader(alcance)
        _tabla_eerr()
else:
    _graficos()
