"""Seed the SQLite database from the synthetic JSON files.

Regenerates the JSON (if missing) and loads advisors, clients, and the
market-sentiment feed into a fresh DB. Run once before the pipeline:

    python -m backend.seed
"""

from __future__ import annotations

import json

from backend import generate_data
from backend.config import ADVISORS_PATH, CLIENTS_PATH, MARKET_PATH
from backend.db import Advisor, Client, MarketSignal, SessionLocal, reset_db


def _ensure_json() -> None:
    if not (CLIENTS_PATH.exists() and ADVISORS_PATH.exists() and MARKET_PATH.exists()):
        print("Synthetic JSON missing — generating...")
        generate_data.main()


def _load_json(path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def seed() -> None:
    _ensure_json()

    advisors = _load_json(ADVISORS_PATH)
    clients = _load_json(CLIENTS_PATH)
    market = _load_json(MARKET_PATH)

    reset_db()
    db = SessionLocal()
    try:
        for a in advisors:
            db.add(Advisor(**a))

        for c in clients:
            db.add(Client(
                client_id=c["client_id"],
                advisor_id=c["advisor_id"],
                name=c["name"],
                email=c.get("email"),
                portfolio_value=c["portfolio_value"],
                portfolio_change_pct=c["portfolio_change_pct"],
                withdrawals_last_90_days=c["withdrawals_last_90_days"],
                account_tenure_years=c["account_tenure_years"],
                days_since_last_contact=c["days_since_last_contact"],
                login_frequency_change=c["login_frequency_change"],
                email_open_rate_change=c["email_open_rate_change"],
                last_contact_note=c.get("last_contact_note", ""),
                life_events=c.get("life_events", []),
                life_events_detail=c.get("life_events_detail", []),
                market_exposure=c.get("market_exposure", []),
                call_log=c.get("call_log", []),
                transactions=c.get("transactions", []),
                digital_behavior=c.get("digital_behavior", []),
            ))

        for m in market:
            db.add(MarketSignal(
                date=m["date"],
                sector=m["sector"],
                sentiment=m["sentiment"],
                signal=m["signal"],
            ))

        db.commit()
        print(f"Seeded {len(advisors)} advisors, {len(clients)} clients, "
              f"{len(market)} market signals into the DB.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
