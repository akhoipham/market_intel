"""Theme tagging: map headlines to investable themes via keyword dictionaries.

This is the 'thematic' layer. Transparent and editable on purpose — add a
theme by adding a line. Later you can layer embedding-based clustering on
top; keyword tagging stays useful as the labeled backbone.
"""
from __future__ import annotations

import re

THEMES: dict[str, list[str]] = {
    "AI & Data Centers": [
        "artificial intelligence", " ai ", "ai chip", "genai", "generative ai",
        "data center", "datacenter", "gpu", "llm", "chatbot", "openai",
        "anthropic", "machine learning", "inference", "ai model",
    ],
    "Semiconductors": [
        "semiconductor", "chip", "chips", "foundry", "wafer", "fab",
        "lithography", "node", "chipmaker",
    ],
    "GLP-1 & Obesity": [
        "glp-1", "weight loss drug", "obesity drug", "ozempic", "wegovy",
        "zepbound", "mounjaro", "semaglutide", "tirzepatide",
    ],
    "Biotech & FDA": [
        "fda", "clinical trial", "phase 1", "phase 2", "phase 3", "pdufa",
        "drug approval", "biotech", "oncology", "gene therapy",
    ],
    "EV & Batteries": [
        "electric vehicle", " ev ", "evs", "battery", "batteries", "charging",
        "lithium", "gigafactory", "autonomous driving", "self-driving",
        "robotaxi",
    ],
    "Crypto & Digital Assets": [
        "bitcoin", "crypto", "ethereum", "blockchain", "stablecoin",
        "digital asset", "btc", "etf inflow", "mining rig",
    ],
    "Rates & Fed": [
        "federal reserve", "fed ", "rate cut", "rate hike", "interest rate",
        "fomc", "powell", "inflation", "cpi", "treasury yield", "bank of canada",
    ],
    "Oil & Gas": [
        "oil", "crude", "opec", "natural gas", "lng", "barrel", "drilling",
        "pipeline", "oil sands", "shale",
    ],
    "Gold & Miners": [
        "gold", "silver", "miner", "mining", "bullion", "precious metal",
        "copper",
    ],
    "Uranium & Nuclear": [
        "uranium", "nuclear", "reactor", "smr", "enrichment",
    ],
    "Defense & Aerospace": [
        "defense contract", "missile", "pentagon", "military", "nato",
        "fighter jet", "satellite", "space launch", "rocket", "drone",
    ],
    "Cybersecurity": [
        "cybersecurity", "cyberattack", "ransomware", "data breach", "hack",
        "hacked", "zero-day", "phishing",
    ],
    "Cloud & Software": [
        "cloud", "saas", "software", "subscription", "enterprise software",
        "platform",
    ],
    "M&A & Deals": [
        "acquisition", "acquires", "acquire", "merger", "takeover", "buyout",
        "to buy", "stake in", "bid for", "go private", "spin-off", "spinoff",
    ],
    "Earnings": [
        "earnings", "quarterly results", "q1 results", "q2 results",
        "q3 results", "q4 results", "guidance", "revenue", "eps", "outlook",
        "forecast",
    ],
    "Capital Returns": [
        "dividend", "buyback", "share repurchase", "special dividend",
    ],
    "IPOs & Listings": [
        "ipo", "initial public offering", "goes public", "direct listing",
        "spac", "debut",
    ],
    "Layoffs & Restructuring": [
        "layoff", "layoffs", "job cuts", "restructuring", "cost cutting",
        "headcount", "plant closure", "store closures",
    ],
    "Legal & Regulatory": [
        "lawsuit", "antitrust", "doj", "ftc", "sec charges", "settlement",
        "probe", "investigation", "fine", "regulator", "subpoena",
    ],
    "Tariffs & Trade": [
        "tariff", "tariffs", "trade war", "export controls", "sanctions",
        "import duty", "trade deal",
    ],
    "Housing & Construction": [
        "housing", "homebuilder", "mortgage", "home sales", "construction",
        "real estate",
    ],
    "Travel & Leisure": [
        "airline", "cruise", "hotel", "bookings", "travel demand", "casino",
        "theme park",
    ],
    "Retail & Consumer": [
        "retail sales", "consumer spending", "same-store", "holiday shopping",
        "e-commerce", "foot traffic",
    ],
    "Banks & Credit": [
        "bank earnings", "loan losses", "credit card", "deposits",
        "net interest", "regional bank", "credit quality",
    ],
    "Quantum Computing": [
        "quantum", "qubit",
    ],
    "Insider & 13F Activity": [
        "insider buying", "insider selling", "13f", "stake disclosed",
        "form 4", "ceo bought", "ceo sold",
    ],
    "Short Interest & Squeezes": [
        "short squeeze", "short interest", "short seller", "heavily shorted",
        "meme stock",
    ],
}

def _kw_pattern(k: str) -> str:
    """Word-bounded pattern. Keywords with deliberate surrounding spaces
    (' ai ', ' ev ') keep those literal spaces as hard boundaries."""
    if k != k.strip():
        return re.escape(k)
    return r"(?<![\w-])" + re.escape(k) + r"(?![\w-])"


_COMPILED = {
    theme: re.compile("|".join(_kw_pattern(k) for k in kws), re.IGNORECASE)
    for theme, kws in THEMES.items()
}


def tag(text: str) -> list[str]:
    padded = f" {text} "  # so edge keywords like " ai " can hit at boundaries
    return [theme for theme, pat in _COMPILED.items() if pat.search(padded)]
