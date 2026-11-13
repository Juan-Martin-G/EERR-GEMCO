"""
calculo/ppto_lineas.py
======================
Presupuesto (PPTO V2) por concepto y linea de negocio, para la vista
"Detalle por linea" de la hoja "Lineas" del panel.

Cada linea se arma con el mismo cargador y la misma formula del presupuesto
que ya usa el panel (cargar_presupuesto_completo + calcular_eerr_ppto),
filtrando las filas de nivel "Linea":

  MMQ, Incardia   empresa = la linea (hoja de la linea + sus ingresos y
                  costos de la hoja Ing-Costos)
  TECSERVICE      empresa Tecservice + Trazabilidad + Mantencion y
                  Reparacion de Esterilizacion, Dental y Endoscopia
                  (= hojas TECSERVICE + SS + Reas + Trazabilidad)
  lineas GEMCO    Linea_Negocio = la linea

Consumibles Dental no tiene presupuesto. El "Total consolidado" no se arma
aqui: es el presupuesto consolidado del panel (bloque ppto.Consolidado).

Controles (controlar_lineas_ppto), que abortan la generacion si fallan:
  (a) por mes y concepto, la suma de las 8 lineas es EXACTAMENTE el
      presupuesto consolidado publicado;
  (b) Resultado del Ejercicio por linea y mes = bloque curvas_j (<= 1 peso);
  (c) cada linea, concepto y mes = sus hojas del PPTO V2 (<= 0,5 M).
Ademas, presupuesto_exacto() falla si alguna fila de nivel "Linea" del
presupuesto no cae en exactamente una linea (p. ej. una linea nueva).
"""

import openpyxl

from calculo.eerr_presupuesto import calcular_eerr_ppto
from calculo.curvas_j import (
    HOJAS_POR_LINEA, MESES_PPTO, MILLON, ENCABEZADO_ETIQUETAS,
    _columna_unica, _filas, _texto,
)

MESES = [str(m) for m in range(1, 13)]

# Linea del panel -> filtros de calcular_eerr_ppto (se suman). El orden es
# el de las columnas de la hoja Lineas.
TECSERVICE_LINEAS_GEMCO = [
    "Trazabilidad",
    "Mantención Esterilización", "Mantención Dental", "Mantención Endoscopía",
    "Reparación Esterilización", "Reparación Dental", "Reparación Endoscopía",
]
FILTROS = {
    "MMQ": [{"empresa": "MMQ"}],
    "Incardia": [{"empresa": "Incardia"}],
    "Equipos Esterilización": [{"linea_negocio": "Equipos Esterilización"}],
    "Consumibles Esterilización": [{"linea_negocio": "Consumibles Esterilización"}],
    "Equipos Endoscopía": [{"linea_negocio": "Equipos Endoscopía"}],
    "Consumibles Endoscopía": [{"linea_negocio": "Consumibles Endoscopía"}],
    "Equipos Dental": [{"linea_negocio": "Equipos Dental"}],
    "TECSERVICE": [{"empresa": "Tecservice"}]
                  + [{"linea_negocio": l} for l in TECSERVICE_LINEAS_GEMCO],
}
LINEAS = list(FILTROS)

# Concepto del panel -> etiqueta(s) de fila en las hojas de linea del PPTO V2
# (se suman). GPBE Total y OGPN Total no son filas de la hoja.
FILAS_HOJA = {
    "Ingresos": ["Ingresos de actividades ordinarias"],
    "Costo de ventas": ["Costo de explotación"],
    "Margen Bruto": ["MARGEN DEL PRODUCTO"],
    "GPBE Directos": ["Gastos por beneficios a los empleados Directos"],
    "GPBE Indirectos": ["Gastos por beneficios a los empleados Indirectos"],
    "GPBE Total": ["Gastos por beneficios a los empleados Directos",
                   "Gastos por beneficios a los empleados Indirectos"],
    "OGPN Directos": ["Otros gastos por naturaleza Directos"],
    "OGPN Indirectos": ["Otros gastos por naturaleza Indirectos"],
    "OGPN Total": ["Otros gastos por naturaleza Directos",
                   "Otros gastos por naturaleza Indirectos"],
    "Subtotal GAV": ["Subtotal"],
    "EBITDA Directo": ["EBITDA"],
    "Finiquitos": ["Finiquitos"],
    "Multas": ["Multas"],
    "Provisión Obsolescencias": ["Provisión Obsolescencias Inventarios"],
    "Provisión Incobrables": ["Provisión Incobrales"],
    "Provisión Habilitación Oficinas": ["Provisión Habilitación Oficinas"],
    "Gastos Adicionales": ["Total Gastos Adicionales"],
    "EBITDA Empresa": ["EBITDA EMPRESA"],
    "Depreciación": ["Gastos por depreciación y amortización"],
    "Resultado Operacional": ["Resultado Operacional"],
    "Otros Ingresos por Función": ["Otros ingresos por función"],
    "Ingreso Financiero": ["Ingresos financieros"],
    "Costo Financiero": ["Costo financiero"],
    "Otros Gastos por Función": ["Otros gastos por función"],
    "Diferencia de Cambio": ["Diferencia de cambio"],
    "Resultado No Operacional": ["Resultado no operacional"],
    "Resultado antes Impuestos": ["Resultado antes de impuestos"],
    "Impuesto a la Renta": ["Impuesto a la renta"],
    "Resultado del Ejercicio": ["Resultado del ejercicio Empresa"],
}

CONCEPTO_RESULTADO = "Resultado del Ejercicio"

# Tolerancias de los controles, en pesos.
TOLERANCIA_CURVAS_J = 1
TOLERANCIA_HOJAS = 500_000      # 0,5 M


# ──────────────────────────────────────────────────────────────────────
# PRESUPUESTO POR LINEA (cargador del panel)
# ──────────────────────────────────────────────────────────────────────

def _controlar_cobertura(full):
    """Cada fila de nivel "Linea" del presupuesto debe caer en exactamente
    una linea del panel; si no, Σ lineas no reconstruiria el consolidado."""
    lin = full[full["Nivel"] == "Linea"]
    cuenta = lin["Monto_Presupuesto"] * 0
    for filtros in FILTROS.values():
        for f in filtros:
            if "empresa" in f:
                cuenta = cuenta + (lin["Empresa_Comercial"] == f["empresa"])
            else:
                cuenta = cuenta + (lin["Linea_Negocio"] == f["linea_negocio"])
    malas = lin[cuenta != 1]
    if len(malas):
        resumen = (malas.assign(_lineas=cuenta[cuenta != 1])
                   .groupby(["Empresa_Comercial", "Linea_Negocio", "_lineas"], dropna=False)
                   ["Monto_Presupuesto"].sum())
        raise ValueError(
            "Presupuesto por linea: hay filas del presupuesto que no caen en "
            "exactamente una linea del panel (Empresa_Comercial, Linea_Negocio, "
            f"lineas en que cae -> monto en M$): {resumen.to_dict()}. Revisar "
            "FILTROS en calculo/ppto_lineas.py."
        )


def presupuesto_exacto(full, claves):
    """
    Presupuesto por linea, mes y concepto, SIN redondear (pesos).

    full:   salida de cargar_presupuesto_completo().
    claves: {concepto del panel: clave de calcular_eerr_ppto} (KEY_PPTO).
    Retorna {linea: {"1".."12": {concepto: valor}}}.
    """
    _controlar_cobertura(full)
    out = {}
    for linea, filtros in FILTROS.items():
        out[linea] = {}
        for i, mes in enumerate(MESES_PPTO):
            valores = dict.fromkeys(claves, 0.0)
            for f in filtros:
                r = calcular_eerr_ppto(full, mes, **f)
                for concepto, clave in claves.items():
                    valores[concepto] += r[clave]
            out[linea][MESES[i]] = valores
    return out


# ──────────────────────────────────────────────────────────────────────
# LECTURA DE LAS HOJAS DE LINEA (para el control c)
# ──────────────────────────────────────────────────────────────────────

def _leer_hoja(wb, hoja, etiquetas):
    """{etiqueta: [12 valores en millones]} de una hoja de linea. Cada
    etiqueta debe estar exactamente una vez; celdas vacias cuentan como 0."""
    filas = _filas(wb, hoja)
    i_enc = next((i for i, fila in enumerate(filas)
                  if {ENCABEZADO_ETIQUETAS, *MESES_PPTO} <= {_texto(v) for v in fila}), None)
    if i_enc is None:
        raise ValueError(f"Presupuesto por linea: la hoja '{hoja}' no tiene la "
                         "fila de encabezado con los meses.")
    enc = filas[i_enc]
    col_et = _columna_unica(enc, ENCABEZADO_ETIQUETAS, hoja)
    cols = [_columna_unica(enc, mes, hoja) for mes in MESES_PPTO]
    out = {}
    for etiqueta in etiquetas:
        cand = [f for f in filas[i_enc + 1:] if _texto(f[col_et]) == etiqueta]
        if len(cand) != 1:
            raise ValueError(f"Presupuesto por linea: en la hoja '{hoja}' la fila "
                             f"'{etiqueta}' esta {len(cand)} veces (se esperaba 1).")
        out[etiqueta] = [float(cand[0][j]) if isinstance(cand[0][j], (int, float))
                         and not isinstance(cand[0][j], bool) else 0.0 for j in cols]
    return out


def leer_hojas(archivo):
    """
    Presupuesto de cada linea leido directo de sus hojas del PPTO V2, para
    contrastar con el cargador. {linea: {"1".."12": {concepto: pesos}}}.
    TECSERVICE suma sus cuatro hojas.
    """
    etiquetas = sorted({e for es in FILAS_HOJA.values() for e in es})
    wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
    try:
        por_hoja = {h: _leer_hoja(wb, h, etiquetas)
                    for hs in HOJAS_POR_LINEA.values() for h in hs}
    finally:
        wb.close()
    return {
        linea: {
            MESES[m]: {
                concepto: sum(por_hoja[h][e][m] for h in hojas for e in FILAS_HOJA[concepto]) * MILLON
                for concepto in FILAS_HOJA
            }
            for m in range(12)
        }
        for linea, hojas in HOJAS_POR_LINEA.items()
    }


# ──────────────────────────────────────────────────────────────────────
# CONTROLES
# ──────────────────────────────────────────────────────────────────────

def controlar_lineas_ppto(lineas_ppto, ppto_consolidado, curvas_j, hojas):
    """
    Controles del bloque "lineas_ppto" (ya redondeado) antes de publicarlo.
    Lanza ValueError si alguno falla; si pasan, retorna las diferencias
    maximas observadas, en pesos:

      suma_vs_consolidado  (a) max |Σ 8 lineas - consolidado| (debe ser 0)
      resultado_vs_curvas  (b) max |Resultado del Ejercicio - curvas_j|
      lineas_vs_hojas      (c) max |linea - sus hojas del PPTO V2|

    ppto_consolidado: {"1".."12": {concepto: valor}} (ppto.Consolidado).
    curvas_j: bloque curvas_j (usa lineas[linea].ppto_mensual).
    hojas: leer_hojas(archivo), o None para omitir el control (c).
    """
    lineas = list(lineas_ppto)
    faltan = [l for l in LINEAS if l not in lineas]
    if faltan:
        raise ValueError(f"Presupuesto por linea: faltan las lineas {faltan}.")
    conceptos = list(lineas_ppto[lineas[0]][MESES[0]])

    # (a) exacto contra el consolidado publicado
    peor_a = 0
    for mes in MESES:
        for c in conceptos:
            suma = sum(lineas_ppto[l][mes][c] for l in lineas)
            dif = suma - ppto_consolidado[mes][c]
            if dif != 0:
                raise ValueError(
                    f"Presupuesto por linea: '{c}', mes {mes}: la suma de las lineas "
                    f"({suma:,}) no es igual al presupuesto consolidado "
                    f"({ppto_consolidado[mes][c]:,}); diferencia {dif:,} pesos."
                )
            peor_a = max(peor_a, abs(dif))

    # (b) Resultado del Ejercicio = curvas_j
    peor_b = 0
    for l in lineas:
        for i, mes in enumerate(MESES):
            dif = lineas_ppto[l][mes][CONCEPTO_RESULTADO] - curvas_j["lineas"][l]["ppto_mensual"][i]
            if abs(dif) > TOLERANCIA_CURVAS_J:
                raise ValueError(
                    f"Presupuesto por linea: Resultado del Ejercicio de {l}, mes {mes}, "
                    f"difiere en {dif:,} pesos del de las curvas J."
                )
            peor_b = max(peor_b, abs(dif))

    # (c) cada linea contra sus hojas
    peor_c = None
    if hojas is not None:
        peor_c = 0.0
        for l in lineas:
            for mes in MESES:
                for c in conceptos:
                    dif = lineas_ppto[l][mes][c] - hojas[l][mes][c]
                    if abs(dif) > TOLERANCIA_HOJAS:
                        raise ValueError(
                            f"Presupuesto por linea: '{c}' de {l}, mes {mes}: "
                            f"{lineas_ppto[l][mes][c]:,} vs {hojas[l][mes][c]:,.0f} en "
                            f"sus hojas {HOJAS_POR_LINEA[l]} (diferencia {dif:,.0f})."
                        )
                    peor_c = max(peor_c, abs(dif))

    return {"suma_vs_consolidado": peor_a, "resultado_vs_curvas": peor_b,
            "lineas_vs_hojas": peor_c}
