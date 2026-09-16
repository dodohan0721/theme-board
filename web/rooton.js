/* Dependency-free SVG charts shared by the two ROOTON services. */
(() => {
 'use strict';
 let serial = 0;
 const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const shapes = {
 chip:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
 power:'<path d="m13 2-8 12h6l-1 8 9-13h-6z"/>',
 ship:'<path d="M3 15 12 19l9-4-2 6H5zM6 16V9h12v7M9 9V5h6v4M12 5V2"/>',
 shield:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6z"/><path d="m8 12 3 3 5-6"/>',
 robot:'<rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 2v4M8 15h8M2 11v4m20-4v4"/><circle cx="8" cy="11" r="1"/><circle cx="16" cy="11" r="1"/>',
 bio:'<path d="M7 2c0 10 10 10 10 20M17 2C17 12 7 12 7 22M8 4h8M8 20h8M9 8h6M9 16h6"/>',
 layers:'<path d="m12 3 10 5-10 5L2 8zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
 globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
 coin:'<circle cx="12" cy="12" r="9"/><path d="M9 6v12m-2-2h7a3 3 0 0 0 0-6H9m-2-2h6a2 2 0 0 1 0 4"/>',
 swap:'<path d="M3 7h17l-4-4m4 4-4 4M21 17H4l4-4m-4 4 4 4"/>',
 news:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h4M8 18h8"/>'
 };
 const icon = name => '<svg viewBox="0 0 24 24" aria-hidden="true">'+(shapes[name] || shapes.layers)+'</svg>';
 const kind = name => /반도체|HBM|AI|전자|chip/i.test(name)?'chip':/전력|에너지|태양|power/i.test(name)?'power':/조선|해운/.test(name)?'ship':/방산|방위/.test(name)?'shield':/로봇|자동차/.test(name)?'robot':/바이오|제약|의료/.test(name)?'bio':/DEX|DeFi/.test(name)?'swap':/결제|밈/.test(name)?'coin':'layers';
 const number = v => Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
 function chart(host, input, options = {}) {
  if (!host) return;
  const rows=(input||[]).filter(r=>r.value!=null && Number.isFinite(Number(r.value))).map(r=>({...r,value:Number(r.value)}));
  const id='rtplot'+(++serial), isBar=options.type==='bar';
  host.classList.add('rt-chart');
  host._rtChart={input,options,width:host.clientWidth};
  if(rows.length<(isBar?1:2)){
   host.innerHTML='<div class="rt-chart-empty"><b>'+esc(options.emptyTitle || '시계열을 기다리고 있습니다')+'</b><small>'+esc(options.empty || '데이터가 두 개 이상 모이면 추이를 표시합니다.')+'</small></div>';return;
  }
  const W=Math.max(280,Math.round(host.clientWidth||760)),H=options.height||190,L=W<420?50:55,R=16,T=20,B=34,iw=W-L-R,ih=H-T-B;
  const values=rows.map(r=>r.value);
  let lo=isBar?Math.min(0,...values):Math.min(...values),hi=Math.max(...values);
  const pad=(hi-lo)*.12 || Math.max(Math.abs(hi)*.015,1);
  if(!isBar) lo-=pad; hi+=pad;
  if (hi===lo)hi=lo+1;
  const timed=!isBar&&rows.every(r=>Number.isFinite(Number(r.time)))&&Number(rows.at(-1).time)>Number(rows[0].time);
  const X=i=>L+(isBar?(i+.5)/rows.length:timed?(Number(rows[i].time)-Number(rows[0].time))/(Number(rows.at(-1).time)-Number(rows[0].time)):i/(rows.length-1))*iw;
  const Y=v=>T+(hi-v)/(hi-lo)*ih;
  const fmt=options.format||number,axis=options.axis||fmt;
  const ink=options.light?'#79828a':'#e3e9eb',line=options.light?'#6c8b90':'#fff0b5';
  let markup='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(options.label||'데이터 추이')+'"><title>'+esc(options.label||'데이터 추이')+'</title><defs><linearGradient id="'+id+'line" x1="0" x2="1"><stop stop-color="'+(options.light?'#5d91ae':'#b6e1dd')+'"/><stop offset="1" stop-color="'+line+'"/></linearGradient><linearGradient id="'+id+'fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="'+line+'" stop-opacity=".3"/><stop offset="1" stop-color="'+line+'" stop-opacity="0"/></linearGradient><linearGradient id="'+id+'bar" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#eee0b7"/><stop offset="1" stop-color="#a3c5d1" stop-opacity=".35"/></linearGradient></defs>';
  for(let i=0;i<3;i++){const v=lo+(hi-lo)*i/2,y=Y(v);markup+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="'+ink+'" opacity=".23" stroke-dasharray="2 5"/><text x="'+(L-9)+'" y="'+(y+4)+'" text-anchor="end" fill="'+ink+'">'+esc(axis(v))+'</text>';}
  if(isBar){
   const bw=Math.min(62,iw/rows.length*.48),zero=Y(0);
   rows.forEach((r,i)=>{const y=Math.min(zero,Y(r.value)),h=Math.max(1,Math.abs(zero-Y(r.value)));markup+='<rect x="'+(X(i)-bw/2)+'" y="'+y+'" width="'+bw+'" height="'+h+'" rx="6" fill="url(#'+id+'bar)"/>';});
  }else{
   const d=rows.map((r,i)=>((!i||(timed&&options.maxGapMs&&Number(r.time)-Number(rows[i-1].time)>options.maxGapMs))?'M':'L')+X(i).toFixed(2)+' '+Y(r.value).toFixed(2)).join(' ');
   markup+=(options.maxGapMs?'':'<path d="'+d+' L'+X(rows.length-1)+' '+(T+ih)+' L'+L+' '+(T+ih)+' Z" fill="url(#'+id+'fill)"/>')+'<path d="'+d+'" fill="none" stroke="url(#'+id+'line)" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>';
  }
  if(!isBar&&options.reference!=null&&Number.isFinite(Number(options.reference))){const ry=Y(Number(options.reference));markup+='<line x1="'+L+'" y1="'+ry+'" x2="'+(W-R)+'" y2="'+ry+'" stroke="'+line+'" stroke-dasharray="4 4" opacity=".7"/><text x="'+(W-R-3)+'" y="'+(ry-7)+'" text-anchor="end" fill="'+line+'">'+esc(fmt(Number(options.reference)))+'</text>';}
  const ticks=isBar?rows.map((_,i)=>i):[...new Set([0,Math.round((rows.length-1)*.25),Math.round((rows.length-1)*.5),Math.round((rows.length-1)*.75),rows.length-1])];
  ticks.forEach(i=>{markup+='<text x="'+X(i)+'" y="'+(H-9)+'" text-anchor="'+(!isBar&&i===0?'start':!isBar&&i===rows.length-1?'end':'middle')+'" fill="'+ink+'">'+esc(isBar&&W<480?(rows[i].shortLabel||rows[i].label||'').slice(0,3):(rows[i].shortLabel||rows[i].label||''))+'</text>';});
  markup+='<g class="rt-cross" opacity="0"><line class="rt-cross-line" y1="'+T+'" y2="'+(T+ih)+'" stroke="'+ink+'" stroke-dasharray="3 4"/><circle class="rt-halo" r="11" fill="'+line+'" opacity=".16"/><circle class="rt-dot" r="4.5" fill="'+line+'" stroke="#fff" stroke-width="1.8"/></g><rect class="rt-chart-hit" x="'+L+'" y="'+T+'" width="'+iw+'" height="'+ih+'" fill="transparent" tabindex="0" role="slider" aria-label="'+esc((options.label||'차트')+' · 좌우 방향키로 값 확인')+'" aria-valuemin="0" aria-valuemax="'+(rows.length-1)+'" aria-valuenow="'+(rows.length-1)+'"/></svg><div class="rt-chart-tip"></div><p class="rt-chart-note">'+esc(options.note||'마우스·터치 또는 방향키로 값 확인')+'</p>';
  host.innerHTML=markup;
  const svg=host.querySelector('svg'),hit=host.querySelector('.rt-chart-hit'),tip=host.querySelector('.rt-chart-tip'),cross=host.querySelector('.rt-cross');
  let selected=rows.length-1;
  function show(i){selected=Math.max(0,Math.min(rows.length-1,i));const r=rows[selected],x=X(selected),y=Y(r.value);
   cross.setAttribute('opacity','1');cross.querySelector('line').setAttribute('x1',x);cross.querySelector('line').setAttribute('x2',x);cross.querySelectorAll('circle').forEach(c=>{c.setAttribute('cx',x);c.setAttribute('cy',y);});
   tip.innerHTML='<span>'+esc(r.label||'')+'</span>'+esc(fmt(r.value));tip.classList.add('on');tip.style.left=Math.max(15,Math.min(85,x/W*100))+'%';
   hit.setAttribute('aria-valuenow',selected);hit.setAttribute('aria-valuetext',(r.label||'')+' '+fmt(r.value));
  }
  hit.addEventListener('pointerdown',()=>hit.focus({preventScroll:true}));
  hit.addEventListener('pointermove',e=>{const point=svg.createSVGPoint();point.x=e.clientX;point.y=e.clientY;const x=point.matrixTransform(svg.getScreenCTM().inverse()).x;let nearest=0;rows.forEach((_,i)=>{if(Math.abs(X(i)-x)<Math.abs(X(nearest)-x))nearest=i;});show(nearest);});
  hit.addEventListener('pointerleave',()=>{if(document.activeElement!==hit){cross.setAttribute('opacity','0');tip.classList.remove('on');}});
  hit.addEventListener('focus',()=>show(selected));hit.addEventListener('blur',()=>{cross.setAttribute('opacity','0');tip.classList.remove('on');});
  hit.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();show(e.key==='Home'?0:e.key==='End'?rows.length-1:selected+(e.key==='ArrowLeft'?-1:1));});
 }
 let resizeTimer;
 window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>document.querySelectorAll('.rt-chart').forEach(host=>{const state=host._rtChart;if(state&&host.clientWidth>0&&state.width!==host.clientWidth)chart(host,state.input,state.options);}),100);});
 window.RootonUI={escape:esc,icon,kind,chart,number};
})();
