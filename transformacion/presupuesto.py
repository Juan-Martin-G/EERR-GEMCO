"""
transformacion/presupuesto.py
==============================
Porta la logica de Power Query del Presupuesto (PPTO V2.xlsx) a Python.

Consultas M portadas:
- Ppto_Consolidado (hoja 'P&L Mensual', Nivel=Consolidado)
- Ppto_Incardia, Ppto_MMQ, Ppto_Tecservice (Nivel=Linea, filtran Costo/Ingresos)
- Ppto_E_Esterilizacion, Ppto_E_Dental, Ppto_E_Endoscopia,
  Ppto_C_Endoscopia, Ppto_C_Esterilizacion, Ppto_Trazabilidad (Nivel=Linea,
  SI incluyen Ingresos/Costo directo)
- Ppto_IngCostos_Faltantes (hoja 'Ing-Costos', rescata Ingresos/Costo de
  lineas especificas: Consumibles Cardiovascular/Traumatologia, Equipos
  Cardiovascular, Mantenciones y Reparaciones)

Validado peso por peso contra 'Resultado del Ejercicio Empresa' de
Enero a Mayo 2026 (ver conversacion de validacion).
"""

import pandas as pd
import warnings
warnings.filterwarnings('ignore')

MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

# Conceptos de subtotal que Power Query excluye de las hojas de linea
CONCEPTOS_EXCLUIR = {
    "%  EBITDA", "%  EBITDA EMPRESA", "% Ebitda Empresa / % Margen Directo",
    "% MARGEN", "EBITDA ", "EBITDA EMPRESA", "MARGEN DEL PRODUCTO",
    "Res. Ejercicio Empresa S/(Gastos Fin+Beneficios Empleados+Gastos Empresa+Costos)",
    "Resultado antes de impuestos", "Resultado del ejercicio Empresa",
    "Resultado Ejercicio Empresa S/Ingresos", "Resultado no operacional",
    "Resultado Operacional ", "Subtotal", "Total Gastos Adicionales",
}


def _find_header_row(raw):
    """Busca la fila que contiene los nombres de los meses (encabezado real)."""
    for i in range(min(10, len(raw))):
        vals = [str(raw.iloc[i, j]) for j in range(raw.shape[1])]
        if 'Enero' in vals and 'Febrero' in vals:
            return i
    return None


def _leer_hoja_linea(archivo, hoja, linea_negocio, filtrar_col=None,
                      excluir_costo_ingresos=True):
    """
    Lee y despivota una hoja P&L de linea de negocio.

    filtrar_col:
        None    -> no filtra filas (excepto exclusion de subtotales)
        'Enero' -> filtra filas donde Enero != 0 (equivalente al M)
        'total' -> filtra filas donde la 2da columna (total/GEMCO xxx) != 0
    excluir_costo_ingresos:
        True para Incardia/MMQ/Tecservice (ingresos/costo vienen de
        Ppto_IngCostos_Faltantes). False para las lineas de equipos/
        consumibles que SI traen su propio Ingresos/Costo de ventas.
    """
    raw = pd.read_excel(archivo, sheet_name=hoja, header=None)
    hr = _find_header_row(raw)
    if hr is None:
        raise ValueError(f"No se encontro encabezado de meses en hoja '{hoja}'")

    fila_head = [str(raw.iloc[hr, j]) for j in range(raw.shape[1])]
    col_concepto = 1
    col_total = 2  # columna C: total anual o "GEMCO xxx"
    col_mes = {}
    for j, v in enumerate(fila_head):
        if v in MESES:
            col_mes[v] = j

    registros = []
    for i in range(hr + 1, len(raw)):
        concepto = raw.iloc[i, col_concepto]
        if pd.isna(concepto) or str(concepto).strip() == '':
            continue
        concepto = str(concepto).strip()
        if concepto in CONCEPTOS_EXCLUIR:
            continue
        if excluir_costo_ingresos and concepto in (
                "Costo de explotación", "Ingresos de actividades ordinarias"):
            continue

        if filtrar_col == 'Enero':
            v = raw.iloc[i, col_mes.get('Enero')]
            try:
                if float(v) == 0 or pd.isna(v):
                    continue
            except (TypeError, ValueError):
                continue
        elif filtrar_col == 'total':
            v = raw.iloc[i, col_total]
            try:
                if float(v) == 0 or pd.isna(v):
                    continue
            except (TypeError, ValueError):
                continue

        for mes, jcol in col_mes.items():
            val = raw.iloc[i, jcol]
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if pd.isna(val):
                continue
            registros.append({
                'Concepto': concepto, 'Mes': mes, 'Monto_Presupuesto': val,
                'Linea_Negocio': linea_negocio, 'Mes_Numero': MESES.index(mes) + 1,
                'Nivel': 'Linea',
            })
    return pd.DataFrame(registros)


def _leer_consolidado(archivo):
    """Ppto_Consolidado, desde la hoja 'P&L Mensual'. Nivel = Consolidado."""
    raw = pd.read_excel(archivo, sheet_name='P&L Mensual', header=None)
    hr = _find_header_row(raw)
    fila_head = [str(raw.iloc[hr, j]) for j in range(raw.shape[1])]
    col_concepto = 1
    col_mes = {}
    for j, v in enumerate(fila_head):
        if v in MESES:
            col_mes[v] = j

    registros = []
    for i in range(hr + 1, len(raw)):
        concepto = raw.iloc[i, col_concepto]
        if pd.isna(concepto) or str(concepto).strip() == '':
            continue
        concepto = str(concepto).strip()
        if concepto in CONCEPTOS_EXCLUIR:
            continue
        # filtro M: Febrero <> 0
        vf = raw.iloc[i, col_mes.get('Febrero')]
        try:
            if float(vf) == 0 or pd.isna(vf):
                continue
        except (TypeError, ValueError):
            continue
        for mes, jcol in col_mes.items():
            val = raw.iloc[i, jcol]
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if pd.isna(val):
                continue
            registros.append({
                'Concepto': concepto, 'Mes': mes, 'Monto_Presupuesto': val,
                'Linea_Negocio': None, 'Mes_Numero': MESES.index(mes) + 1,
                'Nivel': 'Consolidado',
            })
    return pd.DataFrame(registros)


def cargar_presupuesto(archivo):
    """
    Carga y combina las 10 consultas de linea de negocio del presupuesto
    (equivalente a Table.Combine de las 10 Ppto_X en Power Query).
    No incluye Ppto_IngCostos_Faltantes (ver normalizar_faltantes).
    """
    ppto_consolidado = _leer_consolidado(archivo)
    ppto_incardia = _leer_hoja_linea(archivo, 'P&L Incardia', 'Incardia',
                                      filtrar_col='Enero')
    ppto_mmq = _leer_hoja_linea(archivo, 'P&L MMQ', 'MMQ',
                                 filtrar_col='Enero')
    ppto_tecservice = _leer_hoja_linea(archivo, 'P&L TECSERVICE', 'Tecservice',
                                        filtrar_col=None)
    ppto_e_ester = _leer_hoja_linea(archivo, 'P&L E. Esterilización',
                                     'Equipos Esterilización', filtrar_col='Enero',
                                     excluir_costo_ingresos=False)
    ppto_e_dental = _leer_hoja_linea(archivo, 'P&L E. Dental', 'Equipos Dental',
                                      filtrar_col='total',
                                      excluir_costo_ingresos=False)
    ppto_e_endo = _leer_hoja_linea(archivo, 'P&L E. Endoscopía',
                                    'Equipos Endoscopía', filtrar_col='Enero',
                                    excluir_costo_ingresos=False)
    ppto_c_endo = _leer_hoja_linea(archivo, 'P&L C. Endoscopia',
                                    'Consumibles Endoscopía', filtrar_col='Enero',
                                    excluir_costo_ingresos=False)
    ppto_c_ester = _leer_hoja_linea(archivo, 'P&L C. Esterilización',
                                     'Consumibles Esterilización', filtrar_col='Enero',
                                     excluir_costo_ingresos=False)
    ppto_trazab = _leer_hoja_linea(archivo, 'P&L Trazabilidad', 'Trazabilidad',
                                    filtrar_col=None, excluir_costo_ingresos=False)

    return pd.concat([
        ppto_consolidado, ppto_incardia, ppto_mmq, ppto_tecservice,
        ppto_e_ester, ppto_e_dental, ppto_e_endo, ppto_c_endo,
        ppto_c_ester, ppto_trazab,
    ], ignore_index=True)


def normalizar(df):
    """
    Aplica Empresa_Comercial, Concepto (estandarizado), GAV y Concepto_Padre
    igual que las columnas personalizadas de Power Query.
    """
    df = df.copy()

    def empresa_comercial(linea):
        if linea == 'MMQ':
            return 'MMQ'
        if linea == 'Incardia':
            return 'Incardia'
        if linea == 'Tecservice':
            return 'Tecservice'
        if linea == 'Trazabilidad':
            # Ocurre contablemente en GEMCO (igual que Real), aunque la
            # opere Tecservice - ver correccion de atribucion por empresa
            return 'GEMCO'
        if linea in ('Equipos Esterilización', 'Equipos Dental', 'Equipos Endoscopía',
                     'Consumibles Endoscopía', 'Consumibles Esterilización'):
            return 'GEMCO'
        return None
    df['Empresa_Comercial'] = df['Linea_Negocio'].apply(empresa_comercial)

    def concepto_estandar(c):
        if 'Otros gastos de explotación Directos' in c or 'Otros gastos por naturaleza Directos' in c:
            return 'Otros gastos por naturaleza Directos'
        if 'Otros gastos de explotación Indirectos' in c or 'Otros gastos por naturaleza Indirectos' in c:
            return 'Otros gastos por naturaleza Indirectos'
        if 'Otros gastos de explotación' in c:
            return 'Otros gastos por naturaleza'
        if c == 'Costo de explotación':
            return 'Costo de ventas'
        if c == 'Gasto por Beneficio a los Empleados':
            return 'Gastos por beneficios a los empleados'
        if c == 'Depreciación y Amortización':
            return 'Gastos por depreciación y amortización'
        if c == 'Gastos Financieros':
            return 'Costo financiero'
        return c
    df['Concepto'] = df['Concepto'].apply(concepto_estandar)

    def concepto_estandar2(c):
        if c == 'Costo de explotación':
            return 'Costo de ventas'
        if c == 'Gasto por Beneficio a los Empleados':
            return 'Gastos por beneficios a los empleados'
        if c == 'Otros Gastos por Naturaleza':
            return 'Otros gastos por naturaleza'
        if c in ('Gastos por beneficios a los empleados Directos',
                  'Gastos por beneficios a los empleados Indirectos',
                  'Otros gastos por naturaleza Directos',
                  'Otros gastos por naturaleza Indirectos'):
            return c
        if c == 'Ingresos financieros':
            return 'Ingreso financiero'
        return c
    df['Concepto'] = df['Concepto'].apply(concepto_estandar2)

    def gav(c):
        if c.endswith('Directos'):
            return 'GAV DIRECTO'
        if c.endswith('Indirectos'):
            return 'GAV INDIRECTO'
        return None
    df['GAV'] = df['Concepto'].apply(gav)

    def concepto_padre(c):
        c = c.strip()
        if 'beneficios a los' in c:
            return 'Gastos por beneficios a los empleados'
        if 'Otros gastos por naturaleza' in c:
            return 'Otros gastos por naturaleza'
        if c == 'Costo de explotación':
            return 'Costo de ventas'
        if c == 'Gasto por Beneficio a los Empleados':
            return 'Gastos por beneficios a los empleados'
        if c == 'Ingresos financieros':
            return 'Ingreso financiero'
        return c
    df['Concepto_Padre'] = df['Concepto'].apply(concepto_padre)

    return df


def normalizar_faltantes(archivo):
    """
    Porta Ppto_IngCostos_Faltantes desde la hoja 'Ing-Costos'.
    Rescata Ingresos/Costo de ventas para lineas especificas que no vienen
    en sus propias hojas P&L: Consumibles Cardiovascular/Traumatologia,
    Equipos Cardiovascular, Mantenciones y Reparaciones (todas Tecservice
    excepto las 2 primeras que son Incardia/MMQ via Empresa_Comercial).

    Ojo: los valores en esta hoja vienen /1000 respecto al resto (ver
    'Columna dividida' en el M original).
    """
    raw = pd.read_excel(archivo, sheet_name='Ing-Costos', header=None)
    hr = None
    for i in range(min(15, len(raw))):
        vals = [str(raw.iloc[i, j]) for j in range(raw.shape[1])]
        if 'INGRESOS' in vals:
            hr = i
            break
    if hr is None:
        raise ValueError("No se encontro columna 'INGRESOS' en hoja Ing-Costos")

    fila_head = [str(raw.iloc[hr, j]) for j in range(raw.shape[1])]
    col_ingresos = fila_head.index('INGRESOS')
    col_empresa = fila_head.index('EMPRESA') if 'EMPRESA' in fila_head else None
    col_total2026 = None
    for j, v in enumerate(fila_head):
        if 'TOTAL' in v and '2026' in v:
            col_total2026 = j
    col_mes = {}
    for j, v in enumerate(fila_head):
        if v in MESES:
            col_mes[v] = j

    incluir = {
        "CONSUMIBLES CARDIOVACULAR", "CONSUMIBLES TRAUMATOLOGÍA", "EQUIPOS CARDIOVASCULAR",
        "Mantención Dental", "Mantención Endoscopía", "Mantención Esterilización",
        "Matención Medicos", "Matención Reas", "Matención Trazabilidad",
        "Reparación Dental", "Reparación Endoscopía", "Reparación Esterilización",
    }
    rename_linea = {
        "CONSUMIBLES TRAUMATOLOGÍA": "Consumibles Traumatología",
        "CONSUMIBLES CARDIOVACULAR": "Consumibles Cardiovascular",
        "EQUIPOS CARDIOVASCULAR": "Equipos Cardiovascular",
    }

    # La hoja Ing-Costos tiene 3 bloques apilados con las mismas lineas de negocio:
    # Ingresos, Costos, y un tercer bloque "Margen Directo" (= Ingresos + Costos,
    # un valor YA CALCULADO, no un dato nuevo). El M original lo descarta con
    # 3 llamadas Table.RemoveLastN (7+1+1 = 9 filas) sobre la tabla ya filtrada
    # por [TOTAL_2026] <> 0. Replicamos ese descarte aqui: primero recolectamos
    # TODAS las filas candidatas en orden de aparicion, luego quitamos las
    # ultimas 9 antes de construir los registros finales.
    candidatas = []
    for i in range(hr + 1, len(raw)):
        linea_val = raw.iloc[i, col_ingresos]
        if pd.isna(linea_val) or str(linea_val).strip() not in incluir:
            continue
        total26 = raw.iloc[i, col_total2026] if col_total2026 is not None else None
        try:
            if float(total26) == 0 or pd.isna(total26):
                continue
            total26 = float(total26)
        except (TypeError, ValueError):
            continue
        candidatas.append(i)

    filas_validas = set(candidatas[:-9]) if len(candidatas) > 9 else set()

    registros = []
    for i in filas_validas:
        linea_val = str(raw.iloc[i, col_ingresos]).strip()
        empresa_val = raw.iloc[i, col_empresa] if col_empresa is not None else None
        total26 = float(raw.iloc[i, col_total2026])

        concepto = "Ingresos de actividades ordinarias" if total26 >= 0 else "Costo de ventas"
        linea_final = rename_linea.get(linea_val, linea_val)
        # NOTA (correccion): estas lineas (Mantencion/Reparacion/REAS) ocurren
        # contablemente en GEMCO, aunque las opere Tecservice. Se atribuyen a
        # GEMCO para ser consistentes con el Real (ver transformacion/diarios.py).
        emp_final = "GEMCO" if (pd.isna(empresa_val) or str(empresa_val).strip() == '') \
            else str(empresa_val).strip()
        if emp_final == "Gemco":
            emp_final = "GEMCO"

        for mes, jcol in col_mes.items():
            val = raw.iloc[i, jcol]
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if pd.isna(val):
                continue
            registros.append({
                'Concepto': concepto, 'Mes': mes, 'Monto_Presupuesto': val / 1000,
                'Linea_Negocio': linea_final, 'Mes_Numero': MESES.index(mes) + 1,
                'Nivel': 'Linea', 'GAV': None, 'Concepto_Padre': concepto,
                'Empresa_Comercial': emp_final,
            })
    return pd.DataFrame(registros)


def cargar_presupuesto_completo(archivo):
    """
    Funcion de conveniencia: carga, normaliza y combina todo el presupuesto
    en un solo DataFrame listo para calcular_eerr_ppto().
    """
    df = cargar_presupuesto(archivo)
    df_norm = normalizar(df)
    df_falt = normalizar_faltantes(archivo)
    return pd.concat([df_norm, df_falt], ignore_index=True)


if __name__ == '__main__':
    import sys
    archivo = sys.argv[1] if len(sys.argv) > 1 else 'data/raw/PPTO_V2.xlsx'
    full = cargar_presupuesto_completo(archivo)
    print(f"Total filas: {len(full)}")
    print(full['Linea_Negocio'].value_counts(dropna=False))
