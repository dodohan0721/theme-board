# 한투 해외주식(ETF) 조회 가능 여부 테스트 — 키는 로컬에서만 읽고 출력하지 않음
import re, os, json, time, urllib.request, urllib.parse
cfg={}
for p in (os.path.expanduser("~/Desktop/config.py"), os.path.expanduser("~/Desktop/config.py")):
    if os.path.exists(p):
        s=open(p,encoding="utf-8").read()
        for k,v in re.findall(r'^([A-Z_]+)\s*=\s*["\']([^"\']*)["\']', s, re.M): cfg[k]=v
        print("config 읽음:", p); break
else:
    print("config.py 못 찾음"); raise SystemExit
need=["KIS_APP_KEY","KIS_APP_SECRET"]
print("키 존재:", {k: bool(cfg.get(k)) for k in need})
HOST="https://openapi.koreainvestment.com:9443"
def http(url, method="GET", body=None, headers=None):
    d=json.dumps(body).encode() if body else None
    h={"content-type":"application/json; charset=utf-8"}; h.update(headers or {})
    req=urllib.request.Request(url, data=d, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=15) as r: return json.load(r)
try:
    t=http(f"{HOST}/oauth2/tokenP","POST",{"grant_type":"client_credentials","appkey":cfg["KIS_APP_KEY"],"appsecret":cfg["KIS_APP_SECRET"]})
    tok=t.get("access_token")
    print("토큰 발급:", "성공" if tok else f"실패 {t}")
    if not tok: raise SystemExit
    for sym,exch in [("IBIT","NAS"),("FBTC","AMS"),("ETHA","NAS")]:
        h={"authorization":f"Bearer {tok}","appkey":cfg["KIS_APP_KEY"],"appsecret":cfg["KIS_APP_SECRET"],"tr_id":"HHDFS00000300","custtype":"P"}
        q=urllib.parse.urlencode({"AUTH":"","EXCD":exch,"SYMB":sym})
        r=http(f"{HOST}/uapi/overseas-price/v1/quotations/price?{q}",headers=h)
        o=r.get("output") or {}
        print(f"  {sym}({exch}): rt_cd={r.get('rt_cd')} msg={r.get('msg1','')[:30]} last={o.get('last')} tvol={o.get('tvol')} tomv={o.get('tomv')}")
        time.sleep(0.3)
except Exception as e:
    print("오류:", type(e).__name__, str(e)[:200])
