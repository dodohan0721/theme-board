#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 2차 — Cloudflare Pages 배포 추가

    cd ~/theme-board
    python3 fix2.py

Vercel 배포 단계는 그대로 두고 Cloudflare Pages 배포를 뒤에 붙입니다.
며칠 두 곳에 동시 배포하면서 새 주소가 안정적인지 확인한 뒤,
괜찮으면 Vercel 단계를 지우면 됩니다.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
WF = ".github/workflows/snapshot.yml"

G = '\033[0;32m'; Y = '\033[0;33m'; R = '\033[0;31m'; N = '\033[0m'; B = '\033[1m'

STEP = '''
      - name: Cloudflare Pages 배포
        env:
          CLOUDFLARE_API_TOKEN:  ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: |
          # 프로젝트가 없으면 만들고, 이미 있으면 그냥 넘어간다
          npx --yes wrangler@latest pages project create theme-board \\
            --production-branch main || true
          npx --yes wrangler@latest pages deploy web \\
            --project-name theme-board --branch main --commit-dirty=true
'''

if not os.path.exists(WF):
    print(f"  {R}✗{N} {WF} 를 못 찾았습니다. ~/theme-board 에서 실행하세요.")
    sys.exit(1)

src = open(WF, encoding="utf-8").read()

if "Cloudflare Pages 배포" in src:
    print(f"  {Y}·{N} 이미 적용돼 있습니다")
else:
    src = src.rstrip("\n") + "\n" + STEP
    open(WF, "w", encoding="utf-8").write(src)
    print(f"  {G}✓{N} Cloudflare Pages 배포 단계 추가")

# YAML 문법 검사
try:
    import yaml
    d = yaml.safe_load(open(WF, encoding="utf-8"))
    steps = d["jobs"]["build"]["steps"]
    print(f"  {G}✓{N} YAML 문법 정상 — 단계 {len(steps)}개")
    for s in steps:
        nm = s.get("name") or s.get("uses", "")
        print(f"       · {nm}")
except ImportError:
    print(f"  {Y}·{N} PyYAML 이 없어 문법 검사는 건너뜁니다 (동작에는 지장 없음)")
except Exception as e:
    print(f"  {R}✗{N} YAML 오류: {e}")
    sys.exit(1)

print(f"""
{B}다음{N}

  1) Secrets 등록 (아직 안 하셨으면)
       gh secret set CLOUDFLARE_API_TOKEN
       gh secret set CLOUDFLARE_ACCOUNT_ID

  2) 반영
       git commit -am "Cloudflare Pages 배포 추가"
       git push
       gh workflow run snapshot.yml
       gh run watch

  3) 확인
       https://theme-board.pages.dev
""")
