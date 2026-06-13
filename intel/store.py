"""SQLite store + the end-to-end pipeline (ingest -> match -> score -> tag).

Articles are deduped on URL and on a normalized-title hash (wire stories get
syndicated under many URLs). Every processed row keeps its ticker matches,
themes, and sentiment so the dashboard is a pure read.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from . import sentiment, themes
from .ingest import Article, fetch_all
from .matcher import TickerMatcher
from .tickers import load_sec_tickers, load_universe

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "intel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    url_hash TEXT UNIQUE,
    title_hash TEXT,
    title TEXT,
    url TEXT,
    source TEXT,
    kind TEXT,
    published INTEGER,
    fetched INTEGER,
    sentiment REAL,
    tickers TEXT,   -- JSON list of {ticker, company, exchange, sector, evidence}
    themes TEXT     -- JSON list of theme names
);
CREATE INDEX IF NOT EXISTS idx_published ON articles(published);
CREATE INDEX IF NOT EXISTS idx_title_hash ON articles(title_hash);
"""


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:120]


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def process_articles(articles: list[Article],
                     conn: sqlite3.Connection) -> tuple[int, int]:
    """Match, score, tag and insert. Returns (inserted, skipped_dupes)."""
    matcher = TickerMatcher(load_universe(), load_sec_tickers())
    now = int(time.time())
    inserted = skipped = 0

    seen_titles = {row[0] for row in
                   conn.execute("SELECT title_hash FROM articles")}

    for a in articles:
        url_hash = hashlib.sha1(a.url.encode()).hexdigest()
        title_hash = hashlib.sha1(_norm_title(a.title).encode()).hexdigest()
        if title_hash in seen_titles:
            skipped += 1
            continue
        matches = matcher.match(a.title)
        row = (
            url_hash, title_hash, a.title, a.url, a.source, a.kind,
            a.published, now,
            sentiment.score(a.title),
            json.dumps([m.__dict__ for m in matches]),
            json.dumps(themes.tag(a.title)),
        )
        try:
            conn.execute(
                "INSERT INTO articles (url_hash, title_hash, title, url, source,"
                " kind, published, fetched, sentiment, tickers, themes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
            inserted += 1
            seen_titles.add(title_hash)
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    return inserted, skipped


def run_pipeline(db_path: Path = DB_PATH) -> None:
    print("Fetching feeds...")
    articles = fetch_all()
    print(f"Fetched {len(articles)} raw items. Processing...")
    conn = connect(db_path)
    inserted, skipped = process_articles(articles, conn)
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    print(f"Inserted {inserted} new, skipped {skipped} duplicates. "
          f"DB now holds {total} articles.")
    conn.close()


def export_window(conn: sqlite3.Connection, max_age_days: int = 400) -> list[dict]:
    """Everything the dashboard needs, newest first."""
    cutoff = int(time.time()) - max_age_days * 86400
    rows = conn.execute(
        "SELECT title, url, source, kind, published, sentiment, tickers, themes"
        " FROM articles WHERE published >= ? ORDER BY published DESC", (cutoff,))
    out = []
    for title, url, source, kind, published, sent, tickers, theme_list in rows:
        out.append({
            "t": title, "u": url, "s": source, "k": kind, "p": published,
            "sn": round(sent, 3),
            "tk": json.loads(tickers), "th": json.loads(theme_list),
        })
    return out
