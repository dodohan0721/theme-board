#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NXT(넥스트레이드) 시세가 실제로 내려오는지 확인하는 1분짜리 점검

한국투자증권 공식 예제에 거래소 구분값이 이렇게 적혀 있습니다.
    J : KRX   NX : NXT   UN : 통합
같은 주소로 이 값만 바꾸면 되는 구조라, 코드 수정은 사실상 한 글자입니다.
다만 계좌 권한과 시간대에 따라 실제로 값이 오는지가 갈리므로 직접 찔러봅니다.

    cd ~/theme-board
    python3 check_nxt.py            # 삼성전자·SK하이닉스·카카오로 확인
    python3 check_nxt.py 005930     # 원하는 종목으로 확인

언제 돌리면 되나
    정규장(09:00~15:20)  J 와 NX 둘 다 값이 나와야 정상
    15:30~20:00          J 는 멈춰 있고 NX 만 계속 움직이면 성공
"""
import sys, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

G = '\033[0;32m'; Y = '\033[0;33m'; R = '\033[0;31m'; N = '\033[0m'; B = '\033[1m'

try:
    import server as S
except Exception as e:
    print(f"  {R}✗{N} server.py 를 불러오지 못했습니다: {e}")
    print("     ~/theme-board 안에서 실행하고 있는지 확인해 주세요.")
    sys.exit(1)

CODES = sys.argv[1:] or ["005930", "000660", "035720"]
MARKETS = [("J", "KRX 정규장"), ("NX", "NXT 대체거래소"), ("UN", "통합(KRX+NXT)")]

print()
print(f"  기준시각  {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  대상      {', '.join(CODES)}")
print("=" * 74)
print(f"  {'종목':<10}{'거래소':<18}{'현재가':>10}{'등락률':>9}{'거래대금(억)':>14}")
print("-" * 74)

works = {}
for code in CODES:
    name = None
    for mk, label in MARKETS:
        try:
            r = S.kis_get("/uapi/domestic-stock/v1/quotations/inquire-price",
                          "FHKST01010100",
                          {"FID_COND_MRKT_DIV_CODE": mk, "FID_INPUT_ISCD": code})
        except Exception as e:
            print(f"  {code:<10}{label:<18}{R}호출 실패{N}  {e}")
            works.setdefault(mk, []).append(False)
            continue

        rt = str(r.get("rt_cd", ""))
        o = r.get("output") or {}
        if rt != "0" or not o:
            msg = (r.get("msg1") or "응답 없음").strip()
            print(f"  {code:<10}{label:<18}{R}{msg[:38]}{N}")
            works.setdefault(mk, []).append(False)
            continue

        name = name or o.get("hts_kor_isnm") or code
        price = int(o.get("stck_prpr") or 0)
        rate = float(o.get("prdy_ctrt") or 0)
        # 거래대금은 천원 단위(acml_tr_pbmn) → 억 단위로
        val = int(o.get("acml_tr_pbmn") or 0) / 1e8
        col = G if rate > 0 else (R if rate < 0 else N)
        print(f"  {name[:9]:<10}{label:<18}{price:>10,}{col}{rate:>8.2f}%{N}{val:>14,.0f}")
        works.setdefault(mk, []).append(True)
    print("-" * 74)

print()
ok_nx = any(works.get("NX", []))
ok_un = any(works.get("UN", []))
if ok_nx:
    print(f"  {G}✓{N} NXT 시세가 정상적으로 내려옵니다.")
    print(f"     server.py 의 FID_COND_MRKT_DIV_CODE 를 'J' → 'NX'(또는 'UN') 로만 바꾸면 됩니다.")
    print(f"     바꿔야 할 곳은 3군데입니다:  거래대금 순위 · 등락률 순위 · 종목 현재가")
elif ok_un:
    print(f"  {Y}·{N} NX 는 막혀 있지만 UN(통합)은 열려 있습니다. UN 으로 진행하면 됩니다.")
else:
    print(f"  {R}✗{N} NXT 시세가 내려오지 않습니다.")
    print(f"     한국투자증권 고객센터에 '오픈API 대체거래소(NXT) 시세 이용' 신청이 필요한지 문의해 주세요.")
    print(f"     계정 권한 문제일 뿐, 코드 문제는 아닙니다.")
print()
print(f"  {B}참고{N}  NXT 애프터마켓은 15:30~20:00 이고, 거래 종목은 코스피·코스닥 전체가")
print(f"        아니라 700~800종목입니다. 시간외 화면의 테마 순위는 정규장과 달라집니다.")
print()
