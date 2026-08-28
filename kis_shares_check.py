# -*- coding: utf-8 -*-
"""딱 하나만 확인: 한투가 '상장주식수 / 시가총액 / NAV' 를 주는가.
   이게 있으면 ETF 순유입을 우리가 직접 계산할 수 있고,
   없으면 발행사 공식 데이터로 가야 한다."""
import re, os, json, time, urllib.request, urllib.parse

cfg = {}
s = open(os.path.expanduser("~/Desktop/config.py"), encoding="utf-8").read()
for k, v in re.findall(r'^([A-Z_]+)\s*=\s*["\']([^"\']*)["\']', s, re.M):
    cfg[k] = v
HOST = "https://openapi.koreainvestment.com:9443"

def http(url, method="GET", body=None, headers=None):
    d = json.dumps(body).encode() if body else None
    h = {"content-type": "application/json; charset=utf-8"}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=d, headers=h, method=method), timeout=20) as r:
        return json.load(r)

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
tp = os.path.join(CACHE, "kis_token.json"); tok = None
if os.path.exists(tp):
    d = json.load(open(tp))
    if d.get("expire", 0) > time.time() + 600: tok = d["token"]
if not tok:
    r = http(f"{HOST}/oauth2/tokenP", "POST", {"grant_type":"client_credentials",
             "appkey":cfg["KIS_APP_KEY"],"appsecret":cfg["KIS_APP_SECRET"]})
    tok = r["access_token"]
    json.dump({"token":tok,"expire":time.time()+int(r.get("expires_in",86400))}, open(tp,"w"))

def get(path, tr, params):
    h = {"authorization":f"Bearer {tok}","appkey":cfg["KIS_APP_KEY"],
         "appsecret":cfg["KIS_APP_SECRET"],"tr_id":tr,"custtype":"P"}
    time.sleep(0.1)
    return http(f"{HOST}{path}?{urllib.parse.urlencode(params)}", headers=h)

PAT = re.compile(r"cnt|stck_cnt|cap|shrs|shar|nav|aum|tomv|amt|qty|lstg|issu", re.I)

print("="*66)
print(" 상장주식수 / 시가총액 / NAV 관련 필드만 추출 (IBIT)")
print("="*66)

r1 = get("/uapi/overseas-price/v1/quotations/price","HHDFS00000300",
         {"AUTH":"","EXCD":"NAS","SYMB":"IBIT"})
o1 = r1.get("output") or {}
print(f"\n[현재가] 전체 {len(o1)}개 필드 중 해당:")
hit1 = {k:v for k,v in o1.items() if PAT.search(k)}
print("   " + ("없음" if not hit1 else ""))
for k,v in sorted(hit1.items()): print(f"   {k:22s} = {v}")

r2 = get("/uapi/overseas-price/v1/quotations/search-info","CTPF1702R",
         {"PRDT_TYPE_CD":"512","PDNO":"IBIT"})
o2 = r2.get("output") or {}
print(f"\n[상품기본정보] 전체 {len(o2)}개 필드 중 해당:")
hit2 = {k:v for k,v in o2.items() if PAT.search(k)}
print("   " + ("없음" if not hit2 else ""))
for k,v in sorted(hit2.items()): print(f"   {k:22s} = {v}")

print(f"\n[상품기본정보] 값이 채워진 전체 필드명 (참고):")
print("   " + ", ".join(sorted(k for k,v in o2.items() if v not in ("",None,"0","00000000"))))

print("\n" + "="*66)
if hit1 or hit2:
    print(" 결론: 한투에서 받을 수 있음 → 순유입 자체 산출 가능")
else:
    print(" 결론: 한투에 없음 → 순유입은 발행사 공식 데이터로 조달")
print("="*66)
