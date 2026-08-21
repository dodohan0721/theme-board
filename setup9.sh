#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  테마보드 — 회원 전용 상세 한 번에 적용하기
#
#    cd ~/theme-board
#    bash setup9.sh                        # 승인 계정 = config.py 의 내 메일
#    bash setup9.sh a@b.com,c@d.com        # 승인 계정을 직접 지정
#
#  하는 일
#    1) fix9.py 적용 (데이터 분리 · 로그인 화면 · Cloudflare 함수)
#    2) AUTH_SECRET 생성
#    3) Cloudflare 환경변수 4개 등록          ← 대시보드 클릭 대신 여기서
#    4) 지금 있는 스냅샷을 공개/회원용으로 쪼개기 (API 호출 없음 · 비용 0)
#    5) git 커밋 + 푸시
#    6) 배포 후 잠금이 실제로 걸렸는지 확인
#
#  ※ 중간에 멈추면 그 자리에서 무엇을 하면 되는지 알려 줍니다.
#     여러 번 다시 돌려도 안전합니다.
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
step(){ echo -e "\n${B}$1${N}"; }

PROJECT="theme-board"

echo -e "${B}════════════════════════════════════════════════════════════${N}"
echo -e "${B} 테마보드 — 첫 화면 공개 / 상세는 회원 전용${N}"
echo -e "${B}════════════════════════════════════════════════════════════${N}"

# ── 위치 확인 ──────────────────────────────────────────────────────────────
step "[1/6] 위치 확인"
for f in fix9.py export_snapshot.py web/index.html; do
  [ -f "$f" ] || { err "$f 가 없습니다 — ~/theme-board 에서 실행해 주세요."; exit 1; }
done
ok "작업 폴더  $(pwd)"

# ── config.py 찾기 ─────────────────────────────────────────────────────────
CFG=""
for p in config.py ../config.py "$HOME/Desktop/config.py" "$HOME/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
[ -z "$CFG" ] && { err "config.py 를 못 찾았습니다"; exit 1; }
ok "설정 파일  $CFG"

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

CF_TOKEN="$(getval CLOUDFLARE_API_TOKEN)"
[ -z "$CF_TOKEN" ] && CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CF_ACCT="$(getval CLOUDFLARE_ACCOUNT_ID)"
[ -z "$CF_ACCT" ] && CF_ACCT="${CLOUDFLARE_ACCOUNT_ID:-}"

# ── 승인 계정 ──────────────────────────────────────────────────────────────
MEMBERS="${1:-}"
if [ -z "$MEMBERS" ]; then
  MEMBERS="$(getval MY_EMAIL)"
  [ -z "$MEMBERS" ] && MEMBERS="$(git config user.email 2>/dev/null)"
fi
if [ -z "$MEMBERS" ]; then
  err "승인할 이메일을 못 정했습니다."
  echo  "     bash setup9.sh 내메일@example.com  처럼 직접 넣어 주세요."
  exit 1
fi
ok "승인 계정  $MEMBERS"

# ── 코드 적용 ──────────────────────────────────────────────────────────────
step "[2/6] 코드 적용"
python3 fix9.py || { err "fix9.py 실패 — 위 내용을 그대로 알려주세요."; exit 1; }

# ── 비밀키 ────────────────────────────────────────────────────────────────
step "[3/6] 로그인 서명키(AUTH_SECRET)"
mkdir -p .cache
SECFILE=".cache/auth_secret.txt"
if [ -s "$SECFILE" ]; then
  AUTH_SECRET="$(cat "$SECFILE")"
  ok "기존 키 사용 (${#AUTH_SECRET}자) — 바꾸면 로그인한 사람이 전부 풀립니다"
else
  AUTH_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
  printf '%s' "$AUTH_SECRET" > "$SECFILE"
  chmod 600 "$SECFILE"
  ok "새로 만들었습니다 (${#AUTH_SECRET}자) → $SECFILE 에 보관"
fi
grep -q '^\.cache/' .gitignore 2>/dev/null || echo '.cache/' >> .gitignore

# ── Cloudflare 환경변수 ────────────────────────────────────────────────────
step "[4/6] Cloudflare 환경변수 등록"
if [ -z "$CF_TOKEN" ]; then
  warn "CLOUDFLARE_API_TOKEN 을 못 읽어 자동 등록을 건너뜁니다."
  MANUAL=1
else
  export CLOUDFLARE_API_TOKEN="$CF_TOKEN"
  [ -n "$CF_ACCT" ] && export CLOUDFLARE_ACCOUNT_ID="$CF_ACCT"
  MANUAL=0
  putsec(){   # 이름, 값
    printf '%s' "$2" | npx --yes wrangler@latest pages secret put "$1" \
        --project-name "$PROJECT" >/dev/null 2>&1 \
      && ok "$1  등록됨" \
      || { err "$1  등록 실패"; MANUAL=1; }
  }
  putsec AUTH_SECRET   "$AUTH_SECRET"
  putsec MEMBERS       "$MEMBERS"
  putsec DEV_SHOW_CODE "1"
fi

if [ "$MANUAL" = "1" ]; then
  echo
  warn "아래 값을 대시보드에서 직접 넣어 주세요."
  echo  "     dash.cloudflare.com → Workers & Pages → $PROJECT"
  echo  "       → Settings → Variables and Secrets"
  echo
  echo  "     AUTH_SECRET     $SECFILE 안의 값"
  echo  "     MEMBERS         $MEMBERS"
  echo  "     DEV_SHOW_CODE   1"
fi

# ── 지금 스냅샷을 쪼개기 (API 호출 없음) ───────────────────────────────────
step "[5/6] 지금 있는 스냅샷 나누기"
if [ -f web/data.json ]; then
  python3 - <<'PY'
import json, os
p = "web/data.json"
d = json.load(open(p, encoding="utf-8"))
det = d.pop("details", None)
if det is None:
    print("  · 이미 나뉘어 있습니다")
else:
    d["heads"] = {c: v["reason"]["headline"] for c, v in det.items()
                  if (v.get("reason") or {}).get("headline")}
    d["detail_codes"] = sorted(det)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs("web/priv", exist_ok=True)
    json.dump({"ts": d["ts"], "details": det},
              open("web/priv/detail.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    a = os.path.getsize(p) / 1024
    b = os.path.getsize("web/priv/detail.json") / 1024
    print(f"  ✓ 공개 data.json {a:,.0f} KB · 회원 priv/detail.json {b:,.0f} KB")
    print(f"  ✓ 카드 대표문장 {len(d['heads'])}개 · 상세 보유 {len(d['detail_codes'])}종목")
PY
else
  warn "web/data.json 이 없습니다 — 다음 스냅샷부터 나뉩니다"
fi

# ── 커밋 · 배포 ───────────────────────────────────────────────────────────
step "[6/6] 커밋 · 배포"
git add -A >/dev/null 2>&1
if git diff --cached --quiet 2>/dev/null; then
  ok "바뀐 내용 없음 (이미 반영됨)"
else
  git commit -q -m "회원 전용 상세 — 첫 화면은 공개, 상세는 로그인·승인 후" && ok "커밋 완료"
fi
if git push -q 2>/dev/null; then ok "푸시 완료"; else warn "푸시 실패 — 나중에 git push 해 주세요"; fi

if [ "$MANUAL" = "0" ]; then
  echo "  배포 중 …"
  npx --yes wrangler@latest pages deploy web \
      --project-name "$PROJECT" --branch main --commit-dirty=true 2>&1 | tail -3
else
  warn "환경변수를 먼저 넣고 배포해 주세요:"
  echo  "     npx wrangler pages deploy web --project-name $PROJECT --branch main --commit-dirty=true"
fi

# ── 확인 ──────────────────────────────────────────────────────────────────
if [ "$MANUAL" = "0" ]; then
  echo -e "\n${B}확인${N}"
  sleep 6
  URL="https://$PROJECT.pages.dev"
  C1=$(curl -s -o /dev/null -w "%{http_code}" "$URL/data.json")
  C2=$(curl -s -o /dev/null -w "%{http_code}" "$URL/priv/detail.json")
  [ "$C1" = "200" ] && ok "공개 data.json      $C1  (누구나 열람 — 정상)" \
                    || warn "공개 data.json      $C1  (200 이어야 정상)"
  [ "$C2" = "401" ] && ok "회원 priv/detail    $C2  (로그인 필요 — 잠김 성공)" \
                    || err "회원 priv/detail    $C2  (401 이어야 정상 — 아래 안내 참고)"
  if [ "$C2" != "401" ]; then
    echo "     배포가 아직 퍼지는 중일 수 있습니다. 1분 뒤 다시:"
    echo "       curl -s -o /dev/null -w '%{http_code}\\n' $URL/priv/detail.json"
  fi
fi

cat <<EOF

$(echo -e "${B}이제 해보실 것${N}")

  https://$PROJECT.pages.dev

  1. 테마 카드와 랭킹이 로그인 없이 그대로 보이면 정상입니다.
  2. 종목을 누르면 로그인 창이 뜹니다.
  3. $MEMBERS 을 넣고 [인증번호 받기] → 화면에 번호가 나옵니다.
  4. 번호를 넣으면 상세가 열립니다.

$(echo -e "${B}남은 것 — 도메인을 사신 뒤${N}")

  resend.com 가입 → 도메인 인증 → API 키 발급, 그리고

    printf '%s' 're_키값' | npx wrangler pages secret put RESEND_API_KEY --project-name $PROJECT
    printf '%s' '테마보드 <no-reply@내도메인>' | npx wrangler pages secret put MAIL_FROM --project-name $PROJECT
    npx wrangler pages secret delete DEV_SHOW_CODE --project-name $PROJECT

  DEV_SHOW_CODE 를 지우기 전까지는 승인된 메일 주소로 로그인을 시도하면
  화면에 인증번호가 그대로 뜹니다. 시험용이니 메일 연결 뒤 꼭 지워 주세요.

EOF
