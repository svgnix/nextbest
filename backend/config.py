"""Central configuration for the NextBest backend.

Deterministic where it matters: seed all RNG so the demo is reproducible.
"""

from __future__ import annotations

from pathlib import Path

SEED = 42

# Data / persistence
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nextbest.db"
DB_URL = f"sqlite:///{DB_PATH}"

CLIENTS_PATH = DATA_DIR / "clients.json"
ADVISORS_PATH = DATA_DIR / "advisors.json"
MARKET_PATH = DATA_DIR / "market_signals.json"
# Rich per-sector detail (price history for the live charts on the Market page).
MARKET_HISTORY_PATH = DATA_DIR / "market_history.json"

# Book size (the brief: ~300 clients per advisor). We generate one advisor's
# book plus a couple of colleagues so book-level analytics feel real, while
# keeping the LLM drafting cost bounded via TOP_N_DRAFT.
N_CLIENTS = 300
N_ADVISORS = 3
PRIMARY_ADVISOR_ID = "A001"

# The agent drafts (LLM) only for the highest-priority clients to save
# time/tokens; deterministic engines still score the whole book.
TOP_N_DRAFT = 20

# Time-series depth for synthetic history.
N_TRANSACTION_MONTHS = 12
N_BEHAVIOR_WEEKS = 12

# Live market data (5th data source)
# The market-sentiment feed is pulled live from real ETF proxies at data-gen
# time, then cached into market_signals.json. If the fetch fails (no network,
# rate limit), we fall back to a curated static feed so the demo never breaks.
# Set USE_LIVE_MARKET=0 in env to force the deterministic fallback.
import os

USE_LIVE_MARKET = os.getenv("USE_LIVE_MARKET", "1") not in ("0", "false", "False")
MARKET_LOOKBACK = "3mo"          # window of daily closes pulled for the charts
MARKET_SENTIMENT_WINDOW = 21     # trailing trading days used for the sentiment read
MARKET_FETCH_TIMEOUT = 12        # seconds before we give up and fall back

# RAG book copilot
# Dense embeddings run through the OpenAI-compatible proxy; without a key the
# API falls back to a deterministic HashingVectorizer over the same corpus.
RAG_INDEX_PATH = DATA_DIR / "rag_index"   # writes rag_index.npz + rag_index.json
RAG_TOP_K = 6
RAG_EMBED_BATCH = 64
