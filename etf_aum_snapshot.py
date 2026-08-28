# -*- coding: utf-8 -*-
"""ETF 전 종목 스냅샷: 상장주식수 × 종가 = AUM.
   매일 실행하면 상장주식수 변화 × 종가 = 그날의 순유입이 나온다.
   결과는 .cache/etf_shares_YYYYMMDD.json 에 쌓인다."""
import re, os, json, time, urllib.request, urllib.parse, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
cfg = {}
s = open(os.path.expanduser("~/Desktop/config.py"), encoding="utf-8").read()
for k, v in re.findall(r'^([A-Z_]+)\s*=\s*["\']([^"\']*)["\']', s, re.M): cfg[k] = v
HOST = "https://openapi.koreainvestment.com:9443"

def http(url, method="GET", body=None, headers=None):
    d = json.dumps(body).encode() if body else None
    h = {"content-type": "application/json; charset=utf-8"}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=d, headers=h, method=method), timeout=20) as r:
        return json.load(r)

CACHE = os.path.join(BASE, ".cache"); os.makedirs(CACHE, exist_ok=True)
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
    time.sleep(0.08)
    return http(f"{HOST}{path}?{urllib.parse.urlencode(params)}", headers=h)

ETF = [("IBIT","NAS","BTC"),("FBTC","AMS","BTC"),("GBTC","AMS","BTC"),("BTC","AMS","BTC"),
       ("BITB","AMS","BTC"),("ARKB","AMS","BTC"),("BTCO","AMS","BTC"),("EZBC","AMS","BTC"),
       ("BRRR","NAS","BTC"),("HODL","AMS","BTC"),("BTCW","AMS","BTC"),("BITS","NAS","BTC"),
       ("BITO","AMS","BTC"),("ETHA","NAS","ETH"),("ETHE","AMS","ETH"),("FETH","AMS","ETH"),
       ("ETHW","AMS","ETH"),("QETH","AMS","ETH"),("EZET","AMS","ETH")]

today = datetime.datetime.now().strftime("%Y%m%d")
rows, tot = [], {"BTC":0.0, "ETH":0.0}
print(f"{'티커':<7}{'기초':<5}{'종가':>10}{'상장주식수':>16}{'AUM($B)':>11}  ISIN")
print("-"*72)
for sym, exch, und in ETF:
    try:
        p = (get("/uapi/overseas-price/v1/quotations/price","HHDFS00000300",
                 {"AUTH":"","EXCD":exch,"SYMB":sym}).get("output") or {})
        i = (get("/uapi/overseas-price/v1/quotations/search-info","CTPF1702R",
                 {"PRDT_TYPE_CD":"512","PDNO":sym}).get("output") or {})
        last = float(p.get("last") or 0); shr = float(i.get("lstg_stck_num") or 0)
        tot[und] += last*shr/1e9
        rows.append({"ticker":sym,"exch":exch,"underlying":und,"last":last,"shares":shr,
                     "aum_usd":last*shr,"isin":i.get("std_pdno",""),"name":i.get("prdt_eng_name","")})
        print(f"{sym:<7}{und:<5}{last:>10.4f}{shr:>16,.0f}{last*shr/1e9:>11.2f}  {i.get('std_pdno','')}")
    except Exception as e:
        print(f"{sym:<7}{und:<5}  실패 {str(e)[:40]}")

print("-"*72)
print(f"합계   BTC ${tot['BTC']:.1f}B   ETH ${tot['ETH']:.1f}B   전체 ${tot['BTC']+tot['ETH']:.1f}B")

json.dump({"date":today,"rows":rows}, open(os.path.join(CACHE, f"etf_shares_{today}.json"),"w"),
          ensure_ascii=False, indent=1)
print(f"저장 → .cache/etf_shares_{today}.json")

prev = sorted(f for f in os.listdir(CACHE)
              if f.startswith("etf_shares_") and f != f"etf_shares_{today}.json")
if prev:
    old = json.load(open(os.path.join(CACHE, prev[-1])))
    om = {r["ticker"]: r for r in old["rows"]}; net = 0.0
    print(f"\n=== 순유입 ({old['date']} → {today}) ===")
    for r in rows:
        o = om.get(r["ticker"])
        if not o: continue
        d = (r["shares"]-o["shares"])*r["last"]; net += d
        if abs(d) > 1: print(f"   {r['ticker']:<6} {r['shares']-o['shares']:+,.0f}주  ${d/1e6:+,.1f}M")
    print(f"   ─────  총 ${net/1e6:+,.1f}M")
else:
    print("\n※ 이전 스냅샷 없음 — 내일 다시 실행하면 순유입이 계산됩니다.")
