# -*- coding: utf-8 -*-
"""한투 해외주식 — ETF 순유입 산출에 필요한 필드가 오는지 확인.
   확인 항목 3가지
     1) 현재가 응답의 전체 필드 (시가총액/상장주식수 유무)
     2) 상품기본정보 (상장주식수가 여기 있을 가능성)
     3) 기간별시세 (과거 백필 가능 여부)
   키는 로컬에서만 읽고 출력하지 않습니다."""
import re, os, json, time, urllib.request, urllib.parse

cfg = {}
p = os.path.expanduser("~/Desktop/config.py")
s = open(p, encoding="utf-8").read()
for k, v in re.findall(r'^([A-Z_]+)\s*=\s*["\']([^"\']*)["\']', s, re.M):
    cfg[k] = v
HOST = "https://openapi.koreainvestment.com:9443"

def http(url, method="GET", body=None, headers=None):
    d = json.dumps(body).encode() if body else None
    h = {"content-type": "application/json; charset=utf-8"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=d, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

# 토큰 캐시 재사용 (1분 1회 발급 제한 회피)
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE, exist_ok=True)
tp = os.path.join(CACHE, "kis_token.json")
tok = None
if os.path.exists(tp):
    try:
        d = json.load(open(tp))
        if d.get("expire", 0) > time.time() + 600:
            tok = d["token"]
    except Exception:
        pass
if not tok:
    r = http(f"{HOST}/oauth2/tokenP", "POST", {"grant_type": "client_credentials",
             "appkey": cfg["KIS_APP_KEY"], "appsecret": cfg["KIS_APP_SECRET"]})
    tok = r["access_token"]
    json.dump({"token": tok, "expire": time.time() + int(r.get("expires_in", 86400))}, open(tp, "w"))
    print("새 토큰 발급")

def get(path, tr, params):
    h = {"authorization": f"Bearer {tok}", "appkey": cfg["KIS_APP_KEY"],
         "appsecret": cfg["KIS_APP_SECRET"], "tr_id": tr, "custtype": "P"}
    time.sleep(0.1)
    return http(f"{HOST}{path}?{urllib.parse.urlencode(params)}", headers=h)

print("\n" + "="*70)
print(" [1] 현재가 — 전체 필드 덤프 (IBIT)")
print("="*70)
r = get("/uapi/overseas-price/v1/quotations/price", "HHDFS00000300",
        {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT"})
o = r.get("output") or {}
for k in sorted(o):
    print(f"   {k:10s} = {o[k]}")

print("\n" + "="*70)
print(" [2] 상품기본정보 — 상장주식수 유무 (IBIT)")
print("="*70)
try:
    r2 = get("/uapi/overseas-price/v1/quotations/search-info", "CTPF1702R",
             {"PRDT_TYPE_CD": "512", "PDNO": "IBIT"})
    o2 = r2.get("output") or {}
    print(f"   rt_cd={r2.get('rt_cd')} msg={r2.get('msg1','')[:40]}")
    for k in sorted(o2):
        if o2[k] not in ("", None):
            print(f"   {k:16s} = {o2[k]}")
except Exception as e:
    print("   실패:", str(e)[:120])

print("\n" + "="*70)
print(" [3] 기간별시세 — 과거 백필 가능 여부 (IBIT, 최근 5일)")
print("="*70)
try:
    r3 = get("/uapi/overseas-price/v1/quotations/dailyprice", "HHDFS76240000",
             {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT", "GUBN": "0", "BYMD": "", "MODP": "1"})
    print(f"   rt_cd={r3.get('rt_cd')} msg={r3.get('msg1','')[:40]}")
    rows = r3.get("output2") or []
    print(f"   받은 일수: {len(rows)}")
    for row in rows[:5]:
        print("   ", {k: row[k] for k in list(row)[:8]})
except Exception as e:
    print("   실패:", str(e)[:120])

print("\n" + "="*70)
print(" [4] 거래소 코드 확인 — ETF 전 종목")
print("="*70)
SYMS = ["IBIT","FBTC","GBTC","BTC","BITB","ARKB","BTCO","EZBC","BRRR","HODL",
        "BTCW","BITS","BITO","ETHA","ETHE","FETH","ETHW","CETH","QETH","EZET"]
for sym in SYMS:
    hit = None
    for exch in ("NAS","AMS","NYS"):
        try:
            rr = get("/uapi/overseas-price/v1/quotations/price", "HHDFS00000300",
                     {"AUTH": "", "EXCD": exch, "SYMB": sym})
            oo = rr.get("output") or {}
            if rr.get("rt_cd") == "0" and oo.get("last") not in (None, "", "0", "0.0000"):
                hit = (exch, oo.get("last"), oo.get("tvol")); break
        except Exception:
            pass
    print(f"   {sym:6s} {hit if hit else '조회 안 됨'}")
