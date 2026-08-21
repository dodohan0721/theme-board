#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 8차 — 중복 테마 정리

문제 : 상위 10개 테마가 전부 SK하이닉스·삼성전자를 공유해서
       사실상 같은 종목을 열 번 다르게 부르고 있었음
       (거래대금 16~19조 · 등락률 +10.5% 로 다 비슷)
       게다가 'HBM·고대역폭메모리' 와 'HBM(고대역폭메모리)' 처럼 완전 중복도 존재

해결 : 위에서부터 훑으면서, 이미 뽑힌 테마와 주요 종목이 많이 겹치면 건너뛴다
       → 성격이 다른 테마들이 화면을 채운다 (티마 마켓중심과 같은 모양)

    cd ~/theme-board
    python3 fix8.py
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


# ── 1. 전역 ────────────────────────────────────────────────────────────────
sub("중복 제거 상태값",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap', compact=false;",
    "let RAW=null, D=null, cur='home', sortKey='value', minv=300, topN=0, wgt='cap', compact=false, dedup=true, dupN=0;",
    "dedup=true, dupN=0;")

# ── 2. 중복 판정 함수 ──────────────────────────────────────────────────────
sub("중복 테마 판정 함수",
"""function cardHTML(t){""",
"""// ── 중복 테마 정리 ───────────────────────────────────────────────────────
// 테마마다 '거래대금 상위 10종목'을 대표 얼굴로 보고,
// 이미 뽑힌 테마와 60% 이상 겹치면 같은 테마로 간주해 건너뛴다.
// 이름이 달라도(HBM·고대역폭메모리 vs HBM(고대역폭메모리)) 구성이 같으면 하나만 남는다.
function faceCodes(t, k){
  const S=RAW.stocks;
  return [...(t.codes||[])]
    .sort((a,b)=>((S[b]||{}).value||0)-((S[a]||{}).value||0))
    .slice(0, k||10);
}
function dedupThemes(list){
  const out=[], faces=[];
  for(const t of list){
    const c=new Set(faceCodes(t,10));
    if(!c.size){ out.push(t); faces.push(c); continue; }
    let dup=false;
    for(const f of faces){
      if(!f.size) continue;
      let hit=0; c.forEach(x=>{ if(f.has(x)) hit++; });
      if(hit / Math.min(c.size, f.size) >= 0.6){ dup=true; break; }
    }
    if(!dup){ out.push(t); faces.push(c); }
  }
  return out;
}
function cardHTML(t){""",
    "function dedupThemes(")

# ── 3. 정렬 뒤에 적용 ──────────────────────────────────────────────────────
sub("정렬 후 중복 제거 적용",
"""  if(sortKey==='ratio')ts.sort((a,b)=>(b.up/b.n)-(a.up/a.n));""",
"""  if(sortKey==='ratio')ts.sort((a,b)=>(b.up/b.n)-(a.up/a.n));
  dupN=0;
  if(dedup){ const _r=dedupThemes(ts); dupN=ts.length-_r.length; ts=_r; }""",
    "dupN=ts.length-_r.length")

# ── 4. 버튼 ────────────────────────────────────────────────────────────────
sub("중복 제거 버튼",
"""  <div class="seg"><button class="${compact?'on':''}" onclick="compact=!compact;viewHome()">${compact?'✓ 한눈에':'한눈에'}</button></div>""",
"""  <div class="seg"><button class="${compact?'on':''}" onclick="compact=!compact;viewHome()">${compact?'✓ 한눈에':'한눈에'}</button></div>
  <div class="seg"><button class="${dedup?'on':''}" onclick="dedup=!dedup;viewHome()">${dedup?'✓ 중복 테마 정리':'중복 테마 정리'}</button></div>""",
    "dedup=!dedup")

# ── 5. 안내 문구 ───────────────────────────────────────────────────────────
sub("중복 제거 설명 문구",
"""  ${topN?`<br><b style="color:var(--teal-d,#04868c)">테마마다 거래대금 상위 ${topN}종목만으로 거래대금·등락률을 다시 계산했습니다.</b>""",
"""  ${dupN?`<br><b style="color:var(--teal-d,#04868c)">구성 종목이 겹치는 테마 ${dupN}개를 접었습니다.</b> 같은 대형주를 공유하는 테마(예: S7·아이폰·IT대표주)가 화면을 다 차지하지 않도록, 성격이 다른 테마가 올라오게 정리한 것입니다.`:''}
  ${topN?`<br><b style="color:var(--teal-d,#04868c)">테마마다 거래대금 상위 ${topN}종목만으로 거래대금·등락률을 다시 계산했습니다.</b>""",
    "겹치는 테마 ${dupN}개를 접었습니다")

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
    git commit -am "겹치는 테마 정리 — 성격이 다른 테마가 상위에 오도록"
    git push

{B}확인{N}
    https://theme-board.pages.dev
    'HBM' 이 하나만 남고, S7·아이폰·IT대표주 중 하나만 보이면 성공입니다.
    버튼을 껐다 켜며 앞뒤를 비교해 보세요.
""")
