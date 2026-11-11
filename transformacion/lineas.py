"""
transformacion/lineas.py
========================
Asigna cada fila de la base consolidada a una Linea de Reporte, para el
EERR por Linea de Negocio (hoja "Lineas" del panel).

Reglas (editables en data/rules/):
- centro_linea.csv: codigo de centro de costo GEMCO (Cod_Unidad) -> linea.
  El valor especial "PRORRATEO" marca centros de soporte cuyo monto se
  reparte entre las lineas.
- prorrateo_lineas.csv: porcentaje fijo por linea, igual para todos los
  conceptos y todos los meses. Debe sumar 1.0000 exacto.
- Diarios propios (Incardia / MMQ / Tecservice): toda la empresa va a su
  propia linea, sin mirar centro de costo.
- Cod_Unidad sin regla -> "Sin asignar" (no deberia haber ninguno; lo
  vigilan tests/test_lineas.py y detectar_cuentas_nuevas.py).

IMPORTANTE - Empresa_Comercial NO se modifica:
  Las filas del Diario GEMCO asignadas a la linea "Incardia" (centro 204) o
  "MMQ" (centro 205) siguen siendo Empresa_Comercial = GEMCO. Por lo tanto
  NO reciben el factor de participacion MMQ (0.75 / 0.875) ni la regla de
  OGPN de las filiales en calculo/eerr.py. Lo mismo vale para la parte del
  prorrateo que cae en esas lineas. Solo asi la suma de las lineas calza
  con el EERR consolidado.

El DataFrame de entrada nunca se modifica: asignar_lineas() devuelve una
copia expandida, que se usa unicamente para el calculo por linea.

TODO (pendiente de definir con Finanzas - NO implementado):
  1. Cuenta 610505 "Habilitacion Oficina": forzarla siempre a "Provision
     Habilitacion Oficinas". El Diario GEMCO la etiqueta asi de enero a
     julio, pero en agosto y septiembre viene como "Otros gastos por
     naturaleza" (el Excel oficial la mantiene como provision).
  2. Ajuste de gestion de D&A de Tecservice: el Excel oficial no reparte
     toda la depreciacion compartida con los porcentajes de
     prorrateo_lineas.csv; una parte la carga solo a TECSERVICE e
     Incardia. Aqui se reparte todo con los porcentajes fijos.
"""

from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

_RULES_DIR = Path(__file__).parent.parent / "data" / "rules"

PRORRATEO = "PRORRATEO"
SIN_ASIGNAR = "Sin asignar"

# Diarios propios: Empresa (del diario) -> Linea de Reporte
LINEA_POR_EMPRESA = {
    "Incardia": "Incardia",
    "MMQ": "MMQ",
    "Tecservice": "TECSERVICE",
}

_COL_MONTO = "Cargo/abono (ML)"


def cargar_centro_linea(ruta: str | Path | None = None) -> dict:
    """
    Carga centro_linea.csv -> {cod_unidad (int): linea_reporte (str)}.
    Lanza ValueError si hay codigos duplicados o no numericos.
    """
    ruta = Path(ruta) if ruta else _RULES_DIR / "centro_linea.csv"
    df = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    faltan = {"cod_unidad", "linea_reporte"} - set(df.columns)
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas {sorted(faltan)}")

    cod = pd.to_numeric(df["cod_unidad"], errors="coerce")
    if cod.isna().any():
        malos = df.loc[cod.isna(), "cod_unidad"].tolist()
        raise ValueError(f"{ruta.name}: cod_unidad no numerico: {malos}")
    cod = cod.astype(int)

    if cod.duplicated().any():
        dup = sorted(cod[cod.duplicated()].unique().tolist())
        raise ValueError(f"{ruta.name}: cod_unidad duplicado: {dup}")

    linea = df["linea_reporte"].fillna("").str.strip()
    if (linea == "").any():
        vacios = cod[linea == ""].tolist()
        raise ValueError(f"{ruta.name}: linea_reporte vacia para {vacios}")

    return dict(zip(cod, linea))


def cargar_prorrateo(ruta: str | Path | None = None) -> dict:
    """
    Carga prorrateo_lineas.csv -> {linea: pct (float)}, en el orden del CSV.

    Valida que los porcentajes sumen 1.0000 EXACTO (aritmetica decimal
    sobre el texto del CSV, sin error de punto flotante). Lanza ValueError
    si no suman 1, si hay lineas duplicadas o porcentajes negativos.
    """
    ruta = Path(ruta) if ruta else _RULES_DIR / "prorrateo_lineas.csv"
    df = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    faltan = {"linea", "pct"} - set(df.columns)
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas {sorted(faltan)}")

    lineas = df["linea"].fillna("").str.strip()
    if lineas.duplicated().any():
        dup = sorted(lineas[lineas.duplicated()].unique().tolist())
        raise ValueError(f"{ruta.name}: linea duplicada: {dup}")

    try:
        pcts = [Decimal(str(p).strip()) for p in df["pct"]]
    except InvalidOperation as e:
        raise ValueError(f"{ruta.name}: pct no numerico") from e

    if any(p < 0 for p in pcts):
        raise ValueError(f"{ruta.name}: hay porcentajes negativos")

    total = sum(pcts, Decimal(0))
    if total != Decimal(1):
        raise ValueError(
            f"{ruta.name}: los porcentajes deben sumar 1.0000 exacto, "
            f"suman {total} (diferencia {total - Decimal(1)})"
        )

    return {l: float(p) for l, p in zip(lineas, pcts)}


def _validar_reglas(centro_linea: dict, prorrateo: dict) -> None:
    """Toda linea del prorrateo debe ser una linea de reporte conocida
    (evita que un error de tipeo o de tilde cree una linea fantasma)."""
    conocidas = set(LINEA_POR_EMPRESA.values()) | {
        l for l in centro_linea.values() if l != PRORRATEO
    }
    desconocidas = sorted(set(prorrateo) - conocidas)
    if desconocidas:
        raise ValueError(
            "prorrateo_lineas.csv tiene lineas que no existen en "
            f"centro_linea.csv ni en los diarios propios: {desconocidas}"
        )


def lineas_reporte(centro_linea: dict | None = None,
                   prorrateo: dict | None = None) -> list:
    """Lista ordenada de Lineas de Reporte (orden de prorrateo_lineas.csv,
    seguido de cualquier linea de centro_linea.csv que no este ahi)."""
    centro_linea = cargar_centro_linea() if centro_linea is None else centro_linea
    prorrateo = cargar_prorrateo() if prorrateo is None else prorrateo
    orden = list(prorrateo)
    for l in list(centro_linea.values()) + list(LINEA_POR_EMPRESA.values()):
        if l != PRORRATEO and l not in orden:
            orden.append(l)
    return orden


def centros_sin_regla(df: pd.DataFrame,
                      centro_linea: dict | None = None) -> pd.DataFrame:
    """
    Centros de costo del Diario GEMCO presentes en df que NO tienen regla
    en centro_linea.csv. Devuelve un DataFrame (vacio si todo esta bien)
    con columnas: Cod_Unidad, Nombre Unidad, filas, monto, meses.

    df: base consolidada (o solo el diario GEMCO limpio) con Cod_Unidad.
    """
    centro_linea = cargar_centro_linea() if centro_linea is None else centro_linea
    if "Cod_Unidad" not in df.columns:
        raise ValueError("El DataFrame no tiene la columna 'Cod_Unidad' "
                         "(la genera transformacion.diarios.limpiar_gemco).")

    propios = df["Empresa"].isin(LINEA_POR_EMPRESA)
    sin_regla = ~propios & ~df["Cod_Unidad"].isin(list(centro_linea))
    sub = df[sin_regla]

    cols = ["Cod_Unidad", "Nombre Unidad", "filas", "monto", "meses"]
    if sub.empty:
        return pd.DataFrame(columns=cols)

    nombre = (sub["Nombre Unidad"] if "Nombre Unidad" in sub.columns
              else pd.Series("", index=sub.index))
    tmp = pd.DataFrame({
        "Cod_Unidad": sub["Cod_Unidad"],
        "Nombre Unidad": nombre.fillna("").astype(str),
        "monto": sub[_COL_MONTO],
        "mes": sub["Fecha"].dt.month,
    })
    res = (
        tmp.groupby(["Cod_Unidad", "Nombre Unidad"], dropna=False)
        .agg(filas=("monto", "size"),
             monto=("monto", "sum"),
             meses=("mes", lambda s: sorted({int(m) for m in s.dropna()})))
        .reset_index()
    )
    return res[cols]


def asignar_lineas(df: pd.DataFrame,
                   centro_linea: dict | None = None,
                   prorrateo: dict | None = None) -> pd.DataFrame:
    """
    Devuelve una COPIA expandida de la base consolidada con dos columnas
    nuevas: Linea_Reporte y Centro_Origen. El df recibido no se modifica.

    - Diarios propios (Incardia / MMQ / Tecservice): Linea_Reporte segun
      LINEA_POR_EMPRESA; Centro_Origen = la empresa.
    - Diario GEMCO: Linea_Reporte segun centro_linea.csv por Cod_Unidad;
      Centro_Origen = Nombre Unidad.
    - Centros "PRORRATEO": cada fila se explota en una fila por linea con
      pct > 0, con Cargo/abono (ML) x pct. Linea_Reporte = linea destino;
      Centro_Origen = nombre del centro original y Cod_Unidad se conserva
      (trazabilidad: Cod_Unidad de un centro prorrateado identifica las
      filas que vienen del reparto).
    - Cod_Unidad sin regla: Linea_Reporte = "Sin asignar".

    El resto de las columnas (GAV, Empresa_Comercial, Linea_Negocio, etc.)
    se copia tal cual, por lo que calcular_eerr() aplica exactamente las
    mismas reglas que en el consolidado.
    """
    centro_linea = cargar_centro_linea() if centro_linea is None else centro_linea
    prorrateo = cargar_prorrateo() if prorrateo is None else prorrateo
    _validar_reglas(centro_linea, prorrateo)

    if "Cod_Unidad" not in df.columns:
        raise ValueError("El DataFrame no tiene la columna 'Cod_Unidad' "
                         "(la genera transformacion.diarios.limpiar_gemco).")

    out = df.copy()

    linea_empresa = out["Empresa"].map(LINEA_POR_EMPRESA)
    linea_centro = out["Cod_Unidad"].map(centro_linea)
    es_propio = linea_empresa.notna()

    out["Linea_Reporte"] = (
        linea_empresa.where(es_propio, linea_centro)
        .fillna(SIN_ASIGNAR).astype(object)
    )

    nombre_unidad = (out["Nombre Unidad"] if "Nombre Unidad" in out.columns
                     else pd.Series(pd.NA, index=out.index, dtype=object))
    cod_txt = out["Cod_Unidad"].astype("string").fillna(SIN_ASIGNAR)
    centro_gemco = nombre_unidad.where(nombre_unidad.notna(), cod_txt)
    out["Centro_Origen"] = (
        out["Empresa"].where(es_propio, centro_gemco).astype(object)
    )

    # Explosion de los centros a prorratear
    es_prorrateo = out["Linea_Reporte"] == PRORRATEO
    directas = out[~es_prorrateo]
    a_repartir = out[es_prorrateo]

    partes = [directas]
    for linea, pct in prorrateo.items():
        if pct == 0 or a_repartir.empty:
            continue
        parte = a_repartir.copy()
        parte["Linea_Reporte"] = linea
        parte[_COL_MONTO] = parte[_COL_MONTO] * pct
        partes.append(parte)

    return pd.concat(partes, ignore_index=True)
