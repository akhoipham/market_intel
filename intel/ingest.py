"""Ingestion: pull headlines from RSS feeds and SEC EDGAR's live filing feed.

Design choices:
- Every feed failure is isolated (one dead feed never kills a run).
- Timestamps normalized to UTC epoch seconds.
- EDGAR is polled with the required descriptive User-Agent and gives you
  8-K (material events) and Form 4 (insider trades) titles, which the
  matcher can resolve to tickers via the company name in the filing title.
"""
from __future__ import annotations

import calendar
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import feedparser
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FEEDS_JSON = DATA_DIR / "feeds.json"

UA = {"User-Agent": "market-intel-prototype/0.1 (personal research; contact@example.com)"}


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: int  # epoch seconds UTC
    kind: str = "news"  # "news" | "filing"


def _entry_time(entry) -> int:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return calendar.timegm(t)
    return int(time.time())


def fetch_rss(name: str, url: str, timeout: int = 15) -> list[Article]:
    try:
        resp = requests.get(url, headers=UA, timeout=timeout)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"  [warn] {name}: {type(e).__name__}: {e}")
        return []
    out = []
    for entry in parsed.entries:
        title = re.sub(r"\s+", " ", getattr(entry, "title", "")).strip()
        link = getattr(entry, "link", "")
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
            # Titles look like: "8-K - APPLE INC (0000320193) (Filer)"
            title = re.sub(r"\s+", " ", getattr(entry, "title", "")).strip()
            company = re.sub(r"^\S+\s*-\s*", "", title)
            company = re.sub(r"\(\d{7,}\).*$", "", company).strip().title()
            label = {"8-K": "8-K material event", "4": "Form 4 insider filing"}.get(form, form)
            out.append(Article(
                title=f"{label}: {company}",
                url=getattr(entry, "link", ""),
                source="SEC EDGAR",
                published=_entry_time(entry),
                kind="filing",
            ))
        time.sleep(0.4)  # be polite to SEC
    return out


def fetch_all(feeds_path: Path = FEEDS_JSON) -> list[Article]:
    cfg = json.loads(feeds_path.read_text())
    articles: list[Article] = []
    for feed in cfg.get("rss_feeds", []):
        got = fetch_rss(feed["name"], feed["url"])
        print(f"  {feed['name']}: {len(got)} items")
        articles.extend(got)
    edgar = cfg.get("edgar", {})
    if edgar.get("enabled"):
        got = fetch_edgar(edgar.get("forms", ["8-K"]), edgar["url_template"])
        print(f"  SEC EDGAR: {len(got)} items")
        articles.extend(got)
    return articles
