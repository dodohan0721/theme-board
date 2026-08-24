#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  긴급 — 회원 전용 파일이 공개 저장소에 올라간 것 되돌리기
#
#    cd ~/theme-board
#    bash fix10.sh
#
#  무슨 일이 있었나
#    fix9 가 만든 web/priv/detail.json 이 .gitignore 에 없어서
#    공개 저장소에 그대로 커밋됐습니다. 사이트는 잠겨 있지만
#    GitHub 주소로는 그냥 받아집니다.
#
#      https://raw.githubusercontent.com/<계정>/theme-board/main/web/priv/detail.json
#
#  이 스크립트가 하는 일
#    1) web/priv/ 를 .gitignore 에 넣습니다
#    2) 저장소 추적에서 뺍니다 (로컬 파일은 그대로 — 배포에 필요)
#    3) 그 파일을 넣은 커밋 자체를 고쳐서 다시 올립니다
#    4) GitHub 에서 정말 사라졌는지 확인합니다
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
step(){ echo -e "\n${B}$1${N}"; }

[ -d .git ] || { err ".git 이 없습니다 — ~/theme-board 에서 실행해 주세요."; exit 1; }

step "[1/5] 지금 상태"
TRACKED="$(git ls-files web/priv)"
if [ -z "$TRACKED" ]; then
  ok "이미 추적에서 빠져 있습니다"
else
  warn "저장소가 추적 중:  $TRACKED"
fi
[ -f web/priv/detail.json ] && ok "로컬 파일 있음 ($(du -h web/priv/detail.json | cut -f1)) — 배포에 필요하니 지우지 않습니다"

step "[2/5] .gitignore 에 넣기"
if grep -q '^web/priv/' .gitignore 2>/dev/null; then
  ok "이미 들어 있습니다"
else
  printf '\n# 회원 전용 데이터 — 절대 공개 저장소에 올리지 않는다\nweb/priv/\n' >> .gitignore
  ok "web/priv/ 추가"
fi

step "[3/5] 추적에서 빼기"
if [ -n "$TRACKED" ]; then
  git rm -r --cached web/priv -q && ok "git 추적 해제 (파일은 그대로)"
else
  ok "건너뜀"
fi
git add .gitignore

step "[4/5] 커밋 되돌려 올리기"
LAST="$(git log --oneline -1 --format=%H)"
ADDED="$(git log --format=%H -- web/priv | head -1)"
if [ "$LAST" = "$ADDED" ]; then
  # 그 파일을 넣은 커밋이 맨 위 → 커밋 자체를 고쳐서 흔적까지 지운다
  git commit -q --amend --no-edit && ok "커밋 수정 완료 (기록에서도 제거)"
  if git push --force-with-lease -q 2>/dev/null; then
    ok "강제 푸시 완료"
  else
    err "푸시 거절됨 — 그 사이 다른 변경이 올라갔습니다."
    echo "     git pull --rebase 후 다시 실행해 주세요."
    exit 1
  fi
else
  warn "그 파일이 여러 커밋에 걸쳐 있습니다. 새 커밋으로 지웁니다."
  git commit -q -m "회원 전용 데이터를 저장소에서 제외" && ok "커밋 완료"
  git push -q && ok "푸시 완료"
  warn "예전 커밋 기록에는 남습니다. 완전히 지우려면 저장소를 새로 만드는 편이 빠릅니다."
fi

step "[5/5] 확인"
REMOTE="$(git config --get remote.origin.url)"
SLUG="$(echo "$REMOTE" | sed -E 's#.*github.com[:/]##; s#\.git$##')"
BR="$(git rev-parse --abbrev-ref HEAD)"
URL="https://raw.githubusercontent.com/$SLUG/$BR/web/priv/detail.json"
sleep 3
CODE="$(curl -s -o /dev/null -w '%{http_code}' "$URL")"
echo "  $URL"
if [ "$CODE" = "404" ]; then
  ok "GitHub 응답 $CODE — 사라졌습니다"
else
  err "GitHub 응답 $CODE — 아직 남아 있습니다 (1분 뒤 다시 확인해 보세요)"
fi

CODE2="$(curl -s -o /dev/null -w '%{http_code}' https://theme-board.pages.dev/priv/detail.json)"
if [ "$CODE2" = "401" ]; then
  ok "사이트 응답 $CODE2 — 잠금은 그대로 유지됩니다"
else
  warn "사이트 응답 $CODE2 (401 이어야 정상)"
fi

cat <<EOF

$(echo -e "${B}앞으로${N}")

  web/priv/detail.json 은 이제 저장소에 안 올라갑니다.
  대신 갱신할 때마다 그 자리에서 새로 만들어져 배포되므로 동작은 같습니다.
    · 맥에서 돌릴 때   export_snapshot.py 가 만듭니다
    · 자동 갱신일 때   GitHub Actions 안에서 만들어 바로 배포합니다

$(echo -e "${B}남은 위험${N}")

  이미 한 번 공개됐던 파일이라, 그 사이에 받아간 사람이 있으면 되돌릴 수 없습니다.
  올라가 있던 시간이 짧고 내용도 그날치 스냅샷 하나라 실질 피해는 크지 않지만,
  마음에 걸리시면 저장소를 새로 만들어 다시 올리는 것이 가장 확실합니다.

EOF
