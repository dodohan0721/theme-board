#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 수정 12차 — 거래대금을 KRX + NXT 통합으로

무엇이 문제였나
    지금까지 시세를 'J'(KRX 정규장) 로만 조회했습니다.
    그런데 대체거래소 NXT 가 대형주 거래의 상당 부분을 가져가고 있습니다.

        삼성전자   KRX 44,882억  +  NXT 35,346억  =  통합 80,228억
        SK하이닉스 KRX 56,821억  +  NXT 48,182억  =  통합 105,004억

    즉 화면의 거래대금이 실제의 절반 남짓이었고,
    테마 순위도 그만큼 어긋나 있었습니다.

무엇이 바뀌나
    조회 기준을 'UN'(통합) 으로 바꿉니다. 세 군데뿐입니다.
      · 거래대금 순위 · 등락률 순위 · 종목 현재가

    덤으로 시간외까지 따라옵니다.
      15:30 이후에는 KRX 가 멈추고 NXT 만 움직이므로,
      통합값이 그대로 시간외 흐름이 됩니다. 화면을 나눌 필요가 없습니다.
      갱신 종료 시각만 15:50 → 20:00 으로 늘립니다.

되돌리려면
    환경변수 KIS_MARKET=J 로 두면 예전처럼 KRX 만 봅니다.

    cd ~/theme-board
    python3 fix12.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
OK, SKIP, FAIL = [], [], []


def sub(path, desc, old, new, marker=None):
    if not os.path.exists(path):
        FAIL.append(f"{desc} — {path} 없음"); return
    s = open(path, encoding="utf-8").read()
    if (marker or new) in s:
        SKIP.append(f"{desc} — 이미 적용됨"); return
    if old not in s:
        FAIL.append(f"{desc} — 위치를 못 찾음"); return
    open(path, "w", encoding="utf-8").write(s.replace(old, new, 1))
    OK.append(desc)


for p in ("server.py", ".github/workflows/snapshot.yml", "web/index.html"):
    if not os.path.exists(p):
        print(f"  {R}✗{N} {p} 없음 — ~/theme-board 에서 실행하세요."); sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════
# 1. 조회 기준 — J(KRX) → UN(통합)
# ══════════════════════════════════════════════════════════════════════════
sub("server.py", "거래소 구분값 설정",
"""CFG = load_config()""",
'''CFG = load_config()

# ── 거래소 구분 ────────────────────────────────────────────────────────────
#   J  = KRX 정규장만
#   NX = NXT(대체거래소) 만
#   UN = 통합 — KRX + NXT 합산  ← 기본값
#
# NXT 가 대형주 거래의 상당 부분을 가져가므로, KRX 만 보면 거래대금이
# 실제의 절반 수준으로 잡힙니다. 그래서 통합을 기본으로 씁니다.
# 15:30 이후에는 KRX 가 멈추고 NXT 만 움직이므로,
# 같은 값이 그대로 '시간외 흐름' 이 됩니다.
#
# 예전처럼 KRX 만 보려면  KIS_MARKET=J  로 두세요.
MKT = (os.environ.get("KIS_MARKET") or CFG.get("KIS_MARKET") or "UN").strip().upper()
if MKT not in ("J", "NX", "UN"):
    MKT = "UN"
''',
    'MKT = (os.environ.get("KIS_MARKET")')

sub("server.py", "거래대금 순위 — 통합 기준",
    '        "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",',
    '        "FID_COND_MRKT_DIV_CODE": MKT, "FID_COND_SCR_DIV_CODE": "20171",',
    '"FID_COND_MRKT_DIV_CODE": MKT')

sub("server.py", "등락률 순위 — 통합 기준",
    '        "fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20170",',
    '        "fid_cond_mrkt_div_code": MKT, "fid_cond_scr_div_code": "20170",',
    '"fid_cond_mrkt_div_code": MKT')

sub("server.py", "종목 현재가 — 통합 기준",
    '                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})',
    '                {"FID_COND_MRKT_DIV_CODE": MKT, "FID_INPUT_ISCD": code})',
    '{"FID_COND_MRKT_DIV_CODE": MKT, "FID_INPUT_ISCD": code}')

# ══════════════════════════════════════════════════════════════════════════
# 2. 자동 갱신 — 20:00 까지
# ══════════════════════════════════════════════════════════════════════════
sub(".github/workflows/snapshot.yml", "갱신 종료 시각 기본값 20:00",
'''        description: "종료 시각 HHMM (KST)"
        required: false
        default: "1550"''',
'''        description: "종료 시각 HHMM (KST)"
        required: false
        default: "2000"''',
    'default: "2000"')

sub(".github/workflows/snapshot.yml", "루프 종료 시각 20:00",
    """          UNTIL:    ${{ github.event.inputs.until    || '1550' }}""",
    """          UNTIL:    ${{ github.event.inputs.until    || '2000' }}""",
    "|| '2000' }}")

sub(".github/workflows/snapshot.yml", "시간외 이어받기 크론 추가",
'''    - cron: "55 4 * * 1-5"     # KST 13:55  후반 이어받기''',
'''    - cron: "55 4 * * 1-5"     # KST 13:55  후반 이어받기
    - cron: "0 8 * * 1-5"      # KST 17:00  시간외(NXT) 이어받기''',
    'KST 17:00  시간외(NXT) 이어받기')

sub(".github/workflows/snapshot.yml", "설명 주석 갱신",
'''#   08:45 시작 → 루프 → (13:55 새 작업이 이어받음) → 15:50 종료
#   11:00 · 14:00 은 앞 작업이 누락됐을 때를 위한 예비 트리거''',
'''#   08:45 시작 → 루프 → (13:55 · 17:00 새 작업이 이어받음) → 20:00 종료
#   11:00 은 앞 작업이 누락됐을 때를 위한 예비 트리거
#
# 20:00 까지 도는 이유: 15:30~20:00 은 대체거래소(NXT) 애프터마켓이라
# 통합 시세가 계속 움직인다. 한 작업의 최대 실행시간이 6시간이므로
# 세 번에 나눠 이어받는다.''',
    '17:00 새 작업이 이어받음')

# ══════════════════════════════════════════════════════════════════════════
# 3. 화면 — 기준을 밝힌다
# ══════════════════════════════════════════════════════════════════════════
sub("web/index.html", "통합 기준 안내 문구",
'''  <div class="note">사전의 <b>${D.universe}종목</b> 중 <b>${D.scanned}종목</b>을 조회해 테마별로 묶었습니다.''',
'''  <div class="note">거래대금은 <b>KRX + NXT(대체거래소) 합산</b> 기준입니다.${afterHours()}
  사전의 <b>${D.universe}종목</b> 중 <b>${D.scanned}종목</b>을 조회해 테마별로 묶었습니다.''',
    "KRX + NXT(대체거래소) 합산")

sub("web/index.html", "시간외 표시 함수",
"""function themeHead(t){""",
"""// 스냅샷 기준시각이 15:30 을 넘었으면 시간외(NXT) 구간임을 알린다.
// 이때는 KRX 가 멈춰 있어 통합값의 변화가 곧 NXT 의 움직임이다.
function afterHours(){
  const ts=(D&&D.ts)||''; const hm=ts.slice(11,16).replace(':','');
  if(!hm) return '';
  const n=parseInt(hm,10);
  if(n>=1530&&n<=2010)
    return ` <b style="color:var(--teal-d,#04868c)">15:30 이후 — 정규장은 종가로 멈춰 있고, 지금 움직이는 것은 NXT 시간외(15:30~20:00)입니다.</b>`;
  return '';
}
function themeHead(t){""",
    "function afterHours(){")

# ══════════════════════════════════════════════════════════════════════════
# 4. 검사
# ══════════════════════════════════════════════════════════════════════════
import py_compile
try:
    py_compile.compile("server.py", doraise=True); OK.append("server.py 문법 정상")
except Exception as e:
    FAIL.append(f"server.py 문법 오류: {e}")

s = open("server.py", encoding="utf-8").read()
left = s.count('_MRKT_DIV_CODE": "J"') + s.count('_mrkt_div_code": "J"')
if left: FAIL.append(f"아직 'J' 로 고정된 곳이 {left}군데 남아 있음")
else:    OK.append("KRX 고정 호출이 남아 있지 않음")

h = open("web/index.html", encoding="utf-8").read()
if h.count("`") % 2 == 0: OK.append("템플릿 문자열 짝 정상")
else: FAIL.append("백틱(`) 홀수 — 템플릿 문자열 깨짐")

try:
    import yaml as _y
    d = _y.safe_load(open(".github/workflows/snapshot.yml", encoding="utf-8"))
    crons = [c["cron"] for c in d[True]["schedule"]]
    OK.append(f"워크플로 YAML 정상 · 크론 {len(crons)}개")
except ImportError:
    SKIP.append("PyYAML 없음 — YAML 검사 건너뜀")
except Exception as e:
    FAIL.append(f"워크플로 YAML 오류: {e}")

print("\n" + "=" * 62)
for x in OK:   print(f"  {G}✓{N} {x}")
for x in SKIP: print(f"  {Y}·{N} {x}")
for x in FAIL: print(f"  {R}✗{N} {x}")
print("=" * 62)
if FAIL:
    print("\n실패 항목이 있습니다. 위 내용을 그대로 알려주세요.\n"); sys.exit(1)

print(f"""
{B}먼저 눈으로 확인{N}

    python3 -c "
import server as S
print('기준:', S.MKT)
r = S.kis_volume_rank()[:5]
for x in r: print(f\\"  {{x['name'][:10]:<12}} {{x['value']:>8,}}억  {{x['rate']:+.2f}}%\\")
"

  삼성전자·SK하이닉스 거래대금이 예전보다 확 커져 있으면 제대로 바뀐 것입니다.

{B}반영{N}
    git add -A
    git commit -m "거래대금을 KRX+NXT 통합 기준으로 · 20:00까지 갱신"
    git push
    python3 export_snapshot.py --cycles 2 --detail 60 --ai --ai-top 30
    npx wrangler pages deploy --project-name theme-board --branch main --commit-dirty=true

{B}되돌리려면{N}
    printf '%s' 'J' | npx wrangler pages secret put KIS_MARKET --project-name theme-board
  (또는 config.py 에  KIS_MARKET = "J"  한 줄)
""")
