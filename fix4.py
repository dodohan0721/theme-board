#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 4차 — 재무 카드에 당기순이익 추가

    cd ~/theme-board
    python3 fix4.py

DART 에서 이미 받아오고 있던 값이라 화면에 칸만 추가합니다.
분기·반기 보고서는 '누적' 기준입니다(3차 수정 반영분).
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []

P = "web/index.html"
if not os.path.exists(P):
    print(f"  {R}✗{N} {P} 없음 — ~/theme-board 에서 실행하세요."); sys.exit(1)

s = open(P, encoding="utf-8").read()

# ── 재무 타일 추가 ─────────────────────────────────────────────────────────
OLD = """        ${fb('매출액',f.revenue?nf(Math.round(f.revenue/1e8))+'억':'-')}
        ${fb('영업이익률',f.opm!=null?f.opm+'%':'-',f.opm<0?'적자':'')}"""
NEW = """        ${fb('매출액',f.revenue?nf(Math.round(f.revenue/1e8))+'억':'-')}
        ${fb('당기순이익',f.net!=null?nf(Math.round(f.net/1e8))+'억':'-',f.net<0?'적자':'')}
        ${fb('영업이익률',f.opm!=null?f.opm+'%':'-',f.opm<0?'적자':'')}"""

if "당기순이익" in s:
    SKIP.append("당기순이익 — 이미 적용됨")
elif OLD not in s:
    FAIL.append("재무 카드 위치를 못 찾음 (web/index.html)")
else:
    s = s.replace(OLD, NEW, 1)
    OK.append("재무 카드에 당기순이익 추가")

# ── 순손실 경고 문구 ───────────────────────────────────────────────────────
OLD2 = """      ${f.opm<0?'<div class="disc" style="background:#fef2f2;border-color:#fbd5d1;color:#b42318">⚠ 최근 보고서 기준 <b>영업적자</b>입니다.</div>':''}"""
NEW2 = """      ${(f.opm<0||f.net<0)?`<div class="disc" style="background:#fef2f2;border-color:#fbd5d1;color:#b42318">⚠ 최근 보고서 기준 <b>${f.opm<0&&f.net<0?'영업적자·순손실':(f.opm<0?'영업적자':'순손실')}</b>입니다.</div>`:''}"""

if "순손실" in s:
    SKIP.append("순손실 경고 — 이미 적용됨")
elif OLD2 not in s:
    SKIP.append("적자 경고 문구 위치를 못 찾음 (건너뜀)")
else:
    s = s.replace(OLD2, NEW2, 1)
    OK.append("순손실일 때도 경고 표시")

open(P, "w", encoding="utf-8").write(s)

# ── 검증 ───────────────────────────────────────────────────────────────────
chk = open(P, encoding="utf-8").read()
for token, label in (("당기순이익", "당기순이익 칸"), ("f.net", "net 값 참조")):
    if token in chk:
        OK.append(f"{label} 확인")
    else:
        FAIL.append(f"{label} 없음")

# 템플릿 리터럴 백틱 짝 검사 (깨진 따옴표로 화면이 통째로 죽는 걸 방지)
if chk.count("`") % 2 != 0:
    FAIL.append("백틱(`) 개수가 홀수 — 템플릿 문자열이 깨졌을 수 있습니다")
else:
    OK.append("템플릿 문자열 짝 정상")

print("\n" + "=" * 58)
for x in OK:   print(f"  {G}✓{N} {x}")
for x in SKIP: print(f"  {Y}·{N} {x}")
for x in FAIL: print(f"  {R}✗{N} {x}")
print("=" * 58)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)

print(f"""
{B}반영{N}
    git commit -am "재무 카드에 당기순이익 추가"
    git push
    gh workflow run snapshot.yml
    gh run watch

{B}확인{N}
    https://theme-board.pages.dev  →  아무 종목 클릭 → 💰 재무
    '매출액' 옆에 '당기순이익' 칸이 보이면 성공입니다.
""")
