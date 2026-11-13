// app.js — Panel EERR estático · GitHub Pages

// ═══════════════════════════════════════════════════════════════════
//  CONSTANTES
// ═══════════════════════════════════════════════════════════════════
const FILAS_PCT = new Set(['% Margen', '% EBITDA', '% EBITDA Empresa']);
const PCT_NR = {
  '% Margen':         'Margen Bruto',
  '% EBITDA':         'EBITDA Directo',
  '% EBITDA Empresa': 'EBITDA Empresa'
};
const ABR = {
  1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',
  7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'
};
const CR = '#2c5f7c', CP = '#7fb3c8', CPs = '#4a9e8c', CN = '#d97b5f';
const CE = {GEMCO:'#2c5f7c', Incardia:'#4a9e8c', MMQ:'#8c6a2c', Tecservice:'#7f8c9c'};

// Etiquetas de pantalla de los conceptos del EERR: clave interna (la de
// los JSON y de Python, que no cambia) -> nombre completo que se muestra.
// Es el único lugar donde se decide cómo se llama un concepto en pantalla:
// EERR (filas y drill), Líneas (Acumulado y Detalle), Gráficos y mensajes.
// Fuente de los nombres: filas del PPTO V2 / EERR de la V8 / mapeo_clasif.
// "Subtotal GAV" no tiene la sigla desarrollada en ninguna fuente.
const ETIQUETAS_CONCEPTO = {
  'Ingresos':                        'Ingresos',
  'Costo de ventas':                 'Costo de ventas',
  'Margen Bruto':                    'Margen Bruto',
  '% Margen':                        '% Margen',
  'GPBE Directos':                   'Gastos por Beneficios a los Empleados Directos',
  'GPBE Indirectos':                 'Gastos por Beneficios a los Empleados Indirectos',
  'GPBE Total':                      'Gastos por Beneficios a los Empleados Total',
  'OGPN Directos':                   'Otros Gastos por Naturaleza Directos',
  'OGPN Indirectos':                 'Otros Gastos por Naturaleza Indirectos',
  'OGPN Total':                      'Otros Gastos por Naturaleza Total',
  'Subtotal GAV':                    'Subtotal GAV',
  'EBITDA Directo':                  'EBITDA Directo',
  '% EBITDA':                        '% EBITDA',
  'Finiquitos':                      'Finiquitos',
  'Multas':                          'Multas',
  'Provisión Obsolescencias':        'Provisión Obsolescencias Inventarios',
  'Provisión Incobrables':           'Provisión Incobrables',
  'Provisión Habilitación Oficinas': 'Provisión Habilitación Oficinas',
  'Gastos Adicionales':              'Gastos Adicionales',
  'EBITDA Empresa':                  'EBITDA Empresa',
  '% EBITDA Empresa':                '% EBITDA Empresa',
  'Depreciación':                    'Depreciación y Amortización',
  'Resultado Operacional':           'Resultado Operacional',
  'Otros Ingresos por Función':      'Otros Ingresos por Función',
  'Ingreso Financiero':              'Ingreso Financiero',
  'Costo Financiero':                'Costo Financiero',
  'Otros Gastos por Función':        'Otros Gastos por Función',
  'Diferencia de Cambio':            'Diferencia de Cambio',
  'Resultado No Operacional':        'Resultado No Operacional',
  'Resultado antes Impuestos':       'Resultado antes de Impuestos',
  'Impuesto a la Renta':             'Impuesto a la Renta',
  'Resultado del Ejercicio':         'Resultado del Ejercicio',
};
function etiqueta(c) { return ETIQUETAS_CONCEPTO[c] ?? c; }

// Ratios Costo/Ingresos de la hoja "Ratios". Cada uno se calcula como
// ABS(suma de conceptosCosto) / ABS(Ingresos) * 100.
const RATIOS = [
  { key: 'costo_ventas',  label: 'Costo de Ventas',               conceptos: ['Costo de ventas'] },
  { key: 'gpbe',          label: 'Gasto x Beneficios Empleados',  conceptos: ['GPBE Total'] },
  { key: 'ogpn',          label: 'Otros Gastos por Naturaleza',   conceptos: ['OGPN Total'] },
  { key: 'gav_indirecto', label: 'GAV Indirecto',                 conceptos: ['GPBE Indirectos', 'OGPN Indirectos'] },
  { key: 'gav_total',     label: 'GAV Totales',                   conceptos: ['Subtotal GAV'] },
  { key: 'costo_total',   label: 'Costo Total',                   conceptos: ['Costo de ventas', 'Subtotal GAV'] },
];

// ═══════════════════════════════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════════════════════════════
let DATA       = null;
let mesesA     = new Set([1,2,3,4,5]);
let empActivos = new Set(['Consolidado']); // 'Consolidado' o Set de empresas individuales
let varD       = false, varPct = false, enMM = false, hojaA = 'eerr';

// Drill-down tabla
let exConc = new Set();
let exEmp  = {};

// Instancias Chart.js
let cM=null, cW=null, cD=null;

// Estado gráficos
let gVista = 'bar', gReal = true, gPpto = true;

// Estado ratios
let rtCosto = RATIOS[0].key;
let cRatio  = null;

// Estado hoja Líneas (EERR por Línea de Negocio)
let LIN        = null;       // datos_lineas.json: se descarga la primera vez que se abre la hoja
let linCarga   = null;       // descarga en curso (Promise)
let linMeses   = new Set();  // meses a sumar (solo meses con Real); al iniciar, todos
let exLin      = new Set();  // conceptos expandidos (drill por centro de origen)
let linVista   = 'acum';     // 'acum' (una columna por línea) | 'detalle' (una línea, mes a mes)
let linLinea   = null;       // línea elegida en el Detalle; null = la primera. LIN_TOTAL = consolidado
const LIN_TOTAL = '__total__';

// Estado hoja Curvas J (usa el mismo datos_lineas.json, bloque curvas_j)
let cjCharts   = [];         // instancias Chart.js, una por línea

// ═══════════════════════════════════════════════════════════════════
//  FETCH Y ARRANQUE
// ═══════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  fetch('datos_eerr.json')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => { DATA = d; init(); })
    .catch(e => {
      document.getElementById('loading').innerHTML =
        `<p style="color:#d97b5f;font-size:15px">Error al cargar datos: ${e.message}</p>` +
        `<p style="font-size:12px;color:#666;margin-top:8px">` +
        `Abre el sitio con un servidor local:<br>` +
        `<code style="background:#eee;padding:2px 6px;border-radius:3px">` +
        `python -m http.server 8000</code> desde la carpeta <code>docs/</code></p>`;
    });
});

function init() {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('app').style.display     = 'flex';
  buildMesesBtns();
  buildEmpBtns();
  document.getElementById('eerr-tbody').addEventListener('click', handleDrill);
  renderTable();
  initGrafControls();
  initRatiosControls();
  buildLinMesesBtns();
  document.getElementById('lin-tbody').addEventListener('click', handleDrillLin);
  setHoja('eerr');
}

// ═══════════════════════════════════════════════════════════════════
//  NAVEGACIÓN
// ═══════════════════════════════════════════════════════════════════
function setHoja(h) {
  hojaA = h;
  document.querySelectorAll('.nav-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.hoja === h));
  document.getElementById('view-eerr').style.display     = h === 'eerr'     ? '' : 'none';
  document.getElementById('view-graf').style.display     = h === 'graficos' ? '' : 'none';
  document.getElementById('view-ratios').style.display   = h === 'ratios'   ? '' : 'none';
  document.getElementById('view-lineas').style.display   = h === 'lineas'   ? '' : 'none';
  document.getElementById('view-curvas').style.display   = h === 'curvas'   ? '' : 'none';
  document.getElementById('sel-eerr-ctrl').style.display = h === 'eerr'     ? '' : 'none';
  // La hoja Líneas tiene su propio selector de meses (solo meses con Real,
  // la misma selección para todas las columnas) y no usa el de Empresa.
  // La hoja Curvas J no tiene selectores: se oculta la fila completa.
  const sinMesEmpresa = h === 'lineas' || h === 'curvas';
  document.getElementById('sel-lineas-ctrl').style.display = h === 'lineas' ? '' : 'none';
  document.getElementById('sel-grp-meses').style.display   = sinMesEmpresa ? 'none' : '';
  document.getElementById('sel-grp-empresa').style.display = sinMesEmpresa ? 'none' : '';
  document.getElementById('sel-row').style.display         = h === 'curvas' ? 'none' : '';
  if (h === 'graficos') renderGraf();
  if (h === 'ratios')   renderRatios();
  if (h === 'lineas')   abrirLineas();
  if (h === 'curvas')   abrirCurvas();
}

// ═══════════════════════════════════════════════════════════════════
//  SELECTORES — MESES
// ═══════════════════════════════════════════════════════════════════
function buildMesesBtns() {
  const c = document.getElementById('sel-meses');
  for (let m = 1; m <= 12; m++) {
    const b = document.createElement('button');
    b.className = 'sel-btn' + (mesesA.has(m) ? ' active' : '');
    b.textContent = ABR[m];
    b.dataset.mes = m;
    b.onclick = () => {
      if (mesesA.has(m)) mesesA.delete(m); else mesesA.add(m);
      if (!mesesA.size) for (let i = 1; i <= 12; i++) mesesA.add(i);
      document.querySelectorAll('#sel-meses .sel-btn').forEach(x =>
        x.classList.toggle('active', mesesA.has(+x.dataset.mes)));
      renderTable();
      if (hojaA === 'graficos') renderGraf();
      if (hojaA === 'ratios')   renderRatios();
    };
    c.appendChild(b);
  }
}

// ═══════════════════════════════════════════════════════════════════
//  SELECTORES — EMPRESA (multi-select + Consolidado mutuamente excluyente)
// ═══════════════════════════════════════════════════════════════════
function buildEmpBtns() {
  const cont = document.getElementById('sel-empresa');
  ['Consolidado', ...DATA.empresas].forEach(e => {
    const b = document.createElement('button');
    b.className = 'sel-btn' + (e === 'Consolidado' ? ' active' : '');
    b.textContent = e === 'Consolidado' ? 'Consol.' : e;
    b.dataset.emp = e;
    b.onclick = () => clickEmpresa(e);
    cont.appendChild(b);
  });
}

function clickEmpresa(e) {
  if (e === 'Consolidado') {
    // Consolidado activo: desactivar todo lo demás
    empActivos = new Set(['Consolidado']);
  } else if (empActivos.has('Consolidado')) {
    // Había Consolidado: pasar a solo esta empresa
    empActivos = new Set([e]);
  } else {
    // Multi-selección normal entre empresas individuales
    if (empActivos.has(e)) {
      empActivos.delete(e);
      if (!empActivos.size) empActivos = new Set(['Consolidado']); // fallback
    } else {
      empActivos.add(e);
    }
  }
  document.querySelectorAll('#sel-empresa .sel-btn').forEach(b =>
    b.classList.toggle('active', empActivos.has(b.dataset.emp)));
  exConc.clear(); exEmp = {};
  renderTable();
  if (hojaA === 'graficos') renderGraf();
  if (hojaA === 'ratios')   renderRatios();
}

// Las columnas de variación son las mismas para la hoja EERR y la vista
// "Detalle por línea" de la hoja Líneas (como la escala MM$).
function toggleVarD() {
  varD = !varD;
  document.getElementById('btn-vard').classList.toggle('active', varD);
  document.getElementById('btn-vard-lin').classList.toggle('active', varD);
  renderTable();
  if (LIN) renderLineas();
}
function toggleVarPct() {
  varPct = !varPct;
  document.getElementById('btn-varpct').classList.toggle('active', varPct);
  document.getElementById('btn-varpct-lin').classList.toggle('active', varPct);
  renderTable();
  if (LIN) renderLineas();
}
function toggleMM() {
  // La escala es una sola para la hoja EERR y la hoja Líneas.
  enMM = !enMM;
  document.getElementById('btn-mm').classList.toggle('active', enMM);
  document.getElementById('btn-mm-lin').classList.toggle('active', enMM);
  renderTable();
  if (LIN) renderLineas();
}

// ═══════════════════════════════════════════════════════════════════
//  FORMATEO DE NÚMEROS
// ═══════════════════════════════════════════════════════════════════
function fI(n) {
  return Math.abs(Math.round(n)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}
// Formatea un valor ya en millones con 1 decimal y separador de miles en
// la parte entera (convención chilena: punto de miles, coma decimal).
// Ej: 1234.56 -> "1.234,6"
function fMM1(nAbsMillones) {
  const [intPart, decPart] = nAbsMillones.toFixed(1).split('.');
  const intFmt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${intFmt},${decPart}`;
}
function fmt(v, mm) {
  if (v == null || isNaN(v)) return '-';
  if (mm) {
    const s = fMM1(Math.abs(v) / 1e6);
    return v < 0 ? `(${s})` : s;
  }
  return v < 0 ? `(${fI(v)})` : fI(v);
}
function fmtPct(num, ing) {
  if (num == null || !ing) return '-';
  return (num / ing * 100).toFixed(1).replace('.', ',') + '%';
}
function fmtVD(r, p, mm) {
  if (r == null || p == null) return '-';
  const d = r - p;
  if (mm) {
    const s = fMM1(Math.abs(d) / 1e6);
    return d < 0 ? `(${s})` : `+${s}`;
  }
  return d < 0 ? `(${fI(d)})` : `+${fI(d)}`;
}
function fmtVP(r, p) {
  if (r == null || p == null || p === 0) return '-';
  const pct = (r - p) / Math.abs(p) * 100;
  return (pct >= 0 ? '+' : '') + pct.toFixed(1).replace('.', ',') + '%';
}
function fmtMM(v) {
  if (v == null) return '';
  return (v / 1e6).toLocaleString('es-CL', { maximumFractionDigits: 0 }) + ' MM';
}
function fmm(v) {
  if (v == null || isNaN(v)) return '—';
  const s = (Math.abs(v) / 1e6).toLocaleString('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return v < 0 ? `(MM$${s})` : `MM$${s}`;
}
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ═══════════════════════════════════════════════════════════════════
//  HELPERS DE EMPRESA
// ═══════════════════════════════════════════════════════════════════
function esConsolidado() { return empActivos.has('Consolidado'); }
// Lista de empresas individuales para drill-down y gráficos
function empsList()      { return esConsolidado() ? DATA.empresas : [...empActivos]; }
// Etiqueta legible del alcance actual
function empLabel() {
  if (esConsolidado()) return 'Consolidado';
  const arr = [...empActivos];
  return arr.length === 1 ? arr[0] : arr.join(' + ');
}
// MMQ es la UNICA empresa activa (ni Consolidado ni combinada con otra):
// en ese caso MMQ se muestra al 100%, sin el factor de participación de
// GEMCO (ver mmq_100_real / mmq_100_linea_real en el JSON).
function mmqSolo() {
  return !esConsolidado() && empActivos.size === 1 && empActivos.has('MMQ');
}

// ═══════════════════════════════════════════════════════════════════
//  ACCESO A DATOS
// ═══════════════════════════════════════════════════════════════════
function mOrd()   { return [1,2,3,4,5,6,7,8,9,10,11,12].filter(m => mesesA.has(m)); }
function tipos()  { return ['Real','Ppto',...(varD?['Var $']:[]),...(varPct?['Var %']:[])]; }
function tiposA() { return ['Real','Ppto',...(varD?['Var $']:[]),...(varPct?['Var %']:[]),'Ppto Anual']; }

// Nivel 0: valor de concepto para el alcance activo (Consolidado o suma de empresas)
function gR(m, c) {
  if (esConsolidado()) return DATA.real['Consolidado']?.[m+'']?.[c] ?? null;
  if (mmqSolo()) return DATA.mmq_100_real?.[m+'']?.[c] ?? null;
  let total = 0, any = false;
  for (const e of empActivos) {
    const v = DATA.real[e]?.[m+'']?.[c];
    if (v != null) { total += v; any = true; }
  }
  return any ? total : null;
}
function gP(m, c) {
  if (esConsolidado()) return DATA.ppto['Consolidado']?.[m+'']?.[c] ?? null;
  let total = 0, any = false;
  for (const e of empActivos) {
    const v = DATA.ppto[e]?.[m+'']?.[c];
    if (v != null) { total += v; any = true; }
  }
  return any ? total : null;
}
function aR(c) { return [...mesesA].reduce((s, m) => s + (gR(m, c) ?? 0), 0); }
function aP(c) { return [...mesesA].reduce((s, m) => s + (gP(m, c) ?? 0), 0); }
// Ppto acumulado SIEMPRE de los 12 meses del año, sin importar la
// selección de meses del segmentador (columna "Ppto Anual").
function aPAnual(c) {
  let total = 0;
  for (let m = 1; m <= 12; m++) total += (gP(m, c) ?? 0);
  return total;
}

// Nivel 1: drill-down empresa individual (siempre datos de empresa específica)
// MMQ solo (única empresa activa en el selector) usa el bloque 100% en vez
// del bloque ponderado normal.
function deR(m, c, e) {
  if (e === 'MMQ' && mmqSolo()) return DATA.mmq_100_real?.[m+'']?.[c] ?? null;
  return DATA.drilldown_empresa_real[c]?.[m+'']?.[e] ?? null;
}
function deP(m, c, e) { return DATA.drilldown_empresa_ppto[c]?.[m+'']?.[e] ?? null; }
function aeR(c, e)    { return [...mesesA].reduce((s, m) => s + (deR(m, c, e) ?? 0), 0); }
function aeP(c, e)    { return [...mesesA].reduce((s, m) => s + (deP(m, c, e) ?? 0), 0); }
function aeAnualP(c, e) {
  let total = 0;
  for (let m = 1; m <= 12; m++) total += (deP(m, c, e) ?? 0);
  return total;
}

// Nivel 2: drill-down línea (mismo criterio MMQ solo que deR)
function lineaBlockR(c, e, m) {
  if (e === 'MMQ' && mmqSolo()) return DATA.mmq_100_linea_real[c]?.[m+''] || {};
  return DATA.drilldown_linea_real[c]?.[e]?.[m+''] || {};
}
function dlR(m, c, e, l) { return lineaBlockR(c, e, m)[l] ?? null; }
function dlP(m, c, e, l) { return DATA.drilldown_linea_ppto[c]?.[e]?.[m+'']?.[l] ?? null; }
function alR(c, e, l)    { return [...mesesA].reduce((s, m) => s + (dlR(m, c, e, l) ?? 0), 0); }
function alP(c, e, l)    { return [...mesesA].reduce((s, m) => s + (dlP(m, c, e, l) ?? 0), 0); }
function alAnualP(c, e, l) {
  let total = 0;
  for (let m = 1; m <= 12; m++) total += (dlP(m, c, e, l) ?? 0);
  return total;
}

function lineasDe(c, e) {
  const acum = {};
  for (let m = 1; m <= 12; m++) {
    const lins = lineaBlockR(c, e, m);
    Object.entries(lins).forEach(([l, v]) => { acum[l] = (acum[l] || 0) + v; });
  }
  return Object.entries(acum)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .map(([l]) => l);
}

// ═══════════════════════════════════════════════════════════════════
//  TABLA EERR — CABECERA
// ═══════════════════════════════════════════════════════════════════
function buildHead(meses, tp, ta) {
  const n = tp.length, na = ta.length;
  let h1 = `<tr><th class="th-conc sticky-l" rowspan="2">Concepto</th>`;
  meses.forEach(m => { h1 += `<th class="th-mes" colspan="${n}">${ABR[m]}</th>`; });
  h1 += `<th class="th-acum" colspan="${na}">Acumulado</th></tr>`;
  let h2 = '<tr>';
  meses.forEach(() => { tp.forEach(t => { h2 += `<th>${t}</th>`; }); });
  ta.forEach(t => { h2 += `<th class="th-acum-c">${t}</th>`; });
  h2 += '</tr>';
  document.getElementById('eerr-thead').innerHTML = h1 + h2;
}

// ═══════════════════════════════════════════════════════════════════
//  TABLA EERR — VALORES POR CELDA
// ═══════════════════════════════════════════════════════════════════
// Texto de una celda de concepto según el tipo de columna ('Real', 'Ppto',
// 'Var $', 'Var %' o 'Ppto Anual'). getR / getP / getPA: concepto -> valor
// (Real, Ppto y Ppto anual del período de la columna). La usan la hoja EERR
// (cellV, cellAcum) y la vista "Detalle por línea" de la hoja Líneas.
//  - Filas de %: Real y Ppto cada uno sobre sus propios Ingresos; "-" en Var.
//  - Var $ y Var % se calculan sobre los valores del período (en un
//    acumulado, sobre los TOTALES, nunca promediando los % mensuales).
function celdaTipo(c, t, getR, getP, getPA) {
  if (FILAS_PCT.has(c)) {
    if (t === 'Var $' || t === 'Var %') return '-';
    const get = t === 'Real' ? getR : t === 'Ppto Anual' ? getPA : getP;
    return fmtPct(get(PCT_NR[c]), get('Ingresos'));
  }
  if (t === 'Ppto Anual') return fmt(getPA(c), enMM);
  return vCell(getR(c), getP(c), t);
}

function cellV(c, m, t, isPct) {
  return celdaTipo(c, t, k => gR(m, k), k => gP(m, k), aPAnual);
}

function cellAcum(c, t, isPct) {
  return celdaTipo(c, t, aR, aP, aPAnual);
}

function vCell(r, p, t) {
  if (t === 'Real')  return fmt(r, enMM);
  if (t === 'Ppto')  return fmt(p, enMM);
  if (t === 'Var $') return fmtVD(r, p, enMM);
  return fmtVP(r, p);
}
// Variante de vCell para columnas Acumulado: intercepta 'Ppto Anual'
// (que necesita su propio valor, no el par r/p de meses seleccionados)
// y delega el resto a vCell.
function vCellAcum(r, p, pAnual, t) {
  if (t === 'Ppto Anual') return fmt(pAnual, enMM);
  return vCell(r, p, t);
}

// ═══════════════════════════════════════════════════════════════════
//  TABLA EERR — FILAS
// ═══════════════════════════════════════════════════════════════════
function buildMainRow(c, nv, tip, isPct, hasDrill, isExp, meses, tp, ta) {
  const rcls = tip === 'subtotal'   ? 'row-sub'
             : tip === 'porcentaje' ? 'row-pct' : 'row-norm';
  const icls = nv === 1 ? 'conc-n1' : 'conc-n0';
  const ddb  = hasDrill
    ? `<button class="dd-btn" data-c="${esc(c)}" data-n="1">${isExp ? '−' : '+'}</button>`
    : '<span class="dd-sp"></span>';
  let row = `<tr class="${rcls}">`;
  row += `<td class="td-c sticky-l ${icls}">${ddb}${esc(etiqueta(c))}</td>`;
  meses.forEach(m => { tp.forEach(t => { row += `<td class="td-v">${cellV(c, m, t, isPct)}</td>`; }); });
  ta.forEach(t => { row += `<td class="td-v td-acum">${cellAcum(c, t, isPct)}</td>`; });
  return row + '</tr>';
}

function buildEmpRow(c, e, meses, tp, ta, isExp) {
  const ddb = `<button class="dd-btn" data-c="${esc(c)}" data-e="${esc(e)}" data-n="2">${isExp ? '−' : '+'}</button>`;
  let row = '<tr class="row-emp">';
  row += `<td class="td-c sticky-l conc-emp">${ddb}<em>${esc(e)}</em></td>`;
  meses.forEach(m => {
    tp.forEach(t => { row += `<td class="td-v">${vCell(deR(m,c,e), deP(m,c,e), t)}</td>`; });
  });
  ta.forEach(t => { row += `<td class="td-v td-acum">${vCellAcum(aeR(c,e), aeP(c,e), aeAnualP(c,e), t)}</td>`; });
  return row + '</tr>';
}

function buildLinRow(c, e, l, meses, tp, ta) {
  let row = '<tr class="row-lin">';
  row += `<td class="td-c sticky-l conc-lin"><span class="dd-sp"></span>${esc(l)}</td>`;
  meses.forEach(m => {
    tp.forEach(t => { row += `<td class="td-v">${vCell(dlR(m,c,e,l), dlP(m,c,e,l), t)}</td>`; });
  });
  ta.forEach(t => { row += `<td class="td-v td-acum">${vCellAcum(alR(c,e,l), alP(c,e,l), alAnualP(c,e,l), t)}</td>`; });
  return row + '</tr>';
}

// ═══════════════════════════════════════════════════════════════════
//  TABLA EERR — RENDER
// ═══════════════════════════════════════════════════════════════════
function renderTable() {
  const meses = mOrd(), tp = tipos(), ta = tiposA();
  buildHead(meses, tp, ta);
  rebuildBody(meses, tp, ta);
}

function rebuildBody(meses, tp, ta) {
  if (!meses) { meses = mOrd(); tp = tipos(); ta = tiposA(); }
  const cont = document.getElementById('tbl-cont');
  const sl = cont.scrollLeft;
  let html = '';

  for (const [c, nv, tip] of DATA.estructura_eerr) {
    const isPct    = FILAS_PCT.has(c);
    const hasDrill = DATA.conceptos_con_drilldown.includes(c);
    const isExp    = exConc.has(c);
    html += buildMainRow(c, nv, tip, isPct, hasDrill, isExp, meses, tp, ta);

    if (isExp && hasDrill) {
      const emps = empsList(); // Consolidado → DATA.empresas; individuales → las seleccionadas
      emps.forEach(e => {
        const eExp = !!exEmp[c]?.has(e);
        html += buildEmpRow(c, e, meses, tp, ta, eExp);
        if (eExp) {
          lineasDe(c, e).forEach(l => { html += buildLinRow(c, e, l, meses, tp, ta); });
        }
      });
    }
  }

  document.getElementById('eerr-tbody').innerHTML = html;
  cont.scrollLeft = sl;
}

// ═══════════════════════════════════════════════════════════════════
//  DRILL-DOWN HANDLER
// ═══════════════════════════════════════════════════════════════════
function handleDrill(e) {
  const btn = e.target.closest('.dd-btn');
  if (!btn) return;
  const c = btn.dataset.c, n = +btn.dataset.n, emp = btn.dataset.e;
  if (n === 1) {
    if (exConc.has(c)) { exConc.delete(c); delete exEmp[c]; }
    else exConc.add(c);
  } else {
    if (!exEmp[c]) exEmp[c] = new Set();
    if (exEmp[c].has(emp)) exEmp[c].delete(emp); else exEmp[c].add(emp);
  }
  rebuildBody();
}

// ═══════════════════════════════════════════════════════════════════
//  GRÁFICOS — CONTROLES
// ═══════════════════════════════════════════════════════════════════
function initGrafControls() {
  // Select concepto principal (value = key corta para DATA, texto = nombre completo)
  const sc = document.getElementById('g-conc');
  DATA.estructura_eerr.forEach(([c]) => {
    const o = document.createElement('option');
    o.value = c;
    o.textContent = etiqueta(c);
    sc.appendChild(o);
  });
  sc.addEventListener('change', () => buildGMain());

  // Composición concepto
  const dc = document.getElementById('g-d-conc');
  DATA.estructura_eerr
    .filter(([c]) => !FILAS_PCT.has(c))
    .forEach(([c]) => {
      const o = document.createElement('option');
      o.value = c;
      o.textContent = etiqueta(c);
      dc.appendChild(o);
    });
}

// ═══════════════════════════════════════════════════════════════════
//  GRÁFICOS — RENDER
// ═══════════════════════════════════════════════════════════════════
function renderGraf() {
  buildGMain();
  buildGWF();
  buildGD();
}

// ── Callbacks de controles del gráfico principal ─────────────────
function setV2(btn) {
  document.querySelectorAll('[data-v2]').forEach(x => x.classList.remove('on'));
  btn.classList.add('on');
  gVista = btn.dataset.v2;
  buildGMain();
}
function toggleGReal(btn) { gReal = !gReal; btn.classList.toggle('on', gReal); buildGMain(); }
function toggleGPpto(btn) { gPpto = !gPpto; btn.classList.toggle('on', gPpto); buildGMain(); }

// ──────────────────────────────────────────────────────────────────
//  Chart 1: Real vs Presupuesto
// ──────────────────────────────────────────────────────────────────
function buildGMain() {
  const conc  = document.getElementById('g-conc').value;
  const isPct = FILAS_PCT.has(conc);
  const meses = mOrd();

  // Meses seleccionados + Acumulado al final
  const isLine = (gVista !== 'bar');
  let ra, pa;
  if (isPct) {
    ra = meses.map(m => {
      const num = gR(m, PCT_NR[conc]), ing = gR(m, 'Ingresos');
      return (num != null && ing) ? num / ing * 100 : null;
    });
    pa = meses.map(m => {
      const num = gP(m, PCT_NR[conc]), ing = gP(m, 'Ingresos');
      return (num != null && ing) ? num / ing * 100 : null;
    });
  } else {
    ra = meses.map(m => gR(m, conc));
    pa = meses.map(m => gP(m, conc));
  }

  // Acumulado
  let raAcum, paAcum;
  if (isPct) {
    const snR = meses.reduce((s,m) => s + (gR(m, PCT_NR[conc]) ?? 0), 0);
    const siR = meses.reduce((s,m) => s + (gR(m, 'Ingresos')   ?? 0), 0);
    raAcum = siR ? snR / siR * 100 : null;
    const snP = meses.reduce((s,m) => s + (gP(m, PCT_NR[conc]) ?? 0), 0);
    const siP = meses.reduce((s,m) => s + (gP(m, 'Ingresos')   ?? 0), 0);
    paAcum = siP ? snP / siP * 100 : null;
  } else {
    raAcum = meses.reduce((s,m) => s + (gR(m, conc) ?? 0), 0);
    paAcum = meses.reduce((s,m) => s + (gP(m, conc) ?? 0), 0);
  }

  // Acumulado progresivo (solo valores no-pct)
  if (gVista === 'acum' && !isPct) {
    let rs = 0, ps = 0;
    ra = ra.map(v => { if (v != null) rs += v; return v != null ? rs : null; });
    pa = pa.map(v => { if (v != null) ps += v; return v != null ? ps : null; });
  }

  const labels = [...meses.map(m => ABR[m]), 'Acumulado'];
  const raFull = [...ra, raAcum];
  const paFull = [...pa, paAcum];

  const mkBg = (base, acum) => isLine ? undefined
    : [...meses.map(() => base), acum];

  const ds = [];
  if (gReal) ds.push({
    label: 'Real', data: raFull,
    backgroundColor: mkBg(CR, '#1a3040') ?? 'rgba(44,95,124,.12)',
    borderColor: CR, borderWidth: isLine ? 2 : 0, fill: isLine,
    tension: .35, pointRadius: isLine ? 4 : 0,
    borderRadius: isLine ? 0 : 4, spanGaps: true
  });
  if (gPpto) ds.push({
    label: 'Presupuesto', data: paFull,
    backgroundColor: mkBg(CP, '#3f6d8a') ?? 'rgba(127,179,200,.08)',
    borderColor: CP, borderWidth: isLine ? 2 : 0,
    borderDash: isLine ? [5, 5] : undefined, fill: false,
    tension: .35, pointRadius: isLine ? 4 : 0,
    borderRadius: isLine ? 0 : 4, spanGaps: true
  });

  const fmtTip = v => v == null ? null
    : ' ' + (isPct ? v.toFixed(1).replace('.', ',') + '%' : fmm(v));

  if (cM) cM.destroy();
  cM = new Chart(document.getElementById('g-cM'), {
    type: isLine ? 'line' : 'bar',
    data: { labels, datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'center', labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => { const v = ctx.raw; if (v == null) return null; return fmtTip(v); } } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 } } },
        y: { grid: { color: '#edf0f7' }, ticks: {
          callback: v => isPct ? v.toFixed(1) + '%' : fmtMM(v),
          font: { size: 11 }
        }}
      }
    }
  });
}

// ──────────────────────────────────────────────────────────────────
//  Chart 2: Cascada EBITDA (usa empresa compartida)
// ──────────────────────────────────────────────────────────────────
// GAV se separa en sus 2 componentes (GPBE y OGPN) como barras flotantes
// individuales entre Margen Bruto y EBITDA Directo.
const WF_CONCEPTOS = ['Ingresos','Costo de ventas','Margen Bruto','GPBE Total','OGPN Total','EBITDA Directo','Gastos Adicionales','EBITDA Empresa'];
const WF_LABELS    = WF_CONCEPTOS.map(etiqueta); // nombres completos, sin abreviar
const WF_ES_TOTAL  = [false, false, true, false, false, true, false, true];

// Parte una etiqueta larga en varias líneas (por palabra) para que el
// eje X de un gráfico angosto la muestre completa, sin abreviarla.
function wrapLabel(s, maxLen = 16) {
  const words = s.split(' ');
  const lines = [];
  let cur = '';
  words.forEach(w => {
    if ((cur + ' ' + w).trim().length > maxLen && cur) { lines.push(cur); cur = w; }
    else cur = (cur + ' ' + w).trim();
  });
  if (cur) lines.push(cur);
  return lines;
}

function buildGWF() {
  const meses = mOrd();

  // Suma usando gR (respeta empActivos)
  const sums = {};
  WF_CONCEPTOS.forEach(c => {
    sums[c] = meses.reduce((s, m) => s + (gR(m, c) ?? 0), 0);
  });

  const bars = [], cols = [];
  let run = 0;
  WF_CONCEPTOS.forEach((c, i) => {
    const v = sums[c];
    if (WF_ES_TOTAL[i]) {
      bars.push([0, v]);
      cols.push(v >= 0 ? CR : CN);
      run = v;
    } else {
      const en = run + v;
      bars.push([Math.min(run, en), Math.max(run, en)]);
      cols.push(v >= 0 ? CPs : CN);
      run = en;
    }
  });

  const periodo = meses.length === 1
    ? ABR[meses[0]]
    : ABR[meses[0]] + '–' + ABR[meses[meses.length - 1]] + ' (acum.)';
  const tEl = document.getElementById('g-wf-titulo');
  if (tEl) tEl.textContent = empLabel() + ' · ' + periodo;

  if (cW) cW.destroy();
  cW = new Chart(document.getElementById('g-cW'), {
    type: 'bar',
    data: {
      labels: WF_LABELS,
      datasets: [{ data: bars, backgroundColor: cols, borderRadius: 3, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx =>
          ' ' + WF_LABELS[ctx.dataIndex] + ': ' + fmm(sums[WF_CONCEPTOS[ctx.dataIndex]])
        }}
      },
      scales: {
        x: { grid: { display: false }, ticks: {
          font: { size: 9 }, maxRotation: 0, minRotation: 0, autoSkip: false,
          callback: (val, idx) => wrapLabel(WF_LABELS[idx])
        } },
        y: { grid: { color: '#edf0f7' }, ticks: { callback: fmtMM, font: { size: 10 } } }
      }
    }
  });
}

// ──────────────────────────────────────────────────────────────────
//  Chart 3: Composición por Empresa
// ──────────────────────────────────────────────────────────────────
function buildGD() {
  const conc  = document.getElementById('g-d-conc').value;
  const meses = mOrd();
  const vals  = DATA.empresas.map(e =>
    meses.reduce((s, m) => s + (DATA.real[e]?.[m+'']?.[conc] ?? 0), 0)
  );
  if (cD) cD.destroy();
  cD = new Chart(document.getElementById('g-cD'), {
    type: 'bar',
    data: {
      labels: DATA.empresas,
      datasets: [{ data: vals, backgroundColor: DATA.empresas.map(e => CE[e]), borderRadius: 4 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ' ' + ctx.label + ': ' + fmm(ctx.raw) } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        y: { grid: { color: '#edf0f7' }, ticks: { callback: fmtMM, font: { size: 10 } } }
      }
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — CÁLCULO (Costo / Ingresos, respeta empresa/MMQ vía gR/gP)
// ═══════════════════════════════════════════════════════════════════
function costoR(m, ratio) { return ratio.conceptos.reduce((s, c) => s + (gR(m, c) ?? 0), 0); }
function costoP(m, ratio) { return ratio.conceptos.reduce((s, c) => s + (gP(m, c) ?? 0), 0); }

function ratioPct(costo, ingresos) {
  if (ingresos == null || ingresos === 0) return null;
  return Math.abs(costo) / Math.abs(ingresos) * 100;
}

function ratioMesR(m, ratio) { return ratioPct(costoR(m, ratio), gR(m, 'Ingresos')); }
function ratioMesP(m, ratio) { return ratioPct(costoP(m, ratio), gP(m, 'Ingresos')); }

// Acumulado = costo acumulado / ingreso acumulado (NO promedio de % mensuales)
function ratioAcumR(ratio) {
  const costo = [...mesesA].reduce((s, m) => s + costoR(m, ratio), 0);
  return ratioPct(costo, aR('Ingresos'));
}
function ratioAcumP(ratio) {
  const costo = [...mesesA].reduce((s, m) => s + costoP(m, ratio), 0);
  return ratioPct(costo, aP('Ingresos'));
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — FORMATO Y COLOR
// ═══════════════════════════════════════════════════════════════════
function fmtRatio(v) { return v == null ? '-' : v.toFixed(1).replace('.', ',') + '%'; }
// Var % relativo, mismo criterio que "Var %" de la tabla EERR:
// (Real - Ppto) / ABS(Ppto) * 100. "-" si Ppto es 0 (division por cero).
function fmtVarPct(r, p) {
  if (r == null || p == null || p === 0) return '-';
  const pct = (r - p) / Math.abs(p) * 100;
  return (pct < 0 ? '-' : '+') + Math.abs(pct).toFixed(1).replace('.', ',') + '%';
}
// Semáforo por magnitud del ratio: >=90% rojo, 70-90% ámbar, <70% verde.
function rtCellClass(v) {
  if (v == null) return '';
  if (v >= 90) return 'rt-hi';
  if (v >= 70) return 'rt-mid';
  return 'rt-lo';
}
// VAR: positivo (costo real relativamente mayor al presupuestado) = desfavorable.
// El signo de (Real-Ppto) es el mismo tanto en pp como en % relativo (ABS(Ppto)
// solo escala la magnitud, nunca invierte el signo), asi que el criterio
// favorable/desfavorable sigue siendo valido sin ajuste de umbral.
function rtVarClass(r, p) {
  if (r == null || p == null || p === 0) return '';
  const d = r - p;
  if (d > 0) return 'rt-var-bad';
  if (d < 0) return 'rt-var-good';
  return '';
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — CONTROLES
// ═══════════════════════════════════════════════════════════════════
function initRatiosControls() {
  const cont = document.getElementById('rt-sel-costo');
  RATIOS.forEach(r => {
    const b = document.createElement('button');
    b.className = 'gb' + (r.key === rtCosto ? ' on' : '');
    b.textContent = r.label;
    b.dataset.key = r.key;
    b.onclick = () => selectRatio(r.key);
    cont.appendChild(b);
  });
}

function selectRatio(key) {
  rtCosto = key;
  document.querySelectorAll('#rt-sel-costo .gb').forEach(b =>
    b.classList.toggle('on', b.dataset.key === key));
  renderRatios();
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — MATRIZ (tabla)
// ═══════════════════════════════════════════════════════════════════
function rtBuildHead(meses) {
  let h1 = `<tr><th class="th-conc sticky-l" rowspan="2">Indicador</th>`;
  meses.forEach(m => { h1 += `<th class="th-mes" colspan="3">${ABR[m]}</th>`; });
  h1 += `<th class="th-acum" colspan="3">Total</th></tr>`;
  let h2 = '<tr>';
  meses.forEach(() => { ['Real', 'Ppto', 'Var'].forEach(t => { h2 += `<th>${t}</th>`; }); });
  ['Real', 'Ppto', 'Var'].forEach(t => { h2 += `<th class="th-acum-c">${t}</th>`; });
  h2 += '</tr>';
  document.getElementById('rt-thead').innerHTML = h1 + h2;
}

function rtBuildRow(ratio, meses) {
  const active = ratio.key === rtCosto;
  let row = `<tr class="${active ? 'rt-row-active' : ''}">`;
  row += `<td class="td-c sticky-l">${esc(ratio.label)}</td>`;
  meses.forEach(m => {
    const r = ratioMesR(m, ratio), p = ratioMesP(m, ratio);
    row += `<td class="td-v ${rtCellClass(r)}">${fmtRatio(r)}</td>`;
    row += `<td class="td-v ${rtCellClass(p)}">${fmtRatio(p)}</td>`;
    row += `<td class="td-v ${rtVarClass(r, p)}">${fmtVarPct(r, p)}</td>`;
  });
  const rAc = ratioAcumR(ratio), pAc = ratioAcumP(ratio);
  row += `<td class="td-v td-acum ${rtCellClass(rAc)}">${fmtRatio(rAc)}</td>`;
  row += `<td class="td-v td-acum ${rtCellClass(pAc)}">${fmtRatio(pAc)}</td>`;
  row += `<td class="td-v td-acum ${rtVarClass(rAc, pAc)}">${fmtVarPct(rAc, pAc)}</td>`;
  return row + '</tr>';
}

function rtRenderBody(meses) {
  document.getElementById('rt-tbody').innerHTML = RATIOS.map(r => rtBuildRow(r, meses)).join('');
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — GRÁFICO COMBINADO (barras Ingresos/Costo + línea Ratio)
// ═══════════════════════════════════════════════════════════════════
function buildRatioChart(meses) {
  const ratio = RATIOS.find(r => r.key === rtCosto);
  const labels = meses.map(m => ABR[m]);
  // Magnitud absoluta para comparar visualmente Ingresos vs Costo (mismo
  // criterio que el ratio, que también usa ABS() de ambos).
  const ingR   = meses.map(m => { const v = gR(m, 'Ingresos'); return v == null ? null : Math.abs(v); });
  const costR  = meses.map(m => Math.abs(costoR(m, ratio)));
  const ratR   = meses.map(m => ratioMesR(m, ratio));
  const ratP   = meses.map(m => ratioMesP(m, ratio));

  const titEl = document.getElementById('rt-graf-titulo');
  if (titEl) titEl.textContent = `Ingresos vs ${ratio.label} · ${empLabel()}`;

  const ds = [
    { type: 'bar', label: 'Ingresos', data: ingR, backgroundColor: CR,
      yAxisID: 'y', borderRadius: 4, order: 3 },
    { type: 'bar', label: ratio.label, data: costR, backgroundColor: '#a8452a',
      yAxisID: 'y', borderRadius: 4, order: 3 },
    { type: 'line', label: 'Ratio Real', data: ratR, yAxisID: 'y1',
      borderColor: '#c9902e', backgroundColor: '#c9902e', borderWidth: 2,
      tension: .3, pointRadius: 3, spanGaps: true, order: 1 },
    { type: 'line', label: 'Ratio Ppto', data: ratP, yAxisID: 'y1',
      borderColor: '#c9902e', backgroundColor: '#c9902e', borderWidth: 2,
      borderDash: [5, 5], tension: .3, pointRadius: 3, spanGaps: true, order: 2 },
  ];

  if (cRatio) cRatio.destroy();
  cRatio = new Chart(document.getElementById('rt-chart'), {
    data: { labels, datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'center', labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => {
          const v = ctx.raw;
          if (v == null) return null;
          if (ctx.dataset.yAxisID === 'y1') return ' ' + ctx.dataset.label + ': ' + v.toFixed(1).replace('.', ',') + '%';
          return ' ' + ctx.dataset.label + ': ' + fmm(v);
        } } }
      },
      scales: {
        x:  { grid: { display: false }, ticks: { font: { size: 11 } } },
        y:  { position: 'left', grid: { color: '#edf0f7' }, ticks: { callback: fmtMM, font: { size: 11 } } },
        y1: { position: 'right', grid: { display: false },
              ticks: { callback: v => v.toFixed(0) + '%', font: { size: 11 } } }
      }
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  RATIOS — RENDER
// ═══════════════════════════════════════════════════════════════════
function renderRatios() {
  const meses = mOrd();
  rtBuildHead(meses);
  rtRenderBody(meses);
  buildRatioChart(meses);
}

// ═══════════════════════════════════════════════════════════════════
//  LÍNEAS — EERR POR LÍNEA DE NEGOCIO
// ═══════════════════════════════════════════════════════════════════
// Columnas = líneas de negocio + Total; filas = los mismos conceptos de la
// hoja EERR. Los datos están en datos_lineas.json (generar_datos.py), que
// se descarga la primera vez que se abre la hoja.
//
// Cada valor es la SUMA de los meses seleccionados (uno o varios), calculada
// aquí desde los bloques mensuales del JSON. La clave "Acumulado" del JSON
// no se usa. Los porcentajes se recalculan desde los totales ya sumados.

// ── Selector de meses (selección múltiple, como el de la hoja EERR) ──
// Diferencias con el de la hoja EERR: solo ofrece los meses con Real, y
// puede quedar vacío (la hoja muestra un aviso en vez de la tabla).
function buildLinMesesBtns() {
  const cont = document.getElementById('sel-meses-lin');
  linMeses = new Set(DATA.meta.meses_con_real);   // al abrir: todos los meses con Real
  DATA.meta.meses_con_real.forEach(m => {
    const b = document.createElement('button');
    b.className = 'sel-btn active';
    b.textContent = ABR[m];
    b.dataset.mes = m;
    b.onclick = () => {
      if (linMeses.has(m)) linMeses.delete(m); else linMeses.add(m);
      linCambioMeses();
    };
    cont.appendChild(b);
  });
  linPintarPeriodo();
}
function linSelTodos()   { linMeses = new Set(DATA.meta.meses_con_real); linCambioMeses(); }
function linSelLimpiar() { linMeses = new Set(); linCambioMeses(); }

function linCambioMeses() {
  document.querySelectorAll('#sel-meses-lin .sel-btn').forEach(x =>
    x.classList.toggle('active', linMeses.has(+x.dataset.mes)));
  linPintarPeriodo();
  if (LIN) renderLineas();   // los conceptos expandidos (exLin) se conservan
}

// Meses seleccionados, en orden.
function linMesesSel() { return DATA.meta.meses_con_real.filter(m => linMeses.has(m)); }

// "Ene–Sep" si los meses son consecutivos; "Ene, Mar, May" si no lo son.
function linPeriodoTxt() {
  const ms = linMesesSel();
  if (!ms.length) return '';
  if (ms.length === 1) return ABR[ms[0]];
  const consecutivos = ms.every((m, i) => i === 0 || m === ms[i - 1] + 1);
  return consecutivos
    ? `${ABR[ms[0]]}–${ABR[ms[ms.length - 1]]}`
    : ms.map(m => ABR[m]).join(', ');
}

// Texto del período activo: sobre la tabla y al inicio de la nota al pie.
// En la vista Detalle se agrega la línea elegida.
function linPintarPeriodo() {
  const n = linMesesSel().length, txt = linPeriodoTxt();
  const detalle = linVista === 'detalle' && !!LIN;
  const linea   = detalle ? linLineaNombre() : '';
  document.getElementById('lin-periodo-txt').textContent = n ? txt : 'ningún mes seleccionado';
  document.getElementById('lin-periodo-linea').style.display = detalle ? '' : 'none';
  document.getElementById('lin-periodo-linea-txt').textContent = linea;
  document.getElementById('lin-nota-periodo').textContent = !n ? ''
    : detalle
      ? `Línea: ${linea}. ` + (n === 1 ? `Período: ${txt}. `
          : `Período: ${txt} (columnas por mes; «Total período» es la suma de los ${n} meses seleccionados). `)
    : n === 1 ? `Período: ${txt}. `
    : `Período: ${txt} (suma de los ${n} meses seleccionados). `;
  // La nota del presupuesto solo va en el Detalle (la única vista con Ppto).
  document.getElementById('lin-nota-ppto').style.display = linVista === 'detalle' ? '' : 'none';
}

// ── Vistas de la hoja ────────────────────────────────────────────
// "Acumulado por línea": una columna por línea, cada una con la suma de los
// meses seleccionados (solo Real). "Detalle por línea": una sola línea (o
// el total consolidado), Real vs Presupuesto como en la hoja EERR: por cada
// mes seleccionado Real | Ppto | [Var $] | [Var %], luego "Total período"
// (si hay más de un mes) y "Ppto Anual".
// Las dos usan el mismo selector de meses, la misma escala y los mismos
// conceptos expandidos; cambiar de vista no toca nada de eso.
function linSetVista(v) {
  linVista = v === 'detalle' ? 'detalle' : 'acum';
  document.querySelectorAll('#sel-vista-lin .sel-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.vista === linVista));
  const detalle = linVista === 'detalle';
  document.getElementById('sel-linea-grp').style.display = detalle ? '' : 'none';
  document.getElementById('sel-var-lin').style.display   = detalle ? '' : 'none';
  linPintarPeriodo();
  if (LIN) renderLineas();
}

function linSetLinea(v) {
  linLinea = v;
  linPintarPeriodo();
  if (LIN) renderLineas();
}

// Línea del Detalle: la elegida o, si aún no se eligió ninguna, la primera.
function linLineaSel() {
  const lineas = linLineas();
  return linLinea === LIN_TOTAL || lineas.includes(linLinea) ? linLinea : lineas[0];
}
function linLineaNombre() {
  const l = linLineaSel();
  return l === LIN_TOTAL ? 'Total consolidado' : l;
}

// Desplegable de línea (se llena una vez, cuando ya están los datos).
function linBuildLineaSel() {
  const sel = document.getElementById('sel-linea-lin');
  if (!sel.options.length) {
    [...linLineas().map(l => [l, l]), [LIN_TOTAL, 'Total consolidado']].forEach(([valor, texto]) => {
      const o = document.createElement('option');
      o.value = valor;
      o.textContent = texto;
      sel.appendChild(o);
    });
  }
  sel.value = linLineaSel();
}

// ── Descarga de datos (solo la primera vez) ──────────────────────
function cargarLineas() {
  if (LIN) return Promise.resolve(LIN);
  if (!linCarga) {
    linCarga = fetch('datos_lineas.json')
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(d => {
        if (!d.lineas_real || !d.lineas_total_real || !d.lineas_drill_real) {
          throw new Error('el archivo no tiene el formato esperado');
        }
        LIN = d;
        return d;
      })
      .catch(e => { linCarga = null; throw e; }); // permite reintentar al reabrir la hoja
  }
  return linCarga;
}

function linMensaje(html, esError) {
  const msg = document.getElementById('lin-msg');
  msg.className = 'lin-msg' + (esError ? ' err' : '');
  msg.innerHTML = html;
  msg.style.display = '';
  document.getElementById('lin-tbl').style.display  = 'none';
  document.getElementById('lin-nota').style.display = 'none';
}

function abrirLineas() {
  if (LIN) { renderLineas(); return; }
  linMensaje('Cargando datos por línea de negocio…', false);
  cargarLineas()
    .then(() => renderLineas())
    .catch(e => linMensaje(
      `No se pudieron cargar los datos de la hoja Líneas (datos_lineas.json): ${esc(e.message)}.` +
      `<small>El resto del panel sigue funcionando. Vuelve a abrir esta pestaña para ` +
      `reintentar; si el problema continúa, hay que regenerar y publicar el archivo ` +
      `con generar_datos.py.</small>`, true));
}

// ── Acceso a datos ───────────────────────────────────────────────
function linLineas()   { return Object.keys(LIN.lineas_real); }
// Suma de un concepto en un conjunto de meses (por defecto, los
// seleccionados), dentro de un bloque {mes: {concepto: valor}}.
// null si ningún mes trae el dato.
function linSuma(porMes, c, meses = linMesesSel()) {
  let total = 0, any = false;
  for (const m of meses) {
    const v = porMes?.[m + '']?.[c];
    if (v != null) { total += v; any = true; }
  }
  return any ? total : null;
}
function linVal(l, c)  { return linSuma(LIN.lineas_real[l], c); }
function linTot(c)     { return linSuma(LIN.lineas_total_real, c); }

// Drill de un concepto: {centro: suma} sobre un conjunto de líneas y de
// meses. Igual que en el JSON, se omiten los centros cuya suma es 0.
function linDrillCentros(c, lineas, meses) {
  const acum = {};
  lineas.forEach(l => meses.forEach(m => {
    const porCentro = LIN.lineas_drill_real[c]?.[l]?.[m + ''] || {};
    Object.entries(porCentro).forEach(([k, v]) => { acum[k] = (acum[k] || 0) + v; });
  }));
  Object.keys(acum).forEach(k => { if (acum[k] === 0) delete acum[k]; });
  return acum;
}

// Centros de origen que aportan en alguna de las columnas: primero los
// diarios propios (Incardia / MMQ / Tecservice), luego los centros de
// costo por código.
function linCentros(mapas) {
  const claves = new Set();
  mapas.forEach(mapa => Object.keys(mapa).forEach(k => claves.add(k)));
  const esCod = k => /^\d+$/.test(k);
  return [...claves].sort((a, b) => {
    if (esCod(a) !== esCod(b)) return esCod(a) ? 1 : -1;
    return esCod(a) ? a - b : a.localeCompare(b);
  });
}

// ── Columnas de la tabla ─────────────────────────────────────────
// Las dos vistas dibujan la misma tabla; solo cambia qué es cada columna:
//   grupo    texto de la fila superior del encabezado (mes o "Total
//            período"); null si la columna ocupa las dos filas
//   titulo   texto del encabezado (en las columnas con grupo, el tipo:
//            Real / Ppto / Var $ / Var %)
//   total    true en las columnas de total (Total, Total período, Ppto Anual)
//   texto    concepto -> texto de la celda
//   drill    concepto -> {centro: valor} de la columna, o null si la
//            columna no tiene desglose por centro (queda en blanco)
//   control  meses sobre los que la columna muestra la fila de control
//            (Total líneas − Consolidado), o null si no aplica
const MESES_ANIO = [1,2,3,4,5,6,7,8,9,10,11,12];

// Texto de un concepto con el valor de get (los % se recalculan con los
// totales de la columna).
function linTexto(c, get) {
  return FILAS_PCT.has(c) ? fmtPct(get(PCT_NR[c]), get('Ingresos')) : fmt(get(c), enMM);
}

function linColumnas() {
  const meses = linMesesSel();
  const todas = linLineas();

  if (linVista !== 'detalle') {
    // Acumulado por línea: una columna por línea + Total, todas con la
    // suma de los meses seleccionados. Solo Real.
    return [
      ...todas.map(l => ({
        grupo: null, titulo: l, total: false, control: null,
        texto: c => linTexto(c, k => linVal(l, k)),
        drill: c => linDrillCentros(c, [l], meses),
      })),
      { grupo: null, titulo: 'Total', total: true, control: meses,
        texto: c => linTexto(c, linTot),
        drill: c => linDrillCentros(c, todas, meses) },
    ];
  }

  // Detalle por línea: Real vs Presupuesto con las mismas columnas que la
  // hoja EERR (tipos(): Real, Ppto, [Var $], [Var %]) en cada mes y en
  // "Total período" (si hay más de un mes), y al final "Ppto Anual".
  // Real: lineas_real (o lineas_total_real). Ppto: lineas_ppto de la línea,
  // o el presupuesto consolidado del panel para "Total consolidado". Una
  // línea sin presupuesto (Consumibles Dental) muestra "-".
  const linea   = linLineaSel();
  const esTotal = linea === LIN_TOTAL;
  const bloqueR = esTotal ? LIN.lineas_total_real : LIN.lineas_real[linea];
  const bloqueP = esTotal ? DATA.ppto['Consolidado'] : (LIN.lineas_ppto?.[linea] ?? null);
  const lineas  = esTotal ? todas : [linea];
  const getPA   = k => linSuma(bloqueP, k, MESES_ANIO);

  const grupo = (titulo, ms, total) => tipos().map(t => {
    const getR = k => linSuma(bloqueR, k, ms);
    const getP = k => linSuma(bloqueP, k, ms);
    return {
      grupo: titulo, titulo: t, total,
      control: esTotal && t === 'Real' ? ms : null,
      texto: c => celdaTipo(c, t, getR, getP, getPA),
      // El presupuesto no tiene centro de origen: solo Real se desglosa.
      drill: t === 'Real' ? (c => linDrillCentros(c, lineas, ms)) : null,
    };
  });

  const cols = meses.flatMap(m => grupo(ABR[m], [m], false));
  if (meses.length > 1) cols.push(...grupo('Total período', meses, true));
  cols.push({
    grupo: null, titulo: 'Ppto Anual', total: true, control: null,
    texto: c => celdaTipo(c, 'Ppto Anual', null, null, getPA),
    drill: null,
  });
  return cols;
}

// ── Cabecera ─────────────────────────────────────────────────────
// Acumulado: una sola fila. Detalle: dos filas como la hoja EERR (arriba el
// mes, abajo el tipo de columna); "Ppto Anual" ocupa las dos filas.
// (los porcentajes del prorrateo siguen en LIN.lineas_prorrateo, pero
// no se muestran en la hoja)
function linBuildHead(cols) {
  const dosFilas = cols.some(col => col.grupo);
  const rs = dosFilas ? ' rowspan="2"' : '';
  let h1 = `<tr><th class="th-conc sticky-l"${rs}>Concepto</th>`;
  let h2 = '<tr class="th-sub">';
  for (let i = 0; i < cols.length; i++) {
    const col = cols[i];
    if (!col.grupo) {
      h1 += `<th${rs}${col.total ? ' class="th-acum"' : ''}>${esc(col.titulo)}</th>`;
      continue;
    }
    let n = 1;
    while (i + n < cols.length && cols[i + n].grupo === col.grupo) n++;
    h1 += `<th class="${col.total ? 'th-acum' : 'th-mes'}" colspan="${n}">${esc(col.grupo)}</th>`;
    cols.slice(i, i + n).forEach(c2 => {
      h2 += `<th${c2.total ? ' class="th-acum-c"' : ''}>${esc(c2.titulo)}</th>`;
    });
    i += n - 1;
  }
  document.getElementById('lin-thead').innerHTML = h1 + '</tr>' + (dosFilas ? h2 + '</tr>' : '');
}

// ── Filas ────────────────────────────────────────────────────────
// Conceptos cuya comparación Real vs Ppto POR LÍNEA depende del criterio de
// reparto de los costos compartidos (distinto en el Real y en el
// presupuesto). En el Detalle de una línea llevan "†"; en el Total
// consolidado no (el reparto no cambia el total). Incluye los subtotales y
// porcentajes que contienen alguno de ellos.
const MARCA_REPARTO = new Set([
  'GPBE Indirectos', 'GPBE Total', 'OGPN Indirectos', 'OGPN Total',
  'Subtotal GAV', 'EBITDA Directo', '% EBITDA',
  'Finiquitos', 'Provisión Habilitación Oficinas', 'Gastos Adicionales',
  'EBITDA Empresa', '% EBITDA Empresa', 'Depreciación', 'Resultado Operacional',
  'Costo Financiero', 'Diferencia de Cambio', 'Resultado No Operacional',
  'Resultado antes Impuestos', 'Impuesto a la Renta', 'Resultado del Ejercicio',
]);
const MARCA_REPARTO_TXT =
  'Comparación por línea afectada por distinto criterio de reparto entre Real y Presupuesto';

function linMainRow(c, nv, tip, cols, hasDrill, isExp, conMarca) {
  const rcls  = tip === 'subtotal'   ? 'row-sub'
              : tip === 'porcentaje' ? 'row-pct' : 'row-norm';
  const icls  = nv === 1 ? 'conc-n1' : 'conc-n0';
  const ddb   = hasDrill
    ? `<button class="dd-btn" data-c="${esc(c)}">${isExp ? '−' : '+'}</button>`
    : '<span class="dd-sp"></span>';
  // &nbsp;: la † no baja sola a otra línea cuando el nombre se parte
  const marca = conMarca && MARCA_REPARTO.has(c)
    ? `&nbsp;<span class="lin-rep" title="${esc(MARCA_REPARTO_TXT)}">†</span>` : '';
  let row = `<tr class="${rcls}" data-c="${esc(c)}">`;
  row += `<td class="td-c sticky-l ${icls}">${ddb}${esc(etiqueta(c))}${marca}</td>`;
  cols.forEach(col => {
    row += `<td class="td-v${col.total ? ' td-acum' : ''}">${col.texto(c)}</td>`;
  });
  return row + '</tr>';
}

// Fila de un centro de origen. mapas[i] = {centro: valor} de la columna i,
// o null si la columna no tiene desglose (Ppto, Var, Ppto Anual: en blanco).
// En las columnas de total un centro sin valor es 0; en las demás, "-".
function linCentroRow(c, k, cols, mapas, prorrateados) {
  const etiqueta = LIN.lineas_centros?.[k] ?? k;
  const sufijo   = prorrateados.has(k) ? ' (prorrateo)' : '';
  let row = `<tr class="row-emp" data-drill="${esc(c)}">`;
  row += `<td class="td-c sticky-l conc-emp"><span class="dd-sp"></span><em>${esc(etiqueta)}</em>${sufijo}</td>`;
  cols.forEach((col, i) => {
    const txt = !mapas[i] ? '' : fmt(mapas[i][k] ?? (col.total ? 0 : null), enMM);
    row += `<td class="td-v${col.total ? ' td-acum' : ''}">${txt}</td>`;
  });
  return row + '</tr>';
}

// Fila de control: Total líneas − Consolidado, revisado en TODOS los
// conceptos. Cada columna con control muestra la mayor diferencia de sus
// meses (siempre en pesos); debe ser 0. Si algún concepto difiere en más
// de 1 peso se marca en rojo, y los del período completo se nombran.
// En el Detalle de una sola línea no hay nada que controlar: no se dibuja.
function linControlRow(cols) {
  if (!cols.some(col => col.control)) return '';
  const difsDe = meses => DATA.estructura_eerr
    .filter(([c]) => !FILAS_PCT.has(c))
    .map(([c]) => [c, (linSuma(LIN.lineas_total_real, c, meses) ?? 0)
                      - (linSuma(DATA.real['Consolidado'], c, meses) ?? 0)]);
  const peorDe  = difs => difs.reduce((a, b) => Math.abs(b[1]) > Math.abs(a[1]) ? b : a, ['', 0])[1];
  const malosDe = difs => difs.filter(([, d]) => Math.abs(d) > 1);

  // El detalle "No cuadra" es el de la última columna con control: el Total.
  const malos = malosDe(difsDe([...cols].reverse().find(col => col.control).control));
  const det   = malos.length
    ? `<br><span class="rt-var-bad">No cuadra: ${malos.map(([c, d]) => `${esc(etiqueta(c))} ${fmt(d, false)}`).join('; ')}</span>`
    : '';
  let row = `<tr class="row-sub" id="lin-control">`;
  row += `<td class="td-c sticky-l conc-n0"><span class="dd-sp"></span>Total líneas − Consolidado (mayor diferencia, en pesos)${det}</td>`;
  cols.forEach(col => {
    const acum = col.total ? ' td-acum' : '';
    if (!col.control) { row += `<td class="td-v${acum}"></td>`; return; }
    const difs = difsDe(col.control);
    const cls  = malosDe(difs).length ? ' rt-var-bad' : '';
    row += `<td class="td-v${acum}${cls}">${fmt(peorDe(difs), false)}</td>`;
  });
  return row + '</tr>';
}

// ── Render ───────────────────────────────────────────────────────
function renderLineas() {
  linBuildLineaSel();
  linPintarPeriodo();
  if (!linMesesSel().length) {
    linMensaje('Selecciona al menos un mes.', false);
    return;
  }
  document.getElementById('lin-msg').style.display  = 'none';
  document.getElementById('lin-tbl').style.display  = '';
  document.getElementById('lin-nota').style.display = '';
  const cols = linColumnas();
  linBuildHead(cols);
  linRebuildBody(cols);
}

function linRebuildBody(cols) {
  if (!cols) cols = linColumnas();
  const cont = document.getElementById('lin-cont');
  const sl = cont.scrollLeft, st = cont.scrollTop;
  const prorrateados = new Set(LIN.lineas_centros_prorrateados || []);
  const conMarca = linVista === 'detalle' && linLineaSel() !== LIN_TOTAL;
  let html = '';

  for (const [c, nv, tip] of DATA.estructura_eerr) {
    const hasDrill = !FILAS_PCT.has(c) && !!LIN.lineas_drill_real[c];
    const isExp    = hasDrill && exLin.has(c);
    html += linMainRow(c, nv, tip, cols, hasDrill, isExp, conMarca);
    if (isExp) {
      const mapas = cols.map(col => col.drill ? col.drill(c) : null);
      // Filas: los centros con valor en alguna columna con desglose que no
      // sea de total.
      linCentros(mapas.filter((m, i) => m && !cols[i].total))
        .forEach(k => { html += linCentroRow(c, k, cols, mapas, prorrateados); });
    }
  }
  html += linControlRow(cols);

  document.getElementById('lin-tbody').innerHTML = html;
  cont.scrollLeft = sl;
  cont.scrollTop  = st;
}

// ── Drill-down por centro de origen ──────────────────────────────
function handleDrillLin(e) {
  const btn = e.target.closest('.dd-btn');
  if (!btn) return;
  const c = btn.dataset.c;
  if (exLin.has(c)) exLin.delete(c); else exLin.add(c);
  linRebuildBody();
}

// ═══════════════════════════════════════════════════════════════════
//  CURVAS J — RESULTADO DEL EJERCICIO ACUMULADO, REAL vs PRESUPUESTO
// ═══════════════════════════════════════════════════════════════════
// Un gráfico por línea (Total GEMCO + 8 líneas). Los datos vienen en el
// bloque curvas_j de datos_lineas.json (generar_datos.py), que trae solo
// valores MENSUALES en pesos: los acumulados se calculan aquí. Se usa el
// mismo archivo y la misma descarga que la hoja Líneas (cargarLineas), así
// que nunca se baja dos veces.
//
// Presupuesto: 12 meses. Real: de enero al último mes con Real (la curva
// termina ahí). Sin selectores: la interacción es pasar el mouse.

const CJ_MENOS = '−';   // signo menos tipográfico

// Número ya en millones -> "1.234,5" (1 decimal, formato del panel).
// conSigno: antepone "+" a los positivos (para la brecha).
function cjNum(millones, conSigno) {
  const m = Math.round(millones * 10) / 10;
  return (m < 0 ? CJ_MENOS : (conSigno && m > 0 ? '+' : '')) + fMM1(Math.abs(m));
}
// Valor en pesos -> texto en M$.
function cjM(pesos, conSigno) { return cjNum(pesos / 1e6, conSigno); }

// Cumplimiento = Real acumulado / Presupuesto acumulado. Solo tiene lectura
// si el presupuesto acumulado es positivo; si no, "n/a".
function cjCumplimiento(realAc, pptoAc) {
  if (!(pptoAc > 0)) return 'n/a';
  const p = Math.round(realAc / pptoAc * 100);
  return (p < 0 ? CJ_MENOS : '') + fI(p) + '%';
}

// id estable del canvas: "Equipos Esterilización" -> "curva-equipos-esterilizacion"
function cjId(nombre) {
  return 'curva-' + nombre.normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// Series de una línea: mensuales (del JSON) y acumuladas (calculadas aquí).
function cjSerie(nombre) {
  const b = LIN.curvas_j.lineas[nombre];
  const acum = a => { let s = 0; return a.map(v => (s += v)); };
  return {
    ppto: b.ppto_mensual, real: b.real_mensual,
    pptoAc: acum(b.ppto_mensual), realAc: acum(b.real_mensual),
  };
}

// Líneas del tooltip para el mes de índice i (0 = enero). En los meses sin
// Real solo se muestra el Presupuesto.
function cjTooltip(s, i) {
  const hayReal = i < s.real.length;
  const out = [];
  if (hayReal) out.push(`Real del mes: ${cjM(s.real[i])} M$`);
  out.push(`Ppto del mes: ${cjM(s.ppto[i])} M$`);
  if (hayReal) out.push(`Real acum: ${cjM(s.realAc[i])} M$`);
  out.push(`Ppto acum: ${cjM(s.pptoAc[i])} M$`);
  if (hayReal) {
    out.push(`Brecha acum: ${cjM(s.realAc[i] - s.pptoAc[i], true)} M$`);
    out.push(`Cumplimiento: ${cjCumplimiento(s.realAc[i], s.pptoAc[i])}`);
  }
  return out;
}

function cjMensaje(html, esError) {
  const msg = document.getElementById('cj-msg');
  msg.className = 'lin-msg' + (esError ? ' err' : '');
  msg.innerHTML = html;
  msg.style.display = '';
  document.getElementById('cj-cont').style.display = 'none';
}

function abrirCurvas() {
  if (LIN) { renderCurvas(); return; }
  cjMensaje('Cargando curvas J…', false);
  cargarLineas()
    .then(() => { if (hojaA === 'curvas') renderCurvas(); })
    .catch(e => cjMensaje(
      `No se pudieron cargar los datos de la hoja Curvas J (datos_lineas.json): ${esc(e.message)}.` +
      `<small>El resto del panel sigue funcionando. Vuelve a abrir esta pestaña para ` +
      `reintentar; si el problema continúa, hay que regenerar y publicar el archivo ` +
      `con generar_datos.py.</small>`, true));
}

function cjChart(canvas, cj, s) {
  const cero = ctx => ctx.tick && ctx.tick.value === 0;
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels: cj.meses.map(m => ABR[+m]),
      datasets: [
        { label: 'Real', data: s.realAc.map(v => v / 1e6),
          borderColor: CR, backgroundColor: CR, borderWidth: 2,
          pointRadius: 3, pointHoverRadius: 5,
          cubicInterpolationMode: 'monotone', fill: false },
        { label: 'Presupuesto', data: s.pptoAc.map(v => v / 1e6),
          borderColor: CP, backgroundColor: CP, borderWidth: 2, borderDash: [5, 4],
          pointRadius: 0, pointHoverRadius: 4,
          cubicInterpolationMode: 'monotone', fill: false },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          callbacks: {
            title: items => DATA.meses_nombre[cj.meses[items[0].dataIndex]],
            label: () => null,
            beforeBody: items => cjTooltip(s, items[0].dataIndex),
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 0 } },
        y: {
          beginAtZero: true,   // la línea de cero siempre queda dentro del eje
          grid: { color: ctx => cero(ctx) ? '#6b7280' : '#edf0f7',
                  lineWidth: ctx => cero(ctx) ? 1.4 : 1 },
          ticks: { maxTicksLimit: 6, font: { size: 10 }, callback: v => cjNum(v) }
        }
      }
    }
  });
}

function renderCurvas() {
  const cj = LIN.curvas_j;
  if (!cj || !cj.lineas || !Array.isArray(cj.orden) || !Array.isArray(cj.meses)) {
    cjMensaje('El archivo datos_lineas.json publicado no trae las curvas J.' +
      '<small>Hay que regenerarlo y publicarlo con generar_datos.py.</small>', true);
    return;
  }
  if (typeof Chart === 'undefined') {
    cjMensaje('No se pudo cargar la librería de gráficos (Chart.js).' +
      '<small>Revisa tu conexión a internet y recarga la página.</small>', true);
    return;
  }
  document.getElementById('cj-msg').style.display  = 'none';
  document.getElementById('cj-cont').style.display = '';

  cjCharts.forEach(c => c.destroy());
  cjCharts = [];
  const grid = document.getElementById('cj-grid');
  grid.innerHTML = '';

  const ult    = +cj.ultimo_mes_real;
  const mesUlt = DATA.meses_nombre[cj.ultimo_mes_real].toLowerCase();

  cj.orden.forEach((nombre, i) => {
    const s = cjSerie(nombre), n = s.real.length;
    const card = document.createElement('div');
    card.className = 'cj-card' + (i === 0 ? ' cj-total' : '');
    card.dataset.linea = nombre;

    const tit = document.createElement('div');
    tit.className = 'cj-tit';
    tit.textContent = nombre;

    const sub = document.createElement('div');
    sub.className = 'cj-sub';
    sub.textContent = n
      ? `${ABR[ult]}: Real ${cjM(s.realAc[n - 1])} | Ppto ${cjM(s.pptoAc[n - 1])} | ` +
        `Brecha ${cjM(s.realAc[n - 1] - s.pptoAc[n - 1], true)} M$`
      : 'Sin meses con Real';

    const cont = document.createElement('div');
    cont.className = 'cj-chart';
    const canvas = document.createElement('canvas');
    canvas.id = cjId(nombre);
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label',
      `Curva J de ${nombre}: Resultado del Ejercicio acumulado, Real y Presupuesto. ${sub.textContent}`);
    cont.appendChild(canvas);

    card.append(tit, sub, cont);
    grid.appendChild(card);
    cjCharts.push(cjChart(canvas, cj, s));
  });

  // Nota al pie: el Real de las líneas sin presupuesto se informa aparte.
  const excl = Object.entries(cj.excluido || {});
  const exclTxt = excl.length
    ? `; excluye ${excl.map(([l]) => l).join(' y ')} (sin presupuesto; Real acumulado a ${mesUlt}: ` +
      `${cjM(excl.reduce((t, [, b]) => t + b.real_mensual.reduce((a, v) => a + v, 0), 0))} M$)`
    : '';
  document.getElementById('cj-nota').textContent =
    'Resultado del Ejercicio acumulado, en M$. Presupuesto: PPTO V2 (Resultado del ejercicio ' +
    'Empresa de cada hoja de línea; TECSERVICE = TECSERVICE + SS + Reas + Trazabilidad). ' +
    'Real: según la hoja Líneas, con centros comunes prorrateados con porcentajes fijos; el ' +
    'presupuesto reparte los costos compartidos con su propio criterio, por lo que la brecha ' +
    'por línea incluye diferencias de reparto (el Total no se ve afectado). MMQ real ponderado ' +
    'por participación (0,75 / 0,875). Total GEMCO = suma de las 8 líneas' + exclTxt + '. ' +
    "Cumplimiento = Real acumulado / Presupuesto acumulado; 'n/a' si el presupuesto acumulado es ≤ 0.";
}

// ═══════════════════════════════════════════════════════════════════
//  EXPORTAR PDF (screenshot de la tabla EERR actual)
// ═══════════════════════════════════════════════════════════════════
async function exportarPDF() {
  const btn = document.getElementById('btn-pdf');
  if (typeof html2canvas === 'undefined' || typeof window.jspdf === 'undefined') {
    alert('No se pudo generar el PDF: las librerías de exportación no cargaron. Revisa tu conexión a internet e intenta nuevamente.');
    return;
  }

  const cont = document.getElementById('tbl-cont');
  const prevStyle = {
    overflow: cont.style.overflow,
    width:    cont.style.width,
    height:   cont.style.height,
  };
  // Ocultar temporalmente los botones +/- de drill-down: no deben
  // aparecer en la captura, solo los datos.
  const ddBtns = cont.querySelectorAll('.dd-btn');
  ddBtns.forEach(b => { b.dataset.prevVis = b.style.visibility; b.style.visibility = 'hidden'; });

  const prevBtnText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Generando…';

  try {
    // Expandir temporalmente el contenedor para que el scroll no oculte
    // ninguna columna/fila al momento de capturar.
    const fullW = cont.scrollWidth;
    const fullH = cont.scrollHeight;
    cont.style.overflow = 'visible';
    cont.style.width    = fullW + 'px';
    cont.style.height   = fullH + 'px';

    const canvas = await html2canvas(cont, {
      width: fullW,
      height: fullH,
      windowWidth: fullW,
      windowHeight: fullH,
      scale: 2,
      backgroundColor: '#ffffff',
    });

    // Restaurar el contenedor y los botones de drill-down ANTES de tocar jsPDF
    cont.style.overflow = prevStyle.overflow;
    cont.style.width    = prevStyle.width;
    cont.style.height   = prevStyle.height;
    ddBtns.forEach(b => { b.style.visibility = b.dataset.prevVis || ''; delete b.dataset.prevVis; });

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageW  = pdf.internal.pageSize.getWidth();
    const pageH  = pdf.internal.pageSize.getHeight();
    const margin = 10;

    // Encabezado de contexto (fecha, empresa, meses incluidos)
    const ahora    = new Date();
    const fechaTxt = ahora.toLocaleDateString('es-CL', { year: 'numeric', month: 'long', day: 'numeric' });
    const mesesTxt = mOrd().map(m => ABR[m]).join(', ');
    pdf.setFontSize(11);
    pdf.setFont(undefined, 'bold');
    pdf.text('Panel EERR GEMCO', margin, margin);
    pdf.setFontSize(8);
    pdf.setFont(undefined, 'normal');
    pdf.text(`Generado: ${fechaTxt}  ·  Empresa: ${empLabel()}  ·  Meses: ${mesesTxt}`, margin, margin + 5);

    // Escalar la imagen para que quepa COMPLETA en una sola pagina,
    // priorizando el ancho y cayendo a limitar por alto si hiciera falta.
    const headerH = 12;
    const areaW = pageW - margin * 2;
    const areaH = pageH - margin * 2 - headerH;
    const ratio = canvas.height / canvas.width;

    let drawW = areaW, drawH = drawW * ratio;
    if (drawH > areaH) { drawH = areaH; drawW = drawH / ratio; }

    const offX = margin + (areaW - drawW) / 2;
    const offY = margin + headerH + (areaH - drawH) / 2;
    // 'FAST' activa compresion en el PNG embebido - sin esto jsPDF guarda
    // el bitmap crudo sin comprimir (un PDF de varias decenas de MB).
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', offX, offY, drawW, drawH, undefined, 'FAST');

    const y  = ahora.getFullYear();
    const mo = String(ahora.getMonth() + 1).padStart(2, '0');
    const d  = String(ahora.getDate()).padStart(2, '0');
    pdf.save(`EERR_GEMCO_${y}-${mo}-${d}.pdf`);
  } catch (e) {
    // Asegurar restauracion aunque falle a mitad de camino
    cont.style.overflow = prevStyle.overflow;
    cont.style.width    = prevStyle.width;
    cont.style.height   = prevStyle.height;
    ddBtns.forEach(b => { b.style.visibility = b.dataset.prevVis || ''; delete b.dataset.prevVis; });
    alert('No se pudo generar el PDF: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = prevBtnText;
  }
}
