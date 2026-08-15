#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  테마보드 — GitHub 업로드 + Secrets 등록 (2단계)
#
#    cd ~/Desktop/theme-board
#    bash setup2.sh
#
#  ※ gh CLI 가 설치·로그인돼 있어야 자동으로 끝납니다.
#     없으면 붙여넣을 값을 표로 출력합니다.
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
line(){ echo -e "${B}────────────────────────────────────────────────────────────${N}"; }

echo -e "${B}════════════════════════════════════════════════════════════${N}"
echo -e "${B} 테마보드 — GitHub 업로드 & Secrets${N}"
echo -e "${B}════════════════════════════════════════════════════════════${N}"

# ── config.py 찾기 ─────────────────────────────────────────────────────────
CFG=""
for p in config.py .env ../config.py "$HOME/Desktop/config.py" \
         "$HOME/Desktop/kospi_bot/config.py" "$HOME/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
[ -z "$CFG" ] && { err "config.py 를 못 찾았습니다"; exit 1; }
ok "설정 파일: $CFG"

# 값 읽기 — 큰따옴표/작은따옴표/따옴표없음 모두 처리, 주석 제거
getval(){
  grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$CFG" 2>/dev/null | python3 -c '
import sys,re
s=sys.stdin.read()
if not s.strip(): sys.exit()
v=s.split("=",1)[1] if "=" in s else ""
v=v.strip()
m=re.match(r"""^(["\x27])(.*?)\1""", v)
print(m.group(2) if m else re.sub(r"\s*#.*$","",v).strip())
'
}

# ── 키 확인 ────────────────────────────────────────────────────────────────
echo -e "\n${B}[1/4] 키 확인${N}"
KEYS=(KIS_APP_KEY KIS_APP_SECRET DART_API_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET ANTHROPIC_API_KEY)
MISS=0
for k in "${KEYS[@]}"; do
  v="$(getval "$k")"
  if [ -z "$v" ]; then err "$k — 못 읽음"; MISS=1
  else ok "$k  (${#v}자, 끝 4자리 …${v: -4})"; fi
done
[ $MISS -eq 1 ] && warn "못 읽은 키는 GitHub 웹에서 직접 넣으셔야 합니다"

VORG=""; VPRJ=""
if [ -f web/.vercel/project.json ]; then
  VORG=$(python3 -c "import json;print(json.load(open('web/.vercel/project.json')).get('orgId',''))" 2>/dev/null)
  VPRJ=$(python3 -c "import json;print(json.load(open('web/.vercel/project.json')).get('projectId',''))" 2>/dev/null)
fi
[ -n "$VPRJ" ] && ok "Vercel 프로젝트 정보 확인" || warn "web/.vercel/project.json 없음"

# ── Vercel 토큰 ────────────────────────────────────────────────────────────
VTOK="${VERCEL_TOKEN:-}"
if [ -z "$VTOK" ] && [ $# -ge 1 ]; then VTOK="$1"; fi
if [ -z "$VTOK" ]; then
  echo
  read -r -p "  Vercel 토큰을 붙여넣고 Enter (없으면 그냥 Enter): " VTOK
fi
[ -n "$VTOK" ] && ok "Vercel 토큰 입력됨 (${#VTOK}자)" || warn "Vercel 토큰 없음 — 나중에 직접 등록"

# ── git 커밋 ───────────────────────────────────────────────────────────────
echo -e "\n${B}[2/4] git${N}"
[ -d .git ] || { git init -q -b main && ok "git init"; }
git add -A >/dev/null 2>&1
git diff --cached --quiet 2>/dev/null && ok "커밋할 변경 없음" \
  || { git commit -q -m "테마보드 자동 갱신" && ok "커밋 완료"; }
if git ls-files --error-unmatch config.py >/dev/null 2>&1; then
  err "config.py 가 git 에 들어가 있습니다! 아래 실행 후 다시:"
  echo "     git rm --cached config.py && git commit -m 'remove secrets'"
  exit 1
fi
ok "config.py 제외 확인 (안전)"
ok "커밋된 파일 $(git ls-files | wc -l | tr -d ' ')개"

# ── GitHub 업로드 ──────────────────────────────────────────────────────────
echo -e "\n${B}[3/4] GitHub 업로드${N}"
HAS_GH=0
command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 && HAS_GH=1

if [ $HAS_GH -eq 1 ]; then
  USER=$(gh api user -q .login 2>/dev/null)
  ok "gh 로그인: $USER"
  if git remote get-url origin >/dev/null 2>&1; then
    ok "origin 이미 설정됨: $(git remote get-url origin)"
  else
    if gh repo view "$USER/theme-board" >/dev/null 2>&1; then
      git remote add origin "https://github.com/$USER/theme-board.git" && ok "기존 저장소에 연결"
    else
      gh repo create theme-board --public --source=. --remote=origin >/dev/null 2>&1 \
        && ok "저장소 생성 (public)" || err "저장소 생성 실패"
    fi
  fi
  git push -u origin main 2>&1 | tail -2

  echo -e "\n${B}[4/4] Secrets 등록${N}"
  for k in "${KEYS[@]}"; do
    v="$(getval "$k")"
    [ -n "$v" ] && { gh secret set "$k" --body "$v" >/dev/null 2>&1 && ok "$k" || err "$k 실패"; }
  done
  gh secret set KIS_ENV --body "real" >/dev/null 2>&1 && ok "KIS_ENV"
  [ -n "$VORG" ] && gh secret set VERCEL_ORG_ID     --body "$VORG" >/dev/null 2>&1 && ok "VERCEL_ORG_ID"
  [ -n "$VPRJ" ] && gh secret set VERCEL_PROJECT_ID --body "$VPRJ" >/dev/null 2>&1 && ok "VERCEL_PROJECT_ID"
  [ -n "$VTOK" ] && gh secret set VERCEL_TOKEN      --body "$VTOK" >/dev/null 2>&1 && ok "VERCEL_TOKEN"
  echo
  gh secret list 2>/dev/null | sed 's/^/     /'
  echo
  echo -e "${B}  시험 실행:${N}  gh workflow run snapshot.yml"
  echo -e "${B}  결과 보기:${N}  gh run watch"
else
  warn "gh CLI 없음 — 수동으로 진행합니다"
  echo
  echo -e "  ${B}① 업로드${N} (GitHub 에서 theme-board 저장소를 public 으로 먼저 만드세요)"
  echo "       git remote add origin https://github.com/<아이디>/theme-board.git"
  echo "       git push -u origin main"
  echo
  echo -e "  ${B}② Secrets 등록${N} — 저장소 → Settings → Secrets and variables → Actions"
  echo "       → New repository secret 을 눌러 아래를 하나씩"
  echo
  line
  for k in "${KEYS[@]}"; do
    v="$(getval "$k")"; [ -n "$v" ] && printf "  %s\n     %s\n" "$k" "$v"
  done
  printf "  %s\n     %s\n" "KIS_ENV" "real"
  [ -n "$VORG" ] && printf "  %s\n     %s\n" "VERCEL_ORG_ID" "$VORG"
  [ -n "$VPRJ" ] && printf "  %s\n     %s\n" "VERCEL_PROJECT_ID" "$VPRJ"
  [ -n "$VTOK" ] && printf "  %s\n     %s\n" "VERCEL_TOKEN" "$VTOK"
  line
  echo -e "  ${Y}※ 등록 끝나면 Cmd+K 로 터미널 화면을 지우세요${N}"
  echo
  echo -e "  ${B}③ 시험 실행${N} — 저장소 Actions 탭 → '테마보드 스냅샷 갱신' → Run workflow"
fi

echo -e "\n${B}════════════════════════════════════════════════════════════${N}"
