"""Headline sentiment, tuned for financial language.

Returns a score in [-1, 1] plus structural awareness of two failure modes
that pure lexicons get wrong:

1. VOCABULARY GAPS — "slid", "slipped", "risk", "headwind" carry clear
   direction but generic lexicons miss them. The lexicon below is expanded
   to cover the price-move and analyst verbs that dominate market headlines.

2. ATTRIBUTION / COMMENTARY — "Morgan Stanley sees market rally broadening"
   is about the MARKET, not about Morgan Stanley. When a matched company is
   merely the SOURCE of an opinion (a strategist/analyst being quoted), the
   sentiment of the sentence does not attach to that company's stock. The
   `analyze()` function detects this and returns is_commentary=True so the
   pipeline can neutralize the per-ticker score.

The public interface stays simple:
    score(text) -> float                      (unchanged, back-compatible)
    analyze(text) -> {score, label, is_commentary}
"""
from __future__ import annotations

import re

POSITIVE = {
    # earnings / results
    "beat": 2, "beats": 2, "tops": 2, "topped": 2, "exceeds": 2, "exceeded": 2,
    "surpass": 2, "surpasses": 2, "surpassed": 2,
    # price moves up
    "surge": 2, "surges": 2, "surged": 2, "soar": 2, "soars": 2, "soared": 2,
    "jump": 1, "jumps": 1, "jumped": 1, "rally": 2, "rallies": 2, "rallied": 2,
    "rallying": 2, "climb": 1, "climbs": 1, "climbed": 1, "rise": 1, "rises": 1,
    "rose": 1, "gain": 1, "gains": 1, "gained": 1, "spike": 1, "spikes": 1,
    "spiked": 1, "pop": 1, "pops": 1, "popped": 1, "rebound": 1, "rebounds": 1,
    "rebounded": 1, "advance": 1, "advances": 1, "advanced": 1, "higher": 1,
    "rallied": 2, "outperform": 2, "outperforms": 2, "outperformed": 2,
    # analyst / rating
    "upgrade": 2, "upgrades": 2, "upgraded": 2, "raise": 1, "raises": 1,
    "raised": 1, "hike": 1, "hikes": 1, "hiked": 1, "buy": 1, "overweight": 2,
    "bullish": 2, "boost": 1, "boosts": 1, "boosted": 1, "initiate": 1,
    "reiterates": 1, "maintains": 1,
    # business
    "record": 1, "strong": 1, "stronger": 1, "strength": 1, "growth": 1,
    "grows": 1, "grew": 1, "growing": 1, "profit": 1, "profitable": 2,
    "profits": 1, "wins": 2, "win": 1, "won": 1, "award": 1, "awards": 1,
    "awarded": 2, "approval": 2, "approves": 2, "approved": 2, "approve": 2,
    "breakthrough": 2, "expands": 1, "expand": 1, "expansion": 1, "expanded": 1,
    "partnership": 1, "partner": 1, "deal": 1, "buyback": 1, "buybacks": 1,
    "dividend": 1, "accelerates": 1, "accelerate": 1, "accelerating": 1,
    "robust": 1, "milestone": 1, "launches": 1, "launch": 1, "launched": 1,
    "secures": 2, "secure": 1, "secured": 2, "lands": 1, "landed": 1,
    "optimistic": 2, "upbeat": 2, "confident": 1, "momentum": 1, "demand": 1,
    "recovery": 1, "recovers": 1, "recovered": 1, "improve": 1, "improves": 1,
    "improved": 1, "improving": 1, "broadening": 1, "broadens": 1, "tailwind": 2,
    "tailwinds": 2, "raises guidance": 3, "beat estimates": 3,
    # market-level upside moves (were missing — "Chip Stocks Soaring to New
    # Highs" scored flat-neutral because "soaring"/"highs" weren't in the lexicon)
    "soaring": 2, "record high": 2, "record highs": 2, "new high": 2,
    "new highs": 2, "all-time high": 2, "all-time highs": 2, "fresh highs": 2,
    "52-week high": 1,
    # guidance / outlook raises (only "raises guidance" existed; "-ing" and
    # "outlook"/"forecast" variants were missed, e.g. "Raising ... Outlook")
    "raising": 1, "raises outlook": 3, "raising guidance": 3, "raising outlook": 3,
    "raised guidance": 3, "raised outlook": 3, "lifts guidance": 3,
    "lifts outlook": 3, "boosts guidance": 3, "boosts outlook": 3,
    "hikes guidance": 3, "raises forecast": 3, "ups guidance": 3,
    "tops estimates": 3, "beats estimates": 3, "above estimates": 2,
    "tops expectations": 2,
}

NEGATIVE = {
    # earnings / results
    "miss": 2, "misses": 2, "missed": 2, "disappoint": 2, "disappoints": 2,
    "disappointed": 2, "disappointing": 2, "shortfall": 2,
    # price moves down
    "plunge": 2, "plunges": 2, "plunged": 2, "plummet": 2, "plummets": 2,
    "plummeted": 2, "crash": 2, "crashes": 2, "crashed": 2, "sink": 1,
    "sinks": 1, "sank": 2, "slump": 2, "slumps": 2, "slumped": 2, "fall": 1,
    "falls": 1, "fell": 1, "falling": 1, "drop": 1, "drops": 1, "dropped": 1,
    "tumble": 2, "tumbles": 2, "tumbled": 2, "slide": 1, "slides": 1,
    "slid": 2, "sliding": 1, "slip": 1, "slips": 1, "slipped": 1, "dip": 1,
    "dips": 1, "dipped": 1, "decline": 1, "declines": 1, "declined": 1,
    "sell-off": 2, "selloff": 2, "lower": 1, "lowers": 1, "lowered": 1,
    "weakness": 2, "retreat": 1, "retreats": 1, "retreated": 1, "drag": 1,
    "drags": 1, "dragged": 1,
    # analyst / rating
    "downgrade": 2, "downgrades": 2, "downgraded": 2, "cut": 1, "cuts": 1,
    "slash": 2, "slashes": 2, "slashed": 2, "sell": 1, "underweight": 2,
    "bearish": 2, "underperform": 2, "underperforms": 2, "underperformed": 2,
    "reduces": 1, "trim": 1, "trims": 1, "trimmed": 1,
    # risk / trouble
    "weak": 1, "weaker": 1, "loss": 1, "losses": 1, "lawsuit": 2, "sue": 2,
    "sues": 2, "sued": 2, "suing": 2, "litigation": 2, "class action": 2,
    "probe": 2, "investigation": 2, "investigates": 2,
    "investigated": 2, "recall": 2, "recalls": 2, "recalled": 2, "warning": 1,
    "warns": 1, "warned": 1, "bankruptcy": 3, "bankrupt": 3, "default": 2,
    "fraud": 3, "scandal": 2, "layoffs": 2, "layoff": 2, "restructuring": 1,
    "halts": 2, "halted": 2, "suspends": 2, "suspended": 2, "delays": 1,
    "delay": 1, "delayed": 1, "concern": 1, "concerns": 1, "fears": 1,
    "fear": 1, "fines": 2, "fined": 2, "fine": 1, "penalty": 2, "breach": 2,
    "hack": 2, "hacked": 2, "outage": 2, "tariff": 1, "tariffs": 1, "ban": 1,
    "bans": 1, "banned": 2, "rejects": 2, "rejected": 2, "reject": 2,
    "fails": 2, "fail": 1, "failed": 2, "failure": 2, "shutdown": 2,
    "resigns": 1, "resigned": 1, "departs": 1, "departed": 1, "exits": 1,
    "exited": 1, "dilution": 2, "risky": 2, "threat": 1,
    # NOTE: bare "risk"/"risks" intentionally NOT listed — they are neutral in
    # finance ("risk rating", "risk management", "risk-adjusted", "de-risk").
    # Genuinely negative usages ("downside risk") are caught by phrases below.
    "downside risk": 2, "regulatory risk": 1, "risk-off": 2,
    "threats": 1, "threatens": 1, "headwind": 2, "headwinds": 2, "pressure": 1,
    "pressures": 1, "pressured": 1, "struggle": 2, "struggles": 2,
    "struggled": 2, "struggling": 2, "woes": 2, "slowdown": 2, "slowing": 1,
    "slows": 1, "stalls": 1, "stalled": 1, "glut": 1, "oversupply": 2,
    "cuts guidance": 3, "misses estimates": 3, "profit warning": 3,
}

NEGATORS = {"not", "no", "never", "without", "won't", "wont", "doesn't",
            "doesnt", "isn't", "isnt", "denies", "denied", "avoids", "avoided",
            "despite", "fails to", "unlikely"}

# ── Commentary / attribution detection ──────────────────────────────────────
# Verbs of opinion: when a company name is the subject of one of these, the
# company is the SOURCE of a view, not the subject of news.
COMMENTARY_VERBS = re.compile(
    r"\b(sees?|saw|expects?|forecasts?|predicts?|projects?|believes?|"
    r"says?|said|argues?|warns? that|notes?|thinks?|estimates?|"
    r"recommends?|advises?|calls? for|anticipates?|flags?|highlights?|"
    r"is bullish on|is bearish on|weighs? in|comments?)\b",
    re.IGNORECASE,
)
# Strategist/analyst role words near a name strengthen the commentary signal.
ROLE_WORDS = re.compile(
    r"\b(strategist|analyst|economist|cio|chief|head of|desk|research|"
    r"wilson|hartnett|kostin)\b",  # common named strategists; extend freely
    re.IGNORECASE,
)
# Words that mean the headline is about the broad market, not one stock.
MARKET_SUBJECT = re.compile(
    r"\b(market|markets|stocks|equities|s&p|nasdaq|dow|index|sector|"
    r"economy|rates|yields|fed|investors|sentiment|rally|selloff)\b",
    re.IGNORECASE,
)

# Strong negative signals that should DOMINATE a headline regardless of any
# positive words present. "Shareholders sue Microsoft over AI growth story"
# is bearish even though "growth" is positive — the lawsuit is the story.
DOMINANT_NEGATIVE = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|litigation|fraud|scandal|probe|investigation|"
    r"bankrupt(cy)?|default|recall(s|ed)?|halt(s|ed)?|fines?|fined|penalty|"
    r"breach|hack(ed)?|subpoena|indicted|indictment|charges?|misconduct|"
    r"resign(s|ed)?|plunge[sd]?|plummet(s|ed)?|crash(es|ed)?)\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[a-z'&-]+")


def _raw_score(text: str) -> float:
    low = text.lower()

    # Dominant negatives floor the score regardless of positive words present.
    dominant = bool(DOMINANT_NEGATIVE.search(text))

    total, hits = 0.0, 0

    # multi-word phrases first (higher weight, more specific)
    for phrase, val in list(POSITIVE.items()) + [(p, -v) for p, v in NEGATIVE.items()]:
        if " " in phrase and phrase in low:
            total += val
            hits += 1

    words = _WORD_RE.findall(low)
    for i, w in enumerate(words):
        val = POSITIVE.get(w, 0) - NEGATIVE.get(w, 0)
        if val == 0:
            continue
        if any(p in NEGATORS for p in words[max(0, i - 2):i]):
            val = -val * 0.7
        total += val
        hits += 1

    if hits == 0:
        return -0.6 if dominant else 0.0
    s = max(-1.0, min(1.0, total / (hits * 1.8)))
    # A dominant negative signal caps the score firmly in bearish territory,
    # even if positive words ("growth", "AI") would otherwise lift it.
    if dominant:
        s = min(s, -0.5)
    return s


def is_commentary(text: str) -> bool:
    """True when the headline is market/sector commentary attributed to a
    person or firm, rather than news about a specific company's own events."""
    has_verb = bool(COMMENTARY_VERBS.search(text))
    has_market_subject = bool(MARKET_SUBJECT.search(text))
    has_role = bool(ROLE_WORDS.search(text))
    # Commentary if someone is voicing a view AND the subject is the market,
    # OR a named strategist/analyst is clearly the source.
    return (has_verb and has_market_subject) or (has_role and has_verb)


def analyze(text: str, source: str = "") -> dict:
    opinion = is_opinion(text, source)
    s = _blended_raw(text)
    commentary = is_commentary(text)
    # Opinion pieces and market commentary don't attach sentiment to a ticker.
    eff = 0.0 if (commentary or opinion) else s
    return {"score": round(eff, 3), "raw": round(s, 3),
            "label": label(eff), "is_commentary": commentary,
            "is_opinion": opinion}


def score(text: str, source: str = "") -> float:
    """Back-compatible: returns the effective score."""
    return analyze(text, source)["score"]


def label(s: float) -> str:
    if s >= 0.25:
        return "bullish"
    if s <= -0.25:
        return "bearish"
    return "neutral"

# ── VADER blend + opinion detection (added layer) ───────────────────────────
# VADER understands sentence structure (negation, intensifiers, "but" clauses,
# punctuation) that the keyword lexicon alone misses. We blend the two:
# finance lexicon knows domain words ("beat", "downgrade"); VADER knows English.
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
except Exception:
    _VADER = None

# Sources whose question-headlines are editorial/opinion, not hard news.
OPINION_SOURCES = re.compile(
    r"seeking ?alpha|motley ?fool|fool\.com|zacks|investorplace|"
    r"benzinga|the street|thestreet", re.IGNORECASE)

# Headline patterns that signal opinion/clickbait rather than an event.
OPINION_PATTERNS = re.compile(
    r"\?\s*$|"                                  # ends with a question mark
    r"^\s*(is|are|should|could|will|why|how|"
    r"can|does|do|here'?s why|the case for|"
    r"is it time|too late|better buy|"
    r"vs\.?|versus)\b", re.IGNORECASE)


def is_opinion(text: str, source: str = "") -> bool:
    """True for editorial/question headlines that shouldn't drive sentiment."""
    src_op = bool(OPINION_SOURCES.search(source))
    pat_op = bool(OPINION_PATTERNS.search(text.strip()))
    # A question from any source is opinion; a non-question from an opinion
    # source (e.g. an SA news brief) is still treated as news.
    return pat_op or (src_op and "?" in text)


def _blended_raw(text: str) -> float:
    """Combine finance lexicon score with VADER's sentence-level score."""
    lex = _raw_score(text)
    if _VADER is None:
        return lex
    v = _VADER.polarity_scores(text)["compound"]  # already in [-1, 1]
    # Weight the finance lexicon more (it knows the domain), VADER as support.
    blended = 0.65 * lex + 0.35 * v
    return max(-1.0, min(1.0, blended))
