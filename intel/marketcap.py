"""Market-cap tiers — parallel fetching, 24h cache, failure suppression.

Key speed improvements over v1:
- ThreadPoolExecutor: fetches N tickers concurrently instead of one at a time
- No sleep between requests (threading handles natural rate distribution)
- Failed/delisted tickers cached for 7 days so they never retry in normal runs
- yfinance log noise suppressed
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Silence the yfinance "possibly delisted" and "no data" warnings.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

CACHE    = Path(__file__).resolve().parent.parent / "data" / "marketcap_cache.json"
TTL_OK   = 86400      # 24h for successful lookups
TTL_FAIL = 604800     # 7 days for failed/delisted — stops pointless retries
MAX_WORKERS = 12      # concurrent yfinance requests

TIERS = [
    ("mega",  200_000_000_000, float("inf")),
    ("large",  10_000_000_000, 200_000_000_000),
    ("mid",     2_000_000_000,  10_000_000_000),
    ("small",     300_000_000,   2_000_000_000),
    ("micro",               0,     300_000_000),
]


def tier_for(cap: float | None) -> str:
    if not cap or cap <= 0:
        return "unknown"
    for name, lo, hi in TIERS:
        if lo <= cap < hi:
            return name
    return "unknown"


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(c: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, separators=(",", ":")))


def _fetch_one(ticker: str) -> tuple[str, float | None]:
    """Fetch market cap for a single ticker. Returns (ticker, cap_or_None)."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        cap = getattr(info, "market_cap", None)
        if cap is None:
            cap = getattr(info, "marketCap", None)
        return ticker, cap
    except Exception:
        return ticker, None


def fetch_caps(tickers: list[str], cache: dict | None = None) -> dict:
    """Return {ticker: {cap, tier, ts}} using cache where fresh, fetching stale
    tickers in parallel. Gracefully degrades if yfinance is unavailable."""
    cache = cache if cache is not None else _load_cache()
    now = int(time.time())

    # Split: fresh (use cache), stale (need fetch)
    stale = []
    for t in tickers:
        entry = cache.get(t)
        if entry is None:
            stale.append(t)
        elif entry.get("cap") is None:
            # Failed last time — use longer TTL
            if now - entry.get("ts", 0) > TTL_FAIL:
                stale.append(t)
        elif now - entry.get("ts", 0) > TTL_OK:
            stale.append(t)

    if stale:
        try:
            import yfinance  # noqa — confirm available before spinning threads
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(stale))) as ex:
                futures = {ex.submit(_fetch_one, t): t for t in stale}
                for future in as_completed(futures):
                    t, cap = future.result()
                    cache[t] = {"cap": cap, "tier": tier_for(cap), "ts": now}
            elapsed = time.time() - t0
            hits = sum(1 for t in stale if cache[t]["cap"])
            print(f"  market caps: {hits}/{len(stale)} fetched in {elapsed:.1f}s")
        except ImportError:
            for t in stale:
                cache.setdefault(t, {"cap": None, "tier": "unknown", "ts": now})
        _save_cache(cache)

    return {t: cache.get(t, {"cap": None, "tier": "unknown", "ts": now})
            for t in tickers}


def tier_only(tickers: list[str]) -> dict:
    """Convenience: {ticker: tier_string}."""
    return {t: v["tier"] for t, v in fetch_caps(tickers).items()}
