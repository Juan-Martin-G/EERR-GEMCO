"""
tests/_curvas_j_ref.py
======================
Referencia INDEPENDIENTE para los tests de la hoja "Curvas J": lee el
bloque curvas_j de docs/datos_lineas.json y recalcula en Python, sin usar
el codigo del panel ni calculo/curvas_j.py, lo que el panel calcula en el
navegador (acumulados, brecha, cumplimiento y su formato de texto).

La usan tests/test_curvas_j.py y tests/test_curvas_j_ui.py: los acumulados
que se verifican en uno son los mismos que el otro compara contra los
graficos.
"""

import json
import math
from itertools import accumulate
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
DOCS = RAIZ / "docs"
JSON_PANEL = DOCS / "datos_eerr.json"
JSON_LINEAS = DOCS / "datos_lineas.json"
EXCEL_PPTO = RAIZ / "data" / "raw" / "PPTO_V2.xlsx"

TOTAL = "Total GEMCO"
LINEAS = [
    "MMQ", "Incardia", "TECSERVICE",
    "Equipos Esterilización", "Consumibles Esterilización",
    "Equipos Endoscopía", "Consumibles Endoscopía", "Equipos Dental",
]
ORDEN = [TOTAL] + LINEAS
EXCLUIDA = "Consumibles Dental"
CONCEPTO = "Resultado del Ejercicio"

MILLON = 1_000_000
ABR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
       "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MENOS = "−"


def leer_json(ruta):
    if not ruta.exists():
        pytest.skip(f"No existe {ruta}. Correr generar_datos.py")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def leer_curvas_j():
    lineas = leer_json(JSON_LINEAS)
    if "curvas_j" not in lineas:
        pytest.fail("docs/datos_lineas.json no tiene el bloque curvas_j. "
                    "Correr generar_datos.py")
    return lineas["curvas_j"]


def acumular(mensuales):
    """Serie acumulada (pesos) de una serie mensual."""
    return list(accumulate(mensuales))


def acumulados(curvas_j):
    """{linea: {"ppto": [12 acumulados], "real": [n acumulados]}}, en pesos."""
    return {
        linea: {"ppto": acumular(bloque["ppto_mensual"]),
                "real": acumular(bloque["real_mensual"])}
        for linea, bloque in curvas_j["lineas"].items()
    }


# ── Formato del panel (reimplementado aqui) ────────────────────────────────

def _redondear(x):
    """Redondeo a entero como Math.round de JavaScript (mitades hacia arriba)."""
    return math.floor(x + 0.5)


def _miles(entero):
    return f"{entero:,}".replace(",", ".")


def texto_m(pesos, con_signo=False):
    """Pesos -> texto en M$ con 1 decimal: 1.234,5 / −1.234,5 / +1.234,5."""
    decimas = _redondear(pesos / MILLON * 10)
    signo = MENOS if decimas < 0 else ("+" if con_signo and decimas > 0 else "")
    return f"{signo}{_miles(abs(decimas) // 10)},{abs(decimas) % 10}"


def texto_cumplimiento(real_acum, ppto_acum):
    if ppto_acum <= 0:
        return "n/a"
    pct = _redondear(real_acum / ppto_acum * 100)
    return f"{MENOS if pct < 0 else ''}{_miles(abs(pct))}%"


def lineas_tooltip(curvas_j, linea, i):
    """Textos que debe mostrar el tooltip del mes de indice i (0 = enero)."""
    bloque = curvas_j["lineas"][linea]
    ac = acumulados(curvas_j)[linea]
    hay_real = i < len(bloque["real_mensual"])
    out = []
    if hay_real:
        out.append(f"Real del mes: {texto_m(bloque['real_mensual'][i])} M$")
    out.append(f"Ppto del mes: {texto_m(bloque['ppto_mensual'][i])} M$")
    if hay_real:
        out.append(f"Real acum: {texto_m(ac['real'][i])} M$")
    out.append(f"Ppto acum: {texto_m(ac['ppto'][i])} M$")
    if hay_real:
        out.append(f"Brecha acum: {texto_m(ac['real'][i] - ac['ppto'][i], True)} M$")
        out.append(f"Cumplimiento: {texto_cumplimiento(ac['real'][i], ac['ppto'][i])}")
    return out


def subtitulo(curvas_j, linea):
    """Texto bajo el titulo de cada grafico."""
    ac = acumulados(curvas_j)[linea]
    n = len(ac["real"])
    real, ppto = ac["real"][n - 1], ac["ppto"][n - 1]
    return (f"{ABR[n - 1]}: Real {texto_m(real)} | Ppto {texto_m(ppto)} | "
            f"Brecha {texto_m(real - ppto, True)} M$")
