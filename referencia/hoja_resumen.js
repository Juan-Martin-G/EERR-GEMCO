// ═══════════════════════════════════════════════════════════════
// hoja_resumen.js — Gráficos y KPIs de la vista Resumen
// Depende de: datos.js, utils.js
// ═══════════════════════════════════════════════════════════════

// ─── HEADER DINÁMICO ──────────────────────────────────────────
(function(){
  const shMes=document.getElementById('rs-sh-mes');
  if(shMes)shMes.textContent=MES_CORTE_NOMBRE+' '+ANO_ACTUAL;
  const shN=document.getElementById('rs-sh-n');
  if(shN)shN.textContent=DATA.length;

  const nCom=DATA.filter(d=>d.tipo==='Comercial').length;
  const nGar=DATA.filter(d=>d.tipo==='Garantia').length;
  const nGarCli=new Set(DATA.filter(d=>d.tipo==='Garantia').map(d=>d.cliente)).size;
  const carteraAnual=DATA.filter(d=>d.tipo==='Comercial').reduce((s,d)=>s+(d.val||0),0);
  const carteraGar=DATA.filter(d=>d.tipo==='Garantia').reduce((s,d)=>s+(d.val||0),0);

  const garV=document.getElementById('rs-kpi-gar-val');if(garV)garV.textContent=nGar;
  const garS=document.getElementById('rs-kpi-gar-sub');if(garS)garS.textContent=nGarCli+' clientes · '+mm(carteraGar)+' cartera';
  const tlCom=document.getElementById('rs-tipo-com-lbl');if(tlCom)tlCom.textContent=nCom+' Comerciales';
  const tsCom=document.getElementById('rs-tipo-com-sub');if(tsCom)tsCom.textContent='Contratos con valor económico · '+mm(carteraAnual)+' cartera anual';
  const tlGar=document.getElementById('rs-tipo-gar-lbl');if(tlGar)tlGar.textContent=nGar+' Garantía';
  const tsGar=document.getElementById('rs-tipo-gar-sub');if(tsGar)tsGar.textContent='Cobertura valorizada · '+mm(carteraGar)+' · '+nGarCli+' clientes únicos';

  const venc90=DATA.filter(d=>d.dias_vence>=0&&d.dias_vence<=90);
  const venc90Val=DATA.filter(d=>d.dias_vence>=0&&d.dias_vence<=90&&d.tipo==='Comercial').reduce((s,d)=>s+(d.val||0),0);
  const kVencV=document.getElementById('rs-kpi-venc-val');if(kVencV)kVencV.textContent=venc90.length;
  const kVencS=document.getElementById('rs-kpi-venc-sub');if(kVencS)kVencS.textContent=mm(venc90Val)+' en riesgo próx. 90d';

  const pptoNota=document.getElementById('rs-ppto-nota');
  if(pptoNota)pptoNota.innerHTML='Ppto. contratos = <strong>50%</strong> del presupuesto área ('+mm(TOTAL_PRESUP)+'). La cartera anual de contratos vigentes suma '+mm(carteraAnual)+'.';
  const pptoTot=document.getElementById('rs-ppto-total');
  if(pptoTot)pptoTot.textContent=mm(PPTO_CONTRATOS);
})();

// ─── SNAPSHOT DEL MES ─────────────────────────────────────────
(function renderSnapshotMes(){
  const nNuevos=DATA.filter(d=>d.tipo==='Comercial'&&d.es_nuevo&&d.dias_inicio_cli>=0&&d.dias_inicio_cli<=90).length;
  const snapNuevos=document.getElementById('rs-snap-nuevos');if(snapNuevos)snapNuevos.textContent=nNuevos;
  const snapNuevosSub=document.getElementById('rs-snap-nuevos-sub');if(snapNuevosSub)snapNuevosSub.textContent='contratos comerciales nuevos (últ. 90d)';

  const venc30=DATA.filter(d=>d.dias_vence>=0&&d.dias_vence<=30).length;
  const snapV30=document.getElementById('rs-snap-venc30');if(snapV30)snapV30.textContent=venc30;
  const v30col=venc30>5?'var(--rd)':venc30>2?'var(--am)':'var(--az2)';
  if(snapV30)snapV30.style.color=v30col;
  const snapV30S=document.getElementById('rs-snap-venc30-sub');if(snapV30S)snapV30S.textContent='contrato'+(venc30===1?'':'s')+' a vencer ≤30 días';

  // Facturación del mes actual = acum_mes de la tabla semanal (Ingresos Totales)
  const _semTotRow=(APP_DATA.analisis_fac&&APP_DATA.analisis_fac.tabla_semanal||[])
    .find(r=>r.linea&&r.linea.toLowerCase().includes('total'));
  const mesFac=_semTotRow&&_semTotRow.acum_mes>0?_semTotRow.acum_mes:
    (MES_CORTE>=1?(APP_DATA.mensual.total['2026'][MES_CORTE-1]||0):0);
  const snapMesLbl=document.getElementById('rs-snap-mes-lbl');if(snapMesLbl)snapMesLbl.textContent=MESES_FULL[MES_CORTE-1];
  const snapAnoLbl=document.getElementById('rs-snap-ano-lbl');if(snapAnoLbl)snapAnoLbl.textContent=ANO_ACTUAL;
  const snapMesV=document.getElementById('rs-snap-mes-val');if(snapMesV)snapMesV.textContent=fmtMM(mesFac);
  const snapMesS=document.getElementById('rs-snap-mes-sub');if(snapMesS)snapMesS.textContent='último mes completo facturado';

  if(APP_DATA.satisf&&APP_DATA.satisf.nps){
    const nps=APP_DATA.satisf.nps;
    const snapNps=document.getElementById('rs-snap-nps');
    if(snapNps){snapNps.textContent=(nps.nps>0?'+':'')+nps.nps;snapNps.style.color=nps.nps>=50?'var(--gn)':nps.nps>=0?'var(--am)':'var(--rd)';}
    const snapNpsS=document.getElementById('rs-snap-nps-sub');
    if(snapNpsS)snapNpsS.textContent=nps.pro+' prom · '+nps.pas+' pas · '+nps.det+' det';
  }

  if(APP_DATA.visitas&&APP_DATA.visitas.resumen){
    const _vEjes=Object.keys(APP_DATA.visitas.resumen);
    const rEg=APP_DATA.visitas.resumen[_vEjes[0]]||{};
    const rCr=APP_DATA.visitas.resumen[_vEjes[1]]||{};
    const totVis=(rEg.tot_2026_ytd||0)+(rCr.tot_2026_ytd||0);
    const snapVis=document.getElementById('rs-snap-vis');if(snapVis)snapVis.textContent=totVis;
    const snapVisS=document.getElementById('rs-snap-vis-sub');
    if(snapVisS)snapVisS.textContent=(rEg.tot_2026_ytd||0)+' '+(_vEjes[0]||'').split(' ')[0]+' · '+(rCr.tot_2026_ytd||0)+' '+(_vEjes[1]||'').split(' ')[0];
  }
})();

// ─── RESUMEN CHARTS (ejecutar al cargar) ──────────────────────
// ─── GRÁFICO FACTURACIÓN MENSUAL CON SEGMENTADOR ─────────────
(function(){
  const _bbddArr = (APP_DATA.mensual.facturado && APP_DATA.mensual.facturado[String(ANO_ACTUAL)]) || APP_DATA.mensual.total[String(ANO_ACTUAL)] || [];
  const _semTot=(APP_DATA.analisis_fac&&APP_DATA.analisis_fac.tabla_semanal||[])
    .find(r=>r.linea&&r.linea.toLowerCase().includes('total'));
  const _acumMesActual=_semTot&&_semTot.acum_mes>0?_semTot.acum_mes:null;
  const _analYTD = (APP_DATA.analisis_fac&&APP_DATA.analisis_fac.ts_ingresos>0)?APP_DATA.analisis_fac.ts_ingresos:null;
  const _bbddPrev = _bbddArr.slice(0,MES_CORTE-1).reduce((s,v)=>s+v,0);
  const _analPrev = _analYTD&&_acumMesActual?_analYTD-_acumMesActual:_bbddPrev;
  const _kPrev = _bbddPrev>0?_analPrev/_bbddPrev:1;
  window._RS_MENS_SCALED = _bbddArr.map((v,i)=>{
    if(i>=MES_CORTE)return 0;
    if(i===MES_CORTE-1)return _acumMesActual||Math.round(v*_kPrev);
    return Math.round(v*_kPrev);
  });

  const _pmRs=(APP_DATA.analisis_fac&&APP_DATA.analisis_fac.ppto_mensual&&APP_DATA.analisis_fac.ppto_mensual.some(v=>v>0))
    ?APP_DATA.analisis_fac.ppto_mensual:null;
  const _contr  = APP_DATA.mensual.contr_real   || Array(12).fill(0);
  const _nocontr = APP_DATA.mensual.nocontr_real || Array(12).fill(0);

  let _seg='total';
  const _colors={
    total:  MESES_ABR.map((_,i)=>i<MES_CORTE?C.az3:'#B8BFCB'),
    contr:  MESES_ABR.map((_,i)=>i<MES_CORTE?C.te:'rgba(40,210,195,.25)'),
    otros:  MESES_ABR.map((_,i)=>i<MES_CORTE?C.or:'rgba(212,96,0,.25)'),
  };

  function _getData(seg){
    if(seg==='contr')  return _contr.map(v=>v/1e6);
    if(seg==='otros')  return _nocontr.map(v=>v/1e6);
    return _RS_MENS_SCALED.map(v=>v/1e6);
  }
  function _getLbl(seg){
    if(seg==='contr')  return 'Contratos';
    if(seg==='otros')  return 'Otras Facturaciones';
    return 'Real facturado';
  }

  const _cMesChart = new Chart(document.getElementById('cMes').getContext('2d'),{
    type:'bar',
    data:{labels:MESES_ABR,
      datasets:[
        {label:'Real facturado',data:_getData('total'),backgroundColor:_colors.total,borderRadius:5,borderSkipped:false,order:3},
        {label:'Ppto total TS',
         data:_pmRs?_pmRs.map(v=>v/1e6):MESES_ABR.map(()=>TOTAL_PRESUP/12/1e6),
         backgroundColor:'rgba(100,160,230,.45)',borderColor:'#5090D0',borderWidth:1.5,borderRadius:4,borderSkipped:false,order:4},
        {label:'Ppto contratos',
         data:_pmRs?_pmRs.map(v=>v/2/1e6):APP_DATA.mensual.presup_contr.map(v=>v/1e6),
         type:'line',borderColor:C.te,backgroundColor:'rgba(40,210,195,.1)',
         borderWidth:2.5,tension:0.3,pointRadius:4,pointBackgroundColor:C.te,order:2,fill:false}
      ]},
    options:{responsive:true,plugins:{legend:{position:'bottom',labels:{boxWidth:10,font:{size:10}}},
      tooltip:{callbacks:{label:c=>` ${c.dataset.label}: MM$${c.raw.toFixed(1)}`}}},
      scales:{y:{grid:{color:'#E2E6F0'},ticks:{callback:v=>'MM$'+v}},x:{grid:{display:false}}}}
  });

  document.querySelectorAll('#rs-mes-seg .btn').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('#rs-mes-seg .btn').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    _seg=b.dataset.seg;
    _cMesChart.data.datasets[0].label=_getLbl(_seg);
    _cMesChart.data.datasets[0].data=_getData(_seg);
    _cMesChart.data.datasets[0].backgroundColor=_colors[_seg];
    // Ocultar Ppto total cuando se ve segmento
    _cMesChart.data.datasets[1].hidden=(_seg!=='total');
    _cMesChart.update();
  }));
})();
(function(){
  // Misma fuente que KPI6: presup_contr_ytd / ts_ingresos → coincide con indicador % Fact = Contratos
  var _af = APP_DATA.analisis_fac || {};
  var _tsIng = _af.ts_ingresos || 0;
  var _contr = APP_DATA.panel.reduce((s,p)=>s+(p.presup_contr_ytd||0),0);
  var _nocontr = _tsIng > _contr ? _tsIng - _contr : 0;
  var _tot = (_contr + _nocontr) || _contr || 1;
  var pctC = (_contr/_tot*100).toFixed(1);
  var pctN = (_nocontr/_tot*100).toFixed(1);
  new Chart(document.getElementById('cDonut1').getContext('2d'),{
    type:'doughnut',
    data:{labels:['Contratos '+pctC+'%','No Contratos '+pctN+'%'],
      datasets:[{data:[_contr, _nocontr],backgroundColor:[C.az2,C.am],borderWidth:0,hoverOffset:4}]},
    options:{cutout:'70%',responsive:true,maintainAspectRatio:true,
      plugins:{
        legend:{display:true,position:'bottom',labels:{boxWidth:12,font:{size:9},padding:6}},
        tooltip:{callbacks:{label:c=>` ${c.label}: ${fmtMM(c.raw)}`}}
      }
    }
  });
})();
(function(){
  const nCom=DATA.filter(d=>d.tipo==='Comercial').length;
  const nGar=DATA.filter(d=>d.tipo==='Garantia').length;
  new Chart(document.getElementById('cTipo').getContext('2d'),{
    type:'doughnut',data:{labels:['Comercial ('+nCom+')','Garantía ('+nGar+')'],
      datasets:[{data:[nCom,nGar],backgroundColor:[C.az2,C.te],borderWidth:0,hoverOffset:4}]},
    options:{cutout:'62%',responsive:true,maintainAspectRatio:true,plugins:{legend:{display:false}}}
  });
})();
new Chart(document.getElementById('cLong').getContext('2d'),{
  type:'bar',data:{labels:['<1 año','1 año','2 años','3+ años'],
    datasets:[{label:'Contratos',
      data:[DATA.filter(d=>d.long_dias<365).length,
        DATA.filter(d=>d.long_dias>=365&&d.long_dias<730).length,
        DATA.filter(d=>d.long_dias>=730&&d.long_dias<1095).length,
        DATA.filter(d=>d.long_dias>=1095).length],
      backgroundColor:[C.gy,C.az3,C.az2,C.te],borderRadius:4,borderSkipped:false}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
    scales:{y:{grid:{color:'#E2E6F0'},ticks:{stepSize:5}},x:{grid:{display:false}}}}
});

// ─── PRESUPUESTO CONTRATOS INIT ───────────────────────────────
(function(){
  const pct=(TOTAL_CARTERA_VAL/PPTO_CONTRATOS*100);
  const brecha=Math.max(0,PPTO_CONTRATOS-TOTAL_CARTERA_VAL);
  const kpiEl=document.getElementById('kpi-ppto-pct');
  if(kpiEl)kpiEl.textContent=pct.toFixed(1)+'%';
  const kpiSub=document.getElementById('kpi-ppto-sub');
  if(kpiSub)kpiSub.textContent=mm(TOTAL_CARTERA_VAL)+' de '+mm(PPTO_CONTRATOS);
  const rk1=document.getElementById('rs-ppto-total');if(rk1)rk1.textContent=mm(PPTO_CONTRATOS);
  const rk2=document.getElementById('rs-ppto-real');if(rk2)rk2.textContent=mm(TOTAL_CARTERA_VAL);
  const rk2l=document.getElementById('rs-ppto-real-lbl');if(rk2l)rk2l.textContent='COM+GAR ('+pct.toFixed(1)+'%)';
  const rk3=document.getElementById('rs-ppto-brecha');if(rk3)rk3.textContent=mm(brecha);
  const rk3l=document.getElementById('rs-ppto-brecha-lbl');if(rk3l)rk3l.textContent='Brecha ('+(brecha/PPTO_CONTRATOS*100).toFixed(1)+'%)';
})();

new Chart(document.getElementById('cPpto').getContext('2d'),{
  type:'bar',data:{labels:['Cartera COM+GAR','Brecha'],
    datasets:[{data:[(TOTAL_CARTERA_VAL/PPTO_CONTRATOS*100).toFixed(1),(Math.max(0,PPTO_CONTRATOS-TOTAL_CARTERA_VAL)/PPTO_CONTRATOS*100).toFixed(1)],backgroundColor:[C.az2,'#E2E6F0'],borderRadius:4,borderSkipped:false}]},
  options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false},
    tooltip:{callbacks:{label:c=>` ${c.raw}% del ppto contratos (MM$${(PPTO_CONTRATOS/1e6).toFixed(1)})`}}},
    scales:{x:{max:100,grid:{color:'#E2E6F0'},ticks:{callback:v=>v+'%'}},y:{grid:{display:false}}}}
});

// ─── TABLAS ANALISIS FACTURACIÓN ──────────────────────────────
(function renderAnalisisTables(){
  const af = APP_DATA.analisis_fac || {};
  const set=(id,v)=>{const el=document.getElementById(id);if(el)el.textContent=v;};
  set('rs-anal-mes', af.mes_nombre || MES_CORTE_NOMBRE);
  set('rs-anal-ano', ANO_ACTUAL);
  set('rs-anal-semana-tag', 'Semana ' + (af.semana||'—'));
  set('rs-sem-mes-lbl', af.mes_nombre || MES_CORTE_NOMBRE);

  function _mm(v){return v===0||!v?'—':'MM$'+(v/1e6).toFixed(1).replace('.',',');}
  function _pct(v){if(!v&&v!==0)return'—';const s=v>=0?'+':'';return s+v.toFixed(1).replace('.',',')+'%';}
  function _col(v){return v>0?'color:var(--gn)':v<0?'color:var(--rd)':'';}
  function _isTotal(r){return r.linea&&r.linea.toLowerCase().includes('total');}

  // Tabla 1 mensual
  const tb1 = document.getElementById('rs-anal-tbody');
  if(tb1 && af.tabla_mensual){
    tb1.innerHTML = af.tabla_mensual.map(r=>{
      const bold = _isTotal(r) ? 'font-weight:900;background:var(--gy)' : '';
      return `<tr style="${bold}">
        <td style="font-size:.67rem">${r.linea}</td>
        <td class="num">${_mm(r.ingresos)}</td>
        <td class="num" style="${_col(r.provision)}">${_mm(r.provision)}</td>
        <td class="num" style="font-weight:700;color:var(--teal)">${_mm(r.total_ytd)}</td>
        <td class="num">${_mm(r.ppto_acum)}</td>
        <td class="num" style="${_col(r.delta_ppto)}">${_mm(r.delta_ppto)}</td>
        <td class="num" style="${_col(r.delta_ppto_pct)}">${_pct(r.delta_ppto_pct*100)}</td>
        <td class="num">${_mm(r.ingresos_aa)}</td>
        <td class="num" style="${_col(r.delta_aa)}">${_mm(r.delta_aa)}</td>
        <td class="num" style="${_col(r.delta_aa_pct)}">${_pct(r.delta_aa_pct*100)}</td>
        <td class="num">${_mm(r.ppto_anual)}</td>
      </tr>`;
    }).join('');
  }

  // Tabla 2 semanal
  const tb2 = document.getElementById('rs-sem-tbody');
  if(tb2 && af.tabla_semanal){
    tb2.innerHTML = af.tabla_semanal.map(r=>{
      const bold = _isTotal(r) ? 'font-weight:900;background:var(--gy)' : '';
      return `<tr style="${bold}">
        <td style="font-size:.67rem">${r.linea}</td>
        <td class="num">${_mm(r.ingresos)}</td>
        <td class="num">${_mm(r.s1)}</td><td class="num">${_mm(r.s2)}</td>
        <td class="num">${_mm(r.s3)}</td><td class="num">${_mm(r.s4)}</td>
        <td class="num">${_mm(r.s5)}</td>
        <td class="num" style="font-weight:700;color:var(--teal)">${_mm(r.acum_mes)}</td>
        <td class="num">${_mm(r.ppto_mes)}</td>
        <td class="num" style="${_col(r.delta_ppto)}">${_mm(r.delta_ppto)}</td>
        <td class="num" style="${_col(r.delta_ppto_pct)}">${_pct(r.delta_ppto_pct*100)}</td>
        <td class="num" style="${_col(r.vs_mes_ant)}">${_mm(r.vs_mes_ant)}</td>
        <td class="num" style="${_col(r.delta_vs_ant)}">${_mm(r.delta_vs_ant)}</td>
      </tr>`;
    }).join('');
  }
})();

// ─── RESUMEN KPIs DINÁMICOS ───────────────────────────────────
(function renderResumenKPIs(){
  const af = APP_DATA.analisis_fac || {};
  // Fuente master: Analisis Facturación
  const tsIng    = af.ts_ingresos    || 0;   // Facturación TS 2026 YTD
  // Año anterior: mismo período (Ene–mes_corte) desde mensual.facturado — igual que hoja Facturación
  const _mfAA = (APP_DATA.mensual && APP_DATA.mensual.facturado && APP_DATA.mensual.facturado[String(ANO_ACTUAL-1)]) || [];
  const tsIngAA = _mfAA.slice(0, MES_CORTE).reduce((s,v)=>s+v, 0);
  const pptoacum = af.ts_ppto_acum   || 0;
  const carteraAnual = TOTAL_CARTERA_VAL;

  document.getElementById('rs-kpi-tot').textContent = fmtMM(tsIng);
  document.getElementById('rs-kpi-tot-sub').textContent = 'Facturación TS Ene–'+MES_CORTE_NOMBRE+' · '+APP_DATA.panel.length+' clientes panel';
  // Actualizar data-tip dinámicamente (sin valores hardcodeados)
  const _kpiTotW = document.getElementById('rs-kpi-tot') ? document.getElementById('rs-kpi-tot').closest('.kpi') : null;
  if(_kpiTotW){ const _cYTD=APP_DATA.panel.reduce((s,p)=>s+(p.presup_contr_ytd||0),0); const _af2=APP_DATA.analisis_fac||{}; const _ncYTD=Math.max(0,(_af2.ts_ingresos||0)-_cYTD); _kpiTotW.setAttribute('data-tip','Facturación real Servicio Técnico Ene–'+MES_CORTE_NOMBRE+' '+ANO_ACTUAL+': '+fmtMM(_cYTD)+' de contratos + '+fmtMM(_ncYTD)+' de otras facturaciones (correctiva, REAS, trazabilidad, etc.) · '+APP_DATA.panel.length+' clientes panel'); }

  const v25 = tsIngAA>0 ? ((tsIng-tsIngAA)/tsIngAA*100) : 0;
  const kc = document.getElementById('rs-kpi-contr-pct');
  if(kc){
    kc.textContent = (v25>=0?'+':'')+v25.toFixed(1).replace('.',',')+'%';
    kc.style.color = v25>=0 ? '#7DC9D6' : '#FF6B6B';
  }
  const kcLbl = document.querySelector('#view-resumen .kpi:nth-child(2) .kpi-lbl');
  if(kcLbl) kcLbl.textContent = 'Var. vs '+( ANO_ACTUAL-1)+' YTD';
  document.getElementById('rs-kpi-contr-sub').textContent = 'vs '+fmtMM(tsIngAA)+' en Ene-'+MES_CORTE_NOMBRE+' '+(ANO_ACTUAL-1);

  // % contratos: basado en Ingresos TS (sin GD) para que sea comparable con panel clientes
  const contrRealYTD_rs = APP_DATA.panel.reduce((s,p)=>s+(p.presup_contr_ytd||0),0);
  const _totKpi6 = tsIng > 0 ? tsIng : (contrRealYTD_rs || 1);
  const pctFacContr_rs = contrRealYTD_rs / _totKpi6 * 100;
  const nocontrRealYTD_rs = _totKpi6 - contrRealYTD_rs;
  const pctKpi6 = document.getElementById('rs-kpi-pct-contr');
  if(pctKpi6){
    pctKpi6.textContent = pctFacContr_rs.toFixed(1).replace('.',',')+'%';
    pctKpi6.style.color = pctFacContr_rs>=50?'var(--az2)':'var(--or)';
  }
  const pctSub6 = document.getElementById('rs-kpi-pct-contr-sub');
  if(pctSub6) pctSub6.textContent = fmtMM(contrRealYTD_rs)+' contr · '+fmtMM(nocontrRealYTD_rs)+' no contr';

  const pptoCubierto = PPTO_ANUAL_CONTR>0 ? carteraAnual/PPTO_ANUAL_CONTR*100 : 0;
  const kpiP = document.getElementById('kpi-ppto-pct');
  if(kpiP) kpiP.textContent = pptoCubierto.toFixed(1).replace('.',',')+'%';
  const kpiS = document.getElementById('kpi-ppto-sub');
  if(kpiS) kpiS.textContent = fmtMM(carteraAnual)+' de '+fmtMM(PPTO_ANUAL_CONTR);

  const rPR = document.getElementById('rs-ppto-real');
  if(rPR) rPR.textContent = fmtMM(carteraAnual);
  const rPRL = document.getElementById('rs-ppto-real-lbl');
  if(rPRL) rPRL.textContent = 'Cartera anual ('+pptoCubierto.toFixed(1).replace('.',',')+'%)';
  const brecha = Math.max(0, PPTO_ANUAL_CONTR - carteraAnual);
  const rPB = document.getElementById('rs-ppto-brecha');
  if(rPB) rPB.textContent = fmtMM(brecha);
  const rPBL = document.getElementById('rs-ppto-brecha-lbl');
  if(rPBL) rPBL.textContent = 'Brecha ('+(PPTO_ANUAL_CONTR>0?(brecha/PPTO_ANUAL_CONTR*100):0).toFixed(1).replace('.',',')+'%)';

  const cards = document.getElementById('rs-mes-cards');
  if(cards){
    const mes2026 = (APP_DATA.mensual.facturado && APP_DATA.mensual.facturado[String(ANO_ACTUAL)]) || APP_DATA.mensual.total[String(ANO_ACTUAL)];
    // Ppto contratos por mes: 50% del ppto mensual real de GD-PPTO
    const _pmRaw = (APP_DATA.analisis_fac && APP_DATA.analisis_fac.ppto_mensual) || [];
    const _usePM = _pmRaw.some(v=>v>0);
    const colores = ['var(--az3)','var(--az2)','#4A6CC0','var(--teal)','#5BAE99'];
    cards.innerHTML = '';
    for(let i=0;i<MES_CORTE;i++){
      const v = mes2026[i]/1e6;
      const p = (_usePM ? _pmRaw[i] : TOTAL_PRESUP/12) / 1e6;
      const col = colores[i%colores.length];
      const dif = v - p;
      const cls = dif>=0?'+':'';
      const difCol = dif>=0?'var(--teal)':'var(--rd)';
      cards.innerHTML += `<div style="background:var(--gy);border-radius:5px;padding:.5rem;text-align:center;border-top:2px solid ${col}">
        <div style="font-family:'Roboto Condensed',sans-serif;font-weight:900;font-size:1.05rem;color:${col}">${v.toFixed(0)}</div>
        <div style="font-size:.55rem;color:var(--mut)">${MESES_FULL[i]}</div>
        <div style="font-size:.5rem;color:${difCol};font-family:'Roboto Mono',monospace">${cls}${dif.toFixed(0)} vs ppto</div>
      </div>`;
    }
  }

  // Misma fuente que KPI6 y donut: presup_contr_ytd / ts_ingresos → todo consistente
  const contrRealYTD = contrRealYTD_rs;
  const nocontrRealYTD = tsIng > contrRealYTD ? tsIng - contrRealYTD : 0;
  const _totContrYTD = tsIng || (contrRealYTD + nocontrRealYTD) || 1;
  const pctContr = contrRealYTD / _totContrYTD * 100;
  const pctNoContr = nocontrRealYTD / _totContrYTD * 100;

  const dn = document.getElementById('rs-donut-pct');
  if(dn) dn.textContent = pctContr.toFixed(0)+'%';
  const dnLbl = document.querySelector('#view-resumen .donut-l');
  if(dnLbl) dnLbl.textContent = '% Contratos';

  const lblC = document.getElementById('rs-pr-contr-lbl');
  if(lblC) lblC.textContent = 'Contratos ('+fmtMM(contrRealYTD)+')';
  const pctCEl = document.getElementById('rs-pr-contr-pct');
  if(pctCEl) pctCEl.textContent = pctContr.toFixed(1).replace('.',',')+'%';
  const barC = document.getElementById('rs-pr-contr-bar');
  if(barC) barC.style.width = pctContr.toFixed(1)+'%';

  const lblR = document.getElementById('rs-pr-corr-lbl');
  if(lblR) lblR.textContent = 'No Contratos ('+fmtMM(nocontrRealYTD)+')';
  const pctREl = document.getElementById('rs-pr-corr-pct');
  if(pctREl){ pctREl.textContent = pctNoContr.toFixed(1).replace('.',',')+'%'; pctREl.style.color='var(--am)'; }
  const barR = document.getElementById('rs-pr-corr-bar');
  if(barR){ barR.style.width = pctNoContr.toFixed(1)+'%'; barR.style.background='var(--am)'; }

  const note = document.getElementById('rs-pr-note');
  if(note) note.innerHTML = 'En Ene-'+MES_CORTE_NOMBRE+' '+ANO_ACTUAL+' se facturaron <strong>'+fmtMM(tsIng)+'</strong> (Servicio Técnico): <strong style="color:var(--az2)">'+fmtMM(contrRealYTD)+'</strong> ('+pctContr.toFixed(1).replace('.',',')+'%) proviene de contratos y <strong style="color:var(--am)">'+fmtMM(nocontrRealYTD)+'</strong> ('+pctNoContr.toFixed(1).replace('.',',')+'%) de otras facturaciones.';
})();

// ─── FACTURACIÓN POR EJECUTIVO ────────────────────────────────
(function(){
  const ctx = document.getElementById('cRsEjeFac'); if(!ctx) return;
  const porEje = (APP_DATA.mensual && APP_DATA.mensual.por_ejecutivo) || {};
  const ejecutivos = Object.keys(porEje).filter(e => e && e !== 'nan' && e !== 'None');
  if(!ejecutivos.length){ ctx.parentElement.innerHTML='<div style="text-align:center;color:var(--mut);padding:2rem;font-style:italic">Sin datos de ejecutivo en la BBDD</div>'; return; }

  const _PAL=['#002D73','#33448D','#28D2C3','#D46000','#FFC000','#00832F','#C00000','#7B2FBE','#5090D0','#E87722'];
  const _ejeColorMap = {};
  ejecutivos.forEach((e,i) => _ejeColorMap[e] = _PAL[i % _PAL.length]);
  const anoStr = String(ANO_ACTUAL);
  let _ejeFilter = 'todos';
  let _chartEje = null;

  // Agregar segmentador dinámico encima del gráfico
  const card = ctx.closest('.card');
  const filtrDiv = document.createElement('div');
  filtrDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:.3rem;padding:.4rem .8rem .2rem;border-bottom:1px solid var(--brd)';
  const btnTodos = document.createElement('button');
  btnTodos.className = 'btn on'; btnTodos.textContent = 'Todos'; btnTodos.dataset.eje = 'todos';
  filtrDiv.appendChild(btnTodos);
  ejecutivos.forEach((eje, i) => {
    const b = document.createElement('button');
    b.className = 'btn'; b.textContent = eje.split(' ').slice(0,2).join(' ');
    b.dataset.eje = eje;
    b.style.borderLeft = '3px solid ' + _ejeColorMap[eje];
    filtrDiv.appendChild(b);
  });
  card.insertBefore(filtrDiv, card.querySelector('.cb'));

  filtrDiv.querySelectorAll('.btn').forEach(b => b.addEventListener('click', () => {
    filtrDiv.querySelectorAll('.btn').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    _ejeFilter = b.dataset.eje;
    _renderEjeChart();
  }));

  function _renderEjeChart(){
    const labels = MESES_ABR.slice(0, MES_CORTE);
    const ejesActivos = _ejeFilter === 'todos' ? ejecutivos : [_ejeFilter];

    const datasets = ejesActivos.map(eje => {
      const mensArr = (porEje[eje] && porEje[eje][anoStr]) || Array(12).fill(0);
      return {
        label: eje.split(' ').slice(0, 2).join(' '),
        data: mensArr.slice(0, MES_CORTE).map(v => v / 1e6),
        backgroundColor: _ejeColorMap[eje],
        borderRadius: 3,
        stack: _ejeFilter === 'todos' ? 's' : eje
      };
    });

    const totalYTD = ejesActivos.reduce((s, eje) => {
      const arr = (porEje[eje] && porEje[eje][anoStr]) || Array(12).fill(0);
      return s + arr.slice(0, MES_CORTE).reduce((a, v) => a + v, 0);
    }, 0);

    const foot = document.getElementById('rs-eje-foot');
    if(foot) foot.textContent = (_ejeFilter === 'todos' ? ejecutivos.length + ' ejecutivos' : _ejeFilter) + ' · YTD: ' + fmtMM(totalYTD);

    if(_chartEje) _chartEje.destroy();
    _chartEje = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 }, padding: 8 },
            display: _ejeFilter === 'todos' },
          tooltip: {
            mode: 'index',
            callbacks: {
              label: c => ` ${c.dataset.label}: MM$${c.raw.toFixed(1)}`,
              footer: items => _ejeFilter === 'todos' ? ' Total: MM$' + items.reduce((s,i) => s + i.raw, 0).toFixed(1) : ''
            }
          }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, grid: { color: '#E2E6F0' }, ticks: { callback: v => 'MM$' + v } }
        }
      }
    });
  }

  _renderEjeChart();
})();

// ─── FACTURACIÓN POR LÍNEA DE NEGOCIO ─────────────────────────
(function(){
  const ctx = document.getElementById('cRsLineaFac'); if(!ctx) return;
  const lineas = (APP_DATA.analisis_fac && APP_DATA.analisis_fac.lineas_mensual) || {};
  const nombres = Object.keys(lineas);
  if(!nombres.length){ ctx.parentElement.innerHTML='<div style="text-align:center;color:var(--mut);padding:2rem;font-style:italic">Sin datos de línea de negocio</div>'; return; }

  const _PAL = { STESTERILIZACION:'#002D73', STMEDICO:'#7B2FBE', STENDOSCOPIA:'#FFC000', STDENTAL:'#D46000' };
  const _PAL_DEF = ['#33448D','#00832F','#C00000','#28D2C3'];
  const colorOf = (n,i) => _PAL[n.toUpperCase().replace(/[^A-Z]/g,'')] || _PAL_DEF[i % _PAL_DEF.length];

  const anoStr = String(ANO_ACTUAL);
  let _lineaFilter = 'todos';
  let _chartLinea = null;

  const card = ctx.closest('.card');
  const filtrDiv = document.createElement('div');
  filtrDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:.3rem;padding:.4rem .8rem .2rem;border-bottom:1px solid var(--brd)';
  const btnTodos = document.createElement('button');
  btnTodos.className = 'btn on'; btnTodos.textContent = 'Todos'; btnTodos.dataset.ln = 'todos';
  filtrDiv.appendChild(btnTodos);
  nombres.forEach((n, i) => {
    const b = document.createElement('button');
    b.className = 'btn'; b.textContent = n;
    b.dataset.ln = n;
    b.style.borderLeft = '3px solid ' + colorOf(n, i);
    filtrDiv.appendChild(b);
  });
  card.insertBefore(filtrDiv, card.querySelector('.cb'));

  filtrDiv.querySelectorAll('.btn').forEach(b => b.addEventListener('click', () => {
    filtrDiv.querySelectorAll('.btn').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    _lineaFilter = b.dataset.ln;
    _renderLineaChart();
  }));

  function _renderLineaChart(){
    const labels = MESES_ABR.slice(0, MES_CORTE);
    const activos = _lineaFilter === 'todos' ? nombres : [_lineaFilter];

    const datasets = activos.map((n, i) => {
      const arr = lineas[n] || Array(12).fill(0);
      return {
        label: n,
        data: arr.slice(0, MES_CORTE).map(v => v / 1e6),
        backgroundColor: colorOf(n, i),
        borderRadius: 3,
        stack: _lineaFilter === 'todos' ? 's' : n
      };
    });

    const totalYTD = activos.reduce((s, n) => {
      const arr = lineas[n] || Array(12).fill(0);
      return s + arr.slice(0, MES_CORTE).reduce((a, v) => a + v, 0);
    }, 0);

    const foot = document.getElementById('rs-linea-foot');
    if(foot) foot.textContent = (_lineaFilter === 'todos' ? activos.length + ' líneas' : _lineaFilter) + ' · YTD: ' + fmtMM(totalYTD);

    if(_chartLinea) _chartLinea.destroy();
    _chartLinea = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 }, padding: 8 },
            display: _lineaFilter === 'todos' },
          tooltip: {
            mode: 'index',
            callbacks: {
              label: c => ` ${c.dataset.label}: MM$${c.raw.toFixed(1)}`,
              footer: items => _lineaFilter === 'todos' ? ' Total: MM$' + items.reduce((s,i) => s + i.raw, 0).toFixed(1) : ''
            }
          }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, grid: { color: '#E2E6F0' }, ticks: { callback: v => 'MM$' + v } }
        }
      }
    });
  }

  _renderLineaChart();
})();

// ─── RATIOS DE COSTOS ─────────────────────────────────────────
(function(){
  const RC = (APP_DATA && APP_DATA.ratios_costos) || {};
  if(!RC.ratios || !RC.ratios.length) return;

  const mesEl = document.getElementById('rs-ratios-mes');
  if(mesEl) mesEl.textContent = (RC.mes_cierre_nombre||'') + ' 2026';

  const RATIO_COLORS = ['#0A5C8C','#007A72','#7A1FAA','#E87722','#C00000'];
  const meses = RC.meses || [];
  const n = meses.length;

  // Helpers
  const fmm  = v => { const a=Math.abs(v||0); return (v<0?'−':'')+a.toFixed(1); };
  const fpct = v => (v*100).toFixed(1)+'%';
  const numTd = (v, col, bold) =>
    `<td class="num" style="color:${col||'inherit'};${bold?'font-weight:700':''}">MM$${fmm(v)}</td>`;

  // ── Tabla de valores base ──────────────────────────────────────
  const valsEl = document.getElementById('rs-ratios-vals');
  if(valsEl){
    const colHdr = 'background:var(--az3);color:rgba(255,255,255,.85);font-size:.6rem;font-weight:700;text-align:center;padding:.35rem .4rem';
    const thMeses = meses.map(m=>`<th style="${colHdr}">${m.slice(0,3)}</th>`).join('');
    const thTot   = `<th style="${colHdr};background:#1a3a6b">Total</th>`;

    const rowBase = (label, arr, total, colorFn, fmt) => {
      const tds = arr.map(v=>{
        const col = colorFn ? colorFn(v) : 'inherit';
        const disp = fmt==='pct' ? fpct(v) : 'MM$'+fmm(v);
        return `<td class="num" style="color:${col}">${disp}</td>`;
      }).join('');
      const totCol = colorFn ? colorFn(total) : 'inherit';
      const totDisp = fmt==='pct' ? fpct(total) : 'MM$'+fmm(total);
      return `<tr>
        <td style="font-size:.62rem;white-space:nowrap;padding:.3rem .6rem">${label}</td>
        ${tds}
        <td class="num" style="color:${totCol};font-weight:700">${totDisp}</td>
      </tr>`;
    };

    const colIng  = v => v>0?'var(--az2)':'var(--rd)';
    const colContr = v => v>0?'var(--teal)':'var(--rd)';
    const colOtras = v => v>0?'var(--or)':'var(--rd)';
    const colCost  = () => '#b03030';
    const colMarg  = v => v>=0?'#007A72':'var(--rd)';
    const colPct   = v => v>=0.5?'#007A72':v>=0.3?'var(--or)':'var(--rd)';
    const colEbit  = v => v>=0?'#007A72':'var(--rd)';

    const sepRow = (label, bg='rgba(0,45,115,.07)') =>
      `<tr style="background:${bg}"><td colspan="${n+2}" style="font-size:.58rem;font-weight:700;color:var(--mut);padding:.25rem .6rem;letter-spacing:.05em">${label.toUpperCase()}</td></tr>`;

    valsEl.innerHTML = `
      <div style="overflow-x:auto">
        <table class="tbl" style="font-size:.63rem;width:100%;min-width:500px">
          <thead><tr>
            <th style="${colHdr};text-align:left;min-width:200px">Concepto</th>
            ${thMeses}${thTot}
          </tr></thead>
          <tbody>
            ${sepRow('Ingresos')}
            ${rowBase('Ingresos Totales (MM$)',RC.ingresos_totales,RC.total_ingresos_totales,colIng)}
            ${rowBase('Ingresos por Contratos (MM$)',RC.ingresos_contratos,RC.total_ingresos_contratos,colContr)}
            ${rowBase('Ingresos Otras Facturaciones (MM$)',RC.ingresos_otras,RC.total_ingresos_otras,colOtras)}
            ${sepRow('Costos')}
            ${rowBase('Costo de Ventas (MM$)',RC.costo_ventas,RC.total_costo_ventas,colCost)}
            ${rowBase('Gasto Beneficio Empleados (MM$)',RC.gastos_empleados,RC.total_gastos_empleados,colCost)}
            ${rowBase('Otros Gastos por Naturaleza (MM$)',RC.otros_gastos,RC.total_otros_gastos,colCost)}
            ${rowBase('GAV Total (MM$)',RC.gav_total,RC.total_gav,colCost)}
            ${sepRow('Resultados','rgba(0,122,114,.07)')}
            ${rowBase('Margen del Producto (MM$)',RC.margen_mm,RC.total_margen_mm,colMarg)}
            ${rowBase('Margen %',RC.margen_pct,RC.total_margen_pct,colPct,'pct')}
            ${rowBase('EBITDA (MM$)',RC.ebitda,RC.total_ebitda,colEbit)}
          </tbody>
        </table>
      </div>`;
  }

  // ── Toggle + tabla de ratios ───────────────────────────────────
  let _rcMode = 'totales';
  const seg = document.getElementById('rs-ratios-seg');
  if(seg){
    [{key:'totales',label:'Ingresos Totales'},{key:'contratos',label:'Ingresos Contratos'}].forEach((opt,idx)=>{
      const b = document.createElement('button');
      b.className = 'btn'+(idx===0?' on':'');
      b.textContent = opt.label;
      b.style.cssText = 'font-size:.58rem;padding:.18rem .5rem';
      b.addEventListener('click',()=>{
        seg.querySelectorAll('button').forEach(x=>x.classList.remove('on'));
        b.classList.add('on');
        _rcMode = opt.key;
        _renderRatios();
      });
      seg.appendChild(b);
    });
  }

  function _renderRatios(){
    const cardsEl = document.getElementById('rs-ratios-cards'); if(!cardsEl) return;
    const colHdr = 'background:var(--az3);color:rgba(255,255,255,.85);font-size:.6rem;font-weight:700;text-align:center;padding:.35rem .4rem';
    const thMeses = meses.map(m=>`<th style="${colHdr}">${m.slice(0,3)}</th>`).join('');
    const thTot   = `<th style="${colHdr};background:#1a3a6b">Total</th>`;

    const modoLabel = _rcMode==='totales' ? 'Ingresos Totales' : 'Ingresos Contratos';

    const ratioRows = RC.ratios.map((r,i)=>{
      const col = RATIO_COLORS[i];
      const vals = _rcMode==='totales' ? r.totales : r.contratos;
      const total = _rcMode==='totales' ? r.total_totales : r.total_contratos;
      const tds = vals.map(v=>{
        const x = v===null ? 0 : v;
        const c = x>=1?'#007A72':x>=0.7?'var(--or)':'var(--rd)';
        return `<td class="num" style="color:${c}">${x.toFixed(2)}x</td>`;
      }).join('');
      const totC = total>=1?'#007A72':total>=0.7?'var(--or)':'var(--rd)';
      const labelFull = `<span style="color:var(--mut);font-weight:400">${modoLabel}</span><span style="color:var(--mut)"> / </span>${r.nombre}`;
      return `<tr>
        <td style="white-space:nowrap;padding:.35rem .6rem">
          <span style="display:inline-block;width:8px;height:8px;background:${col};border-radius:50%;margin-right:.4rem;vertical-align:middle"></span>
          <span style="font-size:.62rem;font-weight:600">${labelFull}</span>
        </td>
        ${tds}
        <td class="num" style="color:${totC};font-weight:700">${total.toFixed(2)}x</td>
      </tr>`;
    }).join('');
    cardsEl.innerHTML = `
      <div style="overflow-x:auto">
        <table class="tbl" style="font-size:.63rem;width:100%;min-width:500px">
          <thead><tr>
            <th style="${colHdr};text-align:left;min-width:200px">Indicador</th>
            ${thMeses}${thTot}
          </tr></thead>
          <tbody>${ratioRows}</tbody>
        </table>
      </div>`;
  }

  _renderRatios();

  // ── Gráficos ──────────────────────────────────────────────────
  const safeArr = (arr) => Array.isArray(arr) ? arr : [];

  // Opciones de ingreso base (denominador del ratio)
  const BASE_OPTS = [
    { key:'totales',   label:'Ingresos Totales',   dataKey:'ingresos_totales',   color:'#002D73' },
    { key:'contratos', label:'Ingresos Contratos',  dataKey:'ingresos_contratos', color:'#0A5C8C' },
  ];
  // Opciones de costo a comparar (denominador del ratio)
  const COSTO_OPTS = [
    { key:'costo_total',     label:'Costos Totales',               dataKey:null,              color:'#8B0000' },
    { key:'costo_ventas',    label:'Costo de Ventas',              dataKey:'costo_ventas',    color:'#C00000' },
    { key:'gastos_empleados',label:'Gasto Beneficio Empleados',    dataKey:'gastos_empleados', color:'#7A1FAA' },
    { key:'otros_gastos',    label:'Otros Gastos por Naturaleza',  dataKey:'otros_gastos',    color:'#E87722' },
    { key:'gav_total',       label:'GAV Total',                    dataKey:'gav_total',       color:'#C05000' },
  ];

  let _rcBaseKey  = 'totales';
  let _rcCostoKey = 'costo_ventas';
  let _rcChart    = null;

  function _makeSeg(el, opts, getKey, setKey){
    if(!el) return;
    opts.forEach((opt, idx) => {
      const b = document.createElement('button');
      b.className = 'btn' + (idx===0?' on':'');
      b.textContent = opt.label;
      b.style.cssText = 'font-size:.58rem;padding:.18rem .5rem';
      b.addEventListener('click', () => {
        el.querySelectorAll('button').forEach(x=>x.classList.remove('on'));
        b.classList.add('on');
        setKey(opt.key);
        try{ _renderRCChart(); }catch(e){ console.error('RC chart error:', e); }
      });
      el.appendChild(b);
    });
  }

  _makeSeg(
    document.getElementById('rs-rc-base-seg'),
    BASE_OPTS,
    () => _rcBaseKey,
    k => { _rcBaseKey = k; }
  );
  _makeSeg(
    document.getElementById('rs-rc-costo-seg'),
    COSTO_OPTS,
    () => _rcCostoKey,
    k => { _rcCostoKey = k; }
  );

  function _renderRCChart(){
    const ctx = document.getElementById('cRsRatios'); if(!ctx) return;
    if(_rcChart){ _rcChart.destroy(); _rcChart=null; }
    const labels = safeArr(RC.meses);

    const baseOpt  = BASE_OPTS.find(o=>o.key===_rcBaseKey)  || BASE_OPTS[0];
    const costoOpt = COSTO_OPTS.find(o=>o.key===_rcCostoKey)|| COSTO_OPTS[0];

    const baseData = safeArr(RC[baseOpt.dataKey]);

    // Costos Totales se computa sumando los 3 componentes
    let costoData;
    if(costoOpt.key === 'costo_total'){
      const n = baseData.length;
      const cv = safeArr(RC.costo_ventas);
      const ge = safeArr(RC.gastos_empleados);
      const og = safeArr(RC.otros_gastos);
      costoData = Array.from({length: n}, (_,i) => Math.abs(cv[i]||0) + Math.abs(ge[i]||0) + Math.abs(og[i]||0));
    } else {
      costoData = safeArr(RC[costoOpt.dataKey]).map(v=>Math.abs(v||0));
    }

    // Ratio mes a mes: ingreso base / costo
    const ratioData = baseData.map((ing, i) => {
      const b = Math.abs(ing || 0);
      const c = costoData[i] || 0;
      return c > 0 ? +((b / c).toFixed(3)) : null;
    });

    const datasets = [
      {
        label: baseOpt.label,
        data: baseData,
        backgroundColor: baseOpt.color + 'BB',
        borderColor: baseOpt.color,
        borderWidth: 2,
        borderRadius: 4,
        yAxisID: 'y',
        order: 2,
      },
      {
        label: costoOpt.label,
        data: costoData,
        backgroundColor: costoOpt.color + 'BB',
        borderColor: costoOpt.color,
        borderWidth: 2,
        borderRadius: 4,
        yAxisID: 'y',
        order: 3,
      },
      {
        label: 'Ratio ' + baseOpt.label + ' / ' + costoOpt.label,
        data: ratioData,
        type: 'line',
        borderColor: '#FFC000',
        backgroundColor: '#FFC00033',
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 5,
        pointBackgroundColor: '#FFC000',
        fill: false,
        yAxisID: 'yRatio',
        order: 1,
      },
    ];

    _rcChart = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode:'index', intersect:false },
        plugins:{
          legend:{ position:'bottom', labels:{ boxWidth:12, font:{size:9}, padding:10 } },
          tooltip:{
            filter: item => item.dataset.yAxisID !== 'yRatio',
            callbacks:{
              label: c => ` ${c.dataset.label}: MM$${(c.raw||0).toFixed(1)}`,
              footer: items => {
                if(!items.length) return '';
                const i = items[0].dataIndex;
                const r = ratioData[i];
                return r !== null ? `Ratio: ${r.toFixed(2)}x` : '';
              }
            }
          }
        },
        scales:{
          x:{ grid:{display:false}, ticks:{font:{size:9}} },
          y:{
            beginAtZero:true,
            grid:{ color:'#E2E6F0' },
            ticks:{ font:{size:9}, callback: v=>'MM$'+v },
            title:{ display:true, text:'MM$', font:{size:8}, color:'var(--mut)' }
          },
          yRatio:{
            position:'right',
            beginAtZero:true,
            grid:{ display:false },
            ticks:{ font:{size:9}, callback: v=>v.toFixed(2)+'x' },
            title:{ display:true, text:'Ratio', font:{size:8}, color:'#B8860B' }
          }
        }
      }
    });
  }

  try{ _renderRCChart(); }catch(e){ console.error('RC chart error:', e); }
})();

// ─── TOP CLIENTES FACTURACIÓN 2026 ────────────────────────────
(function(){
  const mesLbl=document.getElementById('rs-fac-mes-lbl');if(mesLbl)mesLbl.textContent=MES_CORTE_NOMBRE;
  const top=APP_DATA.panel.filter(p=>(p.real_ytd||0)>0).sort((a,b)=>(b.real_ytd||0)-(a.real_ytd||0)).slice(0,12);
  const totYTD=APP_DATA.panel.reduce((s,p)=>s+(p.real_ytd||0),0);
  const foot=document.getElementById('rs-fac-foot');
  if(foot)foot.textContent=APP_DATA.panel.length+' clientes · '+fmtMM(totYTD)+' total YTD';
  const ctx=document.getElementById('cRsFacTop');if(!ctx)return;
  new Chart(ctx.getContext('2d'),{
    type:'bar',
    data:{labels:top.map(p=>p.cliente.length>40?p.cliente.slice(0,38)+'…':p.cliente),
      datasets:[{label:'Facturación YTD 2026',data:top.map(p=>(p.real_ytd||0)/1e6),
        backgroundColor:top.map((_,i)=>i<3?C.az2:i<6?C.az3:'#8AAEF0'),borderRadius:4}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` MM$${c.raw.toFixed(1)}`}}},
      scales:{x:{beginAtZero:true,grid:{color:'#E2E6F0'},ticks:{callback:v=>'MM$'+v}},
        y:{grid:{display:false},ticks:{font:{size:9}}}}}
  });
})();

// ─── CARTERA POR COORDINADORA ─────────────────────────────────
(function(){
  const grupos={};
  DATA.filter(d=>d.tipo==='Comercial').forEach(d=>{
    const k=d.coord||'Sin asignar';
    if(!grupos[k])grupos[k]={n:0,val:0};
    grupos[k].n++;grupos[k].val+=(d.val||0);
  });
  const arr=Object.entries(grupos).sort((a,b)=>b[1].val-a[1].val);
  const foot=document.getElementById('rs-coord-foot');
  if(foot)foot.textContent=arr.length+' coordinadoras · '+mm(arr.reduce((s,[,g])=>s+g.val,0))+' cartera total';
  const ctx=document.getElementById('cRsCoord');if(!ctx)return;
  const COORD_COLORS=['#003F7F','#0066CC','#28D2C3','#7A1FAA','#E87722','#E63312'];
  new Chart(ctx.getContext('2d'),{
    type:'bar',
    data:{labels:arr.map(([k])=>k.split(' ').slice(0,2).join(' ')),
      datasets:[{label:'Cartera COM (MM$)',data:arr.map(([,g])=>g.val/1e6),
        backgroundColor:arr.map((_,i)=>COORD_COLORS[i%COORD_COLORS.length]),borderRadius:4}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:(c)=>{const g=arr[c.dataIndex][1];return ` MM$${c.raw.toFixed(1)} · ${g.n} contratos`;} }}},
      scales:{x:{beginAtZero:true,grid:{color:'#E2E6F0'},ticks:{callback:v=>'MM$'+v,font:{size:9}}},
        y:{grid:{display:false},ticks:{font:{size:9}}}}}
  });
})();

// ─── NPS + SATISFACCIÓN RESUMEN ──────────────────────────────
(function(){
  if(!APP_DATA.satisf)return;
  const nps=APP_DATA.satisf.nps||{};
  const gl=APP_DATA.satisf.global||{};
  const calEl=document.getElementById('rs-sat-cal');if(calEl)calEl.textContent=(gl.calidad_avg||0).toFixed(2).replace('.',',');
  const tieEl=document.getElementById('rs-sat-tie');if(tieEl)tieEl.textContent=(gl.tiempo_avg||0).toFixed(2).replace('.',',');
  const recEl=document.getElementById('rs-sat-rec');if(recEl){
    recEl.textContent=(gl.recom_avg||0).toFixed(2).replace('.',',');
    recEl.style.color=(gl.recom_avg||0)>=7?'var(--gn)':(gl.recom_avg||0)>=4?'var(--am)':'var(--rd)';
  }
  const satFoot=document.getElementById('rs-sat-foot');
  if(satFoot)satFoot.textContent=(gl.n||0)+' respuestas · NPS '+((nps.nps||0)>0?'+':'')+(nps.nps||0)+' · '+(nps.pro||0)+' prom · '+(nps.pas||0)+' pas · '+(nps.det||0)+' det';
  const ctx=document.getElementById('cRsNps');if(!ctx)return;
  new Chart(ctx.getContext('2d'),{
    type:'bar',
    data:{labels:['Promotores','Pasivos','Detractores'],
      datasets:[{label:'Respuestas',data:[nps.pro||0,nps.pas||0,nps.det||0],
        backgroundColor:[C.gn,C.am,C.rd],borderRadius:5}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` ${c.raw} respuestas`}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:9}}},y:{beginAtZero:true,grid:{color:'#E2E6F0'},ticks:{stepSize:5}}}}
  });
})();

// ─── VISITAS MENSUALES RESUMEN ────────────────────────────────
(function(){
  if(!APP_DATA.visitas)return;
  const v=APP_DATA.visitas;
  const mesLbl=document.getElementById('rs-vis-mes-lbl');if(mesLbl)mesLbl.textContent=MES_CORTE_NOMBRE;
  const _rsVEjes=Object.keys(v.resumen||{});
  const re=v.resumen[_rsVEjes[0]]||{};
  const rc=v.resumen[_rsVEjes[1]]||{};
  const egEl=document.getElementById('rs-vis-eg');if(egEl)egEl.textContent=re.tot_2026_ytd||0;
  const crEl=document.getElementById('rs-vis-cr');if(crEl)crEl.textContent=rc.tot_2026_ytd||0;
  const tot=(re.tot_2026_ytd||0)+(rc.tot_2026_ytd||0);
  const visFoot=document.getElementById('rs-vis-foot');
  if(visFoot)visFoot.textContent=tot+' visitas YTD · '+MES_CORTE_NOMBRE+' '+ANO_ACTUAL;
  const meses=MESES_ABR.slice(0,MES_CORTE);
  const egD=((v.mensual[_rsVEjes[0]]||{})['2026']||[]).slice(0,MES_CORTE);
  const crD=((v.mensual[_rsVEjes[1]]||{})['2026']||[]).slice(0,MES_CORTE);
  const ctx=document.getElementById('cRsVis');if(!ctx)return;
  new Chart(ctx.getContext('2d'),{
    type:'bar',
    data:{labels:meses,datasets:[
      {label:(_rsVEjes[0]||'').split(' ')[0],data:egD,backgroundColor:'rgba(122,31,170,.8)',borderRadius:4,stack:'s'},
      {label:(_rsVEjes[1]||'').split(' ')[0],data:crD,backgroundColor:'rgba(0,63,127,.8)',borderRadius:4,stack:'s'}
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{position:'bottom',labels:{boxWidth:10,font:{size:10}}},
        tooltip:{mode:'index',callbacks:{label:c=>` ${c.dataset.label}: ${c.raw} visitas`}}},
      scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,beginAtZero:true,grid:{color:'#E2E6F0'},ticks:{stepSize:5}}}}
  });
})();

// ─── RESUMEN BAJO CONTRATO ────────────────────────────────────
(function(){
  const body=document.getElementById('rs-alerta-body');if(!body)return;
  const _allAlt=window.ALERTA_DATA||[];
  if(!_allAlt.length){body.innerHTML='<div style="color:var(--mut);font-size:.7rem;text-align:center;padding:1rem">Sin clientes bajo contrato</div>';return;}

  const gapFmt=v=>v===0?'—':(v>0?'−':'+')+'MM$'+(Math.abs(v)/1e6).toFixed(1);
  const gapCol=v=>v>0?'var(--rd)':v<0?'var(--teal)':'var(--mut)';

  // Botones de coordinador — default: Cynthia
  const coords=[...new Set(_allAlt.map(c=>c.coord).filter(Boolean))].sort();
  const _defaultCoord=coords.find(c=>c.toLowerCase().startsWith('cynthia'))||'todas';
  let _rsAltCoord=_defaultCoord;
  const seg=document.getElementById('rs-alt-seg');
  if(seg){
    seg.innerHTML='';
    const btnSt='font-size:.55rem;padding:.18rem .45rem';
    const bAll=document.createElement('button');
    bAll.className='btn'+(_defaultCoord==='todas'?' on':'');bAll.textContent='Todos';bAll.style.cssText=btnSt;
    bAll.addEventListener('click',()=>{seg.querySelectorAll('button').forEach(x=>x.classList.remove('on'));bAll.classList.add('on');_rsAltCoord='todas';_renderAltTable();});
    seg.appendChild(bAll);
    coords.forEach(coord=>{
      const b=document.createElement('button');
      b.className='btn'+(coord===_defaultCoord?' on':'');
      b.textContent=coord.split(' ')[0];b.style.cssText=btnSt;
      b.addEventListener('click',()=>{seg.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');_rsAltCoord=coord;_renderAltTable();});
      seg.appendChild(b);
    });
  }

  function _renderAltTable(){
    const data=_rsAltCoord==='todas'?_allAlt:_allAlt.filter(cli=>cli.coord===_rsAltCoord);
    const totCli=data.length;
    const totContr=data.reduce((s,cli)=>s+cli.contratos.length,0);
    const totEsp=data.reduce((s,cli)=>s+cli.total_expected,0);
    const totReal=data.reduce((s,cli)=>s+cli.total_real,0);
    const totGap=totEsp-totReal;

    const rowsHtml=data.map(cli=>{
      const d=cli.total_gap;
      return`<tr>
        <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${cli.cliente}"><strong>${cli.cliente}</strong></td>
        <td style="color:var(--mut);font-size:.58rem;white-space:nowrap">${cli.coord.split(' ')[0]}</td>
        <td style="text-align:center;color:var(--az2);font-size:.6rem;font-weight:700">${cli.contratos.length}</td>
        <td class="num" style="color:var(--az2)">${mm(cli.total_expected)}</td>
        <td class="num" style="color:var(--teal)">${mm(cli.total_real)}</td>
        <td class="num" style="color:${gapCol(d)};font-weight:800">${gapFmt(d)}</td>
      </tr>`;
    }).join('');

    const totRow=`<tr style="background:var(--az3);font-weight:700">
      <td colspan="3" style="padding:.4rem .7rem;font-size:.62rem;color:rgba(255,255,255,.7)">
        Total · ${totCli} cliente${totCli!==1?'s':''} · ${totContr} contrato${totContr!==1?'s':''}
      </td>
      <td class="num" style="color:rgba(255,255,255,.9)">${mm(totEsp)}</td>
      <td class="num" style="color:var(--teal)">${mm(totReal)}</td>
      <td class="num" style="color:${gapCol(totGap)}">${gapFmt(totGap)}</td>
    </tr>`;

    body.innerHTML=`
      <div style="overflow-x:auto">
        <table class="tbl" style="font-size:.63rem;width:100%">
          <thead><tr>
            <th>Cliente</th><th>Coord.</th>
            <th style="text-align:center">N° Contratos</th>
            <th>Esperado a la fecha</th><th>Real a la fecha</th><th>Diferencia a la fecha</th>
          </tr></thead>
          <tbody>${rowsHtml}</tbody>
          <tfoot>${totRow}</tfoot>
        </table>
      </div>`;
  }
  _renderAltTable();
})();
