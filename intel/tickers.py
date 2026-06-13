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
SEED_CSV = DATA_DIR / "tickers_seed.csv"

# SEC requires a descriptive User-Agent on all requests.
SEC_HEADERS = {"User-Agent": "market-intel-prototype contact@example.com"}
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"


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


def load_universe(path: Path = SEED_CSV) -> list[Company]:
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
    """Download the full SEC ticker list (~10k US-listed names).

    These are used for cashtag/exchange-tag matching only (never bare name
    matching, since we don't have curated aliases or ambiguity flags for them).
    Run this once a week; it's a single small request.
    """
    import requests

    resp = requests.get(SEC_TICKER_URL, headers=SEC_HEADERS, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    slim = {v["ticker"].upper(): {"name": v["title"], "cik": v["cik_str"]}
            for v in raw.values()}
    out_path.write_text(json.dumps(slim))
    return len(slim)


def load_sec_tickers(path: Path = DATA_DIR / "tickers_sec.json") -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}
