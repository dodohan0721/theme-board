#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 5차
    ③ 테마 카드에 거래대금을 등락률과 나란히 표시
    ⑤ '테마 구성 종목 수' 필터 추가 — 상위 N종목만으로 다시 계산

    cd ~/theme-board
    python3 fix5.py

서버는 손대지 않습니다. data.json 에 이미 들어 있는 값으로
브라우저에서 다시 계산하므로 고르는 즉시 순서가 바뀝니다.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []

P = "web/index.html"
if not os.path.exists(P):
    print(f"  {R}✗{N} {P} 없음 — ~/theme-board 에서 실행하세요."); sys.exit(1)
s = open(P, encoding="utf-8").read()


def sub(desc, old, new, marker=None):
    global s
    if (marker or new) in s:
        SKIP.append(f"{desc} — 이미 적용됨"); return
    if old not in s:
        FAIL.append(f"{desc} — 위치를 못 찾음"); return
    s = s.replace(old, new, 1); OK.append(desc)


# ── 1. 전역 변수 ───────────────────────────────────────────────────────────
sub("topN 변수 추가",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300;",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap';",
    "topN=0, wgt=")

# ── 2. 테마 재계산 함수 + applyFilter ──────────────────────────────────────
sub("테마 재계산(tview) 추가",
"""function applyFilter(){
  const keep=RAW.themes.filter(t=>t.value>=minv);""",
"""// 테마를 '거래대금 상위 topN 종목'만으로 다시 계산한다.
// topN=0 이면 원래대로 전체 구성 종목을 쓴다.
function tview(t){
  const S=RAW.stocks;
  if(!topN||!t.codes||t.codes.length<=topN) return t;
  const pick=[...t.codes].sort((a,b)=>((S[b]||{}).value||0)-((S[a]||{}).value||0)).slice(0,topN);
  let val=0,cap=0,wsum=0,rsum=0,up=0;
  pick.forEach(c=>{const x=S[c]||{}; const r=x.rate||0, cp=x.cap||0;
    val+=x.value||0; cap+=cp; wsum+=cp*r; rsum+=r; if(r>0)up++;});
  const byRate=[...pick].sort((a,b)=>((S[b]||{}).rate||0)-((S[a]||{}).rate||0));
  return {...t, codes:byRate, value:Math.round(val),
    pct:+((cap?wsum/cap:rsum/pick.length)).toFixed(2),
    pct_eq:+(rsum/pick.length).toFixed(2),
    up, n:pick.length, picked:true};
}
function applyFilter(){
  const keep=RAW.themes.map(tview).map(t=>({...t,pct:(wgt==='eq'?t.pct_eq:t.pct)}))
                       .filter(t=>t.value>=minv);""",
    "function tview(t){")

# ── 3. 거래대금순 정렬을 명시 (재계산 후에도 순서가 맞도록) ────────────────
sub("거래대금순 정렬 명시",
"""  if(sortKey==='pct')ts.sort((a,b)=>b.pct-a.pct);""",
"""  if(sortKey==='value')ts.sort((a,b)=>b.value-a.value);
  if(sortKey==='pct')ts.sort((a,b)=>b.pct-a.pct);""",
    "sortKey==='value')ts.sort")

# ── 4. 필터 UI 추가 ────────────────────────────────────────────────────────
sub("테마 구성 종목 수 필터 추가",
"""      .map(([v,l])=>`<option value="${v}" ${minv===v?'selected':''}>${l}</option>`).join('')}
  </select></div>""",
"""      .map(([v,l])=>`<option value="${v}" ${minv===v?'selected':''}>${l}</option>`).join('')}
  </select>
  <select style="padding:7px 10px;font-size:13px;font-weight:700;color:var(--ink2);border:1px solid var(--line);border-radius:9px;background:#fff"
    onchange="topN=+this.value;applyFilter();viewHome()">
    ${[[0,'테마 구성 전체'],[3,'주도 3종목'],[5,'주도 5종목'],[10,'주도 10종목'],[20,'주도 20종목']]
      .map(([v,l])=>`<option value="${v}" ${topN===v?'selected':''}>${l}</option>`).join('')}
  </select>
  <select style="padding:7px 10px;font-size:13px;font-weight:700;color:var(--ink2);border:1px solid var(--line);border-radius:9px;background:#fff"
    onchange="wgt=this.value;applyFilter();viewHome()">
    ${[['cap','시총가중'],['eq','동일가중']].map(([v,l])=>
      `<option value="${v}" ${wgt===v?'selected':''}>${l}</option>`).join('')}
  </select></div>""",
    "테마 구성 전체")

# ── 5. 안내 문구 ───────────────────────────────────────────────────────────
sub("필터 설명 문구",
"""  테마 <b>${D.theme_total}개</b> 중 조건을 넘긴 <b>${D.themes.length}개</b>만 표시합니다${D.hidden?` (거래대금 ${minv}억 미만 ${D.hidden}개 숨김)`:''}.</div>""",
"""  테마 <b>${D.theme_total}개</b> 중 조건을 넘긴 <b>${D.themes.length}개</b>만 표시합니다${D.hidden?` (거래대금 ${minv}억 미만 ${D.hidden}개 숨김)`:''}.
  ${topN?`<br><b style="color:var(--teal-d,#04868c)">테마마다 거래대금 상위 ${topN}종목만으로 거래대금·등락률을 다시 계산했습니다.</b> 대형주가 섞여 희석되는 것을 막아, 그날 실제로 주도한 테마가 위로 올라옵니다.`:''}</div>""",
    "종목만으로 거래대금·등락률을 다시 계산")

# ── 6. 카드 헤더에 거래대금 ────────────────────────────────────────────────
sub("카드 헤더에 거래대금 표시",
"""    <div class="chead"><div class="cpill" onclick="openTheme('${t.id}')">${t.name}</div>
      <div class="cpct ${cls(t.pct)} num">${pct(t.pct)}</div></div>
    <div class="cmeta"><span>거래대금 <b>${vfmt(t.value)}</b></span>
      <span>상승 <b>${t.up}/${t.n}</b></span><span class="chip g">${t.cat}</span>""",
"""    <div class="chead"><div class="cpill" onclick="openTheme('${t.id}')">${t.name}</div>
      <div class="cval num">${vfmt(t.value)}</div>
      <div class="cpct ${cls(t.pct)} num">${pct(t.pct)}</div></div>
    <div class="cmeta"><span>상승 <b>${t.up}/${t.n}</b>${t.picked?` <span style="color:var(--teal)">주도 ${t.n}</span>`:''}</span>
      <span class="chip g">${t.cat}</span>""",
    'class="cval num"')

# ── 7. CSS ─────────────────────────────────────────────────────────────────
sub("거래대금 칸 CSS",
""".cpct{background:#fff;border:1px solid var(--line);border-radius:9px;padding:5px 11px;font-weight:900;font-size:19px;display:flex;align-items:center;min-width:88px;justify-content:flex-end}""",
""".cval{background:#eef6f6;border:1px solid var(--line);border-radius:9px;padding:5px 9px;font-weight:800;font-size:14px;color:#3d5155;display:flex;align-items:center;white-space:nowrap}
.cpct{background:#fff;border:1px solid var(--line);border-radius:9px;padding:5px 9px;font-weight:900;font-size:18px;display:flex;align-items:center;min-width:76px;justify-content:flex-end}""",
    ".cval{")

# ── 8. 테마 상세는 항상 전체 구성으로 ──────────────────────────────────────
sub("테마 상세는 전체 구성 기준",
"""  const t=D.themes.find(x=>x.id===id)||RAW.themes.find(x=>x.id===id);""",
"""  const t=RAW.themes.find(x=>x.id===id)||D.themes.find(x=>x.id===id);""",
    "RAW.themes.find(x=>x.id===id)||D.themes")

open(P, "w", encoding="utf-8").write(s)

# ── 검증 ───────────────────────────────────────────────────────────────────
chk = open(P, encoding="utf-8").read()
if chk.count("`") % 2 == 0: OK.append("템플릿 문자열 짝 정상")
else: FAIL.append("백틱(`) 홀수 — 템플릿 문자열 깨짐")

print("\n" + "=" * 58)
for x in OK:   print(f"  {G}✓{N} {x}")
for x in SKIP: print(f"  {Y}·{N} {x}")
for x in FAIL: print(f"  {R}✗{N} {x}")
print("=" * 58)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)
print(f"""
{B}반영{N}
    git commit -am "테마 구성 종목 수 필터 · 카드에 거래대금 표시"
    git push
    gh workflow run snapshot.yml

{B}확인{N}
    https://theme-board.pages.dev
    위쪽 필터에서 '주도 5종목' 을 골라보세요.
    테마 순서가 바뀌고, 로봇 계열이 위로 올라오는지 보시면 됩니다.
""")
