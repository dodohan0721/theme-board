#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 로컬 서버
──────────────────────────────────────────────────────────────────────────────
한국투자증권 OpenAPI(시세·순위) + DART(재무) + 네이버 뉴스 API를 실제로 호출해
테마 단위로 묶은 대시보드를 http://127.0.0.1:8899 에 띄웁니다.

사용법
    python3 server.py                # 서버 실행
    python3 server.py --selftest     # API 4종 연결만 점검하고 종료
    python3 server.py --port 9000    # 포트 변경

의존성: 표준 라이브러리만 사용합니다 (pip install 불필요).

키는 같은 폴더 또는 상위 폴더의 config.py / .env 에서 읽습니다.
이 스크립트는 키를 어디에도 복사·전송하지 않습니다.
"""
import argparse, json, os, re, ssl, sys, time, threading, zipfile, io
import urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
os.makedirs(CACHE, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════
# 설정 로딩
# ══════════════════════════════════════════════════════════════════════════
def load_config():
    """config.py / .env 를 정규식으로 읽는다 (import 하지 않음 → 문법오류 무관)."""
    cands = []
    for d in (HERE, os.path.dirname(HERE), os.path.expanduser("~/Desktop"),
              os.path.expanduser("~/Desktop/kospi_bot"), os.getcwd()):
        for fn in ("config.py", ".env"):
            cands.append(os.path.join(d, fn))
    cfg = {}
    found = []
    for p in cands:
        if not os.path.exists(p):
            continue
        found.append(p)
        try:
            raw = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for m in re.finditer(r'^\s*([A-Z][A-Z0-9_]+)\s*[:=]\s*["\']?([^"\'\n#]+)["\']?',
                             raw, re.M):
            k, v = m.group(1), m.group(2).strip()
            if k not in cfg and v:
                cfg[k] = v
    # 환경변수가 있으면 우선한다 (GitHub Secrets / Vercel 환경변수 / CI 대응)
    env_hit = []
    for k in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ENV", "ACCOUNT",
              "DART_API_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET",
              "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"):
        v = os.environ.get(k)
        if v:
            cfg[k] = v.strip()
            env_hit.append(k)
    cfg["_files"] = found
    cfg["_env"] = env_hit
    return cfg

CFG = load_config()

def need(k):
    v = CFG.get(k)
    if not v:
        sys.exit(f"[설정오류] {k} 를 찾지 못했습니다.\n"
                 f"  확인한 파일: {CFG.get('_files') or '(없음)'}\n"
                 f"  config.py 를 이 스크립트와 같은 폴더에 두세요.")
    return v

IS_REAL = (CFG.get("KIS_ENV", "real").lower() != "vps")
KIS_HOST = "https://openapi.koreainvestment.com:9443" if IS_REAL \
      else "https://openapivts.koreainvestment.com:29443"

# ══════════════════════════════════════════════════════════════════════════
# HTTP 유틸
# ══════════════════════════════════════════════════════════════════════════
_ctx = ssl.create_default_context()

def http(url, method="GET", headers=None, body=None, timeout=20):
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("content-type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"HTTP {e.code} {url.split('?')[0]}\n    → {detail}")
    except Exception as e:
        raise RuntimeError(f"{type(e).__name__}: {e}  ({url.split('?')[0]})")

# ══════════════════════════════════════════════════════════════════════════
# KIS 토큰 (24시간 유효 · 파일 캐시. 1분에 1회만 발급 가능하므로 반드시 캐시)
# ══════════════════════════════════════════════════════════════════════════
_tok_lock = threading.Lock()

def kis_token():
    p = os.path.join(CACHE, "kis_token.json")
    with _tok_lock:
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                if d.get("expire", 0) > time.time() + 600:
                    return d["token"]
            except Exception:
                pass
        r = http(f"{KIS_HOST}/oauth2/tokenP", "POST", body={
            "grant_type": "client_credentials",
            "appkey": need("KIS_APP_KEY"),
            "appsecret": need("KIS_APP_SECRET")})
        if "access_token" not in r:
            raise RuntimeError(f"토큰 발급 실패: {r}")
        d = {"token": r["access_token"], "expire": time.time() + int(r.get("expires_in", 86400))}
        json.dump(d, open(p, "w"))
        print(f"  [KIS] 새 토큰 발급 (유효 {int(r.get('expires_in',86400))/3600:.0f}시간)")
        return d["token"]

class _Rate:
    """KIS 초당 20건 제한 → 전역 토큰버킷(초당 16건)으로 통제."""
    def __init__(self, per_sec=16):
        self.gap = 1.0 / per_sec
        self.lock = threading.Lock()
        self.last = 0.0
    def wait(self):
        with self.lock:
            now = time.time()
            nxt = max(now, self.last + self.gap)
            self.last = nxt
        d = nxt - now
        if d > 0:
            time.sleep(d)

RATE = _Rate(16)

def kis_get(path, tr_id, params):
    h = {"authorization": f"Bearer {kis_token()}",
         "appkey": need("KIS_APP_KEY"), "appsecret": need("KIS_APP_SECRET"),
         "tr_id": tr_id, "custtype": "P"}
    RATE.wait()
    return http(f"{KIS_HOST}{path}?{urllib.parse.urlencode(params)}", headers=h)

# ── 순위: 거래대금 상위 ────────────────────────────────────────────────────
def kis_volume_rank(market="0000", blng="3"):
    """FID_BLNG_CLS_CODE  0:평균거래량 1:거래증가율 2:평균거래회전율 3:거래금액순 4:거래금액회전율
       FID_INPUT_ISCD     0000:전체 0001:코스피 1001:코스닥"""
    r = kis_get("/uapi/domestic-stock/v1/quotations/volume-rank", "FHPST01710", {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": market, "FID_DIV_CLS_CODE": "0",
        "FID_BLNG_CLS_CODE": blng,
        "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "0000000000",
        "FID_INPUT_PRICE_1": "", "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""})
    if r.get("rt_cd") != "0":
        raise RuntimeError(f"순위조회 실패 rt_cd={r.get('rt_cd')} {r.get('msg1')}")
    out = []
    for x in r.get("output", []):
        try:
            out.append({
                "code": x.get("mksc_shrn_iscd", "").strip(),
                "name": x.get("hts_kor_isnm", "").strip(),
                "price": int(float(x.get("stck_prpr", 0) or 0)),
                "diff": int(float(x.get("prdy_vrss", 0) or 0)),
                "rate": float(x.get("prdy_ctrt", 0) or 0),
                "volume": int(float(x.get("acml_vol", 0) or 0)),
                # acml_tr_pbmn 단위는 원 → 억원 변환
                "value": round(float(x.get("acml_tr_pbmn", 0) or 0) / 1e8),
                "rank": int(float(x.get("data_rank", 0) or 0)),
            })
        except Exception:
            continue
    return out

# ── 순위: 등락률 상위 ──────────────────────────────────────────────────────
def kis_fluct_rank(market="0000", updown="0"):
    """updown 0:상승률 1:하락률"""
    r = kis_get("/uapi/domestic-stock/v1/ranking/fluctuation", "FHPST01700", {
        "fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20170",
        "fid_input_iscd": market, "fid_rank_sort_cls_code": updown,
        "fid_input_cnt_1": "0", "fid_prc_cls_code": "0",
        "fid_input_price_1": "", "fid_input_price_2": "",
        "fid_vol_cnt": "", "fid_trgt_cls_code": "0",
        "fid_trgt_exls_cls_code": "0", "fid_div_cls_code": "0",
        "fid_rsfl_rate1": "", "fid_rsfl_rate2": ""})
    if r.get("rt_cd") != "0":
        raise RuntimeError(f"등락률순위 실패 {r.get('msg1')}")
    out = []
    for x in r.get("output", []):
        out.append({"code": x.get("stck_shrn_iscd", "").strip(),
                    "name": x.get("hts_kor_isnm", "").strip(),
                    "price": int(float(x.get("stck_prpr", 0) or 0)),
                    "rate": float(x.get("prdy_ctrt", 0) or 0)})
    return out

# ── 개별 종목 현재가 (시총·PER 등 포함) ───────────────────────────────────
_price_cache = {}
def kis_price(code):
    hit = _price_cache.get(code)
    if hit and time.time() - hit[0] < 45:
        return hit[1]
    r = kis_get("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
    o = r.get("output") or {}
    d = {
        "code": code, "name": o.get("bstp_kor_isnm", ""),
        "price": int(float(o.get("stck_prpr", 0) or 0)),
        "diff": int(float(o.get("prdy_vrss", 0) or 0)),
        "rate": float(o.get("prdy_ctrt", 0) or 0),
        "volume": int(float(o.get("acml_vol", 0) or 0)),
        "value": round(float(o.get("acml_tr_pbmn", 0) or 0) / 1e8),
        "cap": round(float(o.get("hts_avls", 0) or 0)),          # 억원
        "per": _f(o.get("per")), "pbr": _f(o.get("pbr")),
        "eps": _f(o.get("eps")), "bps": _f(o.get("bps")),
        "high52": _f(o.get("w52_hgpr")), "low52": _f(o.get("w52_lwpr")),
        "market": o.get("rprs_mrkt_kor_name", ""),
        "upper": o.get("stck_mxpr"), "lower": o.get("stck_llam"),
    }
    _price_cache[code] = (time.time(), d)
    return d

def _f(v):
    try:
        f = float(v)
        return f if f else None
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════
# KIS 종목마스터 — 종목명 → 종목코드 (순위 API 실패 시 폴백에 사용)
# ══════════════════════════════════════════════════════════════════════════
MST = {"kospi": ("https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip", 228),
       "kosdaq": ("https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip", 222)}

def kis_master():
    """{종목명: (코드, 시장)}. 마스터 파일 다운로드 후 7일 캐시."""
    p = os.path.join(CACHE, "name2code.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        return json.load(open(p, encoding="utf-8"))
    out = {}
    for mkt, (url, tail) in MST.items():
        try:
            with urllib.request.urlopen(url, timeout=60, context=_ctx) as r:
                blob = r.read()
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                txt = z.read(z.namelist()[0]).decode("cp949", "ignore")
            for row in txt.splitlines():
                if len(row) < tail + 22:
                    continue
                head = row[:len(row) - tail]
                code, name = head[0:9].strip(), head[21:].strip()
                if re.fullmatch(r"\d{6}", code) and name:
                    out[name] = [code, "KOSPI" if mkt == "kospi" else "KOSDAQ"]
        except Exception as e:
            print(f"  [마스터] {mkt} 실패: {e}")
    if out.get("삼성전자", [None])[0] != "005930":
        print(f"  ⚠ [마스터] 파싱 검증 실패 (삼성전자→{out.get('삼성전자')}). 폴백 정확도가 낮을 수 있습니다.")
    if out:
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  [마스터] 종목 {len(out)}건 캐시")
    return out

# 스캔 상태: code -> 마지막으로 조회한 행 (테마 260개로 늘면 전량 스캔이 불가능하므로
# 거래대금 상위는 매번, 나머지는 순환해서 조금씩 갱신한다)
_scan_state = {}
_scan_rot = [0]
_SCAN_FILE = os.path.join(CACHE, "scan_state.json")

def _load_scan_state():
    """이전 실행의 거래대금 순서를 복원 (CI는 매번 새 환경이므로 필요)."""
    try:
        d = json.load(open(_SCAN_FILE, encoding="utf-8"))
        if time.time() - d.get("saved", 0) < 3 * 86400:
            for c, v in d.get("value", {}).items():
                _scan_state.setdefault(c, {"code": c, "name": "", "price": 0, "diff": 0,
                                           "rate": 0.0, "volume": 0, "value": v, "rank": 0,
                                           "_stale": True})
            print(f"  [스캔] 이전 순서 {len(d.get('value', {}))}건 복원")
    except Exception:
        pass

def _save_scan_state():
    try:
        json.dump({"saved": time.time(),
                   "value": {c: r["value"] for c, r in _scan_state.items()}},
                  open(_SCAN_FILE, "w", encoding="utf-8"))
    except Exception:
        pass

_load_scan_state()
_universe_matched = [0]
HOT   = 350        # 매 사이클 갱신할 거래대금 상위 종목 수
NEW   = 200        # 매 사이클 새로 발굴할 종목 수
FIRST = 600        # 최초 1회에 조회할 종목 수 (약 38초)

def scan_universe():
    """테마 사전 종목을 우선순위대로 병렬 조회. 전량이 아니라 HOT+NEW 만 돈다."""
    from concurrent.futures import ThreadPoolExecutor
    n2c = kis_master()
    names, seen = [], set()
    for t in THEMES:
        for nm in t["stocks"]:
            if nm not in seen:
                seen.add(nm); names.append(nm)

    targets, miss = {}, []
    for nm in names:
        ent = n2c.get(nm) or n2c.get(nm.replace(" ", "")) or n2c.get(_norm(nm))
        (targets.__setitem__(ent[0], nm) if ent else miss.append(nm))

    _universe_matched[0] = len(targets)
    known = [c for c in targets if c in _scan_state]
    fresh = [c for c in targets if c not in _scan_state]
    known.sort(key=lambda c: -_scan_state[c]["value"])
    hot = known[:HOT]
    cold = known[HOT:]
    r = _scan_rot[0]
    rot = cold[r:r + 80] if cold else []
    _scan_rot[0] = (r + 80) % max(1, len(cold))
    pick = fresh[:FIRST] if not _scan_state else (hot + fresh[:NEW] + rot)

    def one(code):
        try:
            d = kis_price(code)
            if not d.get("price"):
                return None
            return {"code": code, "name": targets[code], "price": d["price"], "diff": d["diff"],
                    "rate": d["rate"], "volume": d["volume"], "value": d["value"], "rank": 0}
        except Exception:
            return None

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for row in ex.map(one, pick):
            if row:
                _scan_state[row["code"]] = row

    _save_scan_state()
    rows = sorted((r for r in _scan_state.values() if not r.get("_stale")),
                  key=lambda x: -x["value"])
    for i, x in enumerate(rows, 1):
        x["rank"] = i
    print(f"  [스캔] {len(pick)}건 조회 / {time.time()-t0:.1f}초 "
          f"· 누적 {len(rows)}종목 / 사전 {len(targets)}종목"
          + (f" · 마스터 미매칭 {len(miss)}" if miss else ""))
    return rows

# ══════════════════════════════════════════════════════════════════════════
# DART — 재무
# ══════════════════════════════════════════════════════════════════════════
def dart_corp_map():
    """종목코드 → DART 고유번호. corpCode.zip 을 받아 캐시(7일)."""
    p = os.path.join(CACHE, "corp_map.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        return json.load(open(p, encoding="utf-8"))
    url = ("https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key=" + need("DART_API_KEY"))
    with urllib.request.urlopen(url, timeout=60, context=_ctx) as r:
        blob = r.read()
    m = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read(z.namelist()[0]).decode("utf-8")
    for corp, stock in re.findall(
            r"<corp_code>(\d+)</corp_code>.*?<stock_code>\s*(\S*?)\s*</stock_code>", xml, re.S):
        if stock and stock != " ":
            m[stock] = corp
    json.dump(m, open(p, "w", encoding="utf-8"))
    print(f"  [DART] 기업코드 {len(m)}건 캐시")
    return m

_ACC = {"매출액": "revenue", "영업수익": "revenue", "수익(매출액)": "revenue",
        "영업이익": "op", "영업이익(손실)": "op",
        "당기순이익": "net", "당기순이익(손실)": "net",
        "자산총계": "assets", "부채총계": "liab", "자본총계": "equity"}

def dart_financials(code):
    """최근 확정 보고서 기준 요약 재무. 실패 시 None."""
    p = os.path.join(CACHE, f"fin2_{code}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 3 * 86400:
        return json.load(open(p, encoding="utf-8"))
    corp = dart_corp_map().get(code)
    if not corp:
        return None
    y = datetime.now().year
    for year in (y, y - 1):
        for rep, label in (("11011", "사업보고서"), ("11014", "3분기"),
                           ("11012", "반기"), ("11013", "1분기")):
            try:
                r = http("https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?" +
                         urllib.parse.urlencode({"crtfc_key": need("DART_API_KEY"),
                            "corp_code": corp, "bsns_year": str(year), "reprt_code": rep}))
            except Exception:
                continue
            if r.get("status") != "000":
                continue
            best = {}
            for it in r.get("list", []):
                key = _ACC.get(it.get("account_nm", "").strip())
                if not key:
                    continue
                if it.get("fs_div") == "CFS" or key not in best:
                    # 분기·반기 보고서에서 손익 항목의 thstrm_amount 는 '해당 3개월'
                    # 금액이고, thstrm_add_amount 가 '당기 누적'이다. 누적을 우선한다.
                    # (자산·부채·자본은 시점 값이라 누적 개념이 없어 그대로 쓴다)
                    raw = ""
                    if key in ("revenue", "op", "net"):
                        raw = (it.get("thstrm_add_amount") or "").strip()
                    if not raw:
                        raw = (it.get("thstrm_amount") or "0").strip()
                    try:
                        best[key] = int(raw.replace(",", ""))
                    except Exception:
                        pass
            if "revenue" in best or "op" in best:
                _lbl = label if rep == "11011" else label + " 누적"
                out = {"period": f"{year} {_lbl}", "fs": "연결우선", **best}
                if best.get("revenue"):
                    out["opm"] = round(best.get("op", 0) / best["revenue"] * 100, 1)
                if best.get("equity"):
                    out["debt"] = round(best.get("liab", 0) / best["equity"] * 100, 1)
                    out["roe"] = round(best.get("net", 0) / best["equity"] * 100, 1)
                json.dump(out, open(p, "w", encoding="utf-8"))
                return out
    return None

# ══════════════════════════════════════════════════════════════════════════
# 네이버 뉴스
# ══════════════════════════════════════════════════════════════════════════
_TAG = re.compile(r"<[^>]+>")
def naver_news(query, n=5):
    p = os.path.join(CACHE, f"news_{re.sub(r'[^0-9A-Za-z가-힣]', '', query)[:30]}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 600:
        return json.load(open(p, encoding="utf-8"))
    req = urllib.request.Request(
        "https://openapi.naver.com/v1/search/news.json?" +
        urllib.parse.urlencode({"query": query, "display": n, "sort": "sim"}))
    req.add_header("X-Naver-Client-Id", need("NAVER_CLIENT_ID"))
    req.add_header("X-Naver-Client-Secret", need("NAVER_CLIENT_SECRET"))
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        d = json.loads(r.read().decode())
    out = []
    for it in d.get("items", []):
        try:
            dt = datetime.strptime(it["pubDate"][:25], "%a, %d %b %Y %H:%M:%S")
        except Exception:
            dt = None
        out.append({
            "title": _TAG.sub("", it["title"]).replace("&quot;", '"').replace("&amp;", "&")
                        .replace("&lt;", "<").replace("&gt;", ">").replace("&apos;", "'"),
            "desc": _TAG.sub("", it.get("description", ""))[:120],
            "url": it.get("originallink") or it.get("link"),
            "nurl": it.get("link"),
            "time": dt.strftime("%m-%d %H:%M") if dt else "",
            "ts": dt.timestamp() if dt else 0})
    out.sort(key=lambda x: -x["ts"])
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return out

# ══════════════════════════════════════════════════════════════════════════
# 테마 엔진
# ══════════════════════════════════════════════════════════════════════════
THEMES = json.load(open(os.path.join(HERE, "themes.json"), encoding="utf-8"))["themes"]

# 테마라기보다 '지수 편입 목록'에 가까워 대시보드에서 제외할 이름들.
# 화면에서 빼고 싶은 테마가 있으면 여기에 키워드를 추가하세요.
BLACKLIST = ("지수", "밸류업", "MSCI", "KRX")

def _norm(s):
    return re.sub(r"[\s\.\-·]", "", (s or "")).upper()

NAME2THEME = {}
for t in THEMES:
    for nm in t["stocks"]:
        NAME2THEME.setdefault(_norm(nm), []).append(t)

def themes_of(name):
    return NAME2THEME.get(_norm(name), [])

_fallback_notice = [False]
_dash_cache = {"ts": 0, "data": None, "mode": None, "building": False}
_dash_lock = threading.Lock()

def build_dashboard(force=False):
    """캐시가 살아있으면 즉시 반환. 만료됐으면 이전 데이터를 주고 뒤에서 갱신."""
    d, age = _dash_cache["data"], time.time() - _dash_cache["ts"]
    ttl = 25 if _dash_cache["mode"] == "rank" else 100      # 스캔 모드는 느리므로 길게
    if force:                                                # 강제 갱신은 끝까지 기다린다
        return _rebuild()
    if d and age < ttl:
        return d
    if d and not _dash_cache["building"]:                    # 오래됐지만 데이터는 있음
        _dash_cache["building"] = True
        def bg():
            try:
                _rebuild()
            except Exception as e:
                print(f"  [백그라운드 갱신 실패] {e}")
            finally:
                _dash_cache["building"] = False
        threading.Thread(target=bg, daemon=True).start()
        return d                                             # 이전 데이터를 바로 준다
    return _rebuild()

def _rebuild():
    """실제 수집 — 최초 1회와 백그라운드 갱신에서만 호출."""
    with _dash_lock:
        mode = "rank"
        try:
            rows = kis_volume_rank("0000", "3")       # 거래대금 상위 (빠름)
            if not rows:
                raise RuntimeError("순위 응답 0건")
        except Exception as e:
            mode = "scan"
            if not _fallback_notice[0]:
                _fallback_notice[0] = True
                print(f"  [순위 API 미지원 → 테마 종목 직접 스캔으로 전환] {e}")
            rows = scan_universe()                    # 테마 종목 직접 스캔

        # 시가총액·PER 은 상위 40종목만 개별 조회 (호출 절약: 초당 20건 제한)
        detail = {}
        for r in ([] if mode == "scan" else rows[:40]):
            try:
                detail[r["code"]] = kis_price(r["code"])
                time.sleep(0.06)
            except Exception:
                pass

        stocks = {}
        for r in rows:
            d = detail.get(r["code"]) or (_price_cache.get(r["code"], (0, {}))[1])
            stocks[r["code"]] = {**r,
                "cap": d.get("cap"), "per": d.get("per"), "pbr": d.get("pbr"),
                "market": d.get("market", ""), "high52": d.get("high52"),
                "themes": [t["id"] for t in themes_of(r["name"])]}

        # 테마 집계
        agg = {}
        for code, s in stocks.items():
            for tid in s["themes"]:
                a = agg.setdefault(tid, {"value": 0, "wsum": 0, "wcap": 0,
                                         "up": 0, "n": 0, "codes": []})
                a["value"] += s["value"]
                cap = s.get("cap") or 0
                a["wsum"] += s["rate"] * cap
                a["wcap"] += cap
                a["up"] += 1 if s["rate"] > 0 else 0
                a["n"] += 1
                a["codes"].append(code)

        out_themes = []
        for t in THEMES:
            a = agg.get(t["id"])
            if not a or a["n"] < 2:            # 2종목 미만은 테마로 보지 않음
                continue
            if len(t["stocks"]) > 200:         # 지나치게 넓은 분류는 제외
                continue
            if any(k in t["name"] for k in BLACKLIST):
                continue
            codes = sorted(a["codes"], key=lambda c: -stocks[c]["rate"])
            eq = sum(stocks[c]["rate"] for c in codes) / len(codes)
            wt = (a["wsum"] / a["wcap"]) if a["wcap"] else eq
            out_themes.append({
                "id": t["id"], "name": t["name"], "cat": t["cat"],
                "pct": round(wt, 2), "pct_eq": round(eq, 2),
                "value": a["value"], "up": a["up"], "n": a["n"],
                "total": len(t["stocks"]), "codes": codes})
        out_themes.sort(key=lambda x: -x["value"])

        data = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "themes": out_themes,
            "stocks": stocks,
            "ranking": [r["code"] for r in rows],
            "mode": mode,
            "building": _dash_cache["building"],
            "scanned": len(rows),
            "universe": _universe_matched[0] or len({n for t in THEMES for n in t["stocks"]}),
            "theme_total": len(THEMES),
        }
        _dash_cache.update(ts=time.time(), data=data, mode=mode)
        return data

# ══════════════════════════════════════════════════════════════════════════
# 급등사유 근거카드 (규칙 기반 · LLM 미사용)
# ══════════════════════════════════════════════════════════════════════════
def surge_reason(code, name, rate, theme_ids, dash):
    if rate < 3:
        return {"status": "insufficient",
                "msg": "오늘 이 종목에서 뚜렷한 급등 신호가 없습니다. (등락률 3% 미만)"}
    try:
        news = naver_news(f"{name} 주가", 5)
    except Exception as e:
        return {"status": "error", "msg": f"뉴스 조회 실패: {e}"}
    KEY = ["계약", "수주", "공급", "실적", "흑자", "특허", "승인", "허가", "수출",
           "증설", "투자", "인수", "협력", "공시", "최대", "돌파", "급등", "신고가"]
    scored = []
    for nw in news:
        sc = sum(2 for k in KEY if k in nw["title"]) + (1 if name in nw["title"] else 0)
        if time.time() - nw["ts"] < 172800:
            sc += 3
        scored.append((sc, nw))
    scored.sort(key=lambda x: -x[0])
    top = [n for sc, n in scored[:3] if sc > 0]
    ctx = None
    for t in dash["themes"]:
        if t["id"] in theme_ids:
            ctx = f"동일 테마 '{t['name']}' {t['n']}종목 중 {t['up']}종목 동반 상승 (평균 {t['pct']:+.2f}%)"
            break
    if not top:
        return {"status": "insufficient", "theme_context": ctx,
                "msg": "뚜렷한 공시·뉴스가 확인되지 않습니다. 수급 요인일 수 있습니다."}
    return {"status": "ok", "evidences": top, "theme_context": ctx,
            "confidence": "높음" if len(top) >= 3 else "보통"}

# ══════════════════════════════════════════════════════════════════════════
# HTTP 서버
# ══════════════════════════════════════════════════════════════════════════
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                p = os.path.join(HERE, "dashboard.html")
                return self._send(open(p, "rb").read(), ctype="text/html; charset=utf-8")

            if u.path == "/api/dashboard":
                d = build_dashboard(force="force" in q)
                minv = int(q.get("minv", ["300"])[0])       # 테마 최소 거래대금(억)
                keep = [t for t in d["themes"] if t["value"] >= minv]
                codes = {c for t in keep for c in t["codes"]}
                return self._send({**d, "themes": keep, "minv": minv,
                                   "hidden": len(d["themes"]) - len(keep),
                                   "stocks": {c: d["stocks"][c] for c in codes},
                                   "ranking": [c for c in d["ranking"] if c in codes]})

            if u.path == "/api/stock":
                code = q.get("code", [""])[0]
                dash = build_dashboard()
                base = dash["stocks"].get(code) or kis_price(code)
                name = base.get("name") or ""
                tids = base.get("themes") or [t["id"] for t in themes_of(name)]
                return self._send({
                    "base": base,
                    "themes": [t for t in dash["themes"] if t["id"] in tids],
                    "reason": surge_reason(code, name, base.get("rate", 0), tids, dash),
                    "financial": dart_financials(code),
                    "news": naver_news(f"{name} 주가", 5),
                })

            if u.path == "/api/theme":
                tid = q.get("id", [""])[0]
                dash = build_dashboard()
                t = next((x for x in dash["themes"] if x["id"] == tid), None)
                if not t:
                    return self._send({"error": "theme not found"}, 404)
                seed = next((x for x in THEMES if x["id"] == tid), {})
                return self._send({
                    "theme": t, "all_stocks": seed.get("stocks", []),
                    "stocks": [dash["stocks"][c] for c in t["codes"]],
                    "news": naver_news(f"{t['name']} 주가", 5)})

            if u.path == "/api/health":
                return self._send({"ok": True, "env": "실전" if IS_REAL else "모의",
                                   "themes": len(THEMES),
                                   "config_files": CFG.get("_files")})
            return self._send({"error": "not found"}, 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send({"error": str(e)}, 500)

# ══════════════════════════════════════════════════════════════════════════
# 셀프테스트
# ══════════════════════════════════════════════════════════════════════════
def selftest():
    print("=" * 72)
    print(" 테마보드 연결 점검")
    print("=" * 72)
    print(f" 설정 출처: 환경변수 {len(CFG.get('_env') or [])}개 · 파일 {CFG.get('_files')}")
    print(f" KIS 환경 : {'실전투자' if IS_REAL else '모의투자'}  ({KIS_HOST})")
    print(f" 테마 사전: {len(THEMES)}개 / 매핑 {sum(len(t['stocks']) for t in THEMES)}건")
    print("-" * 72)
    ok = 0

    print(" [1/5] KIS 접근토큰 …", end=" ", flush=True)
    try:
        kis_token(); print("OK"); ok += 1
    except Exception as e:
        print(f"실패\n       {e}")

    print(" [2/5] KIS 거래대금 순위 …", end=" ", flush=True)
    try:
        rows = kis_volume_rank()
        print(f"OK  {len(rows)}건")
        for r in rows[:5]:
            print(f"       {r['rank']:>2}. {r['name']:<12} {r['price']:>9,}원 "
                  f"{r['rate']:>+7.2f}%  {r['value']:>8,}억")
        ok += 1
    except Exception as e:
        print(f"실패\n       {e}")
        print("       → 순위 API 없이도 동작합니다. '테마 종목 직접 스캔' 폴백으로 전환됩니다.")
        print("         (python3 probe_rank.py 로 어떤 조합이 되는지 찾을 수 있습니다)")

    print(" [3/5] KIS 개별 현재가(삼성전자) …", end=" ", flush=True)
    try:
        d = kis_price("005930")
        print(f"OK  {d['price']:,}원 시총 {d['cap']:,}억 PER {d['per']}")
        ok += 1
    except Exception as e:
        print(f"실패\n       {e}")

    print(" [4/5] DART 재무(삼성전자) …", end=" ", flush=True)
    try:
        f = dart_financials("005930")
        print(f"OK  {f['period']} 매출 {f.get('revenue',0)/1e12:.1f}조 "
              f"영업이익률 {f.get('opm')}%" if f else "데이터 없음")
        ok += 1
    except Exception as e:
        print(f"실패\n       {e}")

    print(" [5/5] 네이버 뉴스 …", end=" ", flush=True)
    try:
        n = naver_news("한미반도체 주가", 3)
        print(f"OK  {len(n)}건")
        for x in n[:2]:
            print(f"       {x['time']}  {x['title'][:44]}")
        ok += 1
    except Exception as e:
        print(f"실패\n       {e}")

    print("-" * 72)
    if ok >= 4:
        print(" 실행 가능합니다.  python3 server.py  로 띄우세요.")
        try:
            d = build_dashboard(force=True)
            print(f" 수집 모드: {'순위 API' if d.get('mode')=='rank' else '테마 종목 직접 스캔(폴백)'}"
                  f" · 종목 {len(d['stocks'])}개 · 테마 {len(d['themes'])}개")
            print(f" 사전 {d['theme_total']}테마 / {d['universe']}종목 중 {d['scanned']}종목 스캔 완료")
            if d["unmatched"]:
                print(f" 미분류 종목({len(d['unmatched'])}): {', '.join(d['unmatched'][:10])}")
                print(" → themes.json 에 추가하면 다음 실행부터 잡힙니다.")
        except Exception as e:
            print(f" 대시보드 조립 실패: {e}")
    else:
        print(f" {ok}/5 성공. 실패 항목의 메시지를 확인하세요.")
    print("=" * 72)

# ══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    print("=" * 72)
    print(f" 테마보드 서버   ({'실전투자' if IS_REAL else '모의투자'} 계정)")
    src = []
    if CFG.get("_env"):   src.append(f"환경변수 {len(CFG['_env'])}개")
    if CFG.get("_files"): src.append(f"파일 {CFG['_files']}")
    print(f" 설정 출처 : {' + '.join(src) or '(없음)'}")
    print(f" 테마 사전 : {len(THEMES)}개")
    print("-" * 72)
    print(" 초기 데이터 로딩 중 … (첫 실행은 20~40초 걸립니다)")
    try:
        d = build_dashboard(force=True)
        print(f" 테마 {len(d['themes'])}개 구성 · 스캔 {d['scanned']}/{d['universe']}종목")
        print(" 켜둔 채 5~7분 지나면 사전 전체가 채워집니다.")
    except Exception as e:
        print(f" ⚠ 초기 로딩 실패: {e}")
        print("   python3 server.py --selftest 로 원인을 확인하세요.")
    print("-" * 72)
    print(f"  ▶  브라우저에서 http://127.0.0.1:{a.port}  를 여세요")
    print("     (종료: Ctrl+C)")
    print("=" * 72)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료합니다.")
