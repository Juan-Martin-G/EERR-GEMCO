"""
generar_datos.py
=================
Precalcula TODO el EERR (Real y Presupuesto, consolidado + por empresa,
incluyendo drill-down de 2 niveles) y lo guarda en un unico archivo JSON
que consume el sitio estatico (HTML/JS puro, sin Python en vivo).

USO: correr este script cada vez que se actualicen los datos fuente
(V11.xlsx / PPTO_V2.xlsx), y subir el JSON resultante junto con el sitio.

    python generar_datos.py

Genera: docs/datos_eerr.json (ajustar ruta de salida segun la estructura
del repo que se use en GitHub Pages - 'docs/' es la convencion mas comun
para servir GitHub Pages desde una subcarpeta del repo principal).
Genera tambien docs/datos_lineas.json (EERR por Linea de Negocio y Curvas
J), que el panel descarga solo al abrir la hoja "Lineas" o "Curvas J".

Reutiliza EXACTAMENTE la misma logica ya validada en:
  - transformacion/diarios.py
  - transformacion/presupuesto.py
  - transformacion/lineas.py   (EERR por Linea de Negocio)
  - calculo/eerr.py
  - calculo/eerr_presupuesto.py
  - calculo/curvas_j.py        (Curvas J: Real vs Presupuesto por linea)
  - calculo/ppto_lineas.py     (Presupuesto por concepto y linea, hoja Lineas)
No reimplementa ninguna regla de negocio - solo orquesta y serializa.
"""

import json
import pandas as pd
from pathlib import Path

from transformacion.diarios import (
    cargar_mapeo_clasif, limpiar_gemco, limpiar_incardia,
    limpiar_mmq, limpiar_tecservice, consolidar,
)
from transformacion.presupuesto import cargar_presupuesto_completo
from transformacion.lineas import (
    asignar_lineas, cargar_centro_linea, cargar_prorrateo, lineas_reporte,
    LINEA_POR_EMPRESA, PRORRATEO, SIN_ASIGNAR,
)
from calculo.eerr import calcular_eerr
from calculo.eerr_presupuesto import calcular_eerr_ppto
from calculo.curvas_j import (
    leer_presupuesto, construir_curvas_j, controlar_curvas_j, CONCEPTO_REAL,
)
from calculo.ppto_lineas import (
    presupuesto_exacto, leer_hojas as leer_hojas_ppto, controlar_lineas_ppto,
)

# ──────────────────────────────────────────────────────────────────────
# CONFIGURACION
# ──────────────────────────────────────────────────────────────────────

ARCHIVO_V11 = "data/raw/v8.xlsx"
ARCHIVO_PPTO = "data/raw/PPTO_V2.xlsx"
SALIDA_JSON = "docs/datos_eerr.json"
# EERR por Linea de Negocio: archivo aparte, que el panel descarga solo
# cuando se abre la hoja "Lineas" (no engorda la carga inicial).
SALIDA_JSON_LINEAS = "docs/datos_lineas.json"

MESES_NUM = list(range(1, 13))
MESES_NOMBRE = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre",
    11: "Noviembre", 12: "Diciembre",
}

EMPRESAS = ["GEMCO", "Incardia", "MMQ", "Tecservice"]

# Conceptos del EERR, en orden de presentacion (igual que ESTRUCTURA_EERR
# de app/main.py). nivel: 0 o 1 (indentacion). tipo: "normal" | "subtotal"
# | "porcentaje".
ESTRUCTURA_EERR = [
    ("Ingresos", 0, "normal"),
    ("Costo de ventas", 0, "normal"),
    ("Margen Bruto", 0, "subtotal"),
    ("% Margen", 0, "porcentaje"),
    ("GPBE Directos", 1, "normal"),
    ("GPBE Indirectos", 1, "normal"),
    ("GPBE Total", 1, "subtotal"),
    ("OGPN Directos", 1, "normal"),
    ("OGPN Indirectos", 1, "normal"),
    ("OGPN Total", 1, "subtotal"),
    ("Subtotal GAV", 0, "subtotal"),
    ("EBITDA Directo", 0, "subtotal"),
    ("% EBITDA", 0, "porcentaje"),
    ("Finiquitos", 1, "normal"),
    ("Multas", 1, "normal"),
    ("Provisión Obsolescencias", 1, "normal"),
    ("Provisión Incobrables", 1, "normal"),
    ("Provisión Habilitación Oficinas", 1, "normal"),
    ("Gastos Adicionales", 0, "subtotal"),
    ("EBITDA Empresa", 0, "subtotal"),
    ("% EBITDA Empresa", 0, "porcentaje"),
    ("Depreciación", 0, "normal"),
    ("Resultado Operacional", 0, "subtotal"),
    ("Otros Ingresos por Función", 1, "normal"),
    ("Ingreso Financiero", 1, "normal"),
    ("Costo Financiero", 1, "normal"),
    ("Otros Gastos por Función", 1, "normal"),
    ("Diferencia de Cambio", 1, "normal"),
    ("Resultado No Operacional", 0, "subtotal"),
    ("Resultado antes Impuestos", 0, "subtotal"),
    ("Impuesto a la Renta", 0, "normal"),
    ("Resultado del Ejercicio", 0, "subtotal"),
]

# Mapeo de nombre de concepto (tabla) -> key en el dict de calcular_eerr()
KEY_REAL = {
    "Ingresos": "Ingresos", "Costo de ventas": "Costo de ventas",
    "Margen Bruto": "Margen Bruto",
    "GPBE Directos": "GPBE Directos", "GPBE Indirectos": "GPBE Indirectos",
    "GPBE Total": "GPBE Total",
    "OGPN Directos": "OGPN Directos", "OGPN Indirectos": "OGPN Indirectos",
    "OGPN Total": "OGPN Total",
    "Subtotal GAV": "Subtotal GAV", "EBITDA Directo": "EBITDA Directo",
    "Finiquitos": "Finiquitos", "Multas": "Multas",
    "Provisión Obsolescencias": "Provisión Obsolescencias",
    "Provisión Incobrables": "Provisión Incobrables",
    "Provisión Habilitación Oficinas": "Provisión Habilitación Oficinas",
    "Gastos Adicionales": "Gastos Adicionales",
    "EBITDA Empresa": "EBITDA Empresa", "Depreciación": "Depreciación",
    "Resultado Operacional": "Resultado Operacional",
    "Otros Ingresos por Función": "Otros Ingresos por Función",
    "Ingreso Financiero": "Ingreso Financiero",
    "Costo Financiero": "Costo Financiero",
    "Otros Gastos por Función": "Otros Gastos por Función",
    "Diferencia de Cambio": "Diferencia de Cambio",
    "Resultado No Operacional": "Resultado No Operacional",
    "Resultado antes Impuestos": "Resultado antes Impuestos",
    "Impuesto a la Renta": "Impuesto a la Renta",
    "Resultado del Ejercicio": "Resultado del Ejercicio",
}

# Mismo mapeo pero hacia las keys de calcular_eerr_ppto()
KEY_PPTO = {
    "Ingresos": "Ingresos", "Costo de ventas": "Costo de Ventas",
    "Margen Bruto": "Margen Bruto",
    "GPBE Directos": "GPBE Directos", "GPBE Indirectos": "GPBE Indirectos",
    "GPBE Total": "GPBE Total",
    "OGPN Directos": "OGPN Directos", "OGPN Indirectos": "OGPN Indirectos",
    "OGPN Total": "OGPN Total",
    "Subtotal GAV": "Subtotal", "EBITDA Directo": "EBITDA Directo",
    "Finiquitos": "Finiquitos", "Multas": "Multas",
    "Provisión Obsolescencias": "Prov Obsolescencias",
    "Provisión Incobrables": "Prov Incobrables",
    "Provisión Habilitación Oficinas": "Prov Habilitacion",
    "Gastos Adicionales": "Gastos Adicionales",
    "EBITDA Empresa": "EBITDA Empresa", "Depreciación": "Depreciacion",
    "Resultado Operacional": "Resultado Operacional",
    "Otros Ingresos por Función": "Otros Ingresos Funcion",
    "Ingreso Financiero": "Ingreso Financiero",
    "Costo Financiero": "Costo Financiero",
    "Otros Gastos por Función": "Otros Gastos Funcion",
    "Diferencia de Cambio": "Diferencia Cambio",
    "Resultado No Operacional": "Resultado No Operacional",
    "Resultado antes Impuestos": "Resultado Antes Impuestos",
    "Impuesto a la Renta": "Impuesto Renta",
    "Resultado del Ejercicio": "Resultado del Ejercicio",
}

# Conceptos con drill-down disponible (mismo criterio que app/main.py):
# nombre_concepto -> (Nombre en EERR nativo, GAV o None)
DRILL_DOWN_FILTROS = {
    "Ingresos": ("Ingresos de actividades ordinarias", None),
    "Costo de ventas": ("Costo de ventas", None),
    "GPBE Directos": ("Gastos por beneficios a los empleados", "GAV DIRECTO"),
    "GPBE Indirectos": ("Gastos por beneficios a los empleados", "GAV INDIRECTO"),
    "OGPN Directos": ("Otros gastos por naturaleza", "GAV DIRECTO"),
    "OGPN Indirectos": ("Otros gastos por naturaleza", "GAV INDIRECTO"),
    "Finiquitos": ("Finiquitos", None),
    "Multas": ("Multas", None),
    "Provisión Obsolescencias": ("Provisión Obsolescencias Inventarios", None),
    "Provisión Incobrables": ("Provisión Incobrales", None),
    "Provisión Habilitación Oficinas": ("Provisión Habilitación Oficinas", None),
    "Depreciación": ("Gastos por depreciación y amortización", None),
    "Otros Ingresos por Función": ("Otros Ingresos por Función", None),
    "Ingreso Financiero": ("Ingreso Financiero", None),
    "Costo Financiero": ("Costo financiero", None),
    "Otros Gastos por Función": ("Otros gastos por función", None),
    "Diferencia de Cambio": ("Diferencia de cambio", None),
}

# Version Presupuesto (Concepto_Padre, GAV) - ojo con mayus/minus exactas
DRILL_DOWN_FILTROS_PPTO = {
    "Ingresos": ("Ingresos de actividades ordinarias", None),
    "Costo de ventas": ("Costo de ventas", None),
    "GPBE Directos": ("Gastos por beneficios a los empleados", "GAV DIRECTO"),
    "GPBE Indirectos": ("Gastos por beneficios a los empleados", "GAV INDIRECTO"),
    "OGPN Directos": ("Otros gastos por naturaleza", "GAV DIRECTO"),
    "OGPN Indirectos": ("Otros gastos por naturaleza", "GAV INDIRECTO"),
    "Finiquitos": ("Finiquitos", None),
    "Multas": ("Multas", None),
    "Provisión Obsolescencias": ("Provisión Obsolescencias Inventarios", None),
    "Provisión Incobrables": ("Provisión Incobrales", None),
    "Provisión Habilitación Oficinas": ("Provisión Habilitación Oficinas", None),
    "Depreciación": ("Gastos por depreciación y amortización", None),
    "Otros Ingresos por Función": ("Otros ingresos por función", None),
    "Ingreso Financiero": ("Ingreso financiero", None),
    "Costo Financiero": ("Costo financiero", None),
    "Otros Gastos por Función": ("Otros gastos por función", None),
    "Diferencia de Cambio": ("Diferencia de cambio", None),
}

# Prorrateo de GAV Indirecto de GEMCO por linea de negocio (ver
# validacion hecha en conversacion: suman 99.9999% ~ 100%)
PROPORCIONES_IND_GEMCO = {
    "Equipos Esterilización": 0.405631,
    "Consumibles Esterilización": 0.068991,
    "Equipos Dental": 0.053527,
    "Equipos Endoscopía": 0.396068,
    "Consumibles Endoscopía": 0.075782,
}

EMPRESAS_GEMCO_REAL = {"GEMCO", "Soporte Indirecto", "Ajustes Contables"}


def _redondear(v):
    """Redondea a entero (pesos) para no arrastrar decimales al JSON."""
    if v is None:
        return None
    return round(float(v))


# ──────────────────────────────────────────────────────────────────────
# CARGA DE DATOS BASE
# ──────────────────────────────────────────────────────────────────────

def cargar_base_real(archivo_v11):
    mapeo = cargar_mapeo_clasif()
    df_g = limpiar_gemco(pd.read_excel(archivo_v11, sheet_name="Diario GEMCO"))
    df_i = limpiar_incardia(pd.read_excel(archivo_v11, sheet_name="Diario Incardia"), mapeo)
    df_m = limpiar_mmq(pd.read_excel(archivo_v11, sheet_name="Diario MMQ"), mapeo)
    df_t = limpiar_tecservice(pd.read_excel(archivo_v11, sheet_name="Diario Tecservice"), mapeo)
    return consolidar(df_g, df_i, df_m, df_t)


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 1: GRID PRINCIPAL (Real y Ppto, Consolidado + 4 empresas)
# ──────────────────────────────────────────────────────────────────────

def generar_grid_real(base):
    """
    { "Consolidado": {"1": {concepto: valor, ...}, "2": {...}, ...},
      "GEMCO": {...}, "Incardia": {...}, "MMQ": {...}, "Tecservice": {...} }
    Meses sin transacciones (6-12) devuelven 0 desde calcular_eerr - se
    mantiene asi (no se fuerza a null) porque calcular_eerr ya maneja
    bien la ausencia de datos internamente (suma vacia = 0).

    El bloque "MMQ" aqui representa siempre el valor PONDERADO (factor
    0.75/0.875 aplicado) - es el que se usa cuando MMQ se combina con
    otra empresa o con el consolidado. El caso "MMQ es la unica empresa
    activa" (100%, sin factor) vive aparte en generar_mmq_100_real().
    """
    resultado = {}
    alcances = {"Consolidado": None, **{e: [e] for e in EMPRESAS}}
    for nombre_alcance, empresas_param in alcances.items():
        resultado[nombre_alcance] = {}
        forzado = True if nombre_alcance == "MMQ" else None
        for mes in MESES_NUM:
            r = calcular_eerr(base, mes=mes, empresas=empresas_param, factor_mmq_forzado=forzado)
            resultado[nombre_alcance][str(mes)] = {
                concepto: _redondear(r[KEY_REAL[concepto]])
                for concepto, _, tipo in ESTRUCTURA_EERR
                if tipo != "porcentaje"
            }
            # Porcentajes calculados aparte (no vienen en calcular_eerr)
            ing = r["Ingresos"]
            resultado[nombre_alcance][str(mes)]["% Margen"] = (
                round(r["Margen Bruto"] / ing * 100, 2) if ing else None
            )
            resultado[nombre_alcance][str(mes)]["% EBITDA"] = (
                round(r["EBITDA Directo"] / ing * 100, 2) if ing else None
            )
            resultado[nombre_alcance][str(mes)]["% EBITDA Empresa"] = (
                round(r["EBITDA Empresa"] / ing * 100, 2) if ing else None
            )
    return resultado


def generar_mmq_100_real(base):
    """
    Bloque MMQ al 100% (SIN factor de participacion 0.75/0.875), para el
    caso en que MMQ es la UNICA empresa activa en el selector del panel.
    Misma forma que grid_real["MMQ"]: {"1": {concepto: valor, ...}, ...}.
    """
    resultado = {}
    for mes in MESES_NUM:
        r = calcular_eerr(base, mes=mes, empresas=["MMQ"], factor_mmq_forzado=False)
        resultado[str(mes)] = {
            concepto: _redondear(r[KEY_REAL[concepto]])
            for concepto, _, tipo in ESTRUCTURA_EERR
            if tipo != "porcentaje"
        }
        ing = r["Ingresos"]
        resultado[str(mes)]["% Margen"] = (
            round(r["Margen Bruto"] / ing * 100, 2) if ing else None
        )
        resultado[str(mes)]["% EBITDA"] = (
            round(r["EBITDA Directo"] / ing * 100, 2) if ing else None
        )
        resultado[str(mes)]["% EBITDA Empresa"] = (
            round(r["EBITDA Empresa"] / ing * 100, 2) if ing else None
        )
    return resultado


def generar_grid_ppto(full_ppto):
    resultado = {}
    alcances = {
        "Consolidado": {},
        "GEMCO": {"empresa": "GEMCO"},
        "Incardia": {"empresa": "Incardia"},
        "MMQ": {"empresa": "MMQ"},
        "Tecservice": {"empresa": "Tecservice"},
    }
    for nombre_alcance, kwargs in alcances.items():
        resultado[nombre_alcance] = {}
        for mes in MESES_NUM:
            mes_nombre = MESES_NOMBRE[mes]
            r = calcular_eerr_ppto(full_ppto, mes_nombre, **kwargs)
            resultado[nombre_alcance][str(mes)] = {
                concepto: _redondear(r[KEY_PPTO[concepto]])
                for concepto, _, tipo in ESTRUCTURA_EERR
                if tipo != "porcentaje"
            }
            ing = r["Ingresos"]
            resultado[nombre_alcance][str(mes)]["% Margen"] = (
                round(r["Margen Bruto"] / ing * 100, 2) if ing else None
            )
            resultado[nombre_alcance][str(mes)]["% EBITDA"] = (
                round(r["EBITDA Directo"] / ing * 100, 2) if ing else None
            )
            resultado[nombre_alcance][str(mes)]["% EBITDA Empresa"] = (
                round(r["EBITDA Empresa"] / ing * 100, 2) if ing else None
            )
    return resultado


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 2: DRILL-DOWN NIVEL 1 (Empresa) - REAL
# ──────────────────────────────────────────────────────────────────────

def generar_drilldown_empresa_real(base):
    """
    Para cada concepto con drill-down, y cada mes, el desglose por
    empresa (GEMCO/Incardia/MMQ/Tecservice).

    El valor de MMQ aqui es siempre el PONDERADO (factor 0.75/0.875
    aplicado) - esta fila se muestra dentro de Consolidado o de una
    combinacion con otra empresa, nunca con MMQ aislado (ese caso usa
    generar_mmq_100_real() desde app.js). Atribucion GEMCO/Tecservice ya
    corregida en limpiar_gemco.
    """
    resultado = {}
    for concepto in DRILL_DOWN_FILTROS:
        resultado[concepto] = {}
        for mes in MESES_NUM:
            fila = {}
            for empresa in EMPRESAS:
                forzado = True if empresa == "MMQ" else None
                r = calcular_eerr(base, mes=mes, empresas=[empresa], factor_mmq_forzado=forzado)
                fila[empresa] = _redondear(r[KEY_REAL[concepto]])
            resultado[concepto][str(mes)] = fila
    return resultado


def generar_drilldown_empresa_ppto(full_ppto):
    resultado = {}
    for concepto in DRILL_DOWN_FILTROS_PPTO:
        resultado[concepto] = {}
        for mes in MESES_NUM:
            mes_nombre = MESES_NOMBRE[mes]
            fila = {}
            for empresa in EMPRESAS:
                r = calcular_eerr_ppto(full_ppto, mes_nombre, empresa=empresa)
                fila[empresa] = _redondear(r[KEY_PPTO[concepto]])
            resultado[concepto][str(mes)] = fila
    return resultado


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 3: DRILL-DOWN NIVEL 2 (Linea de Negocio) - REAL
# ──────────────────────────────────────────────────────────────────────

def _filtrar_transacciones_real(base, concepto, mes, empresa):
    nombre_eerr, gav = DRILL_DOWN_FILTROS[concepto]
    m = (base["Nombre en EERR"] == nombre_eerr) & (base["Fecha"].dt.month == mes)
    if gav is not None:
        m = m & (base["GAV"] == gav)
    if empresa == "GEMCO":
        m = m & (base["Empresa_Comercial"].isin(EMPRESAS_GEMCO_REAL))
    else:
        m = m & (base["Empresa_Comercial"] == empresa)
    return base[m]


def generar_drilldown_linea_real(base):
    """
    concepto -> empresa -> mes -> {linea_negocio: valor}

    CASO ESPECIAL: GPBE Indirectos / OGPN Indirectos bajo GEMCO usan el
    prorrateo de PROPORCIONES_IND_GEMCO en vez de agrupar transacciones
    reales (que en su mayoria no tienen linea asignada, ya que el GAV
    Indirecto se registra bajo Soporte Indirecto sin distincion de linea).
    """
    resultado = {}
    factor_mmq = {m: (0.75 if m <= 3 else 0.875) for m in MESES_NUM}

    for concepto in DRILL_DOWN_FILTROS:
        resultado[concepto] = {}
        for empresa in EMPRESAS:
            resultado[concepto][empresa] = {}
            for mes in MESES_NUM:
                if empresa == "GEMCO" and concepto in ("GPBE Indirectos", "OGPN Indirectos"):
                    nombre_eerr, gav = DRILL_DOWN_FILTROS[concepto]
                    m = (
                        (base["Nombre en EERR"] == nombre_eerr) &
                        (base["GAV"] == gav) &
                        (base["Empresa_Comercial"].isin(EMPRESAS_GEMCO_REAL)) &
                        (base["Fecha"].dt.month == mes)
                    )
                    total_indirecto = base[m]["Cargo/abono (ML)"].sum() * -1
                    fila = {
                        linea: _redondear(total_indirecto * prop)
                        for linea, prop in PROPORCIONES_IND_GEMCO.items()
                    }
                else:
                    trans = _filtrar_transacciones_real(base, concepto, mes, empresa)
                    factor = factor_mmq[mes] if empresa == "MMQ" else 1.0
                    agrupado = (
                        trans.groupby("Linea_Negocio")["Cargo/abono (ML)"].sum() * -1 * factor
                    )
                    fila = {k: _redondear(v) for k, v in agrupado.items()}
                resultado[concepto][empresa][str(mes)] = fila
    return resultado


def generar_mmq_100_linea_real(base):
    """
    concepto -> mes -> {linea_negocio: valor}, MMQ al 100% (SIN factor de
    participacion), para cuando MMQ es la unica empresa activa en el
    selector. Analogo a generar_drilldown_linea_real() pero factor=1.0
    siempre (ese ya aplica el factor siempre, para el caso combinado).
    """
    resultado = {}
    for concepto in DRILL_DOWN_FILTROS:
        resultado[concepto] = {}
        for mes in MESES_NUM:
            trans = _filtrar_transacciones_real(base, concepto, mes, "MMQ")
            agrupado = trans.groupby("Linea_Negocio")["Cargo/abono (ML)"].sum() * -1
            resultado[concepto][str(mes)] = {k: _redondear(v) for k, v in agrupado.items()}
    return resultado


def generar_drilldown_linea_ppto(full_ppto):
    """Analogo, para Presupuesto. Sin caso especial de prorrateo (el
    Ppto no distingue GAV Indirecto por linea de GEMCO de forma distinta
    - ya viene con su propia Linea_Negocio real por cuenta)."""
    resultado = {}
    for concepto, (concepto_padre, gav) in DRILL_DOWN_FILTROS_PPTO.items():
        resultado[concepto] = {}
        for empresa in EMPRESAS:
            resultado[concepto][empresa] = {}
            for mes in MESES_NUM:
                mes_nombre = MESES_NOMBRE[mes]
                m = (
                    (full_ppto["Mes"] == mes_nombre) &
                    (full_ppto["Nivel"] == "Linea") &
                    (full_ppto["Concepto_Padre"] == concepto_padre) &
                    (full_ppto["Empresa_Comercial"] == empresa)
                )
                if gav is not None:
                    m = m & (full_ppto["GAV"] == gav)
                sub = full_ppto[m]
                agrupado = sub.groupby("Linea_Negocio")["Monto_Presupuesto"].sum() * 1e6
                fila = {k: _redondear(v) for k, v in agrupado.items()}
                resultado[concepto][empresa][str(mes)] = fila
    return resultado


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 4: EERR POR LINEA DE NEGOCIO (hoja "Lineas") - REAL
# ──────────────────────────────────────────────────────────────────────
#
# Van en un archivo aparte (docs/datos_lineas.json), no en el JSON principal.
# Bloques, todos sobre la base expandida de asignar_lineas():
#   lineas_real        linea -> periodo -> {concepto: valor}
#   lineas_total_real  periodo -> {concepto: valor}   (suma de las lineas)
#   lineas_drill_real  concepto -> linea -> periodo -> {clave centro: valor}
#   lineas_centros     {clave centro: etiqueta}  ("601" -> "601 Finanzas...")
#   lineas_prorrateo   {linea: pct}  (data/rules/prorrateo_lineas.csv)
#   lineas_centros_prorrateados  [clave centro, ...]  (regla PRORRATEO)
#
# periodo = "1".."12" (igual que los demas bloques) mas "Acumulado", que
# es la suma de los meses de meta.meses_con_real.
#
# REDONDEO: los valores van en pesos enteros, como el resto del JSON, pero
# redondear cada linea por separado deja diferencias de unos pocos pesos
# contra el consolidado. Por eso se redondea "cuadrando" (ver _cuadrar):
# las lineas suman exactamente el consolidado del JSON, y los centros del
# drill suman exactamente el valor de su linea. Ningun valor se mueve mas
# de un par de pesos respecto de su valor exacto.

PERIODO_ACUM = "Acumulado"
CONCEPTOS_VALOR = [c for c, _, tipo in ESTRUCTURA_EERR if tipo != "porcentaje"]

# Diferencia maxima aceptable (pesos) entre la suma exacta de las partes y
# el total al que se cuadran. Algo mayor significa que las partes no
# representan al total (p. ej. filas en una linea que no se esta sumando).
_TOLERANCIA_CUADRE = 2.0


def _porcentajes(ingresos, margen, ebitda, ebitda_empresa):
    """Los 3 porcentajes del EERR, con el mismo criterio que el grid."""
    return {
        "% Margen": round(margen / ingresos * 100, 2) if ingresos else None,
        "% EBITDA": round(ebitda / ingresos * 100, 2) if ingresos else None,
        "% EBITDA Empresa": (
            round(ebitda_empresa / ingresos * 100, 2) if ingresos else None
        ),
    }


def _cuadrar(exactos, objetivo, contexto):
    """
    Redondea a pesos enteros un grupo de valores de modo que sumen
    exactamente `objetivo` (metodo del mayor resto): cada valor se
    redondea normalmente y los pesos que sobran o faltan se asignan, de a
    uno, a los valores que quedaron mas lejos de su redondeo.

    exactos: {clave: valor exacto}. objetivo: total entero ya publicado.
    Lanza ValueError si las partes no suman el objetivo (mas alla del
    redondeo): eso es un error de datos, no algo que corregir aqui.
    """
    desvio = sum(exactos.values()) - objetivo
    if abs(desvio) > _TOLERANCIA_CUADRE:
        raise ValueError(
            f"EERR por linea: las partes no suman el total en {contexto} "
            f"(suma={sum(exactos.values()):,.2f}, total={objetivo:,}, "
            f"diferencia={desvio:,.2f})."
        )

    redondeados = {k: round(v) for k, v in exactos.items()}
    falta = objetivo - sum(redondeados.values())
    if falta == 0:
        return redondeados
    if not redondeados:
        raise ValueError(
            f"EERR por linea: total {objetivo:,} sin partes en {contexto}."
        )

    paso = 1 if falta > 0 else -1
    # Primero los valores con monto (no crear un peso donde habia cero) y,
    # entre ellos, los que el redondeo dejo mas lejos en el sentido del ajuste.
    orden = sorted(
        exactos,
        key=lambda k: (exactos[k] == 0, -paso * (exactos[k] - redondeados[k])),
    )
    i = 0
    while falta != 0:
        redondeados[orden[i % len(orden)]] += paso
        falta -= paso
        i += 1
    return redondeados


def lineas_del_bloque(exp):
    """
    Lineas de Reporte que van en los bloques: las de las reglas (en el
    orden de prorrateo_lineas.csv) y, solo si hay filas sin regla de
    centro de costo, tambien "Sin asignar" (asi la suma sigue calzando
    con el consolidado y el problema queda a la vista).
    """
    lineas = lineas_reporte()
    if (exp["Linea_Reporte"] == SIN_ASIGNAR).any():
        print(f"  ATENCION: hay filas en la linea '{SIN_ASIGNAR}' (centro de "
              "costo sin regla). Correr detectar_cuentas_nuevas.py y "
              "completar data/rules/centro_linea.csv.")
        lineas = lineas + [SIN_ASIGNAR]
    return lineas


def generar_lineas_real(exp, grid_real, meses_con_real, lineas):
    """
    linea -> periodo -> {concepto: valor}. Misma forma que grid_real[alcance]
    mas el periodo "Acumulado".

    Cada valor sale de calcular_eerr(..., lineas=[linea]) sobre la base
    expandida. La linea MMQ queda PONDERADA igual que en el consolidado
    (factor 0.75/0.875 sobre el diario MMQ; el centro 205 de GEMCO al 100%).
    """
    # Subconjunto por linea, para no filtrar la base completa en cada llamada
    exp_por_linea = {l: exp[exp["Linea_Reporte"] == l] for l in lineas}

    resultado = {l: {} for l in lineas}
    for mes in MESES_NUM:
        exactos = {
            l: calcular_eerr(exp_por_linea[l], mes=mes, lineas=[l])
            for l in lineas
        }
        fila = {l: {} for l in lineas}
        for concepto in CONCEPTOS_VALOR:
            cuadrado = _cuadrar(
                {l: exactos[l][KEY_REAL[concepto]] for l in lineas},
                grid_real["Consolidado"][str(mes)][concepto],
                f"{concepto}, mes {mes} (lineas vs consolidado)",
            )
            for l in lineas:
                fila[l][concepto] = cuadrado[l]
        for l in lineas:
            r = exactos[l]
            fila[l].update(_porcentajes(
                r["Ingresos"], r["Margen Bruto"],
                r["EBITDA Directo"], r["EBITDA Empresa"],
            ))
            resultado[l][str(mes)] = fila[l]

    for l in lineas:
        acum = {
            concepto: sum(resultado[l][str(m)][concepto] for m in meses_con_real)
            for concepto in CONCEPTOS_VALOR
        }
        acum.update(_porcentajes(
            acum["Ingresos"], acum["Margen Bruto"],
            acum["EBITDA Directo"], acum["EBITDA Empresa"],
        ))
        resultado[l][PERIODO_ACUM] = acum
    return resultado


def generar_lineas_total_real(lineas_real):
    """periodo -> {concepto: valor}: suma de todas las lineas. Es el
    control de la hoja "Lineas": debe ser igual al consolidado."""
    resultado = {}
    periodos = list(next(iter(lineas_real.values())).keys())
    for periodo in periodos:
        total = {
            concepto: sum(por_periodo[periodo][concepto]
                          for por_periodo in lineas_real.values())
            for concepto in CONCEPTOS_VALOR
        }
        total.update(_porcentajes(
            total["Ingresos"], total["Margen Bruto"],
            total["EBITDA Directo"], total["EBITDA Empresa"],
        ))
        resultado[periodo] = total
    return resultado


def _centros_origen(exp):
    """
    Centro de origen de cada fila de la base expandida.

    Retorna (clave, catalogo):
    - clave: Series con la clave corta del centro por fila. Diario GEMCO:
      el codigo del centro de costo ("601"). Diarios propios: la empresa
      ("Incardia", "MMQ", "Tecservice").
    - catalogo: {clave: etiqueta para mostrar}, p. ej.
      {"601": "601 Finanzas y Contabilidad", "Incardia": "Incardia"}.
    """
    es_propio = exp["Empresa"].isin(LINEA_POR_EMPRESA)
    cod = exp["Cod_Unidad"].astype("string").fillna("s/c").astype(object)
    clave = exp["Empresa"].where(es_propio, cod).astype(object)

    catalogo = {}
    if "Nombre Unidad" in exp.columns:
        nombre = exp["Nombre Unidad"].fillna("").astype(str).str.strip()
        # Un solo nombre por codigo (el mas frecuente), por si el Diario
        # trae el mismo centro escrito de dos formas.
        canonico = nombre[~es_propio].groupby(cod[~es_propio]).agg(
            lambda s: s.value_counts().index[0]
        )
        catalogo = {c: f"{c} {n}".strip() for c, n in canonico.items()}
    for c in sorted(cod[~es_propio].unique()):
        catalogo.setdefault(c, c)
    catalogo = dict(sorted(catalogo.items()))
    for empresa in sorted(exp.loc[es_propio, "Empresa"].unique()):
        catalogo[empresa] = empresa
    return clave, catalogo


def generar_lineas_drill_real(exp, lineas_real, meses_con_real, lineas):
    """
    Retorna (drill, centros):
      drill:   concepto -> linea -> periodo -> {clave de centro: valor}
      centros: {clave de centro: etiqueta}  (bloque "lineas_centros")

    Desglosa cada valor de lineas_real por centro de origen, incluidas las
    filas que llegan por prorrateo (con su centro original). La suma de
    los centros es exactamente el valor de la linea.

    FORMATO COMPACTO (para no inflar el JSON, sin perder trazabilidad):
    - Los centros van por su clave corta ("601"); codigo y nombre estan
      una sola vez en `centros` ("601" -> "601 Finanzas y Contabilidad").
    - Se omiten los centros con valor 0.
    """
    clave_centro, centros = _centros_origen(exp)
    df = exp.assign(_centro=clave_centro, _mes=exp["Fecha"].dt.month)
    df = df[df["Linea_Reporte"].isin(lineas)]

    # (linea, mes) -> {centro: resultado de calcular_eerr}
    exactos = {}
    for (linea, mes, centro), grupo in df.groupby(
            ["Linea_Reporte", "_mes", "_centro"], sort=True):
        exactos.setdefault((linea, int(mes)), {})[centro] = calcular_eerr(
            grupo, mes=int(mes)
        )

    resultado = {}
    for concepto in CONCEPTOS_VALOR:
        clave = KEY_REAL[concepto]
        resultado[concepto] = {}
        for linea in lineas:
            por_periodo = {}
            for mes in MESES_NUM:
                por_centro = {
                    centro: r[clave]
                    for centro, r in exactos.get((linea, mes), {}).items()
                    if r[clave] != 0
                }
                cuadrado = _cuadrar(
                    por_centro,
                    lineas_real[linea][str(mes)][concepto],
                    f"{concepto}, {linea}, mes {mes} (centros vs linea)",
                )
                por_periodo[str(mes)] = {c: v for c, v in cuadrado.items() if v != 0}

            acum = {}
            for mes in meses_con_real:
                for centro, v in por_periodo[str(mes)].items():
                    acum[centro] = acum.get(centro, 0) + v
            por_periodo[PERIODO_ACUM] = {
                c: acum[c] for c in sorted(acum) if acum[c] != 0
            }
            resultado[concepto][linea] = por_periodo
    return resultado, centros


def generar_reglas_prorrateo():
    """
    Retorna (prorrateo, centros_prorrateados) para mostrar en la hoja:
      prorrateo: {linea: pct}, tal cual data/rules/prorrateo_lineas.csv.
      centros_prorrateados: claves de centro ("601") con regla PRORRATEO
        en data/rules/centro_linea.csv.
    """
    centros = sorted(
        str(cod) for cod, linea in cargar_centro_linea().items()
        if linea == PRORRATEO
    )
    return cargar_prorrateo(), centros


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 5: CURVAS J (hoja "Curvas J") - REAL vs PRESUPUESTO POR LINEA
# ──────────────────────────────────────────────────────────────────────
#
# Bloque "curvas_j" de docs/datos_lineas.json: Resultado del Ejercicio
# MENSUAL por linea, Presupuesto (12 meses) y Real (meses con Real), en
# pesos. Los acumulados los calcula el panel. Toda la logica esta en
# calculo/curvas_j.py; aqui solo se le entregan los bloques ya generados.

def generar_curvas_j(archivo_ppto, lineas_real, grid_real, grid_ppto,
                     meses_con_real):
    """
    Retorna (curvas_j, controles). Lanza ValueError (y no se escribe
    ningun JSON) si falla alguno de los controles de calculo/curvas_j.py.
    """
    ppto = leer_presupuesto(archivo_ppto)
    curvas_j = construir_curvas_j(ppto["lineas"], lineas_real, meses_con_real)
    controles = controlar_curvas_j(
        curvas_j,
        ppto_consolidado={
            m: grid_ppto["Consolidado"][m][CONCEPTO_REAL]
            for m in curvas_j["meses"]
        },
        tecservice_consolidado=ppto["tecservice_consolidado"],
        real_consolidado={
            m: grid_real["Consolidado"][m][CONCEPTO_REAL]
            for m in curvas_j["meses"]
        },
    )
    return curvas_j, controles


# ──────────────────────────────────────────────────────────────────────
# BLOQUE 6: PRESUPUESTO POR LINEA (hoja "Lineas", vista Detalle por linea)
# ──────────────────────────────────────────────────────────────────────
#
# Bloque "lineas_ppto" de docs/datos_lineas.json:
#   linea -> "1".."12" -> {concepto: valor}   (pesos enteros, 29 conceptos)
# Las 8 lineas con presupuesto (Consumibles Dental no tiene). El total no va
# aqui: el panel usa ppto.Consolidado de datos_eerr.json. Las lineas se
# redondean "cuadrando" (_cuadrar) para que sumen EXACTAMENTE ese total.

def generar_lineas_ppto(full_ppto, archivo_ppto, grid_ppto, curvas_j):
    """Retorna (lineas_ppto, controles). Lanza ValueError (y no se escribe
    ningun JSON) si falla alguno de los controles de calculo/ppto_lineas.py."""
    claves = {c: KEY_PPTO[c] for c in CONCEPTOS_VALOR}
    exactos = presupuesto_exacto(full_ppto, claves)
    lineas = list(exactos)
    resultado = {l: {} for l in lineas}
    for mes in MESES_NUM:
        m = str(mes)
        fila = {l: {} for l in lineas}
        for concepto in CONCEPTOS_VALOR:
            cuadrado = _cuadrar(
                {l: exactos[l][m][concepto] for l in lineas},
                grid_ppto["Consolidado"][m][concepto],
                f"Presupuesto {concepto}, mes {mes} (lineas vs consolidado)",
            )
            for l in lineas:
                fila[l][concepto] = cuadrado[l]
        for l in lineas:
            resultado[l][m] = fila[l]
    controles = controlar_lineas_ppto(
        resultado, grid_ppto["Consolidado"], curvas_j, leer_hojas_ppto(archivo_ppto),
    )
    return resultado, controles


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    print("Cargando base Real (V11.xlsx)...")
    base = cargar_base_real(ARCHIVO_V11)

    # Meses con datos Real disponibles, detectados directamente desde la
    # base (evita tener que editar esta lista a mano cada vez que llega
    # un mes nuevo).
    meses_con_real = sorted(base["Fecha"].dt.month.dropna().unique().tolist())
    meses_con_real = [int(m) for m in meses_con_real]

    print("Cargando base Presupuesto (PPTO_V2.xlsx)...")
    full_ppto = cargar_presupuesto_completo(ARCHIVO_PPTO)

    print("Generando grid principal Real...")
    grid_real = generar_grid_real(base)

    print("Generando grid principal Presupuesto...")
    grid_ppto = generar_grid_ppto(full_ppto)

    print("Generando drill-down nivel 1 (Empresa) Real...")
    dd_emp_real = generar_drilldown_empresa_real(base)

    print("Generando drill-down nivel 1 (Empresa) Presupuesto...")
    dd_emp_ppto = generar_drilldown_empresa_ppto(full_ppto)

    print("Generando drill-down nivel 2 (Linea) Real...")
    dd_lin_real = generar_drilldown_linea_real(base)

    print("Generando drill-down nivel 2 (Linea) Presupuesto...")
    dd_lin_ppto = generar_drilldown_linea_ppto(full_ppto)

    print("Generando bloque MMQ 100% (empresa unica seleccionada)...")
    mmq_100_real = generar_mmq_100_real(base)
    mmq_100_linea_real = generar_mmq_100_linea_real(base)

    print("Generando EERR por Linea de Negocio (Real)...")
    exp = asignar_lineas(base)
    lineas = lineas_del_bloque(exp)
    lineas_real = generar_lineas_real(exp, grid_real, meses_con_real, lineas)
    lineas_total_real = generar_lineas_total_real(lineas_real)
    lineas_drill_real, lineas_centros = generar_lineas_drill_real(
        exp, lineas_real, meses_con_real, lineas
    )
    lineas_prorrateo, lineas_centros_prorrateados = generar_reglas_prorrateo()

    print("Generando Curvas J (Resultado del Ejercicio, Real vs Presupuesto)...")
    curvas_j, controles_cj = generar_curvas_j(
        ARCHIVO_PPTO, lineas_real, grid_real, grid_ppto, meses_con_real
    )
    print("  Controles (diferencia maxima observada, en pesos):")
    print(f"    Presupuesto 8 lineas vs consolidado, por mes : "
          f"{controles_cj['ppto_vs_consolidado']:,.0f}")
    print(f"    TECSERVICE anual vs 'TECSERVICE Consolidado' : "
          f"{controles_cj['tecservice_vs_pln']:,.0f}")
    print(f"    Real 8 lineas + excluidas vs consolidado     : "
          f"{controles_cj['real_vs_consolidado']:,.0f}")

    print("Generando presupuesto por linea (hoja Lineas, vista Detalle)...")
    lineas_ppto, controles_lp = generar_lineas_ppto(
        full_ppto, ARCHIVO_PPTO, grid_ppto, curvas_j
    )
    print("  Controles (diferencia maxima observada, en pesos):")
    print(f"    Suma 8 lineas vs ppto consolidado (exacto)   : "
          f"{controles_lp['suma_vs_consolidado']:,.0f}")
    print(f"    Resultado del Ejercicio vs curvas J          : "
          f"{controles_lp['resultado_vs_curvas']:,.0f}")
    print(f"    Cada linea vs sus hojas del PPTO V2          : "
          f"{controles_lp['lineas_vs_hojas']:,.2f}")

    salida = {
        "meta": {
            "meses_con_real": meses_con_real,
        },
        "meses_nombre": MESES_NOMBRE,
        "estructura_eerr": ESTRUCTURA_EERR,
        "empresas": EMPRESAS,
        "conceptos_con_drilldown": list(DRILL_DOWN_FILTROS.keys()),
        "real": grid_real,
        "ppto": grid_ppto,
        "drilldown_empresa_real": dd_emp_real,
        "drilldown_empresa_ppto": dd_emp_ppto,
        "drilldown_linea_real": dd_lin_real,
        "drilldown_linea_ppto": dd_lin_ppto,
        "mmq_100_real": mmq_100_real,
        "mmq_100_linea_real": mmq_100_linea_real,
    }

    salida_lineas = {
        "lineas_real": lineas_real,
        "lineas_total_real": lineas_total_real,
        "lineas_drill_real": lineas_drill_real,
        "lineas_centros": lineas_centros,
        "lineas_prorrateo": lineas_prorrateo,
        "lineas_centros_prorrateados": lineas_centros_prorrateados,
        "curvas_j": curvas_j,
        "lineas_ppto": lineas_ppto,
    }

    Path(SALIDA_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    with open(SALIDA_JSON_LINEAS, "w", encoding="utf-8") as f:
        json.dump(salida_lineas, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nListo. JSON generado en: {SALIDA_JSON}")
    print(f"Tamaño: {Path(SALIDA_JSON).stat().st_size / 1024:.1f} KB")
    print(f"JSON de lineas generado en: {SALIDA_JSON_LINEAS}")
    print(f"Tamaño: {Path(SALIDA_JSON_LINEAS).stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
