"""Keep both markets in every full-site deployment. Public JSON only."""
import argparse
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ORIGIN = "https://theme-board.pages.dev"
NAMES = {"kr": "data.json", "us": "data_us.json"}

def validate(data, market):
    if not isinstance(data, dict):
        raise ValueError("snapshot must be an object")
    datetime.strptime(data.get("ts", ""), "%Y-%m-%d %H:%M:%S")
    if not isinstance(data.get("themes"), list) or not isinstance(data.get("ranking"), list):
        raise ValueError("missing themes or ranking")
    if not isinstance(data.get("stocks"), dict) or not data["stocks"]:
        raise ValueError("missing stock prices")
    if market == "us" and data.get("market") != "US":
        raise ValueError("wrong market")
    if market == "kr" and data.get("market") == "US":
        raise ValueError("wrong market")
    for theme in data["themes"]:
        if not isinstance(theme, dict) or not isinstance(theme.get("codes"), list):
            raise ValueError("invalid theme")
    return data

def read_local(path, market):
    try:
        return validate(json.loads(path.read_text(encoding="utf-8-sig")), market)
    except (OSError, ValueError, TypeError):
        return None

def fetch_snapshot(market):
    # A cache-busted missing asset may return SPA HTML with status 200.
    for suffix in ("?t=" + str(time.time_ns()), ""):
        try:
            request = Request(ORIGIN + "/" + NAMES[market] + suffix,
                              headers={"User-Agent": "ROOTON-snapshot-sync/1.0",
                                       "Cache-Control": "no-cache"})
            with urlopen(request, timeout=20) as response:
                if response.status != 200:
                    continue
                data = validate(json.load(response), market)
            return data
        except (OSError, ValueError, TypeError):
            continue
    return None

def snapshot_time(data, market):
    at = datetime.strptime(data["ts"], "%Y-%m-%d %H:%M:%S")
    offset = 0 if market == "us" and data.get("timezone") != "Asia/Seoul" else 9
    return at.replace(tzinfo=timezone(timedelta(hours=offset))).timestamp()

def sync_one(web, market, fetch=fetch_snapshot):
    path = web / NAMES[market]
    local = read_local(path, market)
    remote = fetch(market)
    candidates = [d for d in (local, remote) if d is not None]
    if not candidates:
        raise ValueError(f"{NAMES[market]}: no valid snapshot; deployment stopped")
    best = max(candidates, key=lambda d: snapshot_time(d, market))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(best, ensure_ascii=False, separators=(",", ":")),
                         encoding="utf-8")
    os.replace(temporary, path)
    print(f"{NAMES[market]}: {best['ts']} / {len(best['stocks'])} stocks")
    return best

def require_details(web):
    for name in ("detail.json", "detail_us.json"):
        try:
            data = json.loads((web / "priv" / name).read_text(encoding="utf-8-sig"))
            if not isinstance(data.get("details"), dict) or not data["details"]:
                raise ValueError("empty details")
        except (OSError, ValueError, AttributeError):
            raise ValueError(f"priv/{name}: missing or invalid; deployment stopped")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", type=Path, default=Path(__file__).resolve().parent / "web")
    parser.add_argument("--market", choices=("kr", "us", "both"), default="both",
                        help="market just collected; retain both markets")
    parser.add_argument("--require-details", action="store_true")
    args = parser.parse_args()
    for market in ("kr", "us"):
        sync_one(args.web, market)
    if args.require_details:
        require_details(args.web)

if __name__ == "__main__":
    main()
