#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 1차
    ① 시각이 9시간 어긋나는 문제 (GitHub Actions 는 UTC) → KST 고정
    ② 재무 매출액이 '분기 단독'으로 잡히는 문제 → '당기 누적' 사용
    ③ 갱신 주기 10분 → 15분 (실행에 8분 37초가 걸려 너무 빠듯함)

    cd ~/Desktop/theme-board
    python3 fix1.py
"""
import os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
OK, FAIL, SKIP = [], [], []


def patch(path, subs):
    """subs: [(설명, old, new)] 또는 [(설명, old, new, 적용여부마커)]"""
    if not os.path.exists(path):
        FAIL.append(f"{path} 파일 없음")
        return
    src = open(path, encoding="utf-8").read()
    orig = src
    for sub in subs:
        desc, old, new = sub[0], sub[1], sub[2]
        marker = sub[3] if len(sub) > 3 else new
        if marker in src:
            SKIP.append(f"{desc} — 이미 적용됨")
            continue
        if old not in src:
            FAIL.append(f"{desc} — 해당 코드를 못 찾음 ({path})")
            continue
        src = src.replace(old, new, 1)
        OK.append(desc)
    if src != orig:
        open(path, "w", encoding="utf-8").write(src)


# ── ① 재무: 당기금액(3개월) → 당기누적금액 ────────────────────────────────
patch("server.py", [
    ("재무 — 손익 항목을 '당기 누적'으로",
     '''                    try:
                        best[key] = int(it.get("thstrm_amount", "0").replace(",", ""))
                    except Exception:
                        pass''',
     '''                    # 분기·반기 보고서에서 손익 항목의 thstrm_amount 는 '해당 3개월'
                    # 금액이고, thstrm_add_amount 가 '당기 누적'이다. 누적을 우선한다.
                    # (자산·부채·자본은 시점 값이라 누적 개념이 없어 그대로 쓴다)
                    raw = ""
                    if key in ("revenue", "op", "net"):
                        raw = (it.get("thstrm_add_amount") or "").strip()
                    if not raw:
                        raw = (it.get("thstrm_amount") or "0").strip()
                    try:
                        best[key] = int(raw.replace(",", ""))
                    except Exception:
                        pass'''),

    ("재무 — 기간 표기에 '누적' 명시",
     '''                out = {"period": f"{year} {label}", "fs": "연결우선", **best}''',
     '''                _lbl = label if rep == "11011" else label + " 누적"
                out = {"period": f"{year} {_lbl}", "fs": "연결우선", **best}'''),

    ("재무 — 캐시 무효화 (잘못된 값 재사용 방지)",
     '''    p = os.path.join(CACHE, f"fin_{code}.json")''',
     '''    p = os.path.join(CACHE, f"fin2_{code}.json")'''),
])

# ── ② 시간대 KST 고정 ──────────────────────────────────────────────────────
patch("export_snapshot.py", [
    ("시간대 — KST 고정",
     '''import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor''',
     '''import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

# GitHub Actions 러너는 UTC 로 돌아간다. 화면에 찍히는 '기준시각'이
# 9시간 어긋나지 않도록 한국시간으로 고정한다.
os.environ.setdefault("TZ", "Asia/Seoul")
try:
    time.tzset()
except Exception:
    pass''',
     '''os.environ.setdefault("TZ", "Asia/Seoul")'''),
])

# ── ③ 워크플로: TZ 환경변수 + 주기 15분 ────────────────────────────────────
wf = ".github/workflows/snapshot.yml"
if os.path.exists(wf):
    src = open(wf, encoding="utf-8").read()
    orig = src
    if "TZ: Asia/Seoul" in src:
        SKIP.append("워크플로 TZ — 이미 적용됨")
    else:
        m = re.search(r"(\n    timeout-minutes: \d+\n)", src)
        if m:
            src = src.replace(m.group(1), m.group(1) + "    env:\n      TZ: Asia/Seoul\n", 1)
            OK.append("워크플로 — TZ: Asia/Seoul 추가")
        else:
            m2 = re.search(r"(\n    runs-on: ubuntu-latest\n)", src)
            if m2:
                src = src.replace(m2.group(1), m2.group(1) + "    env:\n      TZ: Asia/Seoul\n", 1)
                OK.append("워크플로 — TZ: Asia/Seoul 추가")
            else:
                FAIL.append("워크플로 — TZ 넣을 위치를 못 찾음")

    if '"*/15 0-6' in src:
        SKIP.append("워크플로 주기 — 이미 15분")
    elif '"*/10 0-6' in src:
        src = src.replace('"*/10 0-6', '"*/15 0-6', 1)
        src = src.replace("10분 간격", "15분 간격")
        OK.append("워크플로 — 갱신 주기 10분 → 15분")

    if src != orig:
        open(wf, "w", encoding="utf-8").write(src)
else:
    FAIL.append(f"{wf} 파일 없음")

# ── 로컬 캐시 청소 (맥에서 다시 돌릴 때 대비) ──────────────────────────────
n = 0
for f in glob.glob(os.path.join(HERE, ".cache", "fin_*.json")):
    try:
        os.remove(f); n += 1
    except Exception:
        pass
if n:
    OK.append(f"로컬 재무 캐시 {n}건 삭제")

# ── 문법 검사 ──────────────────────────────────────────────────────────────
import py_compile
for f in ("server.py", "export_snapshot.py"):
    try:
        py_compile.compile(f, doraise=True)
        OK.append(f"{f} 문법 정상")
    except Exception as e:
        FAIL.append(f"{f} 문법 오류: {e}")

# ── 결과 ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
for s in OK:
    print("  \033[0;32m✓\033[0m " + s)
for s in SKIP:
    print("  \033[0;33m·\033[0m " + s)
for s in FAIL:
    print("  \033[0;31m✗\033[0m " + s)
print("=" * 60)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n")
    sys.exit(1)
print("""
다음 명령으로 반영하세요:

    git commit -am "재무 누적금액 반영 · 시간대 KST 고정 · 주기 15분"
    git push
    gh workflow run snapshot.yml
    gh run watch
""")
