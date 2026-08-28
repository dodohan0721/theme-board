#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  테마보드 — 관리자 화면 붙이기
#
#    cd ~/theme-board
#    bash setup11.sh                                   # 관리자 = 내 메일
#    bash setup11.sh 내메일@x.com 승인할메일@y.com,...   # 직접 지정
#
#  하는 일
#    1) fix11.py 적용
#    2) 회원 명부 저장소(Cloudflare KV) 생성 · wrangler.toml 에 연결
#    3) 관리자 지정 (ADMINS)
#    4) 기존 승인 계정을 명부로 옮김
#    5) 배포
#    6) 실제로 붙었는지 확인
#
#  여러 번 다시 돌려도 안전합니다. 이미 만든 KV 는 다시 만들지 않습니다.
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
step(){ echo -e "\n${B}$1${N}"; }

PROJECT="theme-board"
W="npx --yes wrangler@latest"

echo -e "${B}════════════════════════════════════════════════════════════${N}"
echo -e "${B} 테마보드 — 회원 관리 화면${N}"
echo -e "${B}════════════════════════════════════════════════════════════${N}"

step "[1/6] 코드 적용"
[ -f fix11.py ] || { err "fix11.py 가 없습니다."; exit 1; }
python3 fix11.py || { err "fix11.py 실패 — 위 내용을 그대로 알려주세요."; exit 1; }

# ── 설정값 ────────────────────────────────────────────────────────────────
CFG=""
for p in config.py ../config.py "$HOME/Desktop/config.py" "$HOME/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
getval(){
  [ -z "$CFG" ] && return
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
T="$(getval CLOUDFLARE_API_TOKEN)"; [ -n "$T" ] && export CLOUDFLARE_API_TOKEN="$T"
A="$(getval CLOUDFLARE_ACCOUNT_ID)"; [ -n "$A" ] && export CLOUDFLARE_ACCOUNT_ID="$A"

ADMIN="${1:-}"                      # 쉼표로 여러 명 지정 가능
[ -z "$ADMIN" ] && ADMIN="$(git config user.email 2>/dev/null)"
[ -z "$ADMIN" ] && { err "관리자 이메일을 못 정했습니다.  bash setup11.sh 내메일@x.com[,고객메일@y.com]"; exit 1; }
SEED="${2:-}"
ok "관리자  $ADMIN"
[ -n "$SEED" ] && ok "미리 승인  $SEED"

# ── KV ────────────────────────────────────────────────────────────────────
step "[2/6] 회원 명부 저장소(KV)"
KVID="$(grep -m1 -E '^\s*id\s*=' wrangler.toml 2>/dev/null | sed -E 's/.*"(.*)".*/\1/')"

# ① 이미 만들어 둔 것이 있으면 그대로 쓴다.
#    같은 이름으로 두 번 만들면 "already exists" 오류가 난다.
if [ -z "$KVID" ] || [ "$KVID" = "KV_ID_HERE" ]; then
  echo "  기존 저장소 확인 …"
  KVID="$($W kv namespace list 2>/dev/null | python3 -c '
import sys, json
raw = sys.stdin.read()
i, j = raw.find("["), raw.rfind("]")
if i < 0 or j < 0: sys.exit()
try: arr = json.loads(raw[i:j+1])
except Exception: sys.exit()
for x in arr:
    if str(x.get("title", "")).strip().endswith("TB"):
        print(x.get("id", "")); break
' 2>/dev/null)"
  [ -n "$KVID" ] && ok "이미 있는 TB 를 그대로 씁니다  ($KVID)"
fi

# ② 그래도 없으면 새로 만든다
if [ -z "$KVID" ] || [ "$KVID" = "KV_ID_HERE" ]; then
  echo "  만드는 중 …"
  OUT="$($W kv namespace create TB 2>&1)"
  KVID="$(echo "$OUT" | grep -oE '[0-9a-f]{32}' | head -1)"
  if [ -z "$KVID" ]; then
    err "KV 준비 실패"
    echo "$OUT" | tail -12
    echo
    echo "  대시보드에서 직접 확인하셔도 됩니다:"
    echo "    dash.cloudflare.com → Storage & Databases → KV"
    echo "    TB 옆의 ID 를 복사해 wrangler.toml 의 KV_ID_HERE 자리에 넣고 다시 실행해 주세요."
    exit 1
  fi
  ok "생성 완료  ($KVID)"
fi

# ③ wrangler.toml 에 연결
python3 - "$KVID" <<'PY'
import sys, re
kid = sys.argv[1]
s = open("wrangler.toml", encoding="utf-8").read()
s = re.sub(r'id\s*=\s*"[^"]*"', f'id = "{kid}"', s, count=1)
open("wrangler.toml", "w", encoding="utf-8").write(s)
PY
ok "wrangler.toml 연결  ($KVID)"

# ── 관리자 · 고정 계정 ────────────────────────────────────────────────────
step "[3/6] 관리자 지정"
setsec(){ printf '%s' "$2" | $W pages secret put "$1" --project-name "$PROJECT" >/dev/null 2>&1 \
          && ok "$1 등록" || { err "$1 등록 실패"; return 1; }; }
MANUAL=0
setsec ADMINS  "$ADMIN"  || MANUAL=1
# 관리자 본인은 명부와 상관없이 항상 열리게 남겨 둔다(잠기지 않도록)
setsec MEMBERS "$ADMIN"  || MANUAL=1
if [ "$MANUAL" = "1" ]; then
  warn "대시보드에서 직접 넣어 주세요 — ADMINS=$ADMIN · MEMBERS=$ADMIN"
fi

# ── 기존 승인 계정 옮기기 ─────────────────────────────────────────────────
step "[4/6] 명부에 계정 넣기"
NOW="$(python3 -c 'import time;print(int(time.time()*1000))')"
seed_one(){
  local e; e="$(echo "$1" | tr '[:upper:]' '[:lower:]' | xargs)"
  [ -z "$e" ] && return
  local v; v="$(python3 -c "
import json,sys
print(json.dumps({'email':sys.argv[1],'status':'approved','created':int(sys.argv[2]),'approved':int(sys.argv[2])}))
" "$e" "$NOW")"
  $W kv key put --namespace-id="$KVID" --remote "m:$e" "$v" >/dev/null 2>&1 \
    && ok "$e  승인 상태로 등록" || warn "$e  등록 실패 (관리자 화면에서 승인하시면 됩니다)"
}
IFS=',' read -ra ADM <<< "$ADMIN"
for e in "${ADM[@]}"; do seed_one "$e"; done
if [ -n "$SEED" ]; then
  IFS=',' read -ra ARR <<< "$SEED"
  for e in "${ARR[@]}"; do seed_one "$e"; done
fi

# ── 배포 ──────────────────────────────────────────────────────────────────
step "[5/6] 배포"
git add -A >/dev/null 2>&1
git diff --cached --quiet 2>/dev/null || git commit -q -m "관리자 화면 — 회원 승인을 사이트에서 직접" && ok "커밋"
git push -q 2>/dev/null && ok "푸시" || warn "푸시 실패 — 나중에 git push 해 주세요"
echo "  배포 중 …"
$W pages deploy --project-name "$PROJECT" --branch main --commit-dirty=true 2>&1 | tail -4

# ── 확인 ──────────────────────────────────────────────────────────────────
step "[6/6] 확인"
sleep 6
URL="https://$PROJECT.pages.dev"
C1=$(curl -s -o /dev/null -w "%{http_code}" "$URL/data.json")
C2=$(curl -s -o /dev/null -w "%{http_code}" "$URL/priv/detail.json")
C3=$(curl -s -o /dev/null -w "%{http_code}" "$URL/api/admin/members")
[ "$C1" = "200" ] && ok "공개 data.json    $C1" || warn "공개 data.json    $C1  (200 이어야 정상)"
[ "$C2" = "401" ] && ok "회원 priv/detail  $C2  (잠김)" || err "회원 priv/detail  $C2  (401 이어야 정상)"
[ "$C3" = "401" ] && ok "관리자 API        $C3  (로그인 필요 — 정상)" \
                  || { [ "$C3" = "500" ] && err "관리자 API        $C3  (KV 연결 실패)" \
                       || warn "관리자 API        $C3"; }

cat <<EOF

$(echo -e "${B}이제 이렇게 쓰시면 됩니다${N}")

  $URL 에서 $ADMIN 으로 로그인
    → 오른쪽 위에 [관리자] 버튼이 생깁니다
    → 이메일 인증을 마친 분들이 '승인 대기' 에 쌓입니다
    → [승인] 을 누르면 그 즉시 열립니다 (다시 배포하지 않으셔도 됩니다)

$(echo -e "${B}고객님께 안내하실 내용${N}")

  1. $URL 접속
  2. 아무 종목이나 클릭 → 이메일 입력 → [인증번호 받기]
  3. 화면에 뜨는 6자리 입력  (도메인 연결 전 임시 방식)
  4. '회원 전용 정보입니다' 가 뜨면 사장님께 알려주시면 승인

$(echo -e "${B}참고${N}")

  · $ADMIN 은 명부와 상관없이 항상 열립니다 (잠기는 사고 방지)
  · 이제부터 배포 명령에 폴더 이름을 붙이지 않습니다
      npx wrangler pages deploy            (O)
      npx wrangler pages deploy web        (X)
    자동 갱신 워크플로도 함께 고쳐 두었습니다.

EOF
