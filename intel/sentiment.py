"""Headline sentiment, tuned for financial language.

A compact Loughran-McDonald-style lexicon (general-purpose sentiment tools
misread finance: "liability", "gross", "outstanding" are neutral here, while
"miss", "cuts", "probe" are strongly negative). Scores in [-1, 1].

Deliberately simple and transparent — swap in FinBERT later if you want; the
interface (score(text) -> float) stays the same.
"""
from __future__ import annotations

import re

POSITIVE = {
    "beat": 2, "beats": 2, "tops": 2, "surge": 2, "surges": 2, "soar": 2,
    "soars": 2, "jump": 1, "jumps": 1, "rally": 2, "rallies": 2, "record": 1,
    "upgrade": 2, "upgrades": 2, "upgraded": 2, "raise": 1, "raises": 1,
    "raised": 1, "hike": 1, "hikes": 1, "strong": 1, "stronger": 1,
    "growth": 1, "grows": 1, "profit": 1, "profitable": 2, "gain": 1,
    "gains": 1, "wins": 2, "win": 1, "won": 1, "award": 1, "awarded": 2,
    "approval": 2, "approves": 2, "approved": 2, "breakthrough": 2,
    "outperform": 2, "outperforms": 2, "buy": 1, "bullish": 2, "boost": 1,
    "boosts": 1, "expands": 1, "expansion": 1, "partnership": 1, "deal": 1,
    "buyback": 1, "dividend": 1, "exceeds": 2, "accelerates": 1, "robust": 1,
    "milestone": 1, "launches": 1, "secures": 2, "lands": 1, "higher": 1,
}

NEGATIVE = {
    "miss": 2, "misses": 2, "missed": 2, "plunge": 2, "plunges": 2,
    "plummet": 2, "plummets": 2, "crash": 2, "crashes": 2, "sink": 1,
    "sinks": 1, "slump": 2, "slumps": 2, "fall": 1, "falls": 1, "fell": 1,
    "drop": 1, "drops": 1, "tumble": 2, "tumbles": 2, "slide": 1,
    "slides": 1, "downgrade": 2, "downgrades": 2, "downgraded": 2,
    "cut": 1, "cuts": 1, "slashes": 2, "slashed": 2, "weak": 1, "weaker": 1,
    "loss": 1, "losses": 1, "lawsuit": 2, "sues": 2, "sued": 2, "probe": 2,
    "investigation": 2, "investigates": 2, "recall": 2, "recalls": 2,
    "warning": 1, "warns": 1, "bankruptcy": 3, "bankrupt": 3, "default": 2,
    "fraud": 3, "scandal": 2, "layoffs": 2, "layoff": 2, "restructuring": 1,
    "halts": 2, "halted": 2, "suspends": 2, "suspended": 2, "delays": 1,
    "delayed": 1, "bearish": 2, "sell": 1, "selloff": 2, "short": 1,
    "underperform": 2, "disappointing": 2, "disappoints": 2, "concern": 1,
    "concerns": 1, "fears": 1, "fines": 2, "fined": 2, "penalty": 2,
    "breach": 2, "hack": 2, "hacked": 2, "outage": 2, "tariff": 1,
    "tariffs": 1, "ban": 1, "bans": 1, "banned": 2, "rejects": 2,
    "rejected": 2, "fails": 2, "failed": 2, "lower": 1, "lowers": 1,
    "shutdown": 2, "resigns": 1, "departs": 1, "exits": 1, "dilution": 2,
}

NEGATORS = {"not", "no", "never", "without", "won't", "doesn't", "isn't",
            "denies", "denied", "avoids", "despite"}

_WORD_RE = re.compile(r"[a-z']+")


def score(text: str) -> float:
    words = _WORD_RE.findall(text.lower())
    total, hits = 0.0, 0
    for i, w in enumerate(words):
        val = POSITIVE.get(w, 0) - NEGATIVE.get(w, 0)
        if val == 0:
            continue
        # Flip on a negator within the two preceding words.
        if any(p in NEGATORS for p in words[max(0, i - 2):i]):
            val = -val * 0.7
        total += val
        hits += 1
    if hits == 0:
        return 0.0
    # Normalize: each hit contributes up to ±3; squash to [-1, 1].
    raw = total / (hits * 1.8)
    return max(-1.0, min(1.0, raw))


def label(s: float) -> str:
    if s >= 0.25:
        return "bullish"
    if s <= -0.25:
        return "bearish"
    return "neutral"
