#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KIS 순위 API 탐침 — 어떤 (경로 + tr_id + 파라미터) 조합이 되는지 하나씩 시도합니다.
    python3 probe_rank.py
성공한 조합을 알려주시면 server.py 를 그 조합으로 고정하겠습니다.
"""
import json, os, re, ssl, sys, time, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util
_s = importlib.util.spec_from_file_location("srv", os.path.join(HERE, "server.py"))
S = importlib.util.module_from_spec(_s); _s.loader.exec_module(S)

TOK = S.kis_token()
HDR = lambda tr: {"authorization": f"Bearer {TOK}", "appkey": S.need("KIS_APP_KEY"),
                  "appsecret": S.need("KIS_APP_SECRET"), "tr_id": tr, "custtype": "P"}

def call(path, tr, params):
    url = f"{S.KIS_HOST}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    for k, v in HDR(tr).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"rt_cd": f"HTTP{e.code}", "msg1": e.read().decode("utf-8", "ignore")[:200]}
    except Exception as e:
        return {"rt_cd": "ERR", "msg1": f"{type(e).__name__}: {e}"}

VOL_BASE = {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "0", "FID_BLNG_CLS_CODE": "3",
            "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "", "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""}

FLU_BASE = {"fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": "0000", "fid_rank_sort_cls_code": "0",
            "fid_input_cnt_1": "0", "fid_prc_cls_code": "0",
            "fid_input_price_1": "", "fid_input_price_2": "", "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0", "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0", "fid_rsfl_rate1": "", "fid_rsfl_rate2": ""}

CASES = [
 ("A  거래량순위 quotations/volume-rank + FHPST01710 (EXLS 6자리)",
  "/uapi/domestic-stock/v1/quotations/volume-rank", "FHPST01710", VOL_BASE),
 ("B  거래량순위 + EXLS 10자리",
  "/uapi/domestic-stock/v1/quotations/volume-rank", "FHPST01710",
  {**VOL_BASE, "FID_TRGT_EXLS_CLS_CODE": "0000000000"}),
 ("C  거래량순위 파라미터 소문자",
  "/uapi/domestic-stock/v1/quotations/volume-rank", "FHPST01710",
  {k.lower(): v for k, v in VOL_BASE.items()}),
 ("D  거래량순위 경로가 ranking/ 아래",
  "/uapi/domestic-stock/v1/ranking/volume-rank", "FHPST01710", VOL_BASE),
 ("E  등락률순위 ranking/fluctuation + FHPST01700",
  "/uapi/domestic-stock/v1/ranking/fluctuation", "FHPST01700", FLU_BASE),
 ("F  등락률순위 파라미터 대문자",
  "/uapi/domestic-stock/v1/ranking/fluctuation", "FHPST01700",
  {k.upper(): v for k, v in FLU_BASE.items()}),
 ("G  시가총액순위 ranking/market-cap + FHPST01740",
  "/uapi/domestic-stock/v1/ranking/market-cap", "FHPST01740",
  {"fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20174", "fid_div_cls_code": "0",
   "fid_input_iscd": "0000", "fid_trgt_cls_code": "0", "fid_trgt_exls_cls_code": "0",
   "fid_input_price_1": "", "fid_input_price_2": "", "fid_vol_cnt": ""}),
 ("H  체결강도상위 ranking/volume-power + FHPST01680",
  "/uapi/domestic-stock/v1/ranking/volume-power", "FHPST01680",
  {"fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20168", "fid_input_iscd": "0000",
   "fid_div_cls_code": "0", "fid_input_price_1": "", "fid_input_price_2": "",
   "fid_vol_cnt": "", "fid_trgt_cls_code": "0", "fid_trgt_exls_cls_code": "0"}),
]

print("=" * 78)
print(" KIS 순위 API 탐침   (환경: %s)" % ("실전" if S.IS_REAL else "모의"))
print("=" * 78)
win = []
for label, path, tr, params in CASES:
    r = call(path, tr, params)
    rt, msg = r.get("rt_cd"), (r.get("msg1") or "").strip()
    out = r.get("output")
    n = len(out) if isinstance(out, list) else (1 if out else 0)
    ok = (rt == "0" and n > 0)
    print(f"\n{'✅' if ok else '❌'} {label}")
    print(f"   rt_cd={rt}  msg={msg[:60]}  output={n}건")
    if ok:
        win.append(label)
        first = out[0] if isinstance(out, list) else out
        print("   ── 첫 행 필드 ──")
        for k, v in list(first.items())[:14]:
            print(f"      {k:<26} {str(v)[:24]}")
        open(os.path.join(HERE, f"_probe_{label[0]}.json"), "w", encoding="utf-8").write(
            json.dumps(r, ensure_ascii=False, indent=1))
        print(f"   전체 응답 저장: _probe_{label[0]}.json")
    time.sleep(0.4)

print("\n" + "=" * 78)
print(" 성공: " + (", ".join(w[0] for w in win) if win else "없음"))
print(" → 이 결과를 그대로 복사해서 알려주세요.")
print("=" * 78)
