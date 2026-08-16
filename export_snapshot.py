#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel 배포용 스냅샷 생성기
──────────────────────────────────────────────────────────────────────────────
맥에서 실행 → 한투/DART/네이버를 조회해 web/data.json 을 만듭니다.
Vercel 에는 이 web/ 폴더(정적 파일)만 올라가므로 API 키가 서버에 올라가지 않습니다.

    python3 export_snapshot.py                 # 스냅샷 생성
    python3 export_snapshot.py --detail 80     # 상세(뉴스·재무) 종목 수
    python3 export_snapshot.py --cycles 3      # 스캔 사이클 수 (많을수록 커버리지↑)
    python3 export_snapshot.py --deploy        # 생성 후 vercel --prod 까지 실행
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

# GitHub Actions 러너는 UTC 로 돌아간다. 화면에 찍히는 '기준시각'이
# 9시간 어긋나지 않도록 한국시간으로 고정한다.
os.environ.setdefault("TZ", "Asia/Seoul")
try:
    time.tzset()
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
os.makedirs(WEB, exist_ok=True)

import importlib.util
_s = importlib.util.spec_from_file_location("srv", os.path.join(HERE, "server.py"))
S = importlib.util.module_from_spec(_s)
_s.loader.exec_module(S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", type=int, default=80, help="뉴스·재무를 담을 상위 종목 수")
    ap.add_argument("--cycles", type=int, default=4, help="스캔 사이클 수")
    ap.add_argument("--deploy", action="store_true", help="생성 후 vercel --prod 실행")
    ap.add_argument("--ai", action="store_true",
                    help="기사 본문을 실제로 읽고 AI가 상승 사유를 판단 (ANTHROPIC_API_KEY 필요)")
    ap.add_argument("--ai-top", type=int, default=40, help="AI 판독을 적용할 상위 종목 수")
    a = ap.parse_args()

    print("=" * 70)
    print(" 테마보드 스냅샷 생성")
    print("=" * 70)

    # 스냅샷은 '최신성'보다 '커버리지'가 중요하므로 새 종목 발굴 비중을 크게 잡는다
    # 이전 실행 순서를 복원해 쓰므로, 거래대금 상위는 넉넉히 새로고침한다
    S.FIRST, S.HOT, S.NEW = 800, 700, 500

    t0 = time.time()
    for i in range(1, a.cycles + 1):
        print(f" [{i}/{a.cycles}] 시세 스캔 …")
        d = S.build_dashboard(force=True)
        print(f"      누적 {d['scanned']}/{d['universe']}종목 · 테마 {len(d['themes'])}개")

    # 상세: 거래대금 상위 N종목의 급등사유 + 재무 + 뉴스
    top = d["ranking"][:a.detail]
    print(f"\n 상세 수집 (상위 {len(top)}종목) — 뉴스·DART 재무 …")

    AI = None
    if a.ai:
        key = S.CFG.get("ANTHROPIC_API_KEY")
        if not key:
            print(" ⚠ config.py 에 ANTHROPIC_API_KEY 가 없어 AI 판독을 건너뜁니다.")
        else:
            import importlib.util as _iu
            _sp = _iu.spec_from_file_location("air", os.path.join(HERE, "ai_reason.py"))
            AI = _iu.module_from_spec(_sp); _sp.loader.exec_module(AI)
            AI._KEY = key
            AI.MODEL_OVERRIDE[0] = S.CFG.get("ANTHROPIC_MODEL")
            print(f" AI 판독 사용 — 상위 {a.ai_top}종목의 기사 본문을 읽습니다")

    ai_targets = set(d["ranking"][:a.ai_top]) if AI else set()
    ai_stat = {"ok": 0, "no": 0}

    def detail(code):
        s = d["stocks"].get(code, {})
        name = s.get("name", "")
        tids = s.get("themes", [])
        try:
            reason = S.surge_reason(code, name, s.get("rate", 0), tids, d)
        except Exception as e:
            reason = {"status": "error", "msg": str(e)}
        try:
            fin = S.dart_financials(code)
        except Exception:
            fin = None
        try:
            news = S.naver_news(f"{name} 주가", 5) if s.get("rate", 0) >= 1 else []
        except Exception:
            news = []

        # 기사 본문을 실제로 읽고 판단 (상승률 2% 이상 종목만)
        if AI and code in ai_targets and s.get("rate", 0) >= 2:
            try:
                ctx = (reason or {}).get("theme_context")
                picked, _ = AI.stock_news(S, name)      # 제목 필터를 거친 기사만
                r = AI.analyze(AI._KEY, name, code, s.get("rate", 0), picked, ctx) if picked else None
            except Exception as e:
                r = None
                print(f"      [AI 오류] {name}: {e}")
            if r:
                ai_stat["ok"] += 1
                reason = {"status": "ok", "verified": True,
                          "headline": r["headline"], "confidence": r["confidence"],
                          "read": r["read"], "theme_context": ctx,
                          "evidences": r["evidences"]}
            else:
                ai_stat["no"] += 1
                reason = {"status": "insufficient", "verified": True,
                          "theme_context": (reason or {}).get("theme_context"),
                          "msg": "기사 본문을 확인했으나 이 종목의 상승과 직접 연결되는 "
                                 "공시·계약·실적 내용을 찾지 못했습니다."}
        return code, {"reason": reason, "financial": fin, "news": news}

    details = {}
    with ThreadPoolExecutor(max_workers=3 if a.ai else 4) as ex:
        for i, (code, v) in enumerate(ex.map(detail, top), 1):
            details[code] = v
            if i % 20 == 0:
                print(f"      {i}/{len(top)}")

    # 테마별 전체 구성 종목(‘오늘 조용한 종목’ 표시용)
    theme_stocks = {t["id"]: next((x["stocks"] for x in S.THEMES if x["id"] == t["id"]), [])
                    for t in d["themes"]}

    out = {
        "ts": d["ts"], "themes": d["themes"], "stocks": d["stocks"], "ranking": d["ranking"],
        "universe": d["universe"], "scanned": d["scanned"], "theme_total": d["theme_total"],
        "details": details, "theme_stocks": theme_stocks,
        "generated_by": "export_snapshot.py",
    }
    p = os.path.join(WEB, "data.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(p) / 1024

    print("\n" + "=" * 70)
    print(f" 완료 → web/data.json  ({kb:,.0f} KB)")
    print(f"   테마 {len(d['themes'])}개 · 종목 {len(d['stocks'])}개 · 상세 {len(details)}종목")
    if AI:
        print(f"   AI 본문 판독: 사유 확인 {ai_stat['ok']}종목 · 관련 기사 없음 {ai_stat['no']}종목")
    print(f"   소요 {time.time()-t0:.0f}초 · 기준시각 {d['ts']}")
    print("=" * 70)

    if a.deploy:
        print("\n Vercel 배포 …")
        subprocess.run(["npx", "vercel", "--prod", "--yes"], cwd=WEB)
    else:
        print("\n 배포하려면:")
        print("   cd web && npx vercel --prod")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단했습니다.")
