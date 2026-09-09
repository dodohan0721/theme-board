# -*- coding: utf-8 -*-
"""
해외 종목 상세 → web/priv/detail_us.json

  python3 export_detail_us.py                 # AI 판독 없이 뉴스만
  python3 export_detail_us.py --ai            # AI 로 상승 사유까지
  python3 export_detail_us.py --ai --top 60 --min-rate 3

국내판(export_snapshot.py --ai)과 같은 스키마로 내보내므로 화면 코드를 그대로 씁니다.

■ 국내와 다른 점 — 반드시 알고 계셔야 합니다
  국내는 기사 '본문'을 긁어 읽습니다. 해외는 한국투자증권이 뉴스 '제목'만 주고
  원문 링크를 주지 않습니다. 그래서 AI 가 제목만 보고 판단합니다.
  결과에 source="headline" 을 넣어 화면에서 그렇게 표시하며,
  본문 확인 배지(✓)는 붙이지 않습니다. 근거가 약하면 '불충분'으로 냅니다.
"""
import os, sys, json, time, argparse, re
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
PRIV = os.path.join(WEB, "priv")
sys.path.insert(0, HERE)

import server as S
import server_us as U

SYSTEM = """너는 미국 주식 시장을 보는 애널리스트다.
주어진 것은 특정 종목의 '뉴스 제목 목록'뿐이다. 기사 본문은 없다.

규칙
- 제목에 실제로 적힌 내용만 쓴다. 추측·일반론·배경지식으로 채우지 마라.
- 주가 상승과 직접 연결되는 사건(실적, 가이던스, 계약·수주, 승인·허가, 인수합병,
  투자·증설, 지수 편입, 애널리스트 목표가)이 제목에 없으면 근거 없음으로 판정한다.
- "주가 급등", "상승 마감" 같은 결과만 적힌 제목은 이유가 아니다. 근거로 쓰지 마라.
- 한국어로 답한다. 종목명·고유명사는 원문 표기를 유지한다.
- 투자 권유·전망·매수 의견을 쓰지 마라. 사실만 정리한다.

출력은 아래 JSON 하나만. 다른 말 붙이지 마라.
{"found": true/false,
 "headline": "왜 올랐는지 한 문장 (40자 이내)",
 "confidence": "상|중|하",
 "evidences": [{"title": "인용한 제목 원문 그대로", "text": "그 제목이 말하는 사실 한 줄"}]}

found 가 false 면 headline 과 evidences 는 비운다.
evidences 의 title 은 반드시 입력에 있던 제목을 글자 그대로 옮긴다."""


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def analyze_headlines(key, model, name, code, rate, items):
    """제목만 보고 판단. 지어낸 근거는 걸러낸다."""
    if not items:
        return None
    lines = "\n".join(f"- [{n.get('time','')}] {n['title']}" for n in items)
    user = (f"종목: {name} ({code})\n오늘 등락률: {rate:+.2f}%\n\n"
            f"[뉴스 제목 {len(items)}건]\n{lines}")
    try:
        raw = __import__("ai_reason").call_claude(key, model, SYSTEM, user, max_tokens=700)
    except Exception as e:
        return {"_err": str(e)}

    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        r = json.loads(m.group(0))
    except Exception:
        return None
    if not r.get("found"):
        return None

    # 게이트 — 입력에 없던 제목을 만들어냈으면 버린다
    have = {_norm(n["title"]) for n in items}
    ev = []
    for e in (r.get("evidences") or []):
        t = _norm(e.get("title"))
        if not t:
            continue
        hit = next((n for n in items if _norm(n["title"]) == t), None)
        if not hit:
            hit = next((n for n in items if t and (t in _norm(n["title"]) or _norm(n["title"]) in t)), None)
        if hit:
            ev.append({"title": hit["title"], "text": (e.get("text") or "").strip(),
                       "time": hit.get("time", ""), "url": ""})
    if not ev:
        return None
    return {"headline": (r.get("headline") or "").strip(),
            "confidence": r.get("confidence") or "중",
            "evidences": ev[:3], "read": len(items)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", action="store_true", help="AI 로 상승 사유 판독")
    ap.add_argument("--top", type=int, default=80, help="거래대금 상위 N종목")
    ap.add_argument("--min-rate", type=float, default=2.0, help="AI 판독 최소 상승률(%%)")
    a = ap.parse_args()

    src = os.path.join(WEB, "data_us.json")
    if not os.path.exists(src):
        sys.exit("web/data_us.json 이 없습니다. export_snapshot_us.py 를 먼저 실행하세요.")
    d = json.load(open(src, encoding="utf-8"))
    top = d["ranking"][:a.top]
    print(f"해외 상세 — 상위 {len(top)}종목")

    key = model = None
    if a.ai:
        key = S.CFG.get("ANTHROPIC_API_KEY")
        if not key:
            print("  [건너뜀] ANTHROPIC_API_KEY 가 없어 AI 판독을 하지 않습니다.")
        else:
            model = __import__("ai_reason").pick_model(key, S.CFG.get("ANTHROPIC_MODEL"))
            print(f"  AI 판독 사용 — 상승률 {a.min_rate}%% 이상 종목의 뉴스 제목을 읽습니다")

    stat = {"ok": 0, "no": 0, "err": 0}

    def one(code):
        s = d["stocks"].get(code, {})
        name = s.get("name", code)
        rate = s.get("rate", 0)
        try:
            nw = U.news(symb=code, excd=s.get("excd", ""), n=8)
        except Exception:
            nw = []

        # 테마 맥락 (같은 테마가 함께 올랐는지)
        ctx = None
        for tid in (s.get("themes") or []):
            t = next((x for x in d["themes"] if x["id"] == tid), None)
            if t and t["n"] >= 3 and t["up"] / t["n"] >= 0.6:
                ctx = f"'{t['name']}' 테마가 함께 움직입니다 ({t['n']}종목 중 {t['up']}종목 상승, 평균 {t['pct']:+.2f}%)"
                break

        reason = {"status": "none", "theme_context": ctx}
        if key and rate >= a.min_rate and nw:
            r = analyze_headlines(key, model, name, code, rate, nw)
            if r and "_err" in r:
                stat["err"] += 1
                reason = {"status": "error", "msg": r["_err"], "theme_context": ctx}
            elif r:
                stat["ok"] += 1
                reason = {"status": "ok", "verified": False, "source": "headline",
                          "headline": r["headline"], "confidence": r["confidence"],
                          "read": r["read"], "theme_context": ctx, "evidences": r["evidences"]}
            else:
                stat["no"] += 1
                reason = {"status": "insufficient", "source": "headline",
                          "theme_context": ctx,
                          "msg": "뉴스 제목을 확인했으나 이 종목의 상승과 직접 연결되는 "
                                 "실적·계약·승인 등의 내용을 찾지 못했습니다."}
        elif not nw:
            reason = {"status": "insufficient", "theme_context": ctx,
                      "msg": "이 종목의 뉴스가 조회되지 않았습니다."}

        return code, {"reason": reason, "financial": None, "news": nw}

    details = {}
    with ThreadPoolExecutor(max_workers=3 if a.ai else 5) as ex:
        for i, (code, v) in enumerate(ex.map(one, top), 1):
            details[code] = v
            if i % 20 == 0:
                print(f"      {i}/{len(top)}")

    os.makedirs(PRIV, exist_ok=True)
    p = os.path.join(PRIV, "detail_us.json")
    json.dump({"ts": d["ts"], "market": "US", "details": details},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(p) / 1024
    print(f"\n 완료 → web/priv/detail_us.json  ({kb:,.0f} KB, {len(details)}종목)")
    if a.ai and key:
        print(f"   AI 판독 성공 {stat['ok']} · 근거부족 {stat['no']} · 오류 {stat['err']}")


if __name__ == "__main__":
    main()
