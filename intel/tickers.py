"""Ticker universe: load the curated seed CSV, optionally enrich from SEC.

The seed CSV is the source of truth for matching quality. Each row:
    ticker, exchange, name, aliases (pipe-separated), sector, ambiguous (0/1)

`ambiguous=1` means the company name collides with a common English word or
concept (Target, Gap, Visa, Apple...). The matcher requires extra evidence
(cashtag, exchange tag, or a finance context word) before accepting those.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TICKERS_CSV = DATA_DIR / "tickers.csv"           # single unified universe
# Legacy sources (still read as a fallback if the unified file is absent):
SEED_CSV = DATA_DIR / "tickers_seed.csv"
EXPANDED_CSV = DATA_DIR / "universe_expanded.csv"

# SEC requires a descriptive User-Agent on all requests.
SEC_HEADERS = {"User-Agent": "market-intel-prototype contact@example.com"}
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
# Exchange-labeled variant (NASDAQ/NYSE/etc.) — preferred for the unified file.
SEC_TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


@dataclass
class Company:
    ticker: str
    exchange: str
    name: str
    aliases: list[str] = field(default_factory=list)
    sector: str = ""
    ambiguous: bool = False

    @property
    def display_ticker(self) -> str:
        return f"{self.ticker}.TO" if self.exchange in ("TSX", "TSXV") else self.ticker

    def match_names(self) -> list[str]:
        """All phrases that should map to this company, longest first."""
        names = {self.name} | set(self.aliases)
        cleaned = set()
        for n in names:
            n = n.strip()
            if not n:
                continue
            cleaned.add(n)
            # Also match without trailing corporate suffixes.
            for suffix in (" Inc.", " Inc", " Corporation", " Corp.", " Corp",
                           " Company", " plc", " p.l.c.", " N.V.", " Ltd.",
                           " Ltd", " Group", " Holdings", " & Co."):
                if n.endswith(suffix) and len(n) > len(suffix) + 3:
                    cleaned.add(n[: -len(suffix)].strip())
        return sorted(cleaned, key=len, reverse=True)


def load_universe(path: Path = TICKERS_CSV) -> list[Company]:
    """Load the single unified ticker universe (data/tickers.csv).

    This file is the merge of the curated seed, the NASDAQ/NYSE bulk list, and
    the SEC full list — one row per ticker, with curated aliases and ambiguity
    flags preserved. If it's missing (e.g. first run before regeneration), fall
    back to merging the legacy seed + expanded files."""
    if path.exists():
        return _load_csv(path)
    # ---- legacy fallback ----
    curated = _load_csv(SEED_CSV)
    if not EXPANDED_CSV.exists():
        return curated
    by_ticker = {c.ticker.upper(): c for c in _load_csv(EXPANDED_CSV)}
    for c in curated:
        by_ticker[c.ticker.upper()] = c
    return list(by_ticker.values())


def _load_csv(path: Path) -> list[Company]:
    companies: list[Company] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            companies.append(Company(
                ticker=row["ticker"].strip(),
                exchange=row["exchange"].strip(),
                name=row["name"].strip(),
                aliases=[a.strip() for a in row.get("aliases", "").split("|") if a.strip()],
                sector=row.get("sector", "").strip(),
                ambiguous=row.get("ambiguous", "0").strip() == "1",
            ))
    return companies


def refresh_from_sec(out_path: Path = DATA_DIR / "tickers_sec.json") -> int:
    """Download the current SEC company list with exchange labels and save the
    long-tail map to tickers_sec.json. Run weekly from CI (SEC isn't blocked
    there). The unified data/tickers.csv is then rebuilt from this by
    consolidate_tickers.consolidate().
    """
    import requests

    # Prefer the exchange-labeled file; fall back to the name-only one.
    try:
        resp = requests.get(SEC_TICKER_EXCHANGE_URL, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        ix = {name: i for i, name in enumerate(payload["fields"])}
        slim = {}
        for row in payload["data"]:
            t = str(row[ix["ticker"]]).upper().strip()
            if not t:
                continue
            slim[t] = {"name": str(row[ix["name"]]).strip(),
                       "cik": row[ix["cik"]] if "cik" in ix else 0}
    except Exception:
        resp = requests.get(SEC_TICKER_URL, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()
        slim = {v["ticker"].upper(): {"name": v["title"], "cik": v["cik_str"]}
                for v in resp.json().values()}

    out_path.write_text(json.dumps(slim))
    return len(slim)


def load_sec_tickers(path: Path = DATA_DIR / "tickers_sec.json") -> dict:
    """Long-tail ticker->name map for cashtag/exchange-tag resolution of symbols
    that aren't otherwise matched. Now derived from the unified tickers.csv (so
    it always agrees with the universe). Falls back to the legacy SEC json, then
    to empty."""
    if TICKERS_CSV.exists():
        out = {}
        for c in _load_csv(TICKERS_CSV):
            out[c.ticker.upper()] = {"name": c.name, "cik": 0}
        return out
    if path.exists():
        return json.loads(path.read_text())
    return {}
