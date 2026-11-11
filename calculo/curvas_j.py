"""
calculo/curvas_j.py
===================
Datos de la hoja "Curvas J" del panel: Resultado del Ejercicio mensual,
Real vs Presupuesto, por linea de negocio. El panel acumula en el navegador.

PRESUPUESTO: fila "Resultado del ejercicio Empresa" de cada hoja de linea
de PPTO_V2.xlsx (en millones de CLP; aqui se pasa a pesos, como el Real).
TECSERVICE es la suma de cuatro hojas (TECSERVICE + SS + Reas +
Trazabilidad), igual que el bloque "Tecservice -S&S" de la hoja
"Curva J - Comparacion 2025" del mismo archivo. "P&L E. Medicos" esta
vacia y no se usa.

REAL: concepto "Resultado del Ejercicio" de lineas_real (el EERR por linea
de la hoja "Lineas": centros comunes prorrateados, MMQ ponderado).

TOTAL GEMCO = suma de las 8 lineas, en Real y en Presupuesto. Consumibles
Dental no tiene presupuesto: queda fuera del Total y se guarda aparte
("excluido") para poder cuadrar el Real contra el consolidado.

No se aplica el ajuste de gestion de D&A de Tecservice: la depreciacion es
la contable en el Real y la de cada hoja en el Presupuesto.

Controles (controlar_curvas_j), que abortan la generacion si fallan:
  (i)   suma de las 8 lineas del presupuesto, por mes, vs Resultado del
        Ejercicio del presupuesto consolidado (calcular_eerr_ppto);
  (ii)  TECSERVICE anual (4 hojas) vs columna "TECSERVICE Consolidado" de
        la hoja "P&L Línea de Negocio";
  (iii) suma de las 8 lineas Real + Consumibles Dental, por mes, vs
        Resultado del Ejercicio Real consolidado.
"""

import openpyxl

ETIQUETA_RESULTADO = "Resultado del ejercicio Empresa"
CONCEPTO_REAL = "Resultado del Ejercicio"
ENCABEZADO_ETIQUETAS = "ESTADO RESULTADO"

MESES_PPTO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
              "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Linea del panel -> hojas del PPTO V2 que la componen (se suman mes a mes).
# El orden es el de los graficos.
HOJAS_POR_LINEA = {
    "MMQ": ["P&L MMQ"],
    "Incardia": ["P&L Incardia"],
    "TECSERVICE": ["P&L TECSERVICE", "P&L SS", "P&L Reas", "P&L Trazabilidad"],
    "Equipos Esterilización": ["P&L E. Esterilización"],
    "Consumibles Esterilización": ["P&L C. Esterilización"],
    "Equipos Endoscopía": ["P&L E. Endoscopía"],
    "Consumibles Endoscopía": ["P&L C. Endoscopia"],
    "Equipos Dental": ["P&L E. Dental"],
}
LINEAS = list(HOJAS_POR_LINEA)

TOTAL = "Total GEMCO"
ORDEN = [TOTAL] + LINEAS

# Lineas con Real pero sin presupuesto: fuera del Total, guardadas aparte.
EXCLUIDAS = ["Consumibles Dental"]

HOJA_LINEA_NEGOCIO = "P&L Línea de Negocio"
COLUMNA_TECSERVICE = "TECSERVICE Consolidado"

FUENTE = "PPTO V2 (fila Resultado del ejercicio Empresa)"

MILLON = 1_000_000

# Tolerancias de los controles, en pesos.
TOLERANCIA_PPTO = 500_000   # 0,5 M
TOLERANCIA_REAL = 10        # por mes


# ──────────────────────────────────────────────────────────────────────
# LECTURA DEL PRESUPUESTO (PPTO_V2.xlsx)
# ──────────────────────────────────────────────────────────────────────

def _texto(valor):
    """Texto de una celda, sin espacios sobrantes ni saltos de linea."""
    return "" if valor is None else " ".join(str(valor).split())


def _filas(wb, hoja, max_filas=200, max_cols=60):
    """Las celdas de una hoja como lista de filas (valores ya calculados)."""
    if hoja not in wb.sheetnames:
        raise ValueError(f"Curvas J: el presupuesto no tiene la hoja '{hoja}'.")
    return [list(fila) for fila in wb[hoja].iter_rows(
        min_row=1, max_row=max_filas, max_col=max_cols, values_only=True)]


def _columna_unica(encabezado, texto, hoja):
    """Indice de la unica columna del encabezado con ese texto."""
    cols = [j for j, v in enumerate(encabezado) if _texto(v) == texto]
    if len(cols) != 1:
        raise ValueError(
            f"Curvas J: en la hoja '{hoja}' se esperaba una sola columna "
            f"'{texto}' en la fila de encabezado y hay {len(cols)}."
        )
    return cols[0]


def _ubicar_fila_resultado(filas, hoja, columnas_requeridas):
    """
    Retorna (encabezado, fila del resultado): la fila de encabezado es la
    primera que tiene la columna de etiquetas ("ESTADO RESULTADO") y todas
    las `columnas_requeridas`; la fila del resultado es la UNICA, debajo
    del encabezado, cuya etiqueta es exactamente ETIQUETA_RESULTADO.
    """
    requeridas = {ENCABEZADO_ETIQUETAS, *columnas_requeridas}
    i_enc = next(
        (i for i, fila in enumerate(filas)
         if requeridas <= {_texto(v) for v in fila}),
        None,
    )
    if i_enc is None:
        raise ValueError(
            f"Curvas J: en la hoja '{hoja}' no se encontro la fila de "
            f"encabezado (con '{ENCABEZADO_ETIQUETAS}' y las columnas "
            f"{sorted(columnas_requeridas)})."
        )
    encabezado = filas[i_enc]
    col_etiqueta = _columna_unica(encabezado, ENCABEZADO_ETIQUETAS, hoja)

    candidatas = [
        fila for fila in filas[i_enc + 1:]
        if _texto(fila[col_etiqueta]) == ETIQUETA_RESULTADO
    ]
    if len(candidatas) != 1:
        raise ValueError(
            f"Curvas J: en la hoja '{hoja}' la etiqueta "
            f"'{ETIQUETA_RESULTADO}' deberia estar una sola vez en la "
            f"columna de etiquetas y esta {len(candidatas)} veces."
        )
    return encabezado, candidatas[0]


def _numero(valor, hoja, columna):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(
            f"Curvas J: en la hoja '{hoja}', la fila '{ETIQUETA_RESULTADO}' "
            f"no tiene un numero en la columna '{columna}' (valor: "
            f"{valor!r}). Si el archivo se guardo sin recalcular, abrirlo "
            "en Excel y guardarlo de nuevo."
        )
    return float(valor)


def _resultado_hoja(wb, hoja):
    """Los 12 valores mensuales (millones) del resultado de una hoja de linea."""
    encabezado, fila = _ubicar_fila_resultado(_filas(wb, hoja), hoja, MESES_PPTO)
    return [
        _numero(fila[_columna_unica(encabezado, mes, hoja)], hoja, mes)
        for mes in MESES_PPTO
    ]


def leer_presupuesto(archivo):
    """
    Lee el presupuesto del Resultado del Ejercicio por linea.

    Retorna {
      "lineas": {linea: [12 valores mensuales, en pesos enteros]},
      "tecservice_consolidado": total anual (pesos) de la columna
          "TECSERVICE Consolidado" de "P&L Línea de Negocio" (control),
    }
    """
    wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
    try:
        lineas = {}
        for linea, hojas in HOJAS_POR_LINEA.items():
            por_hoja = [_resultado_hoja(wb, hoja) for hoja in hojas]
            lineas[linea] = [
                round(sum(valores[m] for valores in por_hoja) * MILLON)
                for m in range(12)
            ]

        encabezado, fila = _ubicar_fila_resultado(
            _filas(wb, HOJA_LINEA_NEGOCIO), HOJA_LINEA_NEGOCIO,
            [COLUMNA_TECSERVICE],
        )
        col = _columna_unica(encabezado, COLUMNA_TECSERVICE, HOJA_LINEA_NEGOCIO)
        tecservice = _numero(fila[col], HOJA_LINEA_NEGOCIO, COLUMNA_TECSERVICE)
    finally:
        wb.close()

    return {"lineas": lineas, "tecservice_consolidado": tecservice * MILLON}


# ──────────────────────────────────────────────────────────────────────
# BLOQUE "curvas_j" DEL JSON
# ──────────────────────────────────────────────────────────────────────

def construir_curvas_j(ppto_lineas, lineas_real, meses_con_real):
    """
    Arma el bloque "curvas_j" de docs/datos_lineas.json. Solo valores
    MENSUALES, en pesos (los acumulados los calcula el panel):

      meses            los 12 periodos, con la misma clave que lineas_real
      ultimo_mes_real  ultimo periodo con Real
      orden            Total GEMCO + las 8 lineas, en el orden de los graficos
      lineas           {linea: {ppto_mensual: [12], real_mensual: [n]}}
                       real_mensual va de enero al ultimo mes con Real
      excluido         {linea sin presupuesto: {real_mensual: [n]}}
      fuente           texto de la fuente del presupuesto

    ppto_lineas: {linea: [12 valores]} (leer_presupuesto()["lineas"]).
    lineas_real: bloque lineas_real (linea -> periodo -> {concepto: valor}).
    """
    faltan = [l for l in LINEAS + EXCLUIDAS if l not in lineas_real]
    if faltan:
        raise ValueError(
            f"Curvas J: lineas_real no tiene las lineas {faltan}. "
            "Revisar data/rules/centro_linea.csv y prorrateo_lineas.csv."
        )

    ultimo = max(meses_con_real)
    meses_real = [str(m) for m in range(1, ultimo + 1)]

    def real(linea):
        return [lineas_real[linea][m][CONCEPTO_REAL] for m in meses_real]

    lineas = {
        linea: {"ppto_mensual": list(ppto_lineas[linea]),
                "real_mensual": real(linea)}
        for linea in LINEAS
    }
    # El Total se suma sobre los mismos valores que se guardan por linea.
    total = {
        serie: [sum(lineas[l][serie][i] for l in LINEAS)
                for i in range(len(lineas[LINEAS[0]][serie]))]
        for serie in ("ppto_mensual", "real_mensual")
    }

    return {
        "meses": [str(m) for m in range(1, 13)],
        "ultimo_mes_real": str(ultimo),
        "orden": list(ORDEN),
        "lineas": {TOTAL: total, **lineas},
        "excluido": {l: {"real_mensual": real(l)} for l in EXCLUIDAS},
        "fuente": FUENTE,
    }


def controlar_curvas_j(curvas_j, ppto_consolidado, tecservice_consolidado,
                       real_consolidado):
    """
    Controles del bloque antes de publicarlo. Lanza ValueError si alguno
    falla; si pasan, retorna las diferencias maximas observadas (pesos):

      ppto_vs_consolidado  (i)   max |suma 8 lineas ppto - consolidado|, por mes
      tecservice_vs_pln    (ii)  |TECSERVICE anual - "TECSERVICE Consolidado"|
      real_vs_consolidado  (iii) max |suma 8 lineas + excluidas - consolidado|

    ppto_consolidado: {periodo: Resultado del Ejercicio del presupuesto
        consolidado (calcular_eerr_ppto)}, los 12 meses.
    tecservice_consolidado: leer_presupuesto()["tecservice_consolidado"].
    real_consolidado: {periodo: Resultado del Ejercicio Real consolidado}.
    """
    total = curvas_j["lineas"][TOTAL]

    # (i) Presupuesto: las 8 lineas reconstruyen el consolidado
    difs = {
        mes: total["ppto_mensual"][i] - ppto_consolidado[mes]
        for i, mes in enumerate(curvas_j["meses"])
    }
    mes_peor = max(difs, key=lambda m: abs(difs[m]))
    if abs(difs[mes_peor]) > TOLERANCIA_PPTO:
        raise ValueError(
            "Curvas J: la suma de las 8 lineas del presupuesto no calza con "
            f"el presupuesto consolidado en el mes {mes_peor} (lineas="
            f"{total['ppto_mensual'][int(mes_peor) - 1]:,}, consolidado="
            f"{ppto_consolidado[mes_peor]:,}, diferencia="
            f"{difs[mes_peor]:,}). Revisar si el PPTO tiene una hoja de "
            "linea nueva o con datos (p. ej. 'P&L E. Medicos')."
        )
    dif_ppto = abs(difs[mes_peor])

    # (ii) TECSERVICE = las 4 hojas
    anual = sum(curvas_j["lineas"]["TECSERVICE"]["ppto_mensual"])
    dif_tec = abs(anual - tecservice_consolidado)
    if dif_tec > TOLERANCIA_PPTO:
        raise ValueError(
            "Curvas J: el presupuesto anual de TECSERVICE (suma de las hojas "
            f"{HOJAS_POR_LINEA['TECSERVICE']}) = {anual:,} no calza con "
            f"'{COLUMNA_TECSERVICE}' de '{HOJA_LINEA_NEGOCIO}' = "
            f"{tecservice_consolidado:,.0f} (diferencia={dif_tec:,.0f})."
        )

    # (iii) Real: 8 lineas + excluidas = consolidado
    dif_real = 0
    for i, valor_total in enumerate(total["real_mensual"]):
        mes = curvas_j["meses"][i]
        suma = valor_total + sum(
            bloque["real_mensual"][i] for bloque in curvas_j["excluido"].values()
        )
        dif = abs(suma - real_consolidado[mes])
        if dif > TOLERANCIA_REAL:
            raise ValueError(
                "Curvas J: el Real de las 8 lineas mas "
                f"{list(curvas_j['excluido'])} no calza con el consolidado en "
                f"el mes {mes} (suma={suma:,}, consolidado="
                f"{real_consolidado[mes]:,}, diferencia={dif:,}). Revisar si "
                "hay una linea nueva o filas 'Sin asignar' en lineas_real."
            )
        dif_real = max(dif_real, dif)

    return {
        "ppto_vs_consolidado": dif_ppto,
        "tecservice_vs_pln": dif_tec,
        "real_vs_consolidado": dif_real,
    }
