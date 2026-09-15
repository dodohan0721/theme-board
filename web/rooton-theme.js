/* Presentation adapter: keeps original calculations, APIs and authorization. */
(() => {
 'use strict';
 const ui=RootonUI,E=ui.escape;
 let heroMode='themes',search='',selected='';
 document.body.classList.add('rt-app','rt-theme');
 const logo=document.querySelector('.logo');
 logo.outerHTML='<a class="rt-brand" href="https://mainsaju.shop/">ROOTON<small>시장의 흐름을 읽다</small></a>';
 document.querySelector('[data-m="kr"]').textContent='국내주식';
 document.querySelector('[data-m="us"]').textContent='해외주식';
 const nav=document.querySelector('.gnb'),guide=nav.querySelector('a');
 if(guide){guide.className='rt-guide';guide.textContent='이용 가이드';}
 nav.querySelector('.mktsw').insertAdjacentHTML('afterend','<a href="https://crypto-etf.pages.dev/">크립토</a>');
 document.querySelector('[data-k="home"]').textContent='테마보드';
 document.querySelector('[data-k="rank"]').textContent='랭킹';
 nav.insertAdjacentHTML('afterend','<label class="rt-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg><input id="rt-search" type="search" placeholder="종목·테마 검색" aria-label="종목·테마 검색"></label>');
 compact=true;
 document.querySelectorAll("[data-m]").forEach(b=>b.classList.toggle("on",b.dataset.m===MKT));
 if(MKT==="us")minv=5;
 function sortedThemes(){
  let list=[...D.themes];
  const term=search.trim().toLowerCase();
  if(term)list=list.filter(t=>t.name.toLowerCase().includes(term)||(t.codes||[]).some(c=>(RAW.stocks[c]?.name||'').toLowerCase().includes(term)||c.includes(term)));
  list.sort(sortKey==='pct'?(a,b)=>b.pct-a.pct:sortKey==='ratio'?(a,b)=>b.up/Math.max(b.n,1)-a.up/Math.max(a.n,1):(a,b)=>b.value-a.value);
  dupN=0;
  if(dedup){const filtered=dedupThemes(list);dupN=list.length-filtered.length;list=filtered;}
  return list;
 }
 function hero(list){
  const night=MKT==='kr'&&heroMode==='night',total=Object.values(RAW.stocks||{}).reduce((s,r)=>s+(Number(r.value)||0),0);
  let value=night?(NGT?.last!=null?nf(NGT.last):'—'):displayValue(total);
  return '<section class="rt-hero"><div class="rt-hero-copy">'+(MKT==='kr'?'<div class="rt-hero-tabs"><button data-hero="themes" aria-pressed="'+!night+'">테마 거래대금</button><button data-hero="night" aria-pressed="'+night+'">야간선물</button></div>':'<p class="rt-eyebrow">GLOBAL MARKET</p>')+
   '<h1>'+(night?'KOSPI200 야간선물':MKT==='us'?'해외 테마의 흐름':'오늘, 자금이 향하는 곳')+'</h1><div class="rt-number">'+value+'</div><div class="rt-hero-meta">'+(night?(NGT?'<strong class="'+cls(NGT.rate)+'">'+pct(NGT.rate)+'</strong> '+E(NGT.code)+' · '+E(NGT.ts)+' 기준':'체결 데이터 연결 대기'):'조회 종목 거래대금 · '+E(MKT==='us'?'NASDAQ · NYSE · AMEX':'KRX · NXT')+'<br><strong>'+nf(RAW.scanned)+'</strong> 종목 · <strong>'+nf(D.themes.length)+'</strong> 조건 충족 테마')+'</div></div><div id="rt-market-chart"></div></section>';
 }
 function drawHero(list){
  const host=document.getElementById('rt-market-chart');
  if(MKT==='kr'&&heroMode==='night'){
   const rows=(NGT?.history||[]).filter(p=>p.last!=null).map(p=>({label:p.time||p.ts?.slice(11,16),shortLabel:(p.time||p.ts?.slice(11,16)||'').slice(0,5),value:p.last,time:Date.parse(p.ts?.replace(' ','T')+'+09:00')}));
   ui.chart(host,rows,{label:'KOSPI200 야간선물 체결 추이',format:v=>v.toFixed(2),axis:v=>v.toFixed(1),emptyTitle:NGT?'체결 시계열 수집 중':'야간선물 데이터 연결 대기',empty:'체결값이 누적되면 그래프가 표시됩니다. 수신하지 않은 시세는 그리지 않습니다.',note:'저장된 체결 기준 · 비연속 수집 구간이 포함될 수 있습니다'});
  }else{
   ui.chart(host,list.slice(0,6).map(t=>({label:t.name,shortLabel:t.name.length>7?t.name.slice(0,6)+'…':t.name,value:t.value})),{type:'bar',height:170,label:'상위 여섯 테마 거래대금 비교',format:v=>vfmt(v),axis:v=>MKT==='us'?vfmt(v):v>=1000?(v/10000).toFixed(v>=10000?1:2)+'조':nf(Math.round(v))+'억',note:'상위 6개 테마 · 구성 종목은 테마 간 중복될 수 있습니다'});
  }
 }
 function options(items,val){return items.map(([v,l])=>'<option value="'+v+'" '+(String(val)===String(v)?'selected':'')+'>'+l+'</option>').join('');}
 cardHTML=function(t){
  const codes=(t.codes||[]).slice(0,compact?3:5),hd=themeHead(t);
  return '<article class="rt-raised rt-theme-card '+(selected===t.id?'is-selected':'')+'"><div class="rt-card-top"><span class="rt-emblem">'+ui.icon(ui.kind(t.name))+'</span><div class="rt-card-title"><button data-theme="'+E(t.id)+'">'+E(t.name)+'</button><small>'+E(t.cat)+' · '+t.n+'종목</small></div><strong class="rt-card-pct '+cls(t.pct)+'">'+pct(t.pct)+'</strong></div>'+
   '<div class="rt-card-summary"><span>거래대금</span><strong>'+vfmt(t.value)+'</strong><span>상승 '+t.up+'/'+t.n+'</span></div><div class="rt-stock-rows">'+codes.map(c=>{
    const s=RAW.stocks[c];if(!s)return '';
    return '<button class="rt-stock-row" data-stock="'+E(c)+'" data-parent="'+E(t.id)+'" title="'+E(s.name)+' 상세 보기"><span>'+E(s.name)+'</span><span class="rt-row-rate '+cls(s.rate)+'">'+pct(s.rate)+'</span><span class="rt-row-value">'+vv(s.value)+'</span></button>';
   }).join('')+'</div><div class="rt-card-news">'+ui.icon('news')+'<span>'+(hd?E(hd.headline):'종목을 선택해 상승 이유와 재무정보를 확인하세요.')+'</span></div><button class="rt-card-more" data-theme="'+E(t.id)+'">구성 종목 '+t.n+'개 보기 →</button></article>';
 };
 viewHome=function(){
  if(!D)return;
  const list=sortedThemes(),shown=compact?list.slice(0,6):list;
  const age=Math.max(0,Math.round((Date.now()-Date.parse(D.ts.replace(' ','T')+'+09:00'))/60000));
  document.getElementById('view').innerHTML=hero(list)+
   '<div class="rt-section-head"><div><p class="rt-eyebrow">'+(MKT==='us'?'GLOBAL THEMES':'MARKET PULSE')+'</p><h2>'+(MKT==='us'?'해외 시장의 주도 테마':'오늘의 주도 테마')+'</h2><p>숫자의 움직임에서, 그 이유까지.</p></div><span class="rt-count">'+shown.length+' / '+list.length+'개 테마<span class="rt-snapshot">'+E(D.ts)+' 기준'+(age>1440?' · 저장 데이터':'')+'</span></span></div>'+
   '<div class="rt-controls"><div class="rt-controls-left"><div class="seg">'+[['value','거래대금순'],['pct','등락률순'],['ratio','상승비율순']].map(([k,l])=>'<button data-sort="'+k+'" class="'+(sortKey===k?'on':'')+'">'+l+'</button>').join('')+'</div><button class="rt-pill" data-expand>'+(compact?'주도 6개':'전체 테마')+'</button></div>'+
   '<details class="rt-filters"><summary>조회 조건 조정</summary><div class="rt-filter-body"><label>거래대금<select data-filter="minv">'+options(MKT==='us'?[[0,'전체'],[5,'5M$ 이상'],[20,'20M$ 이상'],[50,'50M$ 이상'],[200,'200M$ 이상']]:[[0,'전체'],[100,'100억 이상'],[300,'300억 이상'],[500,'500억 이상'],[1000,'1,000억 이상'],[3000,'3,000억 이상']],minv)+'</select></label><label>구성 종목<select data-filter="topN">'+options([[0,'전체 구성'],[3,'주도 3종목'],[5,'주도 5종목'],[10,'주도 10종목'],[20,'주도 20종목']],topN)+'</select></label><label>등락률<select data-filter="wgt">'+options([['cap','시총가중'],['eq','동일가중']],wgt)+'</select></label><label><input type="checkbox" data-filter="dedup" '+(dedup?'checked':'')+'>중복 테마 정리</label></div></details></div>'+
   '<div class="cards'+(compact?' cp':'')+'">'+(shown.map(cardHTML).join('')||'<div class="load">조건에 맞는 테마가 없습니다.</div>')+'</div>'+
   (compact&&list.length>6?'<button class="rt-more-themes" data-expand>전체 '+list.length+'개 테마 펼치기 ↓</button>':'')+
   '<details class="market-note"><summary>집계 기준 · '+E(D.ts)+' 스냅샷'+(age>1440?' · 저장 데이터':age>20?' · '+age+'분 전':'')+'</summary><div class="note">시세는 위 기준 시각의 스냅샷입니다. '+E(MKT==='kr'?'KRX + NXT 합산 거래대금':'미국 거래소 기준 · 거래대금 단위 백만달러')+'. '+(dupN?'구성 종목이 겹치는 '+dupN+'개 테마를 정리했습니다. ':'')+(topN?'테마별 거래대금 상위 '+topN+'종목으로 다시 계산했습니다.':'전체 구성 종목으로 집계합니다.')+'</div></details>';
  drawHero(list);
 };
 document.addEventListener('click',e=>{
  const b=e.target.closest('[data-hero],[data-sort],[data-expand],[data-stock],[data-theme]');if(!b)return;
  if(b.hasAttribute('data-hero')){heroMode=b.dataset.hero;viewHome();}
  if(b.hasAttribute('data-sort')){sortKey=b.dataset.sort;viewHome();}
  if(b.hasAttribute('data-expand')){compact=!compact;viewHome();}
  if(b.hasAttribute('data-theme')){selected=b.dataset.theme;viewHome();openTheme(selected);}
  if(b.hasAttribute('data-stock')){selected=b.dataset.parent;document.querySelectorAll('.rt-theme-card').forEach(c=>c.classList.toggle('is-selected',c.contains(b)));openStock(b.dataset.stock);}
 });
 document.addEventListener('change',e=>{
  const k=e.target.dataset.filter;if(!k)return;
  if(k==='minv')minv=+e.target.value;if(k==='topN')topN=+e.target.value;if(k==='wgt')wgt=e.target.value;if(k==='dedup')dedup=e.target.checked;applyFilter();viewHome();
 });
 let timer;
 document.getElementById('rt-search').addEventListener('input',e=>{search=e.target.value;clearTimeout(timer);timer=setTimeout(()=>{if(cur!=='home')go('home');else viewHome();},120);});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.getElementById('dt').classList.contains('on'))closeDt();});
 if(D){applyFilter();render();}
})();
