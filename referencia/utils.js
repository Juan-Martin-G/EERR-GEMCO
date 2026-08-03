// ═══════════════════════════════════════════════════════════════
// utils.js — Constantes de cálculo, helpers, sv(), tooltip, filtros
// Depende de: datos.js (DATA, APP_DATA, MES_CORTE, etc.)
// ═══════════════════════════════════════════════════════════════

const TOTAL_PRESUP=window.PPTO_ANUAL;
const PPTO_CONTRATOS=TOTAL_PRESUP*0.50;
const TOTAL_COM_VAL=DATA.filter(d=>d.tipo==='Comercial').reduce((s,d)=>s+d.val,0);
const TOTAL_GAR_VAL=DATA.filter(d=>d.tipo==='Garantia').reduce((s,d)=>s+d.val,0);
const TOTAL_CARTERA_VAL=TOTAL_COM_VAL+TOTAL_GAR_VAL;
const C={az1:'#002D73',az2:'#33448D',az3:'#0E2D55',te:'#28D2C3',am:'#FFC000',rd:'#C00000',gn:'#00832F',or:'#D46000',gy:'#E2E6F0',mut:'#B8C1D8'};
Chart.defaults.font.family="'Roboto',sans-serif";
Chart.defaults.color='#6B7BA8';

// ─── HELPERS ──────────────────────────────────────────────────
const mm=v=>(v===null||v===undefined||isNaN(v))?'—':'MM$'+(v/1e6).toFixed(1);
const pctOf=(v,t)=>t>0&&!isNaN(v)?((v/t)*100).toFixed(1)+'%':'—';
const shortN=s=>s.length>35?s.slice(0,34)+'…':s;
const shortC=s=>s.split(' ')[0];
const urgC=d=>isNaN(d)?C.mut:d<0?C.rd:d<=30?C.rd:d<=60?C.or:d<=90?'#8B8200':d<=180?C.az2:C.gn;
const urgP=d=>{
  if(isNaN(d)||d===null||d===undefined)return`<span class="pill pgr">—</span>`;
  if(d<0)return`<span class="pill pd">Vencido</span>`;
  if(d<=30)return`<span class="pill pd">${d}d</span>`;
  if(d<=60)return`<span class="pill py">${d}d</span>`;
  if(d<=90)return`<span class="pill py">${d}d</span>`;
  if(d<=180)return`<span class="pill pb">${d}d</span>`;
  return`<span class="pill pg">${d}d</span>`;
};
const tipoBadge=t=>t==='Comercial'?`<span class="tipo-c">COM</span>`:`<span class="tipo-g">GAR</span>`;
const nueBadge=n=>n?`<span class="pill pg" title="Nuevo cliente">🆕</span>`:`<span class="pill pgr">—</span>`;
const pbarHTML=(p,c)=>{const pct=(!isNaN(p)&&p!=null)?Math.min(p,100):0;return`<div class="pbar-inline"><div class="pbar-fill" style="width:${pct}%;background:${c}"></div></div>`;};

// ─── VIEW SWITCHER ─────────────────────────────────────────────
function sv(name,btn){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('on'));
  document.getElementById('view-'+name).classList.add('on');
  btn.classList.add('on');
  window.scrollTo({top:0,behavior:'instant'});
  const inits={
    tipos:initTipos,
    nuevos:initNuevos,
    vencimientos:initVenc,
    vision:initVision,
    presupuesto:initPresupuesto,
    facturacion:initFacturacion,
    panelfact:initPanelFact,
    base:initBaseInstalada,
    satisfaccion:initSatisfaccion,
    visitas:initVisitas,
    alertas:initAlertas
  };
  const k='_i_'+name;
  if(inits[name]&&!window[k]){inits[name]();window[k]=true;}
  if(name==='vencimientos')renderHz();
  if(name==='vision')renderVG();
  if(name==='nuevos')renderNC();
  if(name==='facturacion') setTimeout(renderFcGraficos, 100);
}

// ─── TOOLTIP ──────────────────────────────────────────────────
const ttip=document.getElementById('ttip');
document.querySelectorAll('[data-tip]').forEach(el=>{
  el.addEventListener('mouseenter',()=>{ttip.textContent=el.dataset.tip;ttip.style.opacity='1'});
  el.addEventListener('mousemove',e=>{ttip.style.left=(e.clientX+12)+'px';ttip.style.top=(e.clientY-30)+'px'});
  el.addEventListener('mouseleave',()=>ttip.style.opacity='0');
});

// ─── GENERIC TABLE HELPERS ────────────────────────────────────
function filterT(id,q){document.getElementById(id).querySelectorAll('tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q.toLowerCase())?'':'none');}
let _sd={};
function sortT(id,col,th){
  const tb=document.getElementById(id);
  const rows=[...tb.querySelectorAll('tr')];
  const k=id+col;_sd[k]=!_sd[k];
  if(th){const tbl=th.closest('table');tbl.querySelectorAll('th').forEach(h=>h.classList.remove('th-asc','th-desc'));th.classList.add(_sd[k]?'th-asc':'th-desc');}
  rows.sort((a,b)=>{
    const va=a.cells[col]?.textContent.trim()||'';
    const vb=b.cells[col]?.textContent.trim()||'';
    const sva=va.replace(/[^0-9.\-]/g,''),svb=vb.replace(/[^0-9.\-]/g,'');
    const na=parseFloat(sva),nb=parseFloat(svb);
    if(!isNaN(na)&&!isNaN(nb))return _sd[k]?na-nb:nb-na;
    return _sd[k]?va.localeCompare(vb,'es'):vb.localeCompare(va,'es');
  });
  rows.forEach(r=>tb.appendChild(r));
}
function filterColT(tbodyId,q,col){
  const tb=document.getElementById(tbodyId);
  tb.querySelectorAll('tr').forEach(r=>{
    const cell=r.cells[col];
    r.style.display=(!q||cell&&cell.textContent.toLowerCase().includes(q.toLowerCase()))?'':'none';
  });
  updateTfoot(tbodyId);
}
function updateTfoot(tbodyId){
  const footMap={
    'tb-tc-com':'tfoot-tc-com','tb-tc-gar':'tfoot-tc-gar',
    'tb-hz':'tfoot-hz','tb-vg':'tfoot-vg','tb-nc':'tfoot-nc'
  };
  const fid=footMap[tbodyId]; if(!fid)return;
  const tbody=document.getElementById(tbodyId);
  const rows=[...tbody.querySelectorAll('tr')].filter(r=>r.style.display!=='none');
  const foot=document.getElementById(fid);
  if(!foot)return;
  const count=rows.length;
  const clients=new Set(rows.map(r=>r.cells[1]?.textContent.trim()||'')).size;
  const mmCols={'tb-tc-com':5,'tb-tc-gar':5,'tb-hz':8,'tb-vg':9,'tb-nc':7};
  const pctCols={'tb-tc-com':7,'tb-tc-gar':7,'tb-hz':9,'tb-vg':13,'tb-nc':null};
  const mmCol=mmCols[tbodyId], pctCol=pctCols[tbodyId];
  let totalMM=0, totalPct=0, pctCount=0;
  rows.forEach(r=>{
    if(mmCol!=null){const v=parseFloat((r.cells[mmCol]?.textContent||'').replace(/[^0-9.]/g,''));if(!isNaN(v))totalMM+=v;}
    if(pctCol!=null){const v=parseFloat((r.cells[pctCol]?.textContent||'').replace(/[^0-9.]/g,''));if(!isNaN(v)){totalPct+=v;pctCount++;}}
  });
  let txt=`${count} contratos · ${clients} clientes`;
  if(mmCol!=null&&totalMM>0) txt+=` · MM$${totalMM.toFixed(1)} total`;
  if(pctCol!=null&&pctCount>0) txt+=` · ${(totalPct/pctCount).toFixed(1)}% prom. consumido`;
  foot.innerHTML=`<td class="flab" colspan="20" style="background:var(--az3);color:rgba(255,255,255,.85);padding:.5rem .7rem;font-size:.64rem">${txt}</td>`;
}

// ─── TFOOT OBSERVER ───────────────────────────────────────────
const _obs=new MutationObserver((muts)=>{
  muts.forEach(m=>{
    const id=m.target.id;
    if(['tb-tc-com','tb-tc-gar','tb-hz','tb-vg','tb-nc'].includes(id)) updateTfoot(id);
  });
});
document.addEventListener('DOMContentLoaded',()=>{
  const _h=new Date();
  const _f=String(_h.getDate()).padStart(2,'0')+'/'+String(_h.getMonth()+1).padStart(2,'0')+'/'+_h.getFullYear();
  const elD=document.getElementById('hd-date');if(elD)elD.textContent='📅 '+_f;
  const elT=document.getElementById('rs-tag');if(elT)elT.textContent='Facturación real del área · Servicios de mantención preventiva y correctiva · Datos al '+_f;
  const elF=document.getElementById('ft-main');if(elF)elF.textContent='GEMCO S.A. · TECSERVICE · Panel de Contratos '+ANO_ACTUAL+' · CONFIDENCIAL · Datos al '+_f;
  ['tb-tc-com','tb-tc-gar','tb-hz','tb-vg','tb-nc'].forEach(id=>{
    const el=document.getElementById(id);
    if(el) _obs.observe(el,{childList:true,subtree:true});
  });
});

// ─── PROGRESS BARS ANIMATE ────────────────────────────────────
setTimeout(()=>{document.querySelectorAll('.prf').forEach(el=>{const w=el.style.width;el.style.width='0';setTimeout(()=>el.style.width=w,150);});},200);

// ─── PROGRAMAS CARE (usado en todas las hojas de contratos) ───────
const _PROG_FEATURES={
  BASIC:{label:'Basic',color:'#4caf50',bg:'rgba(76,175,80,.15)',solidBg:'#81c784',
    objetivo:'Cobertura esencial para el mantenimiento preventivo de su equipo médico.',
    items:['Mantenimiento Preventivo según indicación del fabricante (2 visitas x año)','Atención técnica en terreno, con valor preferente','Hasta 2 actividades de capacitación sin costo, al año']},
  ADVANCED:{label:'Advanced',color:'#fbc02d',bg:'rgba(251,192,45,.15)',solidBg:'#fdd835',
    objetivo:'Servicio completo que incluye mantenimiento preventivo y correctivo (mano de obra).',
    items:['Mantenimiento Preventivo','Mantenimiento Correctivo (Solo Mano de obra)','Hasta 2 actividades de capacitación sin costo, al año','Precio preferente para repuestos (descuento 7%)']},
  PROFESIONAL:{label:'Profesional',color:'#42a5f5',bg:'rgba(66,165,245,.15)',solidBg:'#64b5f6',
    objetivo:'Atención prioritaria con monitoreo continuo y soporte técnico especializado, que considera mantenimiento preventivo y correctivo con bolsa de repuestos originales.',
    items:['Mantenimiento Preventivo','Mantenimiento Correctivo','Bolsa de repuestos incluidos','Hasta 4 actividades de capacitación sin costo, al año','Precio preferente para repuestos, fuera de la bolsa (descuento 10%)','Soporte técnico 24/7, según área de cobertura']},
  INTEGRAL:{label:'Integral',color:'#7986cb',bg:'rgba(121,134,203,.15)',solidBg:'#9fa8da',
    objetivo:'Servicio total con todas las coberturas anteriores, más actualizaciones de software, revisiones exhaustivas y servicios de soporte prioritario.',
    items:['Mantenimiento Preventivo','Mantenimiento Correctivo','Repuestos incluidos','Hasta 10 actividades de capacitación sin costo, al año','Soporte técnico 24/7, según área de cobertura','Servicio de Backup (según corresponda - ver archivo equipos)']}
};
function _progKey(p){const u=(p||'').toUpperCase();if(u.includes('BASIC'))return'BASIC';if(u.includes('ADVANCED'))return'ADVANCED';if(u.includes('PROFESIONAL')||u.includes('PROFESSIONAL'))return'PROFESIONAL';if(u.includes('INTEGRAL'))return'INTEGRAL';return null;}
function _ensureProgTip(){if(document.getElementById('_prog-tip'))return;const d=document.createElement('div');d.id='_prog-tip';d.style.cssText='position:fixed;z-index:99999;background:#1e2434;border:1px solid #3a4460;border-radius:8px;padding:.7rem .9rem;min-width:280px;max-width:360px;pointer-events:none;display:none;box-shadow:0 6px 24px rgba(0,0,0,.55);font-family:Roboto,sans-serif';document.body.appendChild(d);}
function _showProgTip(e,key){_ensureProgTip();const info=_PROG_FEATURES[key];if(!info)return;const tip=document.getElementById('_prog-tip');tip.innerHTML=`<div style="font-family:'Roboto Condensed',sans-serif;font-weight:700;font-size:.78rem;color:${info.color};margin-bottom:.4rem;padding-bottom:.3rem;border-bottom:1px solid ${info.color}44">${info.label} Care Program</div><ul style="margin:0;padding-left:1.1rem;font-size:.6rem;color:rgba(255,255,255,.88);line-height:1.75">${info.items.map(i=>`<li>${i}</li>`).join('')}</ul>`;tip.style.display='block';tip.style.left=Math.min(e.clientX+14,window.innerWidth-380)+'px';tip.style.top=Math.min(e.clientY+10,window.innerHeight-200)+'px';}
function _hideProgTip(){const t=document.getElementById('_prog-tip');if(t)t.style.display='none';}
function _progBadge(programa){const key=_progKey(programa);if(!key)return'<span style="color:var(--mut);font-size:.6rem">—</span>';const info=_PROG_FEATURES[key];return`<span style="cursor:help;display:inline-block;padding:.18rem .45rem;border-radius:4px;font-size:.53rem;font-weight:700;font-family:'Roboto Condensed',sans-serif;background:${info.bg};color:${info.color};border:1px solid ${info.color}55;white-space:nowrap" onmouseenter="_showProgTip(event,'${key}')" onmouseleave="_hideProgTip()">${info.label}</span>`;}
