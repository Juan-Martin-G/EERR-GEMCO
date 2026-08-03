"""
calculo/eerr.py
===============
Porta la lógica de la medida DAX 'Valor Real2 EERR' a Python.

Reglas de signo (validadas celda a celda contra Excel):
- GEMCO: ingresos son NEGATIVOS en BD → multiplicar × -1 para presentación.
- Incardia/MMQ/Tecservice: costos/gastos son NEGATIVOS en BD → × -1.
- Factor MMQ: 0.75 para meses 1-3, 0.875 desde mes 4.
- Costo financiero: excluir filas con GAV = 'No corresponde'.
- Finiquitos: excluir filas con Linea_Negocio = 'Sin clasificar' (contrapartidas banco).
"""

import pandas as pd

# Factor de participación MMQ por mes
FACTOR_MMQ = {m: 0.75 for m in range(1, 4)}
FACTOR_MMQ.update({m: 0.875 for m in range(4, 13)})

# Conceptos que son ingresos (el signo de presentación se invierte para GEMCO)
CONCEPTOS_INGRESO = {
    "Ingresos de actividades ordinarias",
    "Otros Ingresos por Función",
    "Ingreso Financiero",
}

# Empresas GEMCO (incluye soporte indirecto que viene del Diario GEMCO)
EMPRESAS_GEMCO = {"GEMCO", "Soporte Indirecto", "Ajustes Contables"}


def _factor_mmq(mes: int) -> float:
    return FACTOR_MMQ.get(mes, 0.875)


def _suma_concepto(df: pd.DataFrame, concepto: str,
                   mes: int | None = None,
                   excluir_gav_no_corresponde: bool = False,
                   excluir_sin_clasificar: bool = False,
                   factor_mmq_activo: bool = True) -> float:
    """
    Suma Cargo/abono (ML) para un concepto EERR dado,
    aplicando el factor MMQ correcto por mes (salvo que
    factor_mmq_activo=False, en cuyo caso MMQ se muestra al 100%).
    """
    mask = df["Nombre en EERR"] == concepto

    if mes is not None:
        mask = mask & (df["Fecha"].dt.month == mes)

    if excluir_gav_no_corresponde:
        mask = mask & (df["GAV"] != "No corresponde")

    if excluir_sin_clasificar:
        mask = mask & (df["Linea_Negocio"] != "Sin clasificar")

    sub = df[mask].copy()
    if sub.empty:
        return 0.0

    # Separar MMQ del resto
    es_mmq = sub["Empresa_Comercial"] == "MMQ"

    # No-MMQ: suma directa
    suma_no_mmq = sub[~es_mmq]["Cargo/abono (ML)"].sum()

    if not factor_mmq_activo:
        # MMQ aislado (unica empresa seleccionada): mostrar al 100%,
        # sin la ponderacion de participacion de GEMCO.
        suma_mmq = sub[es_mmq]["Cargo/abono (ML)"].sum()
    elif mes is not None:
        factor = _factor_mmq(mes)
        suma_mmq = sub[es_mmq]["Cargo/abono (ML)"].sum() * factor
    else:
        # Sin filtro de mes: agrupar por mes y aplicar factor
        mmq_sub = sub[es_mmq].copy()
        if mmq_sub.empty:
            suma_mmq = 0.0
        else:
            mmq_sub["factor"] = mmq_sub["Fecha"].dt.month.map(_factor_mmq)
            suma_mmq = (mmq_sub["Cargo/abono (ML)"] * mmq_sub["factor"]).sum()

    return suma_no_mmq + suma_mmq


def _presentacion(suma_raw: float) -> float:
    """
    Convierte el valor crudo de BD a valor de presentación (× -1).
    Funciona para todos porque el modelo consolidado unifica la convención:
    - GEMCO: ingresos negativos en BD → × -1 → positivos en presentación
    - Incardia/MMQ/Tec: costos negativos en BD → × -1 → negativos en presentación
    """
    return suma_raw * -1


def calcular_eerr(df: pd.DataFrame,
                  mes: int | None = None,
                  empresas: list | None = None,
                  factor_mmq_forzado: bool | None = None) -> dict:
    """
    Calcula el EERR consolidado desde el DataFrame base.

    Parámetros:
        df: DataFrame consolidado (salida de transformacion.diarios.consolidar)
        mes: Mes a filtrar (1-12). None = acumulado.
        empresas: Lista de empresas a incluir. None = todas.
        factor_mmq_forzado: si se pasa True/False, override explicito del
            criterio automatico de mas abajo (usado por generar_datos.py
            para precalcular AMBAS variantes de MMQ - 100% y ponderada -
            aunque en ambos casos se llame con empresas=["MMQ"]).

    Retorna dict con cada línea del EERR en pesos (CLP).

    NOTA sobre MMQ: el factor 0.75/0.875 representa la participación de
    GEMCO en MMQ. Si MMQ es la UNICA empresa seleccionada (empresas ==
    ["MMQ"]), se muestra al 100% real de la empresa, sin ponderar. En
    cualquier otro caso (consolidado de 2+ empresas, incluyendo el
    consolidado total de las 4) el factor se aplica normalmente.
    """
    if factor_mmq_forzado is not None:
        factor_mmq_activo = factor_mmq_forzado
    else:
        # MMQ aislado = sin ponderacion. Cualquier combinacion con otra
        # empresa (incluido el consolidado completo) = con ponderacion.
        factor_mmq_activo = not (empresas is not None and list(empresas) == ["MMQ"])

    # Filtro de empresas
    if empresas:
        todas_ec = set()
        for e in empresas:
            if e == "GEMCO":
                todas_ec.update(EMPRESAS_GEMCO)
            else:
                todas_ec.add(e)
        df = df[df["Empresa_Comercial"].isin(todas_ec)].copy()

    # Filtro de mes
    df_mes = df.copy()
    if mes is not None:
        df_mes = df[df["Fecha"].dt.month == mes].copy()

    def s(concepto, **kwargs):
        """Shortcut: suma y convierte a presentación."""
        kwargs.setdefault("factor_mmq_activo", factor_mmq_activo)
        return _presentacion(_suma_concepto(df_mes, concepto, **kwargs))

    # ── INGRESOS ──────────────────────────────────────────────────
    ingresos = s("Ingresos de actividades ordinarias")

    # ── COSTO DE VENTAS ───────────────────────────────────────────
    costo_ventas = s("Costo de ventas")

    # ── MARGEN BRUTO ──────────────────────────────────────────────
    margen_bruto = ingresos + costo_ventas

    # ── GPBE DIRECTOS ─────────────────────────────────────────────
    gpbe_directos = _presentacion(
        _suma_concepto(df_mes[df_mes["GAV"] == "GAV DIRECTO"],
                       "Gastos por beneficios a los empleados",
                       factor_mmq_activo=factor_mmq_activo)
    )

    # ── GPBE INDIRECTOS ───────────────────────────────────────────
    gpbe_indirectos = _presentacion(
        _suma_concepto(df_mes[df_mes["GAV"] == "GAV INDIRECTO"],
                       "Gastos por beneficios a los empleados",
                       factor_mmq_activo=factor_mmq_activo)
    )

    gpbe_total = gpbe_directos + gpbe_indirectos

    # ── OGPN DIRECTOS: GEMCO GAV DIRECTO + todo Incardia/MMQ/Tecservice ─────
    ogpn_directos = _presentacion(
        _suma_concepto(
            df_mes[
                (df_mes["GAV"] == "GAV DIRECTO") |
                (df_mes["Empresa_Comercial"].isin({"Incardia", "MMQ", "Tecservice"}))
            ],
            "Otros gastos por naturaleza",
            factor_mmq_activo=factor_mmq_activo
        )
    )

    # ── OGPN INDIRECTOS: solo GEMCO GAV INDIRECTO ────────────────────────────
    ogpn_indirectos = _presentacion(
        _suma_concepto(
            df_mes[
                (df_mes["GAV"] == "GAV INDIRECTO") &
                (df_mes["Empresa_Comercial"].isin({"GEMCO", "Soporte Indirecto", "Ajustes Contables"}))
            ],
            "Otros gastos por naturaleza",
            factor_mmq_activo=factor_mmq_activo
        )
    )

    ogpn_total = ogpn_directos + ogpn_indirectos

    # ── EBITDA DIRECTO ────────────────────────────────────────────
    ebitda_directo = (ingresos + costo_ventas +
                      gpbe_directos + gpbe_indirectos +
                      ogpn_directos + ogpn_indirectos)

    # ── GASTOS ADICIONALES ────────────────────────────────────────
    finiquitos = _presentacion(
        _suma_concepto(df_mes, "Finiquitos",
                       excluir_sin_clasificar=True,
                       factor_mmq_activo=factor_mmq_activo)
    )

    multas = s("Multas")

    prov_obsolescencias = s("Provisión Obsolescencias Inventarios")
    prov_incobrables = s("Provisión Incobrales")
    prov_habilitacion = s("Provisión Habilitación Oficinas")

    gastos_adicionales = finiquitos + multas + prov_obsolescencias + prov_incobrables + prov_habilitacion

    # ── EBITDA EMPRESA ────────────────────────────────────────────
    ebitda_empresa = ebitda_directo + gastos_adicionales

    # ── RESULTADO OPERACIONAL ─────────────────────────────────────
    depreciacion = s("Gastos por depreciación y amortización")
    resultado_operacional = ebitda_empresa + depreciacion

    # ── RESULTADO NO OPERACIONAL ──────────────────────────────────
    otros_ingresos = s("Otros Ingresos por Función")
    ingreso_financiero = s("Ingreso Financiero")

    costo_financiero = _presentacion(
        _suma_concepto(df_mes, "Costo financiero",
                       excluir_gav_no_corresponde=True,
                       factor_mmq_activo=factor_mmq_activo)
    )

    otros_gastos_funcion = s("Otros gastos por función")
    diferencia_cambio = s("Diferencia de cambio")

    resultado_no_op = (otros_ingresos + ingreso_financiero +
                       costo_financiero + otros_gastos_funcion +
                       diferencia_cambio)

    # ── RESULTADO ANTES IMPUESTOS ─────────────────────────────────
    resultado_antes_imp = resultado_operacional + resultado_no_op

    return {
        # Líneas principales
        "Ingresos":                    round(ingresos, 2),
        "Costo de ventas":             round(costo_ventas, 2),
        "Margen Bruto":                round(margen_bruto, 2),
        "GPBE Directos":               round(gpbe_directos, 2),
        "GPBE Indirectos":             round(gpbe_indirectos, 2),
        "GPBE Total":                  round(gpbe_total, 2),
        "OGPN Directos":               round(ogpn_directos, 2),
        "OGPN Indirectos":             round(ogpn_indirectos, 2),
        "OGPN Total":                  round(ogpn_total, 2),
        "Subtotal GAV":                round(gpbe_total + ogpn_total, 2),
        "EBITDA Directo":              round(ebitda_directo, 2),
        "Finiquitos":                  round(finiquitos, 2),
        "Multas":                      round(multas, 2),
        "Provisión Obsolescencias":    round(prov_obsolescencias, 2),
        "Provisión Incobrables":       round(prov_incobrables, 2),
        "Provisión Habilitación Oficinas": round(prov_habilitacion, 2),
        "Gastos Adicionales":          round(gastos_adicionales, 2),
        "EBITDA Empresa":              round(ebitda_empresa, 2),
        "Depreciación":                round(depreciacion, 2),
        "Resultado Operacional":       round(resultado_operacional, 2),
        "Otros Ingresos por Función":  round(otros_ingresos, 2),
        "Ingreso Financiero":          round(ingreso_financiero, 2),
        "Costo Financiero":            round(costo_financiero, 2),
        "Otros Gastos por Función":    round(otros_gastos_funcion, 2),
        "Diferencia de Cambio":        round(diferencia_cambio, 2),
        "Resultado No Operacional":    round(resultado_no_op, 2),
        "Resultado antes Impuestos":   round(resultado_antes_imp, 2),
        "Impuesto a la Renta":         round(resultado_antes_imp * -0.27, 2),
        "Resultado del Ejercicio":     round(resultado_antes_imp * 0.73, 2),
    }
