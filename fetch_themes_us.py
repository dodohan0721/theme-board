# -*- coding: utf-8 -*-
"""
ARK ETF 구성종목을 받아 themes_us.json 의 ARK 테마를 갱신한다.

  python3 fetch_themes_us.py

ARK 는 매일 구성종목 CSV 를 공개합니다. 운용사가 직접 큐레이션한 결과라
"어떤 종목이 이 테마에 새로 들어오고 빠졌는지" 가 자동으로 추적됩니다.

※ Global X · Invesco · iShares 는 스크립트 접근이 막혀 있어 자동화가 안 됩니다.
   그쪽 테마는 themes_us.json 에서 직접 관리하세요.
"""
import os, sys, csv, io, json, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
TF = os.path.join(HERE, "themes_us.json")

BASE = "https://assets.ark-funds.com/fund-documents/funds-etf-csv/"
FILES = {
    "ARKK": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
    "ARKQ": "ARK_AUTONOMOUS_TECH._&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
    "ARKW": "ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
    "ARKF": "ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv",
    "ARKX": "ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def holdings(etf):
    """ETF 구성 티커 목록 (비중 큰 순). 미국 상장 보통주만."""
    url = BASE + urllib.parse.quote(FILES[etf], safe=":/&._-")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8-sig", "ignore")

    rows = list(csv.DictReader(io.StringIO(raw)))
    out, seen = [], set()
    for x in rows:
        t = (x.get("ticker") or "").strip().upper()
        if not t or t in seen:
            continue
        # 현금·비상장·해외거래소 표기 제외
        if not t.isalpha() or len(t) > 5:
            continue
        seen.add(t)
        out.append(t)
    return out


def main():
    if not os.path.exists(TF):
        sys.exit(f"themes_us.json 이 없습니다: {TF}")
    d = json.load(open(TF, encoding="utf-8"))
    auto = set(d.get("_auto", []))
    changed = 0

    for t in d.get("themes", []):
        if t.get("id") not in auto:
            continue
        etf = (t.get("etf") or "").upper()
        if etf not in FILES:
            continue
        try:
            new = holdings(etf)
        except Exception as e:
            print(f"  [실패] {etf}: {e}")
            continue
        if not new:
            print(f"  [건너뜀] {etf}: 구성종목 0개")
            continue
        old = set(t.get("stocks") or [])
        added = [x for x in new if x not in old]
        removed = [x for x in old if x not in set(new)]
        t["stocks"] = new
        changed += 1
        msg = f"  {etf:5s} {len(new):3d}종목"
        if added:
            msg += f"  +{','.join(added[:6])}" + ("…" if len(added) > 6 else "")
        if removed:
            msg += f"  -{','.join(removed[:6])}" + ("…" if len(removed) > 6 else "")
        print(msg)

    if changed:
        json.dump(d, open(TF, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n themes_us.json 갱신 완료 ({changed}개 테마)")
    else:
        print("\n 갱신된 테마가 없습니다.")


if __name__ == "__main__":
    main()
