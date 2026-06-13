"""Headline -> ticker entity matching.

Three tiers of evidence, strongest first:

1. Cashtags:            "$NVDA", "$SHOP.TO"          -> always accepted
2. Exchange tags:       "(NASDAQ: AAPL)", "TSX: SU"  -> always accepted
3. Company name/alias:  "Nvidia", "Royal Bank of Canada"
     - unambiguous names: accepted on a word-boundary phrase match
     - ambiguous names (Target, Gap, Visa, Apple...): accepted only if the
       headline ALSO contains a finance context word (shares, stock, earnings,
       CEO, guidance, ...) or an exchange/cashtag reference to the same ticker.

Bare tickers as plain words are never matched ("A", "IT", "ALL", "CAR", "NOW"
would destroy precision). That trade-off costs little: reputable headlines
about a company almost always include its name or a tagged ticker.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .tickers import Company

CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})(?:\.(?:TO|V|CN))?\b")
EXCHANGE_TAG_RE = re.compile(
    r"\(?\b(NYSE|NASDAQ|Nasdaq|TSX|TSXV|TSX-V|AMEX|CBOE)\s*[:\-]\s*([A-Z]{1,5}(?:\.[A-Z])?)\)?"
)

# Words that signal a headline is about a listed company, used to confirm
# ambiguous name matches.
CONTEXT_WORDS = re.compile(
    r"\b(shares?|stock|stocks|earnings|revenue|profit|guidance|forecast|"
    r"quarterly|q[1-4]\b|fy\d{2}|ipo|dividend|buyback|merger|acquisition|"
    r"acquire[sd]?|ceo|cfo|chairman|board|analyst|upgrade[sd]?|downgrade[sd]?|"
    r"price target|valuation|market cap|sec\b|filing|lawsuit|antitrust|"
    r"investors?|wall street|premarket|after.?hours|trading|nyse|nasdaq|tsx|"
    r"layoffs?|restructuring|bankruptcy|sales|outlook|results|beat|miss(es|ed)?|"
    r"recalls?|reports?|announce[sd]?|unveil(s|ed)?|demand|contracts?)\b",
    re.IGNORECASE,
)


@dataclass
class Match:
    ticker: str           # display ticker, e.g. "SHOP.TO"
    company: str
    exchange: str
    sector: str
    evidence: str         # "cashtag" | "exchange_tag" | "name" | "name+context"


class TickerMatcher:
    def __init__(self, universe: list[Company], sec_tickers: dict | None = None):
        self.by_ticker: dict[str, Company] = {}
        for c in universe:
            self.by_ticker[c.ticker.upper()] = c

        # SEC long-tail: cashtag/exchange-tag matching only.
        self.sec_tickers = sec_tickers or {}

        # Build one alternation regex per (company, ambiguity) for name matching.
        # Sort all phrases longest-first so "Bank of America" wins over "Bank".
        phrases: list[tuple[str, Company]] = []
        for c in universe:
            for phrase in c.match_names():
                if len(phrase) < 3:
                    continue  # too short to name-match safely
                phrases.append((phrase, c))
        phrases.sort(key=lambda p: len(p[0]), reverse=True)

        self._name_patterns: list[tuple[re.Pattern, Company]] = [
            (re.compile(r"(?<![\w&])" + re.escape(p) + r"(?![\w])",
                        0 if self._needs_case(p) else re.IGNORECASE), c)
            for p, c in phrases
        ]

    @staticmethod
    def _needs_case(phrase: str) -> bool:
        """Short all-caps aliases (AMD, IBM, UPS, KLA, BP...) must match
        case-sensitively or they'd hit ordinary words."""
        return phrase.isupper() and len(phrase) <= 5

    # ------------------------------------------------------------------
    def match(self, text: str) -> list[Match]:
        found: dict[str, Match] = {}
        confirmed_tickers: set[str] = set()

        # Tier 1: cashtags
        for m in CASHTAG_RE.finditer(text):
            t = m.group(1).upper()
            self._add(found, t, "cashtag", confirmed_tickers)

        # Tier 2: exchange tags
        for m in EXCHANGE_TAG_RE.finditer(text):
            t = m.group(2).upper().split(".")[0]
            self._add(found, t, "exchange_tag", confirmed_tickers)

        # Tier 3: names/aliases
        has_context = bool(CONTEXT_WORDS.search(text))
        consumed_spans: list[tuple[int, int]] = []
        for pattern, comp in self._name_patterns:
            m = pattern.search(text)
            if not m:
                continue
            # Don't double-match inside an already-matched longer phrase
            # ("Bank of Montreal" should not also fire "Montreal Bank" etc.)
            span = m.span()
            if any(s <= span[0] and span[1] <= e for s, e in consumed_spans):
                continue
            key = comp.display_ticker
            if key in found:
                consumed_spans.append(span)
                continue
            if comp.ambiguous:
                if has_context or comp.ticker.upper() in confirmed_tickers:
                    found[key] = Match(key, comp.name, comp.exchange,
                                       comp.sector, "name+context")
                    consumed_spans.append(span)
                # else: skip — "apple pie recipe" stays unmatched
            else:
                found[key] = Match(key, comp.name, comp.exchange,
                                   comp.sector, "name")
                consumed_spans.append(span)

        return list(found.values())

    def _add(self, found: dict, raw_ticker: str, evidence: str,
             confirmed: set[str]) -> None:
        comp = self.by_ticker.get(raw_ticker)
        if comp:
            key = comp.display_ticker
            found.setdefault(key, Match(key, comp.name, comp.exchange,
                                        comp.sector, evidence))
            confirmed.add(raw_ticker)
        elif raw_ticker in self.sec_tickers:
            info = self.sec_tickers[raw_ticker]
            found.setdefault(raw_ticker, Match(raw_ticker, info["name"],
                                               "US", "", evidence))
            confirmed.add(raw_ticker)
