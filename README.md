# EERR App - Estado de Resultados Consolidado

Aplicación web interna que reemplaza el dashboard Power BI de EERR para
GEMCO, Incardia, MMQ y Tecservice.

## Estructura

```
eerr_app/
├── data/
│   ├── raw/          ← Archivos Excel fuente (v8.xlsx, presupuesto.xlsx)
│   └── rules/        ← Reglas editables en CSV
│       └── mapeo_clasif.csv  ← Cuenta SAP → Nombre EERR
├── transformacion/
│   └── diarios.py    ← Limpieza de cada Diario (porta lógica de Power Query)
├── calculo/
│   └── eerr.py       ← Cálculo del EERR (porta lógica DAX)
├── tests/
│   └── test_eerr_enero.py ← Tests de regresión con valores validados
├── app/              ← Interfaz Streamlit (próxima fase)
└── requirements.txt
```

## Reglas críticas (documentadas durante validación celda a celda)

- **Signos GEMCO**: ingresos NEGATIVOS en BD, costos POSITIVOS → presentación × -1
- **Signos Incardia/MMQ/Tec**: ingresos POSITIVOS, costos NEGATIVOS → presentación × -1
- **Factor MMQ**: 0.75 para meses 1-3, 0.875 desde mes 4 (cambio participación societaria)
- **Mapeo_Clasif tiene prioridad** sobre Nombre en EERR nativo del V8 (resuelve inconsistencias, ej: cuenta 610206)
- **Excluir cuentas de balance**: código < 400000 no pertenecen al EERR
- **Excluir contrapartidas**: filas donde GAV = 'No corresponde' Y UNIDAD 2 = 'No corresponde'
- **Costo financiero**: excluir filas con GAV = 'No corresponde' (COMEX)
- **Finiquitos**: excluir Linea_Negocio = 'Sin clasificar' (contrapartida banco 110114)
- **Diario Tecservice incompleto** desde Abril: pendiente completar con Mensual Tecservice

## Instalación

```bash
pip install -r requirements.txt
```

## Correr tests

```bash
# Primero copiar el Excel V8 a data/raw/v8.xlsx
pytest tests/ -v
```

## Diferencias conocidas y aceptadas vs Excel oficial

| Concepto | Mes | PBI/Python | Excel | Motivo |
|----------|-----|-----------|-------|--------|
| Ingresos | Feb | +20,168 más | - | Tx 'Médico' sin 'E.' (aceptada) |
| Ingresos | Mar | -0.5 pesos | - | Redondeo (insignificante) |
| Costo Financiero | Feb/Mar | mayor | menor | Excel tiene error año 2025 en EERR Dental |
| Costo Ventas / GPBE | Varios | menor | mayor | Diario Tecservice incompleto desde Abril |
