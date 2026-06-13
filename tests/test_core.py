"""Tests for the matching, sentiment and theme engines. Run: python -m tests.test_core"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intel.matcher import TickerMatcher
from intel.tickers import load_universe
from intel import sentiment, themes

matcher = TickerMatcher(load_universe())

CASES = [
    # (headline, expected tickers, forbidden tickers)
    ("Nvidia beats earnings estimates, raises full-year guidance",
     {"NVDA"}, set()),
    ("$AAPL slides 3% premarket after iPhone shipment data",
     {"AAPL"}, set()),
    ("Apple pie named official dessert of Vermont county fair",
     set(), {"AAPL"}),
    ("Apple shares fall as analysts cut price targets",
     {"AAPL"}, set()),
    ("Target misses quarterly sales estimates, shares drop",
     {"TGT"}, set()),
    ("Police target gap in downtown fencing after break-ins",
     set(), {"TGT", "GAP"}),
    ("Gap Inc. earnings top estimates on strong Old Navy sales",
     {"GAP"}, set()),
    ("Visa stock hits record high on payment volume growth",
     {"V"}, set()),
    ("Tourist visa rules tightened ahead of summer season",
     set(), {"V"}),
    ("Shopify (TSX: SHOP) announces new AI checkout features",
     {"SHOP.TO"}, set()),
    ("Royal Bank of Canada lifts dividend after record quarter",
     {"RY.TO"}, set()),
    ("Bank of America upgrades Micron to Buy",
     {"BAC", "MU"}, set()),
    ("Ford recalls 200,000 vehicles over braking issue",
     {"F"}, set()),
    ("Harrison Ford to star in new thriller",
     set(), {"F"}),
    ("It's all about timing, says now-famous chef",
     set(), {"IT", "ALL", "NOW"}),
    ("Caterpillar reports stronger construction equipment demand",
     {"CAT"}, set()),
    ("Rare caterpillar species discovered in national park",
     set(), {"CAT"}),
    ("(NASDAQ: SMCI) Super Micro announces 10-for-1 stock split",
     {"SMCI"}, set()),
    ("Cameco and Brookfield complete Westinghouse uranium deal",
     {"CCO.TO", "BN.TO"}, set()),
    ("Eli Lilly's Zepbound shows heart benefits in new trial",
     {"LLY"}, set()),
    ("AMD unveils new MI400 accelerator to challenge Nvidia",
     {"AMD", "NVDA"}, set()),
    ("Amd is a common abbreviation in medical texts",
     set(), {"AMD"}),  # case-sensitive short alias
    ("8-K material event: Tesla Inc",
     {"TSLA"}, set()),
    ("Couche-Tard walks away from Seven & i takeover talks",
     {"ATD.TO"}, set()),
    ("Disney and Netflix battle over streaming sports rights",
     {"DIS", "NFLX"}, set()),
]

SENT_CASES = [
    ("Nvidia beats earnings, raises guidance", "bullish"),
    ("Boeing shares plunge after FAA opens investigation", "bearish"),
    ("Apple to host developer conference in June", "neutral"),
    ("Target misses on revenue, cuts outlook", "bearish"),
]

THEME_CASES = [
    ("Microsoft to spend $80 billion on AI data centers", {"AI & Data Centers"}),
    ("Eli Lilly's GLP-1 pill shows strong weight loss results",
     {"GLP-1 & Obesity"}),
    ("Exxon and Chevron lift output as OPEC holds cuts", {"Oil & Gas"}),
    ("Couche-Tard drops takeover bid", {"M&A & Deals"}),
]


def run():
    failures = 0
    for headline, expected, forbidden in CASES:
        got = {m.ticker for m in matcher.match(headline)}
        missing = expected - got
        wrong = forbidden & got
        if missing or wrong:
            failures += 1
            print(f"FAIL: {headline!r}")
            if missing:
                print(f"      missing: {missing}, got: {got or '{}'}")
            if wrong:
                print(f"      false positive: {wrong}")
    for text, expected in SENT_CASES:
        got = sentiment.label(sentiment.score(text))
        if got != expected:
            failures += 1
            print(f"FAIL sentiment: {text!r} -> {got}, expected {expected}")
    for text, expected in THEME_CASES:
        got = set(themes.tag(text))
        if not expected <= got:
            failures += 1
            print(f"FAIL theme: {text!r} -> {got}, expected ⊇ {expected}")
    total = len(CASES) + len(SENT_CASES) + len(THEME_CASES)
    print(f"\n{total - failures}/{total} checks passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
