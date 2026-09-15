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

// Nombres completos (sin siglas) para las etiquetas de los gráficos.
// Mismo mapeo que NOMBRES_LARGOS en app/main.py.
const NOMBRES_LARGOS = {
  'GPBE Directos':   'Gastos por Beneficios a los Empleados Directos',
  'GPBE Indirectos': 'Gastos por Beneficios a los Empleados Indirectos',
  'GPBE Total':      'Gastos por Beneficios a los Empleados Total',
  'OGPN Directos':   'Otros Gastos por Naturaleza Directos',
  'OGPN Indirectos': 'Otros Gastos por Naturaleza Indirectos',
  'OGPN Total':      'Otros Gastos por Naturaleza Total',
};
function nombreLargo(c) { return NOMBRES_LARGOS[c] || c; }

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
  document.getElementById('sel-eerr-ctrl').style.display = h === 'eerr'     ? '' : 'none';
  if (h === 'graficos') renderGraf();
  if (h === 'ratios')   renderRatios();
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

function toggleVarD() {
  varD = !varD;
  document.getElementById('btn-vard').classList.toggle('active', varD);
  renderTable();
}
function toggleVarPct() {
  varPct = !varPct;
  document.getElementById('btn-varpct').classList.toggle('active', varPct);
  renderTable();
}
function toggleMM() {
  enMM = !enMM;
  document.getElementById('btn-mm').classList.toggle('active', enMM);
  renderTable();
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
  return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';
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
function tiposA() { return ['Real','Ppto','Ppto Anual',...(varD?['Var $']:[]),...(varPct?['Var %']:[])]; }

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
function cellV(c, m, t, isPct) {
  if (isPct) {
    if (t === 'Var $' || t === 'Var %') return '-';
    const nk = PCT_NR[c];
    if (t === 'Real') return fmtPct(gR(m, nk), gR(m, 'Ingresos'));
    return fmtPct(gP(m, nk), gP(m, 'Ingresos'));
  }
  const r = gR(m, c), p = gP(m, c);
  if (t === 'Real')  return fmt(r, enMM);
  if (t === 'Ppto')  return fmt(p, enMM);
  if (t === 'Var $') return fmtVD(r, p, enMM);
  return fmtVP(r, p);
}

function cellAcum(c, t, isPct) {
  if (isPct) {
    if (t === 'Var $' || t === 'Var %') return '-';
    const nk = PCT_NR[c];
    if (t === 'Real')       return fmtPct(aR(nk), aR('Ingresos'));
    if (t === 'Ppto Anual') return fmtPct(aPAnual(nk), aPAnual('Ingresos'));
    return fmtPct(aP(nk), aP('Ingresos'));
  }
  if (t === 'Real')       return fmt(aR(c), enMM);
  if (t === 'Ppto')       return fmt(aP(c), enMM);
  if (t === 'Ppto Anual') return fmt(aPAnual(c), enMM);
  // Var % acumulado: variacion relativa entre los TOTALES acumulados
  // (no promedio de los % mensuales), mismo criterio que Var $.
  if (t === 'Var %')      return fmtVP(aR(c), aP(c));
  return fmtVD(aR(c), aP(c), enMM);
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
  row += `<td class="td-c sticky-l ${icls}">${ddb}${esc(nombreLargo(c))}</td>`;
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
    o.textContent = nombreLargo(c);
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
      o.textContent = nombreLargo(c);
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
const WF_LABELS    = WF_CONCEPTOS.map(nombreLargo); // nombres completos, sin abreviar
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
