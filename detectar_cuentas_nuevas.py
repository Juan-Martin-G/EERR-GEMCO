"""
detectar_cuentas_nuevas.py
==========================
Revisa los datos fuente antes de regenerar el panel y avisa de elementos
nuevos que todavia no tienen regla.

USO:
    python detectar_cuentas_nuevas.py

Chequeos:
  - Centros de costo (columna "Unidad de Negocio" del Diario GEMCO) sin
    regla en data/rules/centro_linea.csv. Sin regla, sus filas caen en la
    linea "Sin asignar" del EERR por Linea de Negocio.

Codigo de salida: 0 si no hay nada nuevo, 1 si hay algo que revisar.
"""

import sys

import pandas as pd

from transformacion.diarios import limpiar_gemco
from transformacion.lineas import centros_sin_regla

ARCHIVO_V11 = "data/raw/v8.xlsx"


def detectar_centros_nuevos(df_gemco_limpio: pd.DataFrame) -> pd.DataFrame:
    """
    Centros de costo del Diario GEMCO (ya limpio, con Cod_Unidad) que no
    estan en data/rules/centro_linea.csv.
    Columnas: Cod_Unidad, Nombre Unidad, filas, monto, meses.
    """
    return centros_sin_regla(df_gemco_limpio)


def _avisar_centros_nuevos(df_gemco_limpio: pd.DataFrame) -> bool:
    """Imprime el aviso. Retorna True si hay centros sin regla."""
    nuevos = detectar_centros_nuevos(df_gemco_limpio)
    if nuevos.empty:
        print("OK - Todos los centros de costo tienen regla en centro_linea.csv")
        return False

    print(f"ATENCION - {len(nuevos)} centro(s) de costo SIN regla en "
          "data/rules/centro_linea.csv:")
    for _, f in nuevos.iterrows():
        cod = "(vacio)" if pd.isna(f["Cod_Unidad"]) else int(f["Cod_Unidad"])
        print(f"  - {cod}  {f['Nombre Unidad']}: {int(f['filas'])} fila(s), "
              f"monto {f['monto']:,.0f}, meses {f['meses']}")
    print("  Agregar una fila 'cod_unidad,linea_reporte' por cada uno "
          "(una linea de reporte, o PRORRATEO).")
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"Leyendo Diario GEMCO de {ARCHIVO_V11}...")
    df_gemco = limpiar_gemco(pd.read_excel(ARCHIVO_V11, sheet_name="Diario GEMCO"))

    hay_novedades = _avisar_centros_nuevos(df_gemco)
    return 1 if hay_novedades else 0


if __name__ == "__main__":
    sys.exit(main())
