#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NXT 2차 점검 — 순위 조회가 통합(UN)을 받는가

종목 현재가는 UN 이 되는 걸 확인했습니다(check_nxt.py).
그런데 테마 순위의 뼈대는 '거래대금 순위'와 '등락률 순위' 두 개라,
이 둘도 UN 을 받아야 통합 거래대금 기준으로 테마를 세울 수 있습니다.

    cd ~/theme-board
    python3 check_nxt2.py
"""
import sys, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'

try:
    import server as S
except Exception as e:
    print(f"  {R}✗{N} server.py 를 불러오지 못했습니다: {e}"); sys.exit(1)

MARKETS = [("J", "KRX 정규장"), ("NX", "NXT"), ("UN", "통합")]
res = {}

print()
print(f"  기준시각  {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 76)

# ── 1. 거래대금 순위 ───────────────────────────────────────────────────────
print(f"\n{B}[1] 거래대금 순위  volume-rank{N}")
for mk, label in MARKETS:
    try:
        r = S.kis_get("/uapi/domestic-stock/v1/quotations/volume-rank", "FHPST01710", {
            "FID_COND_MRKT_DIV_CODE": mk, "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "3",
            "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "0000000000",
            "FID_INPUT_PRICE_1": "", "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""})
    except Exception as e:
        print(f"  {R}✗{N} {label:12s} 호출 실패 — {e}"); res[("rank", mk)] = False; continue

    out = r.get("output") or []
    if str(r.get("rt_cd")) != "0" or not out:
        print(f"  {R}✗{N} {label:12s} {(r.get('msg1') or '응답 없음').strip()[:44]}")
        res[("rank", mk)] = False; continue

    top = out[:3]
    names = " · ".join(f"{x.get('hts_kor_isnm','?')[:8]}({int(x.get('acml_tr_pbmn') or 0)/1e8:,.0f}억)"
                       for x in top)
    print(f"  {G}✓{N} {label:12s} {len(out):>3}종목   {names}")
    res[("rank", mk)] = True

# ── 2. 등락률 순위 ─────────────────────────────────────────────────────────
print(f"\n{B}[2] 등락률 순위  fluctuation{N}")
for mk, label in MARKETS:
    try:
        r = S.kis_get("/uapi/domestic-stock/v1/ranking/fluctuation", "FHPST01700", {
            "fid_cond_mrkt_div_code": mk, "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": "0000", "fid_rank_sort_cls_code": "0",
            "fid_input_cnt_1": "0", "fid_prc_cls_code": "0",
            "fid_input_price_1": "", "fid_input_price_2": "",
            "fid_vol_cnt": "", "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0", "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "", "fid_rsfl_rate2": ""})
    except Exception as e:
        print(f"  {R}✗{N} {label:12s} 호출 실패 — {e}"); res[("flu", mk)] = False; continue

    out = r.get("output") or []
    if str(r.get("rt_cd")) != "0" or not out:
        print(f"  {R}✗{N} {label:12s} {(r.get('msg1') or '응답 없음').strip()[:44]}")
        res[("flu", mk)] = False; continue

    names = " · ".join(f"{x.get('hts_kor_isnm','?')[:8]}({float(x.get('prdy_ctrt') or 0):+.1f}%)"
                       for x in out[:3])
    print(f"  {G}✓{N} {label:12s} {len(out):>3}종목   {names}")
    res[("flu", mk)] = True

# ── 판정 ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 76)
un_ok = res.get(("rank", "UN")) and res.get(("flu", "UN"))
nx_ok = res.get(("rank", "NX")) and res.get(("flu", "NX"))

if un_ok:
    print(f"""
  {G}✓ 통합(UN) 으로 전부 바꿀 수 있습니다.{N}

    그러면 두 가지가 한 번에 해결됩니다.
      · 거래대금이 KRX + NXT 합산이 되어 {B}테마 순위가 실제 자금 흐름과 맞습니다{N}
        (지금은 삼성전자 기준 44,882억만 보고 있고, 실제는 80,228억입니다)
      · 15:30 이후에는 KRX 가 멈추고 NXT 만 움직이므로
        통합값이 그대로 {B}시간외 흐름{N}이 됩니다 — 탭을 나눌 필요가 없습니다

    다음:  python3 fix12.py  →  bash setup12.sh
""")
elif nx_ok:
    print(f"""
  {Y}· 통합(UN) 은 순위에서 막혀 있고, NXT(NX) 단독은 됩니다.{N}

    이 경우엔 정규장/시간외를 화면에서 나누는 방식으로 가야 합니다.
    이 결과를 그대로 알려주세요. 그 구조로 다시 짜드리겠습니다.
""")
else:
    print(f"""
  {R}✗ 순위 조회는 KRX(J) 만 열려 있습니다.{N}

    종목 현재가만 NXT 가 되는 상태라, 테마 순위를 통합으로 세울 수 없습니다.
    한투에 '오픈API 순위분석 대체거래소(NXT) 시세' 이용 가능 여부를 문의해 주세요.
""")
