#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 3차
    ① AI 판독 결과 캐시 — 같은 종목·같은 기사면 재판독하지 않는다
       (새 기사가 뜨면 즉시 다시 판독 / 날짜가 바뀌면 전부 무효)
    ② 실행 시각 정리 — 개장 전 1회 예열 + 장중 15분 간격, 중복 제거

    cd ~/theme-board
    python3 fix3.py
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []

# ══════════════════════════════════════════════════════════════════════════
# ① AI 판독 캐시
# ══════════════════════════════════════════════════════════════════════════
HELPER = '''

# ══════════════════════════════════════════════════════════════════════════
# AI 판독 캐시
#   같은 종목이고 수집된 기사 목록이 그대로면 이전 판독 결과를 재사용한다.
#   기사는 그대로인데 다시 물어보면 답도 똑같이 나오므로 낭비일 뿐이다.
#   새 기사가 하나라도 생기면 키가 달라져 즉시 다시 판독한다(장중 새 재료 반영).
#   날짜가 바뀌면 키에 든 날짜가 달라져 자동으로 무효가 된다.
# ══════════════════════════════════════════════════════════════════════════
import hashlib, glob as _glob

_AI_DIR = os.path.join(HERE, ".cache", "ai")
_ai_hit = [0, 0]          # [재사용, 새로 판독]


def _ai_purge(today):
    """어제까지의 판독 캐시는 지운다."""
    for f in _glob.glob(os.path.join(_AI_DIR, "*.json")):
        if not os.path.basename(f).startswith(today):
            try:
                os.remove(f)
            except Exception:
                pass


def _ai_cached(AI, code, name, rate, picked, ctx):
    os.makedirs(_AI_DIR, exist_ok=True)
    today = time.strftime("%Y%m%d")
    urls = sorted((a.get("url") or a.get("nurl") or "") for a in picked)
    key = hashlib.sha1("|".join(urls).encode()).hexdigest()[:16]
    p = os.path.join(_AI_DIR, f"{today}_{code}_{key}.json")
    if os.path.exists(p):
        try:
            r = json.load(open(p, encoding="utf-8"))
            _ai_hit[0] += 1
            return r
        except Exception:
            pass
    r = AI.analyze(AI._KEY, name, code, rate, picked, ctx)
    _ai_hit[1] += 1
    if r:
        try:
            json.dump(r, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass
    return r

'''

src = open("export_snapshot.py", encoding="utf-8").read()

if "_ai_cached" in src:
    SKIP.append("AI 판독 캐시 — 이미 적용됨")
else:
    old_call = ('                r = AI.analyze(AI._KEY, name, code, s.get("rate", 0), '
                'picked, ctx) if picked else None')
    new_call = ('                r = _ai_cached(AI, code, name, s.get("rate", 0), '
                'picked, ctx) if picked else None')
    if old_call not in src:
        FAIL.append("AI 호출 지점을 못 찾음 (export_snapshot.py)")
    else:
        src = src.replace(old_call, new_call, 1)
        # 헬퍼를 main() 앞에 끼워 넣는다
        m = re.search(r"\ndef main\(\):", src)
        if not m:
            FAIL.append("main() 를 못 찾음")
        else:
            src = src[:m.start()] + HELPER + src[m.start():]
            OK.append("AI 판독 캐시 추가")

# 통계 출력 + 하루 지난 캐시 정리
if "_ai_purge(time.strftime" not in src:
    m2 = re.search(r'(\n    ai_targets = set\(d\["ranking"\]\[:a\.ai_top\]\) if AI else set\(\)\n)', src)
    if m2:
        src = src.replace(m2.group(1),
            m2.group(1) + "    if AI:\n        _ai_purge(time.strftime('%Y%m%d'))\n", 1)
        OK.append("지난 날짜 캐시 자동 정리")
    else:
        SKIP.append("캐시 정리 삽입 위치 못 찾음 (동작에는 지장 없음)")

if 'ai_stat["ok"]' in src and "_ai_hit" in src and "판독 재사용" not in src:
    m3 = re.search(r'(\n    print\(f"   소요 [^\n]*\n)', src)
    if m3:
        src = src.replace(m3.group(1),
            m3.group(1) +
            '    if AI:\n'
            '        print(f"   AI 판독 — 새로 {_ai_hit[1]}건 / 캐시 재사용 {_ai_hit[0]}건")\n', 1)
        OK.append("판독 재사용 통계 출력")

open("export_snapshot.py", "w", encoding="utf-8").write(src)

# ══════════════════════════════════════════════════════════════════════════
# ② 크론 정리
# ══════════════════════════════════════════════════════════════════════════
WF = ".github/workflows/snapshot.yml"
if os.path.exists(WF):
    w = open(WF, encoding="utf-8").read()
    orig = w

    # 15:40(=06:40 UTC) 은 15:45 실행과 겹치므로 제거
    w = re.sub(r'\n *- cron: "40 6 \* \* 1-5".*', "", w)

    # 개장 전 예열 1회 — 23:50 UTC(일~목) = 08:50 KST(월~금)
    if '"50 23' not in w:
        w = re.sub(r'(\n *- cron: "\*/15 0-6 \* \* 1-5"[^\n]*\n)',
                   r'\1    - cron: "50 23 * * 0-4"        # KST 08:50 — 개장 전 예열\n', w, 1)
        OK.append("개장 전(08:50) 예열 실행 추가")
    if w != orig:
        open(WF, "w", encoding="utf-8").write(w)
        OK.append("장 마감 후 중복 실행 제거")
    else:
        SKIP.append("크론 — 변경 없음")
else:
    FAIL.append(f"{WF} 없음")

# ══════════════════════════════════════════════════════════════════════════
import py_compile
try:
    py_compile.compile("export_snapshot.py", doraise=True)
    OK.append("export_snapshot.py 문법 정상")
except Exception as e:
    FAIL.append(f"문법 오류: {e}")

print("\n" + "=" * 58)
for s in OK:   print(f"  {G}✓{N} {s}")
for s in SKIP: print(f"  {Y}·{N} {s}")
for s in FAIL: print(f"  {R}✗{N} {s}")
print("=" * 58)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)
print(f"""
{B}반영{N}
    git commit -am "AI 판독 캐시 · 실행 시각 정리"
    git push
    gh workflow run snapshot.yml
    gh run watch

로그 끝에 이런 줄이 나옵니다:
    AI 판독 — 새로 12건 / 캐시 재사용 18건
두 번째 숫자가 아낀 호출 수입니다.
""")
