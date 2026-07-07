"""Live market-sentiment feed (the 5th data source).

Client data is synthetic by design (that is the compliance thesis of the
product). The *market* layer, however, is public information — so we pull it
live from real, liquid ETF proxies for each sector the book is exposed to,
derive a bullish/neutral/bearish read from the trailing return, and phrase a
short signal line the agent can reason over.

Robustness for the demo: the fetch runs once at data-generation time and is
cached into ``market_signals.json``. If the network is unavailable or the
provider rate-limits us, we fall back to a curated static feed so the demo is
never at the mercy of wifi. Toggle with ``USE_LIVE_MARKET`` in config/env.

The output shape is identical whether live or fallback::

    {"date": "2026-07-01", "sector": "tech_equities",
     "sentiment": "bullish", "signal": "Tech equities (XLK) ..."}

``sentiment`` is always one of ``bullish`` / ``neutral`` / ``bearish`` — the
frontend styles those tokens directly, so they must not change.
"""

from __future__ import annotations

import random as _random_module
from datetime import date, timedelta

from backend.config import MARKET_LOOKBACK, MARKET_SENTIMENT_WINDOW, USE_LIVE_MARKET

# ---------------------------------------------------------------------------
# The sectors the synthetic book is exposed to, mapped to a real ETF proxy.
# These are large, liquid funds — good stand-ins for "how is this sector doing".
# ---------------------------------------------------------------------------

MARKET_SECTORS = [
    "tech_equities",
    "muni_bonds",
    "emerging_markets",
    "real_estate_funds",
    "healthcare_equities",
    "energy_sector",
    "treasury_bonds",
    "private_equity",
    "commodities",
    "esg_funds",
]

SECTOR_ETFS = {
    "tech_equities": "XLK",         # Technology Select Sector
    "muni_bonds": "MUB",            # iShares National Muni Bond
    "emerging_markets": "EEM",      # iShares MSCI Emerging Markets
    "real_estate_funds": "VNQ",     # Vanguard Real Estate
    "healthcare_equities": "XLV",   # Health Care Select Sector
    "energy_sector": "XLE",         # Energy Select Sector
    "treasury_bonds": "IEF",        # iShares 7-10yr Treasury
    "private_equity": "PSP",        # Invesco Global Listed Private Equity
    "commodities": "DBC",           # Invesco DB Commodity Index
    "esg_funds": "ESGU",            # iShares ESG Aware MSCI USA
}

# ---------------------------------------------------------------------------
# Curated static fallback (used only if the live fetch is unavailable).
# Kept here as the single source of truth so generate_data and tools agree.
# ---------------------------------------------------------------------------

FALLBACK_SIGNAL_TEXT = {
    "tech_equities": "Tech sector up 12% YTD; AI-driven rally broadening to mid-caps.",
    "muni_bonds": "Municipal bond yields at 3-year highs; tax-equivalent yield attractive for HNW.",
    "emerging_markets": "EM currencies under pressure from a strong dollar; selective opportunities in India.",
    "real_estate_funds": "Commercial REIT valuations at a discount to NAV; institutional money rotating in.",
    "healthcare_equities": "Healthcare lagging; defensive positioning ahead of policy changes.",
    "energy_sector": "Energy prices stabilising; dividend yields in majors above 4%.",
    "treasury_bonds": "Yield curve normalising; front-end rates offer 5%+ with minimal duration risk.",
    "private_equity": "PE exit activity recovering; 2021-22 vintage funds approaching distributions.",
    "commodities": "Gold at all-time highs on central-bank buying; broad commodities mixed.",
    "esg_funds": "ESG fund inflows rebounding after the 2025 pause; regulatory clarity improving.",
}

FALLBACK_SENTIMENT = {
    "tech_equities": "bullish",
    "muni_bonds": "bullish",
    "emerging_markets": "bearish",
    "real_estate_funds": "bullish",
    "healthcare_equities": "bearish",
    "energy_sector": "neutral",
    "treasury_bonds": "bullish",
    "private_equity": "neutral",
    "commodities": "neutral",
    "esg_funds": "bullish",
}

# Return thresholds (over the lookback window) that define sentiment tone.
_BULLISH_ABOVE = 2.0   # % — up more than this reads bullish
_BEARISH_BELOW = -2.0  # % — down more than this reads bearish

# Nicer display labels for the signal line (handles acronyms sensibly).
_SECTOR_LABELS = {
    "esg_funds": "ESG funds",
    "reit": "REITs",
}


# ---------------------------------------------------------------------------
# Sentiment + phrasing from a raw return
# ---------------------------------------------------------------------------

def _sentiment_from_return(pct: float) -> str:
    if pct > _BULLISH_ABOVE:
        return "bullish"
    if pct < _BEARISH_BELOW:
        return "bearish"
    return "neutral"


def sector_label(sector: str) -> str:
    return _SECTOR_LABELS.get(sector, sector.replace("_", " ").capitalize())


def _signal_text(sector: str, ticker: str, pct: float, sentiment: str) -> str:
    label = sector_label(sector)
    move = f"{pct:+.1f}% over the past month"
    if sentiment == "bullish":
        tail = "momentum firmly positive — a timely opening to discuss adding on strength."
    elif sentiment == "bearish":
        tail = "under pressure — a defensive or reassurance conversation may be worthwhile."
    else:
        tail = "trading roughly flat — no strong signal either way right now."
    return f"{label} ({ticker}) {move}; {tail}"


def _change_over_window(closes: list[float], window: int) -> float:
    """Percent change over the last ``window`` points (or the full series)."""
    if len(closes) < 2:
        return 0.0
    ref = closes[-window] if len(closes) > window else closes[0]
    if ref <= 0:
        return 0.0
    return (closes[-1] - ref) / ref * 100.0


# Roughly one quarter of trading days — keeps the chart to ~3 months.
_HISTORY_POINTS = 66


def _build_detail_from_history_map(history_map: dict[str, list[dict]]) -> list[dict]:
    """Turn {sector: [{date, close}, ...]} into rich per-sector detail records."""
    detail: list[dict] = []
    for sector, ticker in SECTOR_ETFS.items():
        history = history_map.get(sector)
        if not history or len(history) < 2:
            continue
        history = history[-_HISTORY_POINTS:]
        close_vals = [h["close"] for h in history]
        pct = _change_over_window(close_vals, MARKET_SENTIMENT_WINDOW)
        sentiment = _sentiment_from_return(pct)
        detail.append({
            "sector": sector,
            "label": sector_label(sector),
            "ticker": ticker,
            "date": history[-1]["date"],
            "sentiment": sentiment,
            "signal": _signal_text(sector, ticker, pct, sentiment),
            "change_pct": round(pct, 1),
            "last_close": history[-1]["close"],
            "live": True,
            "history": history,
        })
    return detail


# ---------------------------------------------------------------------------
# Live source 1: Yahoo chart API (direct) — a single plain GET per ticker.
# Often succeeds even when the yfinance batch endpoint is being rate-limited.
# ---------------------------------------------------------------------------

def _yahoo_chart_one(ticker: str) -> list[dict] | None:
    """Fetch one ticker's daily closes from the Yahoo chart API, with a couple
    of retries. Alternates the query1/query2 hosts to dodge rate limiting."""
    import json as _json
    import time
    import urllib.request
    from datetime import datetime, timezone

    for attempt in range(3):
        host = "query1" if attempt % 2 == 0 else "query2"
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{ticker}?range=3mo&interval=1d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=MARKET_FETCH_TIMEOUT) as resp:
                payload = _json.loads(resp.read().decode("utf-8", errors="ignore"))
            result = payload["chart"]["result"][0]
            stamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]["close"]
        except Exception:  # noqa: BLE001 — network / parse / rate-limit
            time.sleep(1.5 * (attempt + 1))  # Yahoo throttles bursts; back off
            continue

        rows = []
        for ts, close in zip(stamps, quote):
            if close is None:
                continue
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            rows.append({"date": d, "close": round(float(close), 2)})
        if len(rows) >= 2:
            return rows
    return None


def _yahoo_chart_history_map() -> dict[str, list[dict]]:
    import time

    history_map: dict[str, list[dict]] = {}
    for sector, ticker in SECTOR_ETFS.items():
        rows = _yahoo_chart_one(ticker)
        if rows:
            history_map[sector] = rows
        time.sleep(1.2)  # spacing calls avoids Yahoo's burst rate limiter
    return history_map


# ---------------------------------------------------------------------------
# Live source 2: yfinance (Yahoo) — rich but occasionally rate-limited.
# ---------------------------------------------------------------------------

def _yfinance_history_map(lookback: str = MARKET_LOOKBACK) -> dict[str, list[dict]]:
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001 — yfinance not installed
        return {}

    import time

    tickers = list(SECTOR_ETFS.values())
    closes = None
    for attempt in range(3):
        try:
            raw = yf.download(
                tickers, period=lookback, interval="1d",
                auto_adjust=True, progress=False, threads=False,
            )
        except Exception:  # noqa: BLE001 — network / provider failure
            raw = None
        if raw is not None and not getattr(raw, "empty", True):
            try:
                candidate = raw["Close"].dropna(how="all")
            except Exception:  # noqa: BLE001
                candidate = None
            if candidate is not None and not candidate.empty:
                closes = candidate
                break
        if attempt < 2:
            time.sleep(4 + attempt * 6)  # 4s, then 10s
    if closes is None:
        return {}

    history_map: dict[str, list[dict]] = {}
    for sector, ticker in SECTOR_ETFS.items():
        try:
            series = closes[ticker].dropna()
        except Exception:  # noqa: BLE001 — ticker column missing
            continue
        rows = []
        for idx, val in series.items():
            d = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
            rows.append({"date": d, "close": round(float(val), 2)})
        if len(rows) >= 2:
            history_map[sector] = rows
    return history_map


# ---------------------------------------------------------------------------
# Live source 3: Stooq — free, no key. Daily CSV per symbol (may be blocked by
# a browser-verification challenge on some corporate networks).
# ---------------------------------------------------------------------------

def _stooq_history_map() -> dict[str, list[dict]]:
    import urllib.request

    history_map: dict[str, list[dict]] = {}
    for sector, ticker in SECTOR_ETFS.items():
        symbol = f"{ticker.lower()}.us"
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=MARKET_FETCH_TIMEOUT) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001 — network failure
            continue

        lines = text.strip().splitlines()
        if len(lines) < 2 or not lines[0].lower().startswith("date"):
            continue

        rows = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            d, close = parts[0], parts[4]
            try:
                rows.append({"date": d, "close": round(float(close), 2)})
            except ValueError:
                continue
        if len(rows) >= 2:
            history_map[sector] = rows
    return history_map


# ---------------------------------------------------------------------------
# Curated static fallback (synthesizes a plausible history from the sentiment
# so the charts still render when the network is unavailable).
# ---------------------------------------------------------------------------

_FALLBACK_DRIFT = {"bullish": 6.0, "bearish": -6.0, "neutral": 0.6}


def _synth_history(current_date: date, sentiment: str, rng: _random_module.Random, days: int = 63) -> list[dict]:
    target = _FALLBACK_DRIFT.get(sentiment, 0.5)
    start = 100.0
    end = start * (1 + target / 100.0)
    history = []
    for i in range(days):
        frac = i / (days - 1)
        base = start + (end - start) * frac
        close = round(base + base * rng.uniform(-0.01, 0.01), 2)
        d = (current_date - timedelta(days=(days - 1 - i))).isoformat()
        history.append({"date": d, "close": close})
    return history


def fallback_market_detail(current_date: date, rng: _random_module.Random | None = None) -> list[dict]:
    """Rich per-sector detail from the curated static feed, with a synthesized
    price history so the charts still render offline."""
    rng = rng or _random_module
    detail = []
    for sector in MARKET_SECTORS:
        sentiment = FALLBACK_SENTIMENT[sector]
        history = _synth_history(current_date, sentiment, rng)
        close_vals = [h["close"] for h in history]
        pct = _change_over_window(close_vals, MARKET_SENTIMENT_WINDOW)
        detail.append({
            "sector": sector,
            "label": sector_label(sector),
            "ticker": SECTOR_ETFS[sector],
            "date": history[-1]["date"],
            "sentiment": sentiment,
            "signal": FALLBACK_SIGNAL_TEXT[sector],
            "change_pct": round(pct, 1),
            "last_close": history[-1]["close"],
            "live": False,
            "history": history,
        })
    return detail


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def build_market_detail(current_date: date, rng: _random_module.Random | None = None) -> list[dict]:
    """Return rich per-sector detail (with price history): live ETF data when
    possible, else the curated fallback. Tries Yahoo first, then Stooq (free,
    no rate limits), then falls back. Prints which path was taken."""
    if USE_LIVE_MARKET:
        # yfinance batch is a single request (least likely to trip Yahoo's
        # burst rate limiter), so try it first; then the per-ticker chart API,
        # then Stooq.
        sources = (
            ("Yahoo/yfinance", _yfinance_history_map),
            ("Yahoo chart API", _yahoo_chart_history_map),
            ("Stooq", _stooq_history_map),
        )
        for source, fetch in sources:
            history_map = fetch()
            detail = _build_detail_from_history_map(history_map)
            if detail:
                print(f"  Market feed: LIVE via {source} — {len(detail)} sectors with real price history.")
                return detail
        print("  Market feed: live sources unavailable — using curated fallback.")
    else:
        print("  Market feed: live disabled (USE_LIVE_MARKET=0) — using curated fallback.")
    return fallback_market_detail(current_date, rng)


def feed_from_detail(detail: list[dict]) -> list[dict]:
    """Reduce rich detail to the simple sentiment feed the DB + agent consume."""
    feed = [
        {"date": d["date"], "sector": d["sector"], "sentiment": d["sentiment"], "signal": d["signal"]}
        for d in detail
    ]
    feed.sort(key=lambda s: s["date"], reverse=True)
    return feed


def build_market_feed(current_date: date, rng: _random_module.Random | None = None) -> list[dict]:
    """Backward-compatible simple feed, derived from the rich detail."""
    return feed_from_detail(build_market_detail(current_date, rng))
