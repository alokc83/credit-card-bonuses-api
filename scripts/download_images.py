#!/usr/bin/env python3
"""Download original card images into images_org/ from exports/data.json."""

from __future__ import annotations

import concurrent.futures
import json
import ssl
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "images_org"
DATA_JSON = ROOT / "exports" / "data.json"
BASE = "https://offeroptimist.com"
CTX = ssl.create_default_context()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not DATA_JSON.exists():
        print(f"File not found: {DATA_JSON}")
        return

    with open(DATA_JSON, "r", encoding="utf-8") as f:
        cards = json.load(f)

    jobs: dict[str, tuple[str, Path, str]] = {}
    for card in cards:
        path = (card.get("imageUrl") or "").strip()
        if not path:
            continue
        if path.startswith("http"):
            url = path
            rel = urlparse(url).path.lstrip("/")
        else:
            rel = path.lstrip("/")
            url = f"{BASE}/{rel}"
        
        # If relative path starts with 'images/', strip it to put into OUT (which is images_org)
        clean_rel = rel[7:] if rel.startswith("images/") else rel
        dest = OUT / clean_rel
        jobs[str(dest)] = (url, dest, card.get("name") or "")

    print(f"Checking/downloading {len(jobs)} images -> {OUT}")

    def fetch(job: tuple[str, Path, str]) -> tuple[str, Path, int, str | None]:
        url, dest, _name = job
        if dest.exists() and dest.stat().st_size > 0:
            return "skip", dest, dest.stat().st_size, None
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "CreditCardBonuses-Archive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60, context=CTX) as response:
                data = response.read()
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok", dest, len(data), None
        except Exception as exc:
            return "fail", dest, 0, f"{url}: {exc}"

    ok = skip = fail = total = 0
    failures: list[str] = []
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for status, _dest, size, err in pool.map(fetch, jobs.values()):
            if status == "ok":
                ok += 1
                total += size
            elif status == "skip":
                skip += 1
                total += size
            else:
                fail += 1
                if err:
                    failures.append(err)

    print(f"Done in {time.time() - started:.1f}s: ok={ok}, cached/skipped={skip}, failed={fail}")
    for item in failures:
        print("  FAIL:", item)


if __name__ == "__main__":
    main()
