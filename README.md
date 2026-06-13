# SIGNAL/DESK — thematic market intelligence prototype

A working prototype of the core loop for a bottom-up, thematic equity screener:

    RSS wires + SEC EDGAR  →  ticker matching  →  sentiment  →  theme tagging  →  dashboard

Everything is free data. No API keys required.

**Full setup, scheduling, and free-hosting instructions: [`docs/OPERATING-GUIDE.md`](docs/OPERATING-GUIDE.md)**

## Quick start

```bash
pip install -r requirements.txt

# See it working immediately with bundled sample headlines:
python run.py demo
# then open dashboard.html in a browser

# Run it for real (internet required):
python run.py refresh-tickers     # one-time: SEC's full ticker list (~10k names)
python run.py fetch build         # pull feeds, process, regenerate dashboard
```

Put `python run.py fetch build` on a cron (every 15–30 min is plenty and polite)
and the dashboard stays fresh. SQLite accumulates history, so the 1W/1M windows
fill up over time.

## What's inside

| File | Role |
|---|---|
| `intel/matcher.py` | Headline → ticker matching. Three evidence tiers: cashtags, exchange tags `(NASDAQ: AAPL)`, curated name/alias. Ambiguous names (Target, Gap, Visa, Apple, Ford…) require a finance context word. Bare tickers are never matched as plain words. |
| `intel/sentiment.py` | Finance-tuned lexicon scorer with negation handling. Swap in FinBERT later; interface stays `score(text) -> float`. |
| `intel/themes.py` | ~28 investable themes via word-bounded keyword dictionaries. Add a theme by adding a line. |
| `intel/ingest.py` | RSS + EDGAR (8-K and Form 4 live feeds) with polite headers and per-feed failure isolation. |
| `intel/store.py` | SQLite store, dedup on URL hash *and* normalized-title hash (kills wire syndication dupes), pipeline orchestration. |
| `intel/dashboard.py` | Generates a single self-contained `dashboard.html` — time windows (1H/8H/1D/3D/1W/1M/3M/6M/YTD/1Y), clickable theme tape, sortable ticker leaderboard, headline tape, free-text filter. Works offline. |
| `data/tickers_seed.csv` | The curated NYSE/NASDAQ/TSX universe with aliases and ambiguity flags. **This file is where matching quality lives — grow it.** |
| `data/feeds.json` | Feed list. Edit freely; a dead feed never breaks a run. |
| `tests/test_core.py` | 33 checks including the trap cases ("Apple pie", "Harrison Ford", "tourist visa"). |

## Design decisions you may want to revisit

- **Precision over recall.** A name like "Metro" or "Loblaw" only matches with
  finance context. You'll miss a few headlines; you won't pollute the leaderboard.
- **Headline-only sentiment.** Cheap and surprisingly serviceable. Next step:
  fetch article lead paragraphs for matched headlines only (keeps volume small).
- **Keyword themes, not embeddings.** Transparent and instantly editable.
  When you add embedding clustering later, keep this as the labeled backbone.
- **Static HTML, no server.** One file to host anywhere (GitHub Pages, S3).
  When you outgrow it, the `export_window()` JSON is already your API payload.

## Natural next modules (in the order I'd build them)

1. **Insider clusters**: you're already ingesting Form 4 titles; parse the
   filing XML to get buy/sell, role, and dollar value, then flag clustered buys.
2. **Catalyst calendar**: earnings dates via free APIs, FDA PDUFA dates, lockup
   expirations from S-1s.
3. **EOD prices**: attach 1D/1W returns to the leaderboard so "mentions up +
   price flat" anomalies pop out.
4. **Stocktwits message counts** per matched ticker for the social layer
   (pre-tagged with tickers — no entity matching needed).

## Caveats

- Free RSS endpoints change; if a feed dies, replace its URL in `feeds.json`.
- Personal/research use. Check each source's terms before any public redeployment.
- Sentiment on headlines is a coarse signal — treat it as triage, not truth.
