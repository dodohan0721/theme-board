#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 7차 — 자동 갱신 구조 교체

문제 : GitHub 이 `*/15` 크론을 거의 다 씹어서 하루 5번밖에 안 돌았음
해결 : 크론으로 매번 부르지 말고, 아침에 한 번 켜서 그 안에서 반복

    cd ~/theme-board
    python3 fix7.py
"""
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'

WF = ".github/workflows/snapshot.yml"
if not os.path.exists(WF):
    print(f"  {R}✗{N} {WF} 없음 — ~/theme-board 에서 실행하세요."); sys.exit(1)

YAML = '''name: 테마보드 스냅샷 갱신

# ──────────────────────────────────────────────────────────────────────────
# GitHub 의 schedule 은 "최선을 다하지만 보장하지 않는" 방식이라
# */15 같은 잦은 주기는 대부분 무시된다(실측: 하루 28회 예상 → 실제 5회).
# 그래서 크론은 하루 몇 번만 쓰고, 실행된 작업 안에서 반복한다.
#
#   08:45 시작 → 루프 → (13:55 새 작업이 이어받음) → 15:50 종료
#   11:00 · 14:00 은 앞 작업이 누락됐을 때를 위한 예비 트리거
# ──────────────────────────────────────────────────────────────────────────
on:
  schedule:
    - cron: "45 23 * * 0-4"    # KST 08:45  개장 전 시작
    - cron: "0 2 * * 1-5"      # KST 11:00  예비
    - cron: "55 4 * * 1-5"     # KST 13:55  후반 이어받기
  workflow_dispatch:
    inputs:
      interval:
        description: "갱신 간격(초)"
        required: false
        default: "600"
      until:
        description: "종료 시각 HHMM (KST)"
        required: false
        default: "1550"

# 새 작업이 뜨면 이전 작업을 끊고 이어받는다
concurrency:
  group: snapshot
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 340
    env:
      TZ: Asia/Seoul
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 캐시 복원
        uses: actions/cache@v4
        with:
          path: .cache
          key: tb-cache-${{ github.run_id }}
          restore-keys: tb-cache-

      - name: 장중 반복 갱신
        env:
          KIS_APP_KEY:           ${{ secrets.KIS_APP_KEY }}
          KIS_APP_SECRET:        ${{ secrets.KIS_APP_SECRET }}
          KIS_ENV:               real
          DART_API_KEY:          ${{ secrets.DART_API_KEY }}
          NAVER_CLIENT_ID:       ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET:   ${{ secrets.NAVER_CLIENT_SECRET }}
          ANTHROPIC_API_KEY:     ${{ secrets.ANTHROPIC_API_KEY }}
          CLOUDFLARE_API_TOKEN:  ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          INTERVAL: ${{ github.event.inputs.interval || '600' }}
          UNTIL:    ${{ github.event.inputs.until    || '1550' }}
        run: |
          echo "간격 ${INTERVAL}초 · ${UNTIL}(KST) 까지 · 시작 $(date '+%F %T')"
          n=0
          while : ; do
            n=$((n+1))
            echo "════════ ${n}회차  $(date '+%F %T') ════════"

            python3 export_snapshot.py --cycles 2 --detail 60 --ai --ai-top 30 \\
              || echo "!! 스냅샷 실패 — 다음 회차로 넘어감"

            npx --yes wrangler@latest pages deploy web \\
              --project-name theme-board --branch main --commit-dirty=true \\
              || echo "!! 배포 실패 — 다음 회차로 넘어감"

            NOW=$(date +%H%M)
            if [ "$NOW" -ge "$UNTIL" ]; then
              echo "종료 시각(${UNTIL}) 도달 — ${n}회 갱신하고 마칩니다"
              break
            fi
            echo "다음 갱신까지 ${INTERVAL}초 대기 …"
            sleep "$INTERVAL"
          done
'''

shutil.copy(WF, WF + ".bak")
open(WF, "w", encoding="utf-8").write(YAML)
print(f"  {G}✓{N} 워크플로 교체 (원본은 snapshot.yml.bak 로 백업)")

# ── 검증 ───────────────────────────────────────────────────────────────────
ok = True
try:
    import yaml as _y
    d = _y.safe_load(open(WF, encoding="utf-8"))
    steps = d["jobs"]["build"]["steps"]
    crons = [c["cron"] for c in d[True]["schedule"]]   # 'on' 은 YAML 에서 True 로 파싱됨
    print(f"  {G}✓{N} YAML 문법 정상 — 단계 {len(steps)}개")
    print(f"  {G}✓{N} 크론 {len(crons)}개: {', '.join(crons)}")
    print(f"  {G}✓{N} 최대 실행 {d['jobs']['build']['timeout-minutes']}분 · TZ {d['jobs']['build']['env']['TZ']}")
except ImportError:
    print(f"  {Y}·{N} PyYAML 없음 — 문법 검사 건너뜀 (동작에는 지장 없음)")
except Exception as e:
    print(f"  {R}✗{N} YAML 오류: {e}"); ok = False

if not ok:
    print("\n원본으로 되돌리려면:  mv .github/workflows/snapshot.yml.bak .github/workflows/snapshot.yml\n")
    sys.exit(1)

print(f"""
{B}바뀌는 것{N}

  전  크론 */15 → GitHub 이 대부분 무시 → 하루 5회
  후  크론은 하루 3번만 → 작업 안에서 10분마다 반복 → 하루 40회 이상

{B}반영{N}
    git add -A
    git commit -m "자동 갱신을 장중 루프 방식으로 교체"
    git push
    gh workflow run snapshot.yml -f interval=600 -f until=1550
    gh run watch

{B}확인{N}
    로그에 "1회차 / 2회차 …" 가 10분 간격으로 쌓이면 성공입니다.
    지금 수동으로 돌리면 15:50 까지 계속 돕니다.
    중간에 멈추려면:  gh run cancel <실행번호>
""")
