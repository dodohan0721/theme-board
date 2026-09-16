# -*- coding: utf-8 -*-
"""
해외(미국) 테마 수집 — server.py 의 KIS 계층을 그대로 재사용한다.

  · 토큰 · 레이트리밋 · HTTP 는 server.py 것을 쓴다 (중복 구현 안 함)
  · 업종 분류는 한국투자증권이 직접 준다 (해외주식-048 / 049)
  · 거래대금은 해외 업종API가 안 주므로 현재가 × 거래량 으로 계산한다
  · 미국은 실시간 무료(0분 지연). 아시아만 15분 지연.

사용하는 API
  해외주식-049  업종별코드조회   HHDFS76370100   /uapi/overseas-price/v1/quotations/industry-price
  해외주식-048  업종별시세       HHDFS76370000   /uapi/overseas-price/v1/quotations/industry-theme
  해외주식-041  상승률/하락률    HHDFS76290000   /uapi/overseas-stock/v1/ranking/updown-rate
  해외주식-039  거래량급증       HHDFS76270000   /uapi/overseas-stock/v1/ranking/volume-surge
"""
import os, re, json, time, threading
from datetime import datetime, timezone, timedelta
import server as S            # 토큰 · RATE · kis_get · CACHE · need 재사용

# ── 거래소 ────────────────────────────────────────────────────────────────
EXCD = {"NAS": "나스닥", "NYS": "뉴욕", "AMS": "아멕스"}

# 거래량조건 0:전체 1:1백주↑ 2:1천주↑ 3:1만주↑ 4:10만주↑ 5:100만주↑
VOL_RANG = os.environ.get("US_VOL_RANG", "0")   # 0:전체 — 필터를 걸면 종목이 크게 줄어든다

_ind_lock = threading.Lock()


def _rows(r, *keys):
    """KIS 응답에서 output1/output2 중 list 인 것을 꺼낸다."""
    out = []
    for k in (keys or ("output2", "output1", "output")):
        v = r.get(k)
        if isinstance(v, list):
            out = v
            if out:
                return out
    return out


def _f(x, d=0.0):
    try:
        return float(str(x).replace(",", "").strip() or 0)
    except Exception:
        return d


def _i(x, d=0):
    try:
        return int(_f(x, d))
    except Exception:
        return d


# ══════════════════════════════════════════════════════════════════════════
# 업종
# ══════════════════════════════════════════════════════════════════════════
def industry_codes(excd):
    """거래소의 업종 코드 목록 → [{'icod':..., 'name':...}, ...]  (파일 캐시 1일)"""
    p = os.path.join(S.CACHE, f"us_ind_{excd}.json")
    with _ind_lock:
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 86400:
            try:
                return json.load(open(p, encoding="utf-8"))
            except Exception:
                pass
    r = S.kis_get("/uapi/overseas-price/v1/quotations/industry-price",
                  "HHDFS76370100", {"EXCD": excd, "AUTH": ""})
    out = []
    for x in _rows(r, "output1", "output2"):
        if not isinstance(x, dict):
            continue
        # 필드명이 문서마다 다를 수 있어 방어적으로 찾는다
        icod = next((str(x[k]).strip() for k in x
                     if re.search(r"(icod|icode|code|cod)$", k, re.I) and str(x[k]).strip()), "")
        name = next((str(x[k]).strip() for k in x
                     if re.search(r"(name|nam|knam|ename)$", k, re.I) and str(x[k]).strip()), "")
        if icod and name:
            out.append({"icod": icod, "name": name})
    if out:
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def industry_stocks(excd, icod, vol_rang=None):
    """업종 구성종목 + 시세 → [{code,name,price,rate,volume,value}, ...]"""
    r = S.kis_get("/uapi/overseas-price/v1/quotations/industry-theme",
                  "HHDFS76370000",
                  {"EXCD": excd, "ICOD": icod,
                   "VOL_RANG": vol_rang or VOL_RANG, "AUTH": "", "KEYB": ""})
    out = []
    for x in _rows(r, "output2", "output1"):
        if not isinstance(x, dict):
            continue
        sym = str(x.get("symb", "")).strip().upper()
        if not sym:
            continue
        last, vol = _f(x.get("last")), _i(x.get("tvol"))
        out.append({
            "code": sym,
            "name": (x.get("name") or x.get("ename") or sym).strip(),
            "ename": (x.get("ename") or "").strip(),
            "price": last,
            "diff": _f(x.get("diff")),
            "rate": _f(x.get("rate")),
            "volume": vol,
            # 해외 업종API 는 거래대금을 안 준다 → 현재가 × 거래량 (단위: 백만달러)
            "value": round(last * vol / 1_000_000, 1),
            "excd": excd,
        })
    return out


# ══════════════════════════════════════════════════════════════════════════
# 순위 (거래대금 tamt 를 여기서 보강한다)
# ══════════════════════════════════════════════════════════════════════════
def updown_rate(excd, gubn="1", nday="0", vol_rang=None):
    """gubn 1:상승률 0:하락률"""
    r = S.kis_get("/uapi/overseas-stock/v1/ranking/updown-rate", "HHDFS76290000",
                  {"EXCD": excd, "NDAY": nday, "GUBN": gubn,
                   "VOL_RANG": vol_rang or VOL_RANG, "AUTH": "", "KEYB": ""})
    return [{"code": str(x.get("symb", "")).strip().upper(),
             "rate": _f(x.get("rate")),
             "tamt": _f(x.get("tamt"))}
            for x in _rows(r, "output2", "output1") if isinstance(x, dict) and x.get("symb")]


def volume_surge(excd, minx="8", vol_rang=None):
    """minx 8:60분전 9:120분전"""
    r = S.kis_get("/uapi/overseas-stock/v1/ranking/volume-surge", "HHDFS76270000",
                  {"EXCD": excd, "MINX": minx,
                   "VOL_RANG": vol_rang or VOL_RANG, "AUTH": "", "KEYB": ""})
    return [{"code": str(x.get("symb", "")).strip().upper(),
             "tamt": _f(x.get("tamt")),
             "surge": _f(x.get("n_rate"))}
            for x in _rows(r, "output2", "output1") if isinstance(x, dict) and x.get("symb")]


# ══════════════════════════════════════════════════════════════════════════
# 뉴스 (해외주식-053  HHPSTH60100C1)
# ══════════════════════════════════════════════════════════════════════════
_NEWS_TTL = 900  # 15분 캐시


def news(symb="", excd="", n=8):
    """해외뉴스 제목. symb 를 주면 그 종목, 비우면 전체 시황.
       KIS 는 제목만 주고 본문 링크는 주지 않는다."""
    key = f"us_news_{(symb or 'ALL')}_{excd or 'X'}"
    p = os.path.join(S.CACHE, key + ".json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < _NEWS_TTL:
        try:
            return json.load(open(p, encoding="utf-8"))[:n]
        except Exception:
            pass
    try:
        r = S.kis_get("/uapi/overseas-price/v1/quotations/news-title", "HHPSTH60100C1", {
            "INFO_GB": "", "CLASS_CD": "", "NATION_CD": "US",
            "EXCHANGE_CD": excd or "", "SYMB": symb or "",
            "DATA_DT": "", "DATA_TM": "", "CTS": ""})
    except Exception:
        return []
    out = []
    for x in _rows(r, "outblock1", "output", "output1", "output2"):
        if not isinstance(x, dict):
            continue
        t = (x.get("title") or "").strip()
        if not t:
            continue
        dt, tm = str(x.get("data_dt", "")), str(x.get("data_tm", ""))
        when = ""
        if len(dt) == 8:
            when = f"{dt[4:6]}-{dt[6:8]}" + (f" {tm[:2]}:{tm[2:4]}" if len(tm) >= 4 else "")
        out.append({
            "title": t,
            "time": when,
            "source": (x.get("source") or "").strip(),
            "symb": (x.get("symb") or "").strip().upper(),
            "symb_name": (x.get("symb_name") or "").strip(),
            "url": "",                       # KIS 는 원문 링크를 주지 않음
            "cat": (x.get("class_name") or "").strip(),
        })
    if out:
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return out[:n]


# ══════════════════════════════════════════════════════════════════════════
# ETF 기반 테마 (선택) — themes_us.json 에 stocks 가 채워져 있으면 함께 낸다
# ══════════════════════════════════════════════════════════════════════════
def etf_themes():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes_us.json")
    if not os.path.exists(p):
        return []
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for t in d.get("themes", []):
        st = [s.strip().upper() for s in (t.get("stocks") or []) if s and s.strip()]
        if st:
            out.append({"id": t.get("id") or t.get("etf", "").lower(),
                        "name": t.get("name", ""), "cat": t.get("cat", "ETF"),
                        "stocks": st})
    return out


# ══════════════════════════════════════════════════════════════════════════
# 조립
# ══════════════════════════════════════════════════════════════════════════
def build(excds=("NAS", "NYS", "AMS"), min_value=5.0, verbose=True):
    """국내판 data.json 과 같은 스키마로 돌려준다.
       min_value: 테마 표시 최소 거래대금(백만달러)"""
    stocks, themes = {}, []
    tamt = {}   # 순위 API 에서 얻은 실제 거래대금

    for ex in excds:
        # 1) 거래대금 보강용 순위 먼저
        for fn, arg in ((updown_rate, "1"), (updown_rate, "0")):
            try:
                for x in fn(ex, arg):
                    if x["tamt"]:
                        tamt[x["code"]] = x["tamt"] / 1_000_000
            except Exception as e:
                if verbose:
                    print(f"  [경고] {ex} 등락률순위: {e}")
        try:
            for x in volume_surge(ex):
                if x["tamt"]:
                    tamt[x["code"]] = x["tamt"] / 1_000_000
        except Exception as e:
            if verbose:
                print(f"  [경고] {ex} 거래량급증: {e}")

        # 2) 업종별로 구성종목 수집
        inds = industry_codes(ex)
        if verbose:
            print(f"  [{EXCD.get(ex, ex)}] 업종 {len(inds)}개")
        for ind in inds:
            if ind['icod'] in ('000', '0'):   # '전체' 는 업종이 아니라 집계
                continue
            try:
                rows = industry_stocks(ex, ind["icod"])
            except Exception as e:
                if verbose:
                    print(f"    [건너뜀] {ind['name']}: {e}")
                continue
            if not rows:
                continue
            codes = []
            for s in rows:
                c = s["code"]
                if c in tamt:
                    s["value"] = round(tamt[c], 1)
                prev = stocks.get(c)
                if prev:
                    prev.setdefault("themes", [])
                else:
                    s["themes"] = []
                    stocks[c] = s
                codes.append(c)

            tid = f"{ex.lower()}-{ind['icod']}"
            for c in codes:
                if tid not in stocks[c]["themes"]:
                    stocks[c]["themes"].append(tid)

            sel = [stocks[c] for c in codes]
            val = round(sum(x["value"] for x in sel), 1)
            up = sum(1 for x in sel if x["rate"] > 0)
            wsum = sum(x["value"] for x in sel) or 1
            themes.append({
                "id": tid,
                "name": f"{ind['name']}",
                "cat": EXCD.get(ex, ex),
                "pct": round(sum(x["rate"] * x["value"] for x in sel) / wsum, 2),
                "pct_eq": round(sum(x["rate"] for x in sel) / len(sel), 2),
                "value": val, "up": up, "n": len(sel), "total": len(sel),
                "codes": [x["code"] for x in sorted(sel, key=lambda z: -z["value"])],
            })

    # 3) ETF 테마 (있을 때만)
    for t in etf_themes():
        sel = [stocks[c] for c in t["stocks"] if c in stocks]
        if len(sel) < 3:
            continue
        wsum = sum(x["value"] for x in sel) or 1
        themes.append({
            "id": t["id"], "name": t["name"], "cat": t["cat"],
            "pct": round(sum(x["rate"] * x["value"] for x in sel) / wsum, 2),
            "pct_eq": round(sum(x["rate"] for x in sel) / len(sel), 2),
            "value": round(sum(x["value"] for x in sel), 1),
            "up": sum(1 for x in sel if x["rate"] > 0),
            "n": len(sel), "total": len(t["stocks"]),
            "codes": [x["code"] for x in sorted(sel, key=lambda z: -z["value"])],
        })
        for x in sel:
            if t["id"] not in x["themes"]:
                x["themes"].append(t["id"])

    total_themes = len(themes)
    themes = [t for t in themes if t["value"] >= min_value]
    themes.sort(key=lambda t: -t["value"])
    ranking = [c for c, _ in sorted(stocks.items(), key=lambda kv: -kv[1]["value"])]

    return {
        "ts": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Seoul",
        "themes": themes,
        "stocks": stocks,
        "ranking": ranking,
        "universe": len(stocks),
        "scanned": len(stocks),
        "theme_total": total_themes,
        "market": "US",
        "unit": "백만달러",
    }


if __name__ == "__main__":
    d = build()
    print(f"\n테마 {len(d['themes'])}개 / 종목 {len(d['stocks'])}개")
    for t in d["themes"][:10]:
        print(f"  {t['name']:24s} {t['value']:>10,.0f}M  {t['pct']:+.2f}%  ({t['up']}/{t['n']})")
