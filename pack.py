#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테마보드 — 소스 묶음 만들기

    cd ~/theme-board
    python3 pack.py

바탕화면에 theme-board_소스_YYYYMMDD.zip 을 만듭니다.
키 파일(config.py, .env)·캐시·디버그 찌꺼기는 절대 담지 않습니다.
"""
import os, sys, zipfile, hashlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'

# ── 담을 것 ────────────────────────────────────────────────────────────────
FILES = [
    # (경로, 분류, 설명)
    ("server.py",            "핵심",   "한투·DART·네이버 호출, 테마 집계 엔진 (공용 라이브러리)"),
    ("export_snapshot.py",   "핵심",   "스냅샷 생성기 — web/data.json 을 만든다"),
    ("ai_reason.py",         "핵심",   "뉴스 기사 본문을 읽고 상승 근거를 정리"),
    ("fetch_themes.py",      "핵심",   "네이버 금융에서 테마·종목 매핑 수집"),
    ("themes.json",          "데이터", "테마 301개 / 종목 매핑"),
    ("web/index.html",       "화면",   "메인 화면 (단일 파일, 외부 의존 없음)"),
    ("web/guide.html",       "화면",   "고객용 '화면 보는 법'"),
    ("web/vercel.json",      "설정",   "Vercel 캐시·보안 헤더"),
    ("web/data.json",        "데이터", "최신 스냅샷 (자동 생성물, 참고용)"),
    (".github/workflows/snapshot.yml", "자동화", "GitHub Actions — 평일 장중 15분마다 갱신·배포"),
    (".gitignore",           "설정",   "키 파일이 저장소에 올라가지 않도록 차단"),
    ("AUTOMATION.md",        "문서",   "자동화 구조 설명"),
    ("README.md",            "문서",   "프로젝트 개요"),
]
SETUP = [
    ("setup_github.sh", "최초 GitHub Actions 설정"),
    ("setup2.sh",       "저장소 업로드 + Secrets 등록"),
    ("fix1.py",         "1차 수정 — 시간대 KST · 재무 누적 · 주기 15분"),
    ("fix2.py",         "2차 수정 — Cloudflare Pages 배포 추가"),
]
NEVER = ("config.py", ".env", ".key", ".pem", "credential", "secret")

# ── 안전 검사 ──────────────────────────────────────────────────────────────
print(f"{B}════════════════════════════════════════════════{N}")
print(f"{B} 테마보드 소스 묶기{N}")
print(f"{B}════════════════════════════════════════════════{N}\n")

picked, missing = [], []
for item in FILES:
    (picked if os.path.exists(item[0]) else missing).append(item)
setup_ok = [(f, d) for f, d in SETUP if os.path.exists(f)]

for f, *_ in picked:
    low = f.lower()
    if any(bad in low for bad in NEVER):
        print(f"  {R}✗{N} 위험: {f} 가 목록에 있습니다. 중단합니다.")
        sys.exit(1)

# ── MANIFEST ───────────────────────────────────────────────────────────────
today = datetime.date.today().strftime("%Y-%m-%d")
lines = [
    "# 테마보드 — 소스 구성",
    "",
    f"묶은 날짜: {today}",
    "사이트: https://theme-board.pages.dev",
    "저장소: https://github.com/dodohan0721/theme-board",
    "",
    "## 파일",
    "",
    "| 파일 | 분류 | 설명 | 크기 |",
    "|---|---|---|---|",
]
for f, cat, desc in picked:
    kb = os.path.getsize(f) / 1024
    lines.append(f"| `{f}` | {cat} | {desc} | {kb:,.0f} KB |")
if setup_ok:
    lines += ["", "## setup/ — 설정용 스크립트 (한 번 쓰고 보관)", "",
              "| 파일 | 설명 |", "|---|---|"]
    for f, d in setup_ok:
        lines.append(f"| `setup/{f}` | {d} |")
lines += [
    "",
    "## 담지 않은 것",
    "",
    "- `config.py`, `.env` — **API 키.** 절대 배포물에 포함하지 않습니다",
    "- `.cache/` — 토큰·종목마스터 캐시 (자동 재생성)",
    "- `.git/`, `__pycache__/`, `_debug_*` — 작업 부산물",
    "",
    "## 돌리는 법",
    "",
    "키는 `config.py` 또는 환경변수로 넣습니다. 필요한 값:",
    "",
    "```",
    "KIS_APP_KEY  KIS_APP_SECRET  KIS_ENV=real",
    "DART_API_KEY",
    "NAVER_CLIENT_ID  NAVER_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
    "```",
    "",
    "```bash",
    "python3 export_snapshot.py --cycles 2 --detail 60 --ai --ai-top 30",
    "```",
    "",
    "`web/data.json` 이 만들어집니다. `web/` 폴더를 정적 호스팅에 올리면 끝입니다.",
    "서버가 따로 필요 없고, 브라우저가 `data.json` 만 읽습니다.",
    "",
    "자동 갱신은 `.github/workflows/snapshot.yml` 이 담당합니다.",
    "GitHub Secrets 에 위 키들과 `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID` 를 등록해야 합니다.",
]
manifest = "\n".join(lines)

# ── 압축 ───────────────────────────────────────────────────────────────────
out = os.path.expanduser(f"~/Desktop/theme-board_소스_{today.replace('-','')}.zip")
root = "theme-board"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(f"{root}/MANIFEST.md", manifest)
    for f, cat, desc in picked:
        z.write(f, f"{root}/{f}")
        print(f"  {G}✓{N} {f}")
    for f, d in setup_ok:
        z.write(f, f"{root}/setup/{f}")
        print(f"  {G}✓{N} setup/{f}")

for f, cat, desc in missing:
    print(f"  {Y}·{N} {f} — 없음 (건너뜀)")

# ── 검증 ───────────────────────────────────────────────────────────────────
with zipfile.ZipFile(out) as z:
    names = z.namelist()
    bad = [n for n in names if any(b in n.lower() for b in NEVER)]
    if bad:
        print(f"\n  {R}✗{N} 키 파일이 들어갔습니다: {bad}")
        os.remove(out); sys.exit(1)

size = os.path.getsize(out) / 1024
sha = hashlib.sha256(open(out, "rb").read()).hexdigest()[:16]

print(f"""
{B}════════════════════════════════════════════════{N}
  {G}✓{N} 파일 {len(names)}개 · {size:,.0f} KB
  {G}✓{N} 키 파일 미포함 확인
  체크섬 {sha}

  {B}{out}{N}
{B}════════════════════════════════════════════════{N}
""")
