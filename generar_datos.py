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

Reutiliza EXACTAMENTE la misma logica ya validada en:
  - transformacion/diarios.py
  - transformacion/presupuesto.py
  - calculo/eerr.py
  - calculo/eerr_presupuesto.py
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
from calculo.eerr import calcular_eerr
from calculo.eerr_presupuesto import calcular_eerr_ppto

# ──────────────────────────────────────────────────────────────────────
# CONFIGURACION
# ──────────────────────────────────────────────────────────────────────

ARCHIVO_V11 = "data/raw/v8.xlsx"
ARCHIVO_PPTO = "data/raw/PPTO_V2.xlsx"
SALIDA_JSON = "docs/datos_eerr.json"

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
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    print("Cargando base Real (V11.xlsx)...")
    base = cargar_base_real(ARCHIVO_V11)

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

    salida = {
        "meta": {
            "meses_con_real": [1, 2, 3, 4, 5],  # ajustar cada vez que
                                                  # se agregue un mes nuevo
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

    Path(SALIDA_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA_JSON, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nListo. JSON generado en: {SALIDA_JSON}")
    print(f"Tamaño: {Path(SALIDA_JSON).stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
