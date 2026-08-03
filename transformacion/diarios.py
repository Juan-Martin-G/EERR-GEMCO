"""
transformacion/diarios.py
=========================
Porta la lógica de los "Diario X Limpio" de Power Query a Python.

Reglas clave (documentadas durante validación celda a celda):
- Convención de signos GEMCO: ingresos NEGATIVOS, costos POSITIVOS en BD.
- Convención Incardia/MMQ/Tecservice: ingresos POSITIVOS, costos NEGATIVOS.
- Factor de participación MMQ: 0.75 para meses 1-3, 0.875 desde mes 4.
- Mapeo_Clasif tiene PRIORIDAD sobre el Nombre en EERR nativo del V8.
- Excluir cuentas de balance (código < 400000).
- Excluir filas donde TANTO GAV como UNIDAD 2 son "No corresponde".
- Cuentas alfanuméricas (ej: "0005P") → se tratan como código -1 (sin mapeo).
"""

import pandas as pd
from pathlib import Path

# Ruta de reglas
_RULES_DIR = Path(__file__).parent.parent / "data" / "rules"


def cargar_mapeo_clasif() -> dict:
    """Carga el mapeo cuenta → nombre_eerr desde CSV de reglas."""
    df = pd.read_csv(_RULES_DIR / "mapeo_clasif.csv")
    return dict(zip(df["cuenta"], df["nombre_eerr"]))


def _to_int_cuenta(valor) -> int:
    """Convierte código de cuenta a int. Retorna -1 si es alfanumérico."""
    try:
        return int(float(str(valor)))
    except (ValueError, TypeError):
        return -1


def _normalizar_eerr(nombre: str) -> str:
    """Quita sufijos ' Directos' e ' Indirectos' del nombre EERR."""
    if pd.isna(nombre):
        return "Sin clasificar"
    return str(nombre).replace(" Directos", "").replace(" Indirectos", "").strip()


def _aplicar_prioridad_mapeo(codigo_cuenta: int, nombre_eerr_nativo: str,
                              mapeo: dict) -> str:
    """
    Aplica prioridad: Mapeo_Clasif primero, nativo del V8 como fallback.
    Resuelve inconsistencias del V8 (ej: cuenta 610206 marcada como OGPN
    en Diario pero debe ser GPBE según Mensual).
    """
    if codigo_cuenta in mapeo:
        return mapeo[codigo_cuenta]
    if nombre_eerr_nativo == "Sin clasificar":
        return "Sin clasificar"
    return nombre_eerr_nativo


def limpiar_incardia(df_raw: pd.DataFrame, mapeo: dict) -> pd.DataFrame:
    """
    Limpia el Diario Incardia. Equivalente a 'Diario Incardia Limpio' en PQ.

    Columnas requeridas en df_raw:
      Fecha de contabilización, Cuenta de mayor/Código SN,
      Cuenta de mayor/Nombre SN, Cargo/abono (ML), Nombre en EERR
    """
    df = df_raw.copy()

    # 1. Tipos
    df["Fecha"] = pd.to_datetime(df["Fecha de contabilización"], errors="coerce")
    df["Cargo/abono (ML)"] = pd.to_numeric(df["Cargo/abono (ML)"], errors="coerce")

    # 2. Código de cuenta seguro (alfanuméricos → -1)
    df["Cuenta_Int"] = df["Cuenta de mayor/Código SN"].apply(_to_int_cuenta)

    # 3. Nombre EERR nativo normalizado (reemplazar errores y nulos)
    df["EERR_nativo"] = df["Nombre en EERR"].apply(_normalizar_eerr)
    df.loc[df["EERR_nativo"] == "nan", "EERR_nativo"] = "Sin clasificar"

    # 4. PRIORIDAD: Mapeo_Clasif sobre nativo V8
    df["Nombre en EERR"] = df.apply(
        lambda r: _aplicar_prioridad_mapeo(r["Cuenta_Int"], r["EERR_nativo"], mapeo),
        axis=1
    )

    # 5. Filtros
    df = df[
        df["Cargo/abono (ML)"].notna() &
        (df["Cargo/abono (ML)"] != 0) &
        (~df["Nombre en EERR"].isin(["No corresponde", "Sin clasificar",
                                      "Impuesto a la renta"]))
    ].copy()

    # 6. Empresa y Linea_Negocio
    df["Empresa"] = "Incardia"
    df["Empresa_Comercial"] = "Incardia"
    df["Linea_Negocio"] = df["Cuenta_Int"].map({
        410101: "Equipos Cardiovascular",
        410110: "Consumibles Cardiovascular",
        510101: "Equipos Cardiovascular",
        510119: "Consumibles Cardiovascular",
    }).fillna("Soporte Indirecto")

    # 7. GAV: empleados → siempre DIRECTO
    df["GAV"] = df["Nombre en EERR"].apply(
        lambda n: "GAV DIRECTO" if n == "Gastos por beneficios a los empleados"
        else None
    )

    # 8. Columnas de salida estándar
    return _columnas_estandar(df)


def limpiar_mmq(df_raw: pd.DataFrame, mapeo: dict) -> pd.DataFrame:
    """
    Limpia el Diario MMQ. Equivalente a 'Diario MMQ Limpio' en PQ.
    Factor de participación se aplica en la capa de cálculo, no aquí.
    """
    df = df_raw.copy()

    df["Fecha"] = pd.to_datetime(df["Fecha de contabilización"], errors="coerce")
    df["Cargo/abono (ML)"] = pd.to_numeric(df["Cargo/abono (ML)"], errors="coerce")
    df["Cuenta_Int"] = df["Cuenta de mayor/Código SN"].apply(_to_int_cuenta)

    df["EERR_nativo"] = df["Nombre en EERR"].apply(_normalizar_eerr)
    df.loc[df["EERR_nativo"] == "nan", "EERR_nativo"] = "Sin clasificar"

    df["Nombre en EERR"] = df.apply(
        lambda r: _aplicar_prioridad_mapeo(r["Cuenta_Int"], r["EERR_nativo"], mapeo),
        axis=1
    )

    df = df[
        df["Cargo/abono (ML)"].notna() &
        (df["Cargo/abono (ML)"] != 0) &
        (~df["Nombre en EERR"].isin(["No corresponde", "Sin clasificar",
                                      "Impuesto a la renta"]))
    ].copy()

    df["Empresa"] = "MMQ"
    df["Empresa_Comercial"] = "MMQ"
    df["Linea_Negocio"] = df["Cuenta_Int"].map({
        410101: "Equipos Traumatología",
        410105: "Repuestos Traumatología",
        410110: "Consumibles Traumatología",
        510101: "Equipos Traumatología",
        510102: "Repuestos Traumatología",
        510119: "Consumibles Traumatología",
        510113: "Otros MMQ",
    }).fillna("Soporte Indirecto")

    df["GAV"] = df["Nombre en EERR"].apply(
        lambda n: "GAV DIRECTO" if n == "Gastos por beneficios a los empleados"
        else None
    )

    return _columnas_estandar(df)


def limpiar_tecservice(df_raw: pd.DataFrame, mapeo: dict) -> pd.DataFrame:
    """
    Limpia el Diario Tecservice. Equivalente a 'Diario Tecservice Limpio' en PQ.
    Nota: diarios incompletos desde Abril - usar Mensual Tecservice como complemento.
    """
    df = df_raw.copy()

    df["Fecha"] = pd.to_datetime(df["Fecha de contabilización"], errors="coerce")
    df["Cargo/abono (ML)"] = pd.to_numeric(df["Cargo/abono (ML)"], errors="coerce")
    df["Cuenta_Int"] = df["Cuenta de mayor/Código SN"].apply(_to_int_cuenta)

    df["EERR_nativo"] = df["Nombre en EERR"].apply(_normalizar_eerr)
    df.loc[df["EERR_nativo"] == "nan", "EERR_nativo"] = "Sin clasificar"

    df["Nombre en EERR"] = df.apply(
        lambda r: _aplicar_prioridad_mapeo(r["Cuenta_Int"], r["EERR_nativo"], mapeo),
        axis=1
    )

    df = df[
        df["Cargo/abono (ML)"].notna() &
        (df["Cargo/abono (ML)"] != 0) &
        (~df["Nombre en EERR"].isin(["No corresponde", "Sin clasificar",
                                      "Impuesto a la renta"]))
    ].copy()

    df["Empresa"] = "Tecservice"
    df["Empresa_Comercial"] = "Tecservice"
    df["Linea_Negocio"] = "SS Nueva Empresa"

    # Empleados forzado a GAV DIRECTO
    df["GAV"] = df["Nombre en EERR"].apply(
        lambda n: "GAV DIRECTO" if n == "Gastos por beneficios a los empleados"
        else None
    )

    return _columnas_estandar(df)


def limpiar_gemco(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia el Diario GEMCO. Equivalente a 'Diario GEMCO Limpio' en PQ.

    Reglas GEMCO específicas:
    - Excluir cuentas de balance (código < 400000)
    - Excluir filas donde GAV = 'No corresponde' Y UNIDAD 2 = 'No corresponde'
    - Normalizar Nombre en EERR (quitar Directos/Indirectos)
    """
    df = df_raw.copy()

    df["Fecha"] = pd.to_datetime(df["Fecha de contabilización"], errors="coerce")
    df["Cargo/abono (ML)"] = pd.to_numeric(df["Cargo/abono (ML)"], errors="coerce")
    df["Cuenta_Int"] = df["Cuenta de mayor/Código SN"].apply(_to_int_cuenta)

    df["Nombre en EERR"] = df["Nombre en EERR"].apply(_normalizar_eerr)

    # Filtros GEMCO
    df = df[
        (df["Nombre en EERR"] != "No corresponde") &
        df["Cargo/abono (ML)"].notna() &
        (df["Cargo/abono (ML)"] != 0) &
        (df["Cuenta_Int"] >= 400000)
    ].copy()

    df["Empresa"] = "GEMCO"

    # Linea_Negocio desde Nombre Unidad
    _mapa_linea = {
        "E. Esterilización": "Equipos Esterilización",
        "Esterilización":    "Consumibles Esterilización",
        "E. Dental":         "Equipos Dental",
        "Dental":            "Consumibles Dental",
        "E. Endoscopía":     "Equipos Endoscopía",
        "Endoscopía":        "Consumibles Endoscopía",
        "E. Médico":         "Equipos Médicos",
        "Médico":            "Equipos Médicos",
        "Cardiovascular":    "Cordis",
        "Mantención Esterilización":  "Mantención Esterilización",
        "Mantención Dental":          "Mantención Dental",
        "Mantención Endoscopía":      "Mantención Endoscopía",
        "Mantención Médico":          "Mantención E. Médicos",
        "Reparación Esterilización":  "Reparación Esterilización",
        "Reparación Dental":          "Reparación Dental",
        "Reparación Endoscopía":      "Reparación Endoscopía",
        "Reparación Médico":          "Reparación E. Médicos",
        "REAS":              "REAS",
        "Trazabilidad":      "Trazabilidad",
        "Servicios y Soluciones": "SS Nueva Empresa",
        "Finanzas y Contabilidad": "Finanzas y Contabilidad",
        "Operaciones":       "Operaciones",
        "Personas":          "Personas",
        "Comercial":         "Comercial",
        "Marketing":         "Marketing",
        "Gerencia General":  "Gerencia General",
        "Control de Gestión": "Control de Gestión",
        "Rol Privado":       "Rol Privado",
        "administracion":    "Administración",
        "proyectos":         "Proyectos",
    }
    df["Linea_Negocio"] = df["Nombre Unidad"].map(_mapa_linea).fillna("Sin clasificar")

    # Empresa_Comercial desde Linea_Negocio
    # NOTA: las lineas de Mantencion/Reparacion/REAS/Trazabilidad/SS Nueva Empresa
    # son operadas por Tecservice pero OCURREN CONTABLEMENTE en GEMCO (es su
    # propio Diario/entidad legal). Por eso se atribuyen a GEMCO, no a Tecservice.
    # Tecservice como empresa solo debe llevar lo que esta en su propio Diario.
    _gemco_lines = {
        "Equipos Esterilización", "Consumibles Esterilización",
        "Equipos Dental", "Consumibles Dental",
        "Equipos Endoscopía", "Consumibles Endoscopía",
        "Equipos Médicos", "Cordis",
        "Mantención Esterilización", "Mantención Dental",
        "Mantención Endoscopía", "Mantención E. Médicos",
        "Reparación Esterilización", "Reparación Dental",
        "Reparación Endoscopía", "Reparación E. Médicos",
        "REAS", "Trazabilidad", "SS Nueva Empresa",
    }
    _admin_lines = {
        "Finanzas y Contabilidad", "Operaciones", "Personas", "Comercial",
        "Marketing", "Gerencia General", "Control de Gestión",
        "Rol Privado", "Administración", "Proyectos",
    }

    def _empresa_comercial(row):
        l = row["Linea_Negocio"]
        eerr = row["Nombre en EERR"]
        if l in _gemco_lines:
            return "GEMCO"
        if l in _admin_lines and eerr == "Ingresos de actividades ordinarias":
            return "Ajustes Contables"
        return "Soporte Indirecto"

    df["Empresa_Comercial"] = df.apply(_empresa_comercial, axis=1)

    return _columnas_estandar(df)


def _columnas_estandar(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna solo las columnas estándar del modelo consolidado."""
    cols = [
        "Fecha", "Cuenta_Int", "Cuenta de mayor/Nombre SN",
        "Cargo/abono (ML)", "Nombre en EERR",
        "Empresa", "Empresa_Comercial", "Linea_Negocio", "GAV",
    ]
    # Agregar columnas opcionales si existen
    for col in ["UNIDAD 2", "Tipo de Gasto", "Nombre Unidad"]:
        if col in df.columns:
            cols.append(col)
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)


def consolidar(df_gemco: pd.DataFrame, df_incardia: pd.DataFrame,
               df_mmq: pd.DataFrame, df_tec: pd.DataFrame) -> pd.DataFrame:
    """Une los 4 diarios limpios en la base consolidada."""
    return pd.concat(
        [df_gemco, df_incardia, df_mmq, df_tec],
        ignore_index=True
    )
