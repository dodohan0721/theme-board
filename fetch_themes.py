#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마 사전 자동 수집기
──────────────────────────────────────────────────────────────────────────────
네이버 금융 '테마별 시세' 에서 테마 목록과 편입 종목을 긁어
server.py 가 쓰는 themes.json 형식으로 만들어 줍니다.

    python3 fetch_themes.py                  # 수집 → themes_naver.json 저장
    python3 fetch_themes.py --merge          # 기존 themes.json 과 합쳐서 덮어씀
    python3 fetch_themes.py --pages 3        # 앞 3페이지만 (테스트용)
    python3 fetch_themes.py --debug          # 파싱 실패 시 원본 HTML 조각 출력

표준 라이브러리만 사용합니다. (pip install 불필요)

⚠ 주의
  · 네이버 금융은 크롤러를 차단한 이력이 있습니다(2021년 사례). 이 스크립트는
    브라우저 User-Agent 를 보내고 요청 간 0.5초 간격을 둡니다. 간격을 더 줄이지 마세요.
  · 하루 1회 정도만 돌리면 충분합니다. 테마 편입은 그렇게 자주 바뀌지 않습니다.
  · 상업 서비스에 붙이기 전 네이버 이용약관을 직접 확인하세요. 이 스크립트는
    개인이 자기 화면을 만들기 위한 용도로 작성된 것입니다.
"""
import argparse, json, os, re, sys, time
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://finance.naver.com"
LIST = BASE + "/sise/theme.naver?&page={}"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

RE_THEME = re.compile(r'sise_group_detail\.naver\?type=theme&(?:amp;)?no=(\d+)"[^>]*>\s*([^<]+?)\s*<')
RE_STOCK = re.compile(r'/item/main\.naver\?code=(\d{6})"[^>]*>\s*([^<]+?)\s*<')
RE_NEXT  = re.compile(r'theme\.naver\?&(?:amp;)?page=(\d+)')


def get(url, debug=False, retry=2):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": BASE + "/sise/theme.naver",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    for i in range(retry + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            for enc in ("euc-kr", "cp949", "utf-8"):      # 네이버 금융은 EUC-KR
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if debug:
                print(f"    HTTP {e.code} {url}")
            if e.code in (403, 429) and i < retry:
                time.sleep(3 * (i + 1))
                continue
            raise
        except Exception as e:
            if i < retry:
                time.sleep(2)
                continue
            raise
    return ""


def cat_of(name):
    """테마명으로 대략의 분류를 붙인다(UI 필터용, 정확도 목적 아님)."""
    T = [("바이오", ["바이오", "제약", "의료", "백신", "진단", "치료", "임플란트", "줄기세포", "톡신", "비만"]),
         ("기술",   ["반도체", "AI", "인공지능", "로봇", "소프트웨어", "클라우드", "데이터", "보안", "통신",
                    "게임", "메타버스", "블록체인", "양자", "디스플레이", "OLED", "카메라", "웨어러블"]),
         ("소재",   ["2차전지", "리튬", "니켈", "희토류", "철강", "화학", "시멘트", "비철", "정유", "소재"]),
         ("정책",   ["원자력", "원전", "태양광", "풍력", "수소", "그린", "탄소", "방산", "우주", "정책",
                    "남북", "정치", "대선", "재난", "정부"]),
         ("산업",   ["조선", "건설", "기계", "자동차", "항공", "해운", "물류", "전력", "인프라", "플랜트"]),
         ("소비",   ["화장품", "음식료", "유통", "엔터", "여행", "면세", "의류", "가구", "교육", "카지노"]),
         ("금융",   ["은행", "증권", "보험", "지주", "리츠", "핀테크"])]
    for cat, keys in T:
        if any(k in name for k in keys):
            return cat
    return "기타"


def slugify(name, used):
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", name).strip("-").lower()[:40] or "theme"
    base, i = s, 2
    while s in used:
        s = f"{base}-{i}"; i += 1
    used.add(s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0, help="가져올 목록 페이지 수 (0=전체)")
    ap.add_argument("--merge", action="store_true", help="기존 themes.json 과 합쳐서 덮어쓰기")
    ap.add_argument("--out", default=None)
    ap.add_argument("--delay", type=float, default=0.5, help="요청 간격(초). 줄이지 마세요")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    out_path = a.out or os.path.join(HERE, "themes.json" if a.merge else "themes_naver.json")

    print("=" * 70)
    print(" 네이버 금융 테마 수집기")
    print("=" * 70)

    # ── 1) 목록 페이지에서 테마 수집 ────────────────────────────────────
    print(" [1/2] 테마 목록 수집 …")
    try:
        html = get(LIST.format(1), a.debug)
    except Exception as e:
        print(f"\n ✗ 목록 페이지 접속 실패: {e}")
        print("   · 회사/학교 네트워크나 VPN이면 차단됐을 수 있습니다.")
        print("   · 브라우저에서 https://finance.naver.com/sise/theme.naver 가 열리는지 먼저 확인하세요.")
        return 1

    if a.debug:
        open(os.path.join(HERE, "_debug_list.html"), "w", encoding="utf-8").write(html)
        print("   원본 저장: _debug_list.html")

    pages = [int(x) for x in RE_NEXT.findall(html)] or [1]
    last = max(pages)
    if a.pages:
        last = min(last, a.pages)
    print(f"   전체 {last} 페이지")

    themes, seen = [], set()
    for p in range(1, last + 1):
        h = html if p == 1 else get(LIST.format(p), a.debug)
        found = RE_THEME.findall(h)
        for no, nm in found:
            nm = nm.strip()
            if no in seen or not nm:
                continue
            seen.add(no)
            themes.append({"no": no, "name": nm})
        print(f"   page {p:>2}: {len(found):>3}건 (누적 {len(themes)})")
        if p < last:
            time.sleep(a.delay)

    if not themes:
        print("\n ✗ 테마를 하나도 못 찾았습니다. HTML 구조가 바뀐 것 같습니다.")
        print("   --debug 로 다시 돌려서 _debug_list.html 을 확인해 주세요.")
        return 1

    # ── 2) 테마별 편입 종목 ────────────────────────────────────────────
    print(f"\n [2/2] 편입 종목 수집 … (총 {len(themes)}개 · 약 {len(themes)*a.delay/60:.1f}분)")
    used_slugs, out, fails = set(), [], 0
    for i, t in enumerate(themes, 1):
        url = f"{BASE}/sise/sise_group_detail.naver?type=theme&no={t['no']}"
        try:
            h = get(url, a.debug)
        except Exception as e:
            fails += 1
            print(f"   [{i:>3}/{len(themes)}] {t['name'][:20]:<22} 실패 {e}")
            time.sleep(a.delay)
            continue

        pairs, names = RE_STOCK.findall(h), []
        for code, nm in pairs:
            nm = nm.strip()
            if nm and nm not in names:
                names.append(nm)

        if names:
            out.append({"id": slugify(t["name"], used_slugs), "name": t["name"],
                        "cat": cat_of(t["name"]), "naver_no": t["no"], "stocks": names})
            mark = ""
        else:
            fails += 1
            mark = "  ← 종목 0건"
            if a.debug and fails <= 2:
                open(os.path.join(HERE, f"_debug_detail_{t['no']}.html"), "w",
                     encoding="utf-8").write(h)

        if i % 10 == 0 or names == [] or i == len(themes):
            print(f"   [{i:>3}/{len(themes)}] {t['name'][:20]:<22} {len(names):>3}종목{mark}")
        time.sleep(a.delay)

    # ── 3) 저장 ────────────────────────────────────────────────────────
    if a.merge and os.path.exists(os.path.join(HERE, "themes.json")):
        old = json.load(open(os.path.join(HERE, "themes.json"), encoding="utf-8"))["themes"]
        by_name = {t["name"]: t for t in out}
        merged, added = list(out), 0
        for o in old:
            if o["name"] in by_name:                 # 같은 이름이면 수기 종목을 합집합으로
                tgt = by_name[o["name"]]
                for s in o["stocks"]:
                    if s not in tgt["stocks"]:
                        tgt["stocks"].append(s)
            else:
                o.setdefault("source", "manual")
                merged.append(o); added += 1
        out = merged
        print(f"\n   기존 수기 테마 {added}개 유지 · 이름 겹치는 테마는 종목 합집합 처리")

    data = {"_comment": f"네이버 금융 테마별 시세 수집 ({time.strftime('%Y-%m-%d %H:%M')}). "
                        f"종목명 기준 매칭. 수정은 이 파일에서.",
            "_source": "finance.naver.com/sise/theme.naver",
            "themes": out}
    json.dump(data, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    total = sum(len(t["stocks"]) for t in out)
    uniq = len({s for t in out for s in t["stocks"]})
    print("\n" + "=" * 70)
    print(f" 완료 → {out_path}")
    print(f"   테마 {len(out)}개 · 매핑 {total}건 · 고유 종목 {uniq}개" + (f" · 실패 {fails}건" if fails else ""))
    print("=" * 70)
    big = sorted(out, key=lambda t: -len(t["stocks"]))[:8]
    print(" 종목 많은 테마 상위 8개:")
    for t in big:
        print(f"   {t['name'][:24]:<26} {len(t['stocks']):>3}종목  {', '.join(t['stocks'][:4])} …")
    print("\n 이제 python3 server.py 를 다시 실행하면 이 사전이 적용됩니다.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n중단했습니다.")
