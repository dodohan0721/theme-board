#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
급등 사유 판독기 — 기사 본문을 실제로 읽고 AI가 판단합니다.
──────────────────────────────────────────────────────────────────────────────
기존 방식: 뉴스 '제목'에 계약·수주 같은 키워드가 있으면 골라 붙임 (읽지 않음)
이 방식  : 기사 URL 을 열어 '본문'을 가져온 뒤, Claude 가 읽고
           "이 종목이 오른 사유가 맞는지" 판단해 근거 문장을 인용

    python3 ai_reason.py --test 042700     # 종목 하나로 시험
    (export_snapshot.py --ai 로 자동 사용)

원칙
  · 기사 본문은 판단에만 쓰고 저장하지 않습니다 (제목·링크만 보관)
  · 사실 서술만 출력합니다. 전망·추천·목표가 표현은 차단합니다
  · 근거가 없으면 지어내지 않고 "확인되지 않음"으로 고정 출력합니다
"""
import json, os, re, ssl, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
_ctx = ssl.create_default_context()
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ── 출력에서 차단할 표현 (투자 권유로 읽힐 수 있는 말) ──────────────────────
BANNED = ["매수", "매도", "목표가", "목표주가", "유망", "추천", "전망",
          "기대된다", "예상된다", "저평가", "고평가", "수혜가 예상", "상승할",
          "오를 것", "사야", "팔아야", "비중 확대", "비중 축소"]


# ══════════════════════════════════════════════════════════════════════════
# 1) 기사 본문 가져오기
# ══════════════════════════════════════════════════════════════════════════
_DROP = re.compile(r"<(script|style|noscript|iframe|header|footer|nav|aside)[^>]*>.*?</\1>",
                   re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n{3,}")

# 한국 언론사 CMS 본문 컨테이너 패턴 (앞쪽일수록 우선)
_BODY_PATS = (
    # 네이버 뉴스
    r'<article[^>]*id="dic_area"[^>]*>(.*?)</article>',
    r'<div[^>]*id="dic_area"[^>]*>(.*?)</div>',
    r'<div[^>]*id="articleBodyContents"[^>]*>(.*?)</div>',
    # 이지엔소프트 CMS — articleView.html?idxno= 를 쓰는 국내 수백 개 매체 공통
    r'<(?:div|article)[^>]*id="article-view-content-div"[^>]*>(.*?)</(?:div|article)>',
    r'<(?:div|article)[^>]*itemprop="articleBody"[^>]*>(.*?)</(?:div|article)>',
    r'<div[^>]*class="[^"]*article[-_]?ve?i?ew[-_]?body[^"]*"[^>]*>(.*?)</div>',
    # 기타 흔한 형태
    r'<div[^>]*id="articleBody"[^>]*>(.*?)</div>',
    r'<div[^>]*class="[^"]*(?:article|news)[-_]?(?:body|content|view|text)[^"]*"[^>]*>(.*?)</div>',
    r'<div[^>]*id="newsEndContents"[^>]*>(.*?)</div>',
    r'<article[^>]*>(.*?)</article>',
)

LAST_ERROR = {}          # url -> 실패 사유 (진단용)

def _decompress(raw, enc):
    if not enc:
        return raw
    try:
        if "gzip" in enc:
            import gzip; return gzip.decompress(raw)
        if "deflate" in enc:
            import zlib
            try: return zlib.decompress(raw)
            except zlib.error: return zlib.decompress(raw, -zlib.MAX_WBITS)
        if "br" in enc:
            import brotli; return brotli.decompress(raw)
    except Exception:
        pass
    return raw

def fetch_article(url, timeout=10, limit=2500):
    """기사 URL → 본문 텍스트. 실패하면 None (사유는 LAST_ERROR 에 기록)."""
    host = (re.search(r"https?://([^/]+)", url) or [None, ""])[1]
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": f"https://{host}/",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
            raw = _decompress(r.read(600_000), (r.headers.get("Content-Encoding") or "").lower())
            enc = (r.headers.get_content_charset() or "").lower()
    except urllib.error.HTTPError as e:
        LAST_ERROR[url] = f"HTTP {e.code}"
        return None
    except Exception as e:
        LAST_ERROR[url] = type(e).__name__
        return None

    html = None
    for e in ([enc] if enc else []) + ["utf-8", "euc-kr", "cp949"]:
        try:
            html = raw.decode(e); break
        except Exception:
            continue
    if html is None:
        html = raw.decode("utf-8", "ignore")

    # <meta charset> 로 재판정 (헤더가 거짓말하는 사이트 대비)
    mm = re.search(r'charset=["\']?\s*([\w\-]+)', html[:2000], re.I)
    if mm and mm.group(1).lower() not in ("utf-8", "utf8") and "\ufffd" in html[:3000]:
        try: html = raw.decode(mm.group(1))
        except Exception: pass

    body = None
    for pat in _BODY_PATS:
        m = re.search(pat, html, re.S | re.I)
        if m and len(m.group(1)) > 300:
            body = m.group(1); break
    used_fallback = body is None
    if used_fallback:
        body = html

    txt = _DROP.sub(" ", body)
    txt = re.sub(r"<br\s*/?>|</p>|</div>", "\n", txt, flags=re.I)
    txt = _TAG.sub(" ", txt)
    txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
              .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
              .replace("&apos;", "'").replace("&middot;", "·"))
    txt = _NL.sub("\n\n", _WS.sub(" ", txt)).strip()
    txt = re.split(r"(저작권자|무단전재|ⓒ|Copyright|기자 [\w.]+@|<!--)", txt)[0].strip()

    if len(txt) < 150:
        LAST_ERROR[url] = f"본문 짧음({len(txt)}자)"
        return None
    if used_fallback:
        LAST_ERROR[url] = "본문영역 못찾음(페이지 전체 사용)"
    return txt[:limit]


# ══════════════════════════════════════════════════════════════════════════
# 1-b) 종목 뉴스 수집 — 검색어를 여러 개 던지고 제목으로 걸러낸다
# ══════════════════════════════════════════════════════════════════════════
def _norm_name(s):
    return re.sub(r"[\s·\-\.'\"]", "", s or "")

# 종목명이 없는데 자주 딸려오는 시황·나열형 기사 제목 패턴
_JUNK = re.compile(r"(주요공시|변동 현황|급등주|특징주 총정리|시황|마감시황|개장|"
                   r"코스피 마감|코스닥 마감|주간 증시|장중 특징)")

def stock_news(S, name, want=5):
    """S = server 모듈. 여러 검색어로 모아 제목에 종목명이 있는 기사만 남긴다."""
    queries = [f'"{name}"', f"{name} 공시", f"{name} 계약 수주"]
    seen, pool = set(), []
    for q in queries:
        try:
            for it in S.naver_news(q, 10):
                u = it.get("url")
                if not u or u in seen:
                    continue
                seen.add(u)
                pool.append(it)
        except Exception:
            continue
        if len([p for p in pool if _norm_name(name) in _norm_name(p["title"])]) >= want:
            break

    keep = [p for p in pool
            if _norm_name(name) in _norm_name(p["title"]) and not _JUNK.search(p["title"])]
    keep.sort(key=lambda x: -x.get("ts", 0))
    dropped = len(pool) - len(keep)
    return keep[:want], dropped

# ══════════════════════════════════════════════════════════════════════════
# 2) Claude API
# ══════════════════════════════════════════════════════════════════════════
_model_cache = [None]
MODEL_OVERRIDE = [None]   # export_snapshot 이 config.py 의 ANTHROPIC_MODEL 을 넣어줌

def pick_model(key, override=None):
    """사용 가능한 모델 중 가장 저렴한 haiku 계열을 자동 선택.
       config.py 에 ANTHROPIC_MODEL 을 넣으면 그 값을 씁니다."""
    if override:
        _model_cache[0] = override
    if _model_cache[0]:
        return _model_cache[0]
    try:
        req = urllib.request.Request("https://api.anthropic.com/v1/models?limit=100",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            models = [m["id"] for m in json.loads(r.read())["data"]]
    except Exception as e:
        print(f"  [AI] 모델 목록 조회 실패({e}) → 기본값 사용")
        _model_cache[0] = "claude-haiku-4-5-20251001"
        return _model_cache[0]
    for kw in ("haiku", "sonnet"):
        hit = [m for m in models if kw in m]
        if hit:
            _model_cache[0] = sorted(hit)[-1]
            print(f"  [AI] 모델: {_model_cache[0]}")
            return _model_cache[0]
    _model_cache[0] = models[0]
    return _model_cache[0]


SYSTEM = """당신은 한국 주식 시장의 사실 정리 도구입니다. 아래 규칙을 반드시 지킵니다.

1. 제공된 기사 본문 안에 실제로 적힌 내용만 서술합니다. 본문에 없는 내용은 절대 쓰지 않습니다.
2. 각 근거에는 참고한 기사 번호(ref)를 반드시 표기합니다.
3. 다음 표현을 사용하지 않습니다: 매수, 매도, 목표가, 유망, 추천, 전망, 기대된다,
   예상된다, 저평가, 고평가, 오를 것, 사야 한다.
4. 과거·현재의 사실만 서술합니다. 미래 예측이나 투자 판단은 출력하지 않습니다.
5. 기사들이 이 종목의 주가 움직임과 직접 관련이 없으면, 억지로 사유를 만들지 말고
   relevant를 false로 반환합니다.
6. 한국어로, 각 근거는 한 문장(60자 이내)으로 씁니다."""

USER_TMPL = """종목: {name} ({code})
오늘 등락률: {rate:+.2f}%
{theme_line}
아래는 이 종목과 관련해 수집된 기사 본문입니다.

{articles}

이 기사들을 읽고 다음 JSON만 출력하세요(설명 없이 JSON만):
{{
  "relevant": true 또는 false,
  "headline": "이 종목이 오늘 움직인 사유를 40자 이내 한 문장으로. relevant=false면 빈 문자열",
  "reasons": [
    {{"text": "기사 본문에 근거한 사실 문장", "ref": 기사번호}}
  ],
  "confidence": "high" | "medium" | "low"
}}
- reasons는 최대 3개입니다.
- 공시·계약·실적처럼 구체적 사실이 있으면 high, 업종 전반 언급 수준이면 medium,
  간접적이면 low 입니다."""


def call_claude(key, model, system, user, max_tokens=700):
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60, context=_ctx) as r:
        d = json.loads(r.read())
    return "".join(b.get("text", "") for b in d.get("content", []))


# ══════════════════════════════════════════════════════════════════════════
# 3) 검증 게이트
# ══════════════════════════════════════════════════════════════════════════
def gate(result, articles):
    """금지 표현·근거 유효성 검사. 통과 못한 항목은 버린다."""
    if not isinstance(result, dict) or not result.get("relevant"):
        return None
    head = (result.get("headline") or "").strip()
    if any(b in head for b in BANNED):
        return None
    ok = []
    for r in result.get("reasons", [])[:3]:
        t = (r.get("text") or "").strip()
        ref = r.get("ref")
        if not t or any(b in t for b in BANNED):
            continue
        if not isinstance(ref, int) or not (1 <= ref <= len(articles)):
            continue
        ok.append({"text": t, "ref": ref})
    if not ok or not head:
        return None
    return {"headline": head, "reasons": ok,
            "confidence": result.get("confidence", "medium")}


# ══════════════════════════════════════════════════════════════════════════
# 4) 메인 진입점
# ══════════════════════════════════════════════════════════════════════════
def analyze(key, name, code, rate, news, theme_context=None, max_articles=3):
    """news: [{title,url,time}] → 본문을 읽고 판단한 결과 dict 또는 None"""
    if not news:
        return None
    cands = news[:max_articles + 3]

    def grab(n):
        # 네이버 뉴스 미러가 있으면 먼저 시도 (차단이 적고 구조가 일정함)
        for u in ([n["nurl"]] if n.get("nurl") and n["nurl"] != n["url"] else []) + [n["url"]]:
            b = fetch_article(u)
            if b:
                return b
        return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        bodies = list(ex.map(grab, cands))

    arts, used = [], []
    for n, b in zip(cands, bodies):
        if not b:
            continue
        used.append(n)
        arts.append(f"[기사 {len(used)}] {n.get('time','')} · {n['title']}\n{b}")
        if len(used) >= max_articles:
            break
    if not arts:
        return None

    model = pick_model(key, MODEL_OVERRIDE[0])
    theme_line = f"소속 테마 상황: {theme_context}" if theme_context else ""
    user = USER_TMPL.format(name=name, code=code, rate=rate,
                            theme_line=theme_line, articles="\n\n".join(arts))
    for attempt in (1, 2):
        try:
            raw = call_claude(key, model, SYSTEM, user)
        except urllib.error.HTTPError as e:
            print(f"  [AI] HTTP {e.code}: {e.read().decode('utf-8','ignore')[:160]}")
            return None
        except Exception as e:
            print(f"  [AI] 호출 실패: {e}")
            return None
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            continue
        try:
            res = gate(json.loads(m.group(0)), used)
        except Exception:
            res = None
        if res:
            res["evidences"] = [{"title": used[r["ref"] - 1]["title"],
                                 "url": used[r["ref"] - 1]["url"],
                                 "time": used[r["ref"] - 1].get("time", ""),
                                 "text": r["text"]} for r in res["reasons"]]
            res["read"] = len(used)
            return res
    return None


# ── 단독 실행 테스트 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import importlib.util, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="042700", help="종목코드")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("srv", os.path.join(HERE, "server.py"))
    S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
    key = S.CFG.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("config.py 에 ANTHROPIC_API_KEY 가 없습니다.")

    d = S.kis_price(a.test)
    name = None
    for t in S.THEMES:
        for nm in t["stocks"]:
            ent = S.kis_master().get(nm)
            if ent and ent[0] == a.test:
                name = nm; break
        if name: break
    name = name or a.test
    print(f"종목 {name}({a.test})  {d['rate']:+.2f}%  {d['price']:,}원\n")

    news, dropped = stock_news(S, name)
    print(f"수집된 기사 {len(news)}건" + (f"  (관련 없는 기사 {dropped}건 걸러냄)" if dropped else ""))
    for n in news:
        print(f"  · {n['time']}  {n['title'][:50]}")
    if not news:
        print("\n  이 종목 이름이 제목에 들어간 기사를 찾지 못했습니다.")
        sys.exit(0)

    print("\n본문을 읽는 중 …")
    bodies = {}
    for n in news:
        b = None
        for u in ([n["nurl"]] if n.get("nurl") and n["nurl"] != n["url"] else []) + [n["url"]]:
            b = fetch_article(u)
            if b:
                break
        host = re.sub(r"^www\.", "", (re.search(r"https?://([^/]+)", n["url"]) or [None,"?"])[1])
        bodies[n["url"]] = b
        why = "" if b else f"  ← {LAST_ERROR.get(n['url'], '알 수 없음')}"
        print(f"  {'✅' if b else '❌'} {host:<22} {len(b) if b else 0:>5}자  {n['title'][:26]}{why}")
    ok_n = sum(1 for b in bodies.values() if b)
    print(f"  → {ok_n}/{len(news)}건 본문 확보")

    print("\nAI 판독 중 …")
    r = analyze(key, name, a.test, d["rate"], news)
    print("\n" + "=" * 70)
    if r:
        print(f" 한 줄 요약: {r['headline']}")
        print(f" 읽은 기사: {r['read']}건 · 신뢰도: {r['confidence']}")
        for i, e in enumerate(r["evidences"], 1):
            print(f"\n  {i}. {e['text']}")
            print(f"     └ {e['time']} {e['title'][:44]}")
            print(f"       {e['url'][:70]}")
    else:
        print(" 판단 결과: 이 종목의 상승과 직접 관련된 기사를 확인하지 못했습니다.")
        print(" (사유를 임의로 생성하지 않습니다)")
    print("=" * 70)

    # 결과를 파일로 남겨 나중에 확인할 수 있게 한다
    log = {"code": a.test, "name": name, "rate": d["rate"], "price": d["price"],
           "news": news, "dropped": dropped,
           "body_ok": {u: (len(b) if b else 0) for u, b in bodies.items()},
           "result": r}
    lp = os.path.join(S.CACHE, "last_ai_test.json")
    json.dump(log, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n 결과 저장: .cache/last_ai_test.json")
