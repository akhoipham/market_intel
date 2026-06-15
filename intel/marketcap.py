"""Market-cap tiers, fetched lazily for matched tickers and cached 24h.

Why lazy: the universe has ~4,500 tickers but only a few hundred appear in
news on any given day. We fetch caps only for tickers that actually matched,
cache them in data/marketcap_cache.json, and refresh entries older than 24h.
That keeps us to ~100-300 yfinance calls/day instead of thousands.

Tiers (USD):
    mega   >= 200B
    large  10B - 200B
    mid    2B - 10B
    small  300M - 2B
    micro  < 300M
"""
from __future__ import annotations

import json
import time
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "marketcap_cache.json"
TTL = 86400  # 24h

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
    CACHE.write_text(json.dumps(c, separators=(",", ":")))


def _yf_symbol(ticker: str) -> str:
    # Our display tickers use ".TO" for TSX, which is already yfinance's format.
    return ticker


def fetch_caps(tickers: list[str], cache: dict | None = None) -> dict:
    """Return {ticker: {cap, tier, ts}} for the given tickers, using cache
    where fresh and fetching the rest. Network failures degrade gracefully."""
    cache = cache if cache is not None else _load_cache()
    now = int(time.time())
    stale = [t for t in tickers
             if t not in cache or now - cache[t].get("ts", 0) > TTL]

    if stale:
        try:
            import yfinance as yf
            for t in stale:
                try:
                    info = yf.Ticker(_yf_symbol(t)).fast_info
                    cap = getattr(info, "market_cap", None) or info.get("market_cap")
                    cache[t] = {"cap": cap, "tier": tier_for(cap), "ts": now}
                except Exception:
                    cache[t] = {"cap": None, "tier": "unknown", "ts": now}
                time.sleep(0.15)  # be gentle
        except ImportError:
            for t in stale:
                cache.setdefault(t, {"cap": None, "tier": "unknown", "ts": now})
        _save_cache(cache)

    return {t: cache.get(t, {"cap": None, "tier": "unknown", "ts": now})
            for t in tickers}


def tier_only(tickers: list[str]) -> dict:
    """Convenience: {ticker: tier}."""
    return {t: v["tier"] for t, v in fetch_caps(tickers).items()}
