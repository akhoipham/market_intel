#!/usr/bin/env python3
"""SIGNAL/DESK prototype CLI.

  python run.py fetch            pull all RSS feeds + EDGAR, store new headlines
  python run.py build            regenerate dashboard.html from the store
  python run.py fetch build      both, in order (use this on a cron)
  python run.py demo             load fixture headlines into a demo DB and build
  python run.py refresh-tickers  download SEC's full ticker list (cashtag long-tail)

First real run:  python run.py refresh-tickers && python run.py fetch build
Then open dashboard.html in a browser.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from intel import dashboard, store
from intel.ingest import Article
from intel.tickers import refresh_from_sec


def cmd_fetch():
    store.run_pipeline()


def cmd_build():
    dashboard.build()


def cmd_refresh_tickers():
    # 1) Pull current SEC list (CI has network access SEC allows).
    refresh_from_sec()
    # 2) Rebuild the single unified data/tickers.csv from all three sources.
    #    This step was missing from root run.py — intel/run.py had it but this
    #    file is what the GitHub Actions workflow actually calls.
    from intel.consolidate_tickers import consolidate
    n = consolidate()
    print(f"Rebuilt unified data/tickers.csv with {n} tickers.")


def cmd_demo():
    fixtures = json.loads(
        (Path(__file__).parent / "fixtures" / "headlines.json").read_text())
    now = int(time.time())
    articles = [
        Article(title=f["t"], url=f.get("u", f"https://example.com/{i}"),
                source=f["s"], published=now - f["m"] * 60,
                kind=f.get("k", "news"))
        for i, f in enumerate(fixtures)
    ]
    demo_db = Path(__file__).parent / "data" / "intel.db"
    if demo_db.exists():
        demo_db.unlink()
    conn = store.connect(demo_db)
    inserted, _ = store.process_articles(articles, conn)
    conn.close()
    print(f"Loaded {inserted} fixture headlines.")
    dashboard.build()


if __name__ == "__main__":
    cmds = sys.argv[1:] or ["fetch", "build"]
    dispatch = {"fetch": cmd_fetch, "build": cmd_build, "demo": cmd_demo,
                "refresh-tickers": cmd_refresh_tickers}
    for c in cmds:
        if c not in dispatch:
            print(__doc__)
            sys.exit(1)
        dispatch[c]()
