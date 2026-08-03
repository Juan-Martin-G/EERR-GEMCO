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
let gVista = 'bar', gReal = true, gPpto = true, gPorLinea = false;

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
  document.getElementById('sel-eerr-ctrl').style.display = h === 'eerr'     ? '' : 'none';
  if (h === 'graficos') renderGraf();
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
function fmt(v, mm) {
  if (v == null || isNaN(v)) return '-';
  if (mm) {
    const s = (Math.abs(v) / 1e6).toFixed(1).replace('.', ',');
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
    const s = (Math.abs(d) / 1e6).toFixed(1).replace('.', ',');
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
function tiposA() { return ['Real','Ppto',...(varD?['Var $']:[])]; }

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

// Nivel 2: drill-down línea (mismo criterio MMQ solo que deR)
function lineaBlockR(c, e, m) {
  if (e === 'MMQ' && mmqSolo()) return DATA.mmq_100_linea_real[c]?.[m+''] || {};
  return DATA.drilldown_linea_real[c]?.[e]?.[m+''] || {};
}
function dlR(m, c, e, l) { return lineaBlockR(c, e, m)[l] ?? null; }
function dlP(m, c, e, l) { return DATA.drilldown_linea_ppto[c]?.[e]?.[m+'']?.[l] ?? null; }
function alR(c, e, l)    { return [...mesesA].reduce((s, m) => s + (dlR(m, c, e, l) ?? 0), 0); }
function alP(c, e, l)    { return [...mesesA].reduce((s, m) => s + (dlP(m, c, e, l) ?? 0), 0); }

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
    if (t === 'Var $') return '-';
    const nk = PCT_NR[c];
    if (t === 'Real') return fmtPct(aR(nk), aR('Ingresos'));
    return fmtPct(aP(nk), aP('Ingresos'));
  }
  const ar = aR(c), ap = aP(c);
  if (t === 'Real')  return fmt(ar, enMM);
  if (t === 'Ppto')  return fmt(ap, enMM);
  return fmtVD(ar, ap, enMM);
}

function vCell(r, p, t) {
  if (t === 'Real')  return fmt(r, enMM);
  if (t === 'Ppto')  return fmt(p, enMM);
  if (t === 'Var $') return fmtVD(r, p, enMM);
  return fmtVP(r, p);
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
  row += `<td class="td-c sticky-l ${icls}">${ddb}${esc(c)}</td>`;
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
  ta.forEach(t => { row += `<td class="td-v td-acum">${vCell(aeR(c,e), aeP(c,e), t)}</td>`; });
  return row + '</tr>';
}

function buildLinRow(c, e, l, meses, tp, ta) {
  let row = '<tr class="row-lin">';
  row += `<td class="td-c sticky-l conc-lin"><span class="dd-sp"></span>${esc(l)}</td>`;
  meses.forEach(m => {
    tp.forEach(t => { row += `<td class="td-v">${vCell(dlR(m,c,e,l), dlP(m,c,e,l), t)}</td>`; });
  });
  ta.forEach(t => { row += `<td class="td-v td-acum">${vCell(alR(c,e,l), alP(c,e,l), t)}</td>`; });
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
  // Select concepto principal
  const sc = document.getElementById('g-conc');
  DATA.estructura_eerr.forEach(([c]) => {
    const o = document.createElement('option');
    o.value = o.textContent = c;
    sc.appendChild(o);
  });
  sc.addEventListener('change', () => { updateLineaBtn(); buildGMain(); });

  // Composición concepto
  const dc = document.getElementById('g-d-conc');
  DATA.estructura_eerr
    .filter(([c]) => !FILAS_PCT.has(c))
    .forEach(([c]) => {
      const o = document.createElement('option');
      o.value = o.textContent = c;
      dc.appendChild(o);
    });
}

// ═══════════════════════════════════════════════════════════════════
//  GRÁFICOS — RENDER
// ═══════════════════════════════════════════════════════════════════
function renderGraf() {
  updateLineaBtn();
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

function toggleGLinea(btn) {
  const conc = document.getElementById('g-conc').value;
  if (!DATA.conceptos_con_drilldown.includes(conc)) return;
  gPorLinea = !gPorLinea;
  btn.classList.toggle('on', gPorLinea);
  buildGMain();
}

function updateLineaBtn() {
  const btn = document.getElementById('btn-linea');
  if (!btn) return;
  const conc     = document.getElementById('g-conc').value;
  const hasDrill = DATA.conceptos_con_drilldown.includes(conc);
  btn.disabled      = !hasDrill;
  btn.style.opacity = hasDrill ? '' : '0.35';
  btn.style.cursor  = hasDrill ? '' : 'default';
  if (!hasDrill && gPorLinea) {
    gPorLinea = false;
    btn.classList.remove('on');
  }
}

// ──────────────────────────────────────────────────────────────────
//  Chart 1: Real vs Presupuesto
// ──────────────────────────────────────────────────────────────────
function buildGMain() {
  const conc     = document.getElementById('g-conc').value;
  const isPct    = FILAS_PCT.has(conc);
  const hasDrill = DATA.conceptos_con_drilldown.includes(conc);
  const meses    = mOrd();

  // ── Modo Por Línea de Negocio ───────────────────────────────────
  if (gPorLinea && hasDrill) {
    const emps = empsList();
    const acumR = {}, acumP = {};
    emps.forEach(e => {
      meses.forEach(m => {
        const lR = lineaBlockR(conc, e, m);
        Object.entries(lR).forEach(([l, v]) => { acumR[l] = (acumR[l] || 0) + v; });
        const lP = DATA.drilldown_linea_ppto[conc]?.[e]?.[m+''] || {};
        Object.entries(lP).forEach(([l, v]) => { acumP[l] = (acumP[l] || 0) + v; });
      });
    });

    const ents   = Object.entries(acumR).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const labels = ents.map(([l]) => l.length > 32 ? l.slice(0, 31) + '…' : l);
    const vR     = ents.map(([l]) => acumR[l] ?? 0);
    const vP     = ents.map(([l]) => acumP[l] ?? 0);

    const ds = [];
    if (gReal) ds.push({ label:'Real',         data:vR, backgroundColor:CR, borderRadius:3 });
    if (gPpto) ds.push({ label:'Presupuesto',   data:vP, backgroundColor:CP, borderRadius:3 });

    if (cM) cM.destroy();
    cM = new Chart(document.getElementById('g-cM'), {
      type: 'bar',
      data: { labels, datasets: ds },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => ' ' + ctx.dataset.label + ': ' + fmm(ctx.raw) } }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 30 } },
          y: { grid: { color: '#edf0f7' }, ticks: { callback: fmtMM, font: { size: 11 } } }
        }
      }
    });
    return;
  }

  // ── Modo Normal (meses seleccionados + Acumulado al final) ──────
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
        legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
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
const WF_CONCEPTOS = ['Ingresos','Costo de ventas','Margen Bruto','Subtotal GAV','EBITDA Directo','Gastos Adicionales','EBITDA Empresa'];
const WF_LABELS    = ['Ingresos','Costo VTA','Marg. Bruto','Subt. GAV','EBITDA Dir.','Gs. Adic.','EBITDA Emp.'];
const WF_ES_TOTAL  = [false, false, true, false, true, false, true];

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
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 25 } },
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
