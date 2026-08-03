"""
calculo/eerr_presupuesto.py
=============================
Porta la logica COMPLETA de la medida DAX 'Valor Presupuesto2 EERR' a Python,
incluyendo las 4 ramas jerarquicas (misma prioridad que el DAX):

  1. Linea:              filtra por una Linea_Negocio especifica
  2. MultiplesEmpresas:  filtra por 2+ Empresa_Comercial (ignora Linea_Negocio)
  3. Empresa:            filtra por una sola Empresa_Comercial
  4. Consolidado:        sin filtro (Nivel='Consolidado', default)

Validado peso por peso contra:
- Resultado del Ejercicio Empresa CONSOLIDADO, Enero-Mayo 2026
- Resultado del Ejercicio Empresa INCARDIA (empresa individual), Enero 2026:
  10,738,432.26
"""


def _suma(full, concepto_padre, mes_nombre, gav=None,
          linea_negocio=None, empresa=None, empresas=None):
    m = (full['Mes'] == mes_nombre) & (full['Concepto_Padre'] == concepto_padre)

    if linea_negocio is not None:
        m = m & (full['Nivel'] == 'Linea') & (full['Linea_Negocio'] == linea_negocio)
    elif empresas is not None:
        # MultiplesEmpresas: ignora Linea_Negocio, filtra por lista de empresas
        m = m & (full['Nivel'] == 'Linea') & (full['Empresa_Comercial'].isin(empresas))
    elif empresa is not None:
        m = m & (full['Nivel'] == 'Linea') & (full['Empresa_Comercial'] == empresa)
    else:
        m = m & (full['Nivel'] == 'Consolidado')

    if gav is not None:
        m = m & (full['GAV'] == gav)

    return full[m]['Monto_Presupuesto'].sum() * 1e6


def calcular_eerr_ppto(full, mes_nombre, linea_negocio=None, empresa=None, empresas=None):
    """
    Calcula el EERR de Presupuesto para un mes, con filtro opcional.

    Parametros (excluyentes entre si, igual que la medida DAX; si no se
    pasa ninguno -> Consolidado):
        linea_negocio: nombre exacto de una Linea_Negocio
                       (ej. 'Incardia', 'Equipos Esterilización',
                        'Mantención Dental', 'Trazabilidad', etc.)
        empresa:       nombre de UNA Empresa_Comercial
                       ('GEMCO','Incardia','MMQ','Tecservice')
        empresas:      lista de 2+ Empresa_Comercial seleccionadas

    Retorna dict con cada linea del EERR en pesos (CLP).
    """
    kwargs = dict(linea_negocio=linea_negocio, empresa=empresa, empresas=empresas)

    def c(concepto_padre, gav=None):
        return _suma(full, concepto_padre, mes_nombre, gav=gav, **kwargs)

    ingresos = c('Ingresos de actividades ordinarias')
    costo_ventas = c('Costo de ventas')
    margen_bruto = ingresos + costo_ventas

    gpbe_directos = c('Gastos por beneficios a los empleados', 'GAV DIRECTO')
    gpbe_indirectos = c('Gastos por beneficios a los empleados', 'GAV INDIRECTO')
    gpbe_total = gpbe_directos + gpbe_indirectos

    ogpn_directos = c('Otros gastos por naturaleza', 'GAV DIRECTO')
    ogpn_indirectos = c('Otros gastos por naturaleza', 'GAV INDIRECTO')
    ogpn_total = ogpn_directos + ogpn_indirectos

    subtotal = gpbe_total + ogpn_total
    ebitda_directo = margen_bruto + gpbe_total + ogpn_total

    finiquitos = c('Finiquitos')
    multas = c('Multas')
    prov_obs = c('Provisión Obsolescencias Inventarios')
    prov_inc = c('Provisión Incobrales')
    prov_hab = c('Provisión Habilitación Oficinas')
    gastos_adicionales = finiquitos + multas + prov_obs + prov_inc + prov_hab

    ebitda_empresa = ebitda_directo + gastos_adicionales

    depreciacion = c('Gastos por depreciación y amortización')
    resultado_operacional = ebitda_empresa + depreciacion

    otros_ing_fun = c('Otros ingresos por función')
    ing_fin = c('Ingreso financiero')
    costo_fin = c('Costo financiero')
    otros_gas_fun = c('Otros gastos por función')
    dif_cambio = c('Diferencia de cambio')
    resultado_no_op = otros_ing_fun + ing_fin + costo_fin + otros_gas_fun + dif_cambio

    resultado_antes_imp = resultado_operacional + resultado_no_op
    impuesto = resultado_antes_imp * -0.27
    resultado_ejercicio = resultado_antes_imp + impuesto

    return {
        'Ingresos': ingresos,
        'Costo de Ventas': costo_ventas,
        'Margen Bruto': margen_bruto,
        'GPBE Directos': gpbe_directos,
        'GPBE Indirectos': gpbe_indirectos,
        'GPBE Total': gpbe_total,
        'OGPN Directos': ogpn_directos,
        'OGPN Indirectos': ogpn_indirectos,
        'OGPN Total': ogpn_total,
        'Subtotal': subtotal,
        'EBITDA Directo': ebitda_directo,
        'Finiquitos': finiquitos,
        'Multas': multas,
        'Prov Obsolescencias': prov_obs,
        'Prov Incobrables': prov_inc,
        'Prov Habilitacion': prov_hab,
        'Gastos Adicionales': gastos_adicionales,
        'EBITDA Empresa': ebitda_empresa,
        'Depreciacion': depreciacion,
        'Resultado Operacional': resultado_operacional,
        'Otros Ingresos Funcion': otros_ing_fun,
        'Ingreso Financiero': ing_fin,
        'Costo Financiero': costo_fin,
        'Otros Gastos Funcion': otros_gas_fun,
        'Diferencia Cambio': dif_cambio,
        'Resultado No Operacional': resultado_no_op,
        'Resultado Antes Impuestos': resultado_antes_imp,
        'Impuesto Renta': impuesto,
        'Resultado del Ejercicio': resultado_ejercicio,
    }
