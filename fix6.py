#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 6차
    ③ '한눈에' 보기 — 상위 6개 테마를 한 화면에
    ④ 테마 카드에 대표 뉴스 한 줄 — 그 테마를 끌어올린 종목의 상승 사유

    cd ~/theme-board
    python3 fix6.py

④ 는 이미 판독해 둔 근거(details)를 그대로 끌어다 쓰므로
API 호출도, 추가 비용도 없습니다.
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


# ── 1. compact 전역 ────────────────────────────────────────────────────────
sub("한눈에 보기 상태값",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap';",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap', compact=false;",
    "compact=false;")

# ── 2. 테마 대표 뉴스 뽑기 ─────────────────────────────────────────────────
sub("테마 대표 뉴스 함수",
"""function cardHTML(t){""",
"""// 테마를 끌어올린 종목의 '상승 사유'를 테마 카드 대표 문장으로 쓴다.
// 이미 판독해 둔 결과(details)를 재사용하므로 추가 호출이 없다.
function themeHead(t){
  const DT=RAW.details||{};
  for(const c of (t.codes||[])){
    const r=(DT[c]||{}).reason;
    if(r&&r.status==='ok'&&r.headline)
      return {code:c, name:(RAW.stocks[c]||{}).name||'', headline:r.headline, verified:!!r.verified};
  }
  return null;
}
function cardHTML(t){""",
    "function themeHead(t){")

# ── 3. 카드에 대표 뉴스 줄 + 한눈에 모드 ───────────────────────────────────
sub("카드에 대표 뉴스 줄",
"""  const codes=t.codes.slice(0,5);""",
"""  const codes=t.codes.slice(0,compact?3:5);
  const hd=themeHead(t);""",
    "compact?3:5")

sub("대표 뉴스 표시",
"""      <div class="cpct ${cls(t.pct)} num">${pct(t.pct)}</div></div>
    <div class="cmeta">""",
"""      <div class="cpct ${cls(t.pct)} num">${pct(t.pct)}</div></div>
    ${hd?`<div class="chl" title="${hd.headline}" onclick="openStock('${hd.code}')">
      <b>${hd.name}</b><span class="tx">${hd.headline}</span>${hd.verified?'<span class="ok">✓</span>':''}</div>`:''}
    <div class="cmeta">""",
    'class="chl"')

# ── 4. 한눈에 버튼 ─────────────────────────────────────────────────────────
sub("한눈에 버튼 추가",
"""      `<button class="${sortKey===k?'on':''}" onclick="sortKey='${k}';viewHome()">${l}</button>`).join('')}
  </div>""",
"""      `<button class="${sortKey===k?'on':''}" onclick="sortKey='${k}';viewHome()">${l}</button>`).join('')}
  </div>
  <div class="seg"><button class="${compact?'on':''}" onclick="compact=!compact;viewHome()">${compact?'✓ 한눈에':'한눈에'}</button></div>""",
    "compact=!compact")

# ── 5. 상위 6개만 + compact 클래스 ─────────────────────────────────────────
sub("한눈에 모드에서 상위 6개만",
"""  <div class="cards">${ts.map(cardHTML).join('')||'<div class="load">조건에 맞는 테마가 없습니다.</div>'}</div>`;""",
"""  <div class="cards${compact?' cp':''}">${(compact?ts.slice(0,6):ts).map(cardHTML).join('')||'<div class="load">조건에 맞는 테마가 없습니다.</div>'}</div>`;""",
    "compact?' cp':''")

# ── 6. CSS ─────────────────────────────────────────────────────────────────
# .chl 은 원본에 이미 정의돼 있으므로 덮어쓰지 않고 필요한 것만 덧붙인다.
sub("한눈에 보기 CSS",
""".cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}""",
""".cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.cards.cp{grid-template-columns:repeat(3,1fr);gap:10px}
.cards.cp .cpill{font-size:14px;padding:6px 11px}
.cards.cp .cpct{font-size:16px;min-width:70px}
.cards.cp .cval{font-size:13px}
.cards.cp .chl{font-size:11.6px;padding:6px 9px;margin-bottom:6px}
.cards.cp .cmore{padding:7px;font-size:11.8px}
.chl b{color:var(--ink);font-weight:800;white-space:nowrap}
.chl .tx{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.chl .ok{color:#137a5c;font-weight:800}""",
    ".cards.cp{")

open(P, "w", encoding="utf-8").write(s)

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
    git commit -am "한눈에 보기 · 테마 대표 뉴스 한 줄"
    git push
    gh workflow run snapshot.yml
""")
