# -*- coding: utf-8 -*-
"""
해외(미국) 스냅샷 → web/data_us.json

  python3 export_snapshot_us.py
  python3 export_snapshot_us.py --excd NAS,NYS      # 거래소 제한
  python3 export_snapshot_us.py --min-value 20      # 표시 최소 거래대금(백만달러)

국내판(export_snapshot.py)과 같은 스키마로 내보내므로
화면(web/index.html)의 렌더 코드를 그대로 씁니다.
"""
import os, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
sys.path.insert(0, HERE)

import server_us as U


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    t0 = time.time()
    excds = tuple(x.strip().upper() for x in arg("--excd", "NAS,NYS,AMS").split(",") if x.strip())
    min_value = float(arg("--min-value", "5"))

    print(f"해외 스냅샷 시작 — 거래소 {', '.join(excds)}")
    d = U.build(excds=excds, min_value=min_value)

    os.makedirs(WEB, exist_ok=True)
    out = {
        "ts": d["ts"],
        "market": "US",
        "unit": d["unit"],
        "themes": d["themes"],
        "stocks": d["stocks"],
        "ranking": d["ranking"],
        "universe": d["universe"],
        "scanned": d["scanned"],
        "theme_total": d["theme_total"],
        "theme_stocks": {t["id"]: t["codes"] for t in d["themes"]},
        "generated_by": "export_snapshot_us",
    }
    p = os.path.join(WEB, "data_us.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(p) / 1024

    print(f"\n 완료 → web/data_us.json  ({kb:,.0f} KB, {time.time()-t0:.0f}초)")
    print(f"   테마 {len(d['themes'])}개 (전체 {d['theme_total']}개) / 종목 {d['universe']}개")
    if not d["themes"]:
        print("\n [확인] 테마가 0개입니다. 미국장 개장 시간(한국시간 23:30~06:00)에")
        print("        실행했는지, KIS 해외주식 이용신청이 되어 있는지 확인하세요.")


if __name__ == "__main__":
    main()
