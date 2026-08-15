#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  테마보드 — GitHub Actions 자동화 설정 (한 번만 실행)
#
#    cd ~/Desktop/theme-board
#    bash setup_github.sh
#
#  하는 일
#    1. .gitignore 생성 (키 파일이 절대 올라가지 않게)
#    2. .github/workflows/snapshot.yml 생성
#    3. config.py 에서 키를 읽어 GitHub Secrets 에 자동 등록 (gh CLI 있을 때)
#    4. git 저장소 초기화 + 첫 커밋
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'; B='\033[1m'
ok(){ echo -e "  ${GREEN}✓${NC} $1"; }
warn(){ echo -e "  ${YELLOW}!${NC} $1"; }
err(){ echo -e "  ${RED}✗${NC} $1"; }
echo -e "${B}════════════════════════════════════════════════════════════${NC}"
echo -e "${B} 테마보드 GitHub Actions 설정${NC}"
echo -e "${B}════════════════════════════════════════════════════════════${NC}"

# ── 1. .gitignore ──────────────────────────────────────────────────────────
echo -e "\n${B}[1/5] .gitignore${NC}"
cat > .gitignore <<'EOF'
# ⚠️ 절대 커밋되면 안 되는 것들
config.py
.env
*.key
*.pem

# 캐시·로그·임시파일
.cache/
__pycache__/
*.pyc
*.log
_debug_*.html
_probe_*.json
themes_naver.json

# Vercel 로컬 설정 (프로젝트 ID는 Secrets 로 전달)
web/.vercel/
EOF
ok ".gitignore 생성 — config.py 는 절대 올라가지 않습니다"

# ── 2. 워크플로 ────────────────────────────────────────────────────────────
echo -e "\n${B}[2/5] GitHub Actions 워크플로${NC}"
mkdir -p .github/workflows
cat > .github/workflows/snapshot.yml <<'EOF'
name: 테마보드 스냅샷 갱신

# GitHub Actions cron 은 UTC 기준. 한국시간 = UTC + 9
#   00:00~06:59 UTC  =  09:00~15:59 KST (장중)
on:
  schedule:
    - cron: "*/10 0-6 * * 1-5"    # 평일 장중 10분 간격
    - cron: "40 6 * * 1-5"        # KST 15:40 — 종가 확정본
  workflow_dispatch:               # Actions 탭에서 수동 실행

concurrency:
  group: snapshot
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # 한투 토큰(24h)·DART 기업코드·종목마스터·스캔순서를 다음 실행에 물려준다
      - name: 캐시 복원
        uses: actions/cache@v4
        with:
          path: .cache
          key: tb-cache-${{ github.run_id }}
          restore-keys: tb-cache-

      - name: 스냅샷 생성
        env:
          KIS_APP_KEY:         ${{ secrets.KIS_APP_KEY }}
          KIS_APP_SECRET:      ${{ secrets.KIS_APP_SECRET }}
          KIS_ENV:             real
          DART_API_KEY:        ${{ secrets.DART_API_KEY }}
          NAVER_CLIENT_ID:     ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          ANTHROPIC_API_KEY:   ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python3 export_snapshot.py --cycles 2 --detail 60 --ai --ai-top 30
          echo "--- 생성 결과 ---"
          ls -lh web/data.json

      - name: Vercel 배포
        env:
          VERCEL_TOKEN:      ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID:     ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
        run: npx --yes vercel@latest deploy web --prod --yes --token "$VERCEL_TOKEN"
EOF
ok ".github/workflows/snapshot.yml 생성 (평일 장중 10분 간격)"

# ── 3. 키 읽기 ─────────────────────────────────────────────────────────────
echo -e "\n${B}[3/5] 키 확인${NC}"
CFG=""
for p in config.py ../config.py "$HOME/Desktop/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
if [ -z "$CFG" ]; then err "config.py 를 못 찾았습니다"; exit 1; fi
ok "설정 파일: $CFG"

getval(){ grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$CFG" 2>/dev/null \
          | sed -E 's/^[^=]*=[[:space:]]*//; s/^"//; s/"[[:space:]]*$//; s/[[:space:]]*$//'; }

declare -a KEYS=(KIS_APP_KEY KIS_APP_SECRET DART_API_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET ANTHROPIC_API_KEY)
MISSING=0
for k in "${KEYS[@]}"; do
  v="$(getval "$k")"
  if [ -z "$v" ]; then err "$k 없음"; MISSING=1
  else ok "$k  (${#v}자)"; fi
done
[ $MISSING -eq 1 ] && warn "빠진 키는 나중에 직접 등록하셔야 합니다"

# Vercel 프로젝트 ID
VORG=""; VPRJ=""
if [ -f web/.vercel/project.json ]; then
  VORG=$(python3 -c "import json;print(json.load(open('web/.vercel/project.json')).get('orgId',''))" 2>/dev/null)
  VPRJ=$(python3 -c "import json;print(json.load(open('web/.vercel/project.json')).get('projectId',''))" 2>/dev/null)
fi
if [ -n "$VPRJ" ]; then ok "Vercel 프로젝트 연결 정보 확인"
else warn "web/.vercel/project.json 이 없습니다 — 'cd web && npx vercel link' 를 먼저 해주세요"; fi

# ── 4. git ─────────────────────────────────────────────────────────────────
echo -e "\n${B}[4/5] git 저장소${NC}"
if [ ! -d .git ]; then
  git init -q -b main && ok "git init"
else ok "이미 git 저장소입니다"; fi
git add -A >/dev/null 2>&1
if git diff --cached --quiet 2>/dev/null; then ok "커밋할 변경 없음"
else git commit -q -m "테마보드 — 자동 갱신 설정" && ok "커밋 완료"; fi

# 안전 확인 — config.py 가 커밋에 안 들어갔는지
if git ls-files --error-unmatch config.py >/dev/null 2>&1; then
  err "config.py 가 git 에 포함돼 있습니다! 아래로 제거하세요:"
  echo "     git rm --cached config.py && git commit -m 'remove secrets'"
else ok "config.py 는 제외됨 (안전)"; fi

# ── 5. GitHub 연결 ─────────────────────────────────────────────────────────
echo -e "\n${B}[5/5] GitHub 연결${NC}"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  ok "gh CLI 로그인 확인 — 자동으로 진행합니다"
  if ! git remote get-url origin >/dev/null 2>&1; then
    echo "  저장소를 만듭니다 (공개/public — Actions 실행시간 무제한 무료)"
    gh repo create theme-board --public --source=. --remote=origin --push \
      && ok "저장소 생성 + 업로드 완료" || err "저장소 생성 실패"
  else
    git push -u origin main -q && ok "업로드 완료"
  fi
  echo "  Secrets 등록 중 …"
  for k in "${KEYS[@]}"; do
    v="$(getval "$k")"
    [ -n "$v" ] && gh secret set "$k" --body "$v" >/dev/null 2>&1 && ok "  $k"
  done
  [ -n "$VORG" ] && gh secret set VERCEL_ORG_ID --body "$VORG" >/dev/null 2>&1 && ok "  VERCEL_ORG_ID"
  [ -n "$VPRJ" ] && gh secret set VERCEL_PROJECT_ID --body "$VPRJ" >/dev/null 2>&1 && ok "  VERCEL_PROJECT_ID"
  echo
  warn "VERCEL_TOKEN 은 직접 등록해야 합니다:"
  echo "     1) vercel.com → 아바타 → Settings → Tokens → Create Token"
  echo "     2) gh secret set VERCEL_TOKEN --body \"<복사한값>\""
  echo
  echo -e "${B}  마지막 단계${NC} — Actions 탭에서 'Run workflow' 로 한 번 돌려보세요:"
  echo "     gh workflow run '테마보드 스냅샷 갱신'"
else
  warn "gh CLI 가 없거나 로그인되지 않았습니다 — 수동으로 진행합니다"
  echo
  echo -e "  ① GitHub 에서 새 저장소 'theme-board' 를 ${B}공개(public)${NC}로 만드세요"
  echo "  ② 아래를 실행:"
  echo "       git remote add origin https://github.com/<아이디>/theme-board.git"
  echo "       git push -u origin main"
  echo "  ③ 저장소 → Settings → Secrets and variables → Actions 에서 아래를 등록:"
  echo
  printf "     %-22s %s\n" "이름" "값"
  printf "     %-22s %s\n" "──────────────────────" "──────────────────"
  for k in "${KEYS[@]}"; do
    v="$(getval "$k")"; [ -n "$v" ] && printf "     %-22s %s\n" "$k" "$v"
  done
  [ -n "$VORG" ] && printf "     %-22s %s\n" "VERCEL_ORG_ID" "$VORG"
  [ -n "$VPRJ" ] && printf "     %-22s %s\n" "VERCEL_PROJECT_ID" "$VPRJ"
  printf "     %-22s %s\n" "VERCEL_TOKEN" "(vercel.com → Settings → Tokens 에서 발급)"
  echo
  echo -e "  ${YELLOW}위 값들은 화면에만 표시됩니다. 등록 후 터미널을 지우세요 (Cmd+K)${NC}"
  echo "  ④ Actions 탭 → '테마보드 스냅샷 갱신' → Run workflow 로 시험 실행"
fi

echo -e "\n${B}════════════════════════════════════════════════════════════${NC}"
echo -e " 설정 끝. 이후로는 ${B}맥을 꺼놔도${NC} 평일 장중 10분마다 자동 갱신됩니다."
echo -e "${B}════════════════════════════════════════════════════════════${NC}"
