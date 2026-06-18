"""Consolidate all ticker sources into the single unified data/tickers.csv.

Merge priority (highest wins): curated seed > expanded (NASDAQ/NYSE) > SEC long-tail.
A final noise-word pass flags any single-common-word company name as ambiguous,
regardless of source, so names like "News"/"Team"/"NEWS CORP" can never bare-match
ordinary prose (they still match via cashtag, exchange tag, or finance context).

Run standalone (`python -m intel.consolidate_tickers`) or via run.py refresh-tickers,
which first pulls a current SEC list from CI.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_CSV = DATA_DIR / "tickers_seed.csv"
EXPANDED_CSV = DATA_DIR / "universe_expanded.csv"
SEC_JSON = DATA_DIR / "tickers_sec.json"
OUT_CSV = DATA_DIR / "tickers.csv"

FIELDS = ["ticker", "exchange", "name", "aliases", "sector", "ambiguous"]

# Tokens that don't make a name distinctive on their own.
_SUFFIX = {"corp", "inc", "co", "ltd", "plc", "group", "the", "holdings",
           "corporation", "company", "sa", "nv", "ag", "class", "a", "b", "c"}
# Single-word names matching these bare-match ordinary prose -> force ambiguous.
_COMMON = set("""news team group global power energy systems holdings capital industries
technologies financial international resources solutions company corporation partners
enterprises services one first open box fox root stem compass pool gap target visa ford
apple now main sound wing peak arch core edge flow grid loop node data cloud metal gold
oil gas sun star wave atlas summit union alliance liberty heritage legacy pioneer frontier
horizon beacon match life health home work play build grow rise leap shift bank trust fund""".split())


def _is_noise_word_name(name: str) -> bool:
    words = re.sub(r"[^\w\s]", " ", name).split()
    base = [w for w in words if w.lower() not in _SUFFIX]
    return len(base) == 1 and base[0].lower() in _COMMON


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def consolidate(out_path: Path = OUT_CSV) -> int:
    merged: dict[str, dict] = {}

    # Layer 3 (lowest): SEC long-tail.
    if SEC_JSON.exists():
        sec = json.loads(SEC_JSON.read_text())
        for t, info in sec.items():
            T = t.upper()
            merged[T] = {"ticker": T, "exchange": "US", "name": info["name"],
                         "aliases": "", "sector": "", "ambiguous": "0"}

    # Layer 2: expanded NASDAQ/NYSE.
    for r in _read_csv(EXPANDED_CSV):
        T = r["ticker"].upper()
        merged[T] = {k: (r.get(k, "") or "").strip() for k in FIELDS}
        merged[T]["ticker"] = T

    # Layer 1 (highest): curated seed — best names, aliases, TSX 60.
    for r in _read_csv(SEED_CSV):
        T = r["ticker"].upper()
        merged[T] = {k: (r.get(k, "") or "").strip() for k in FIELDS}
        merged[T]["ticker"] = T

    # Final pass: force ambiguous on noise-word names from ANY layer, UNLESS the
    # row carries curated aliases (an alias means we trust the curation).
    flagged = 0
    for row in merged.values():
        if row["ambiguous"] != "1" and not row["aliases"] and _is_noise_word_name(row["name"]):
            row["ambiguous"] = "1"
            flagged += 1

    rows = sorted(merged.values(), key=lambda r: r["ticker"])
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    n = consolidate()
    print(f"Wrote {OUT_CSV} with {n} tickers")
