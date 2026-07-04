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
