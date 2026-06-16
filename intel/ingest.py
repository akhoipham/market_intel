"""Ingestion: parallel RSS fetching + SEC EDGAR.

v2 changes:
- All RSS feeds fetched concurrently via ThreadPoolExecutor (was sequential)
- With 15 feeds at 15s timeout each, sequential worst-case was 225s;
  parallel worst-case is ~15s (one slow feed doesn't block others)
- EDGAR kept sequential — SEC asks for polite, low-volume access
- Per-feed failure isolation unchanged (one dead feed never kills a run)
"""
from __future__ import annotations

import calendar
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import feedparser
import requests

DATA_DIR  = Path(__file__).resolve().parent.parent / "data"
FEEDS_JSON = DATA_DIR / "feeds.json"

UA = {"User-Agent": "market-intel-prototype/0.2 (personal research; contact@example.com)"}
RSS_WORKERS = 20   # concurrent RSS fetches — bumped for larger feed list
RSS_TIMEOUT = 12   # seconds per feed (slightly tighter to fail fast on dead feeds)


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: int   # epoch seconds UTC
    kind: str = "news"


def _entry_time(entry) -> int:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return calendar.timegm(t)
    return int(time.time())


def fetch_rss(name: str, url: str, tier: str = "secondary",
              timeout: int = RSS_TIMEOUT) -> list[Article]:
    try:
        resp = requests.get(url, headers=UA, timeout=timeout)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as e:
        # Only log failures for primary/wire feeds; suppress noisy opinion-tier warns
        if tier != "opinion":
            print(f"  [warn] {name}: {type(e).__name__}: {e}")
        return []
    out = []
    for entry in parsed.entries:
        title = re.sub(r"\s+", " ", getattr(entry, "title", "")).strip()
        link  = getattr(entry, "link", "")
        if not title or not link:
            continue
        out.append(Article(title=title, url=link, source=name,
                           published=_entry_time(entry)))
    return out


def fetch_edgar(forms: list[str], url_template: str) -> list[Article]:
    out = []
    for form in forms:
        url = url_template.format(form=form)
        try:
            resp = requests.get(url, headers=UA, timeout=20)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"  [warn] EDGAR {form}: {type(e).__name__}: {e}")
            continue
        for entry in parsed.entries:
            title   = re.sub(r"\s+", " ", getattr(entry, "title", "")).strip()
            company = re.sub(r"^\S+\s*-\s*", "", title)
            company = re.sub(r"\(\d{7,}\).*$", "", company).strip().title()
            label   = {"8-K": "8-K material event",
                       "4":   "Form 4 insider filing"}.get(form, form)
            out.append(Article(
                title=f"{label}: {company}",
                url=getattr(entry, "link", ""),
                source="SEC EDGAR",
                published=_entry_time(entry),
                kind="filing",
            ))
        time.sleep(0.4)   # polite pause between EDGAR requests
    return out


def fetch_all(feeds_path: Path = FEEDS_JSON) -> list[Article]:
    cfg   = json.loads(feeds_path.read_text())
    feeds = cfg.get("rss_feeds", [])

    # ── parallel RSS ─────────────────────────────────────────────────────────
    articles: list[Article] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(RSS_WORKERS, len(feeds))) as ex:
        futures = {ex.submit(fetch_rss, f["name"], f["url"],
                             f.get("tier", "secondary")): f["name"]
                   for f in feeds}
        for future in as_completed(futures):
            name = futures[future]
            got  = future.result()
            print(f"  {name}: {len(got)} items")
            articles.extend(got)
    print(f"  RSS complete in {time.time()-t0:.1f}s ({len(articles)} items)")

    # ── sequential EDGAR ─────────────────────────────────────────────────────
    edgar = cfg.get("edgar", {})
    if edgar.get("enabled"):
        got = fetch_edgar(edgar.get("forms", ["8-K"]), edgar["url_template"])
        print(f"  SEC EDGAR: {len(got)} items")
        articles.extend(got)

    return articles
