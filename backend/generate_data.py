"""Component 1 — Synthetic data generator.

Generates a realistic advisor book covering all six Apex data sources:
client profiles, transaction history, advisor call logs, life events,
market sentiment, and digital behaviour. Writes three JSON files under
backend/data/ (clients, advisors, market signals). Seeded for reproducibility.

Each client keeps the flat scalar signals the deterministic engines consume
(login_frequency_change, ...) AND richer time-series (monthly transactions,
weekly digital behaviour, dated life events) that the multi-page UI charts.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta

from faker import Faker

from backend.config import (
    ADVISORS_PATH,
    CLIENTS_PATH,
    MARKET_HISTORY_PATH,
    MARKET_PATH,
    N_ADVISORS,
    N_BEHAVIOR_WEEKS,
    N_CLIENTS,
    N_TRANSACTION_MONTHS,
    PRIMARY_ADVISOR_ID,
    SEED,
)
from backend.market_data import MARKET_SECTORS, build_market_detail, feed_from_detail

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)

# Fixed "today" so the whole demo (dates, gaps, trends) is reproducible.
CURRENT_DATE = date(2026, 7, 1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIFE_EVENT_OPTIONS = [
    "property_purchase",
    "child_education",
    "inheritance",
    "retirement",
    "business_sale",
    "divorce_settlement",
    "relocation",
]

# Market sectors + the curated fallback text/sentiment now live in
# backend/market_data.py (single source of truth). MARKET_SECTORS is imported
# above and reused here for call-log flavour and per-client exposures.

CALL_NOTE_TEMPLATES_ENGAGED = [
    "Discussed portfolio rebalancing toward {sector}. Client enthusiastic.",
    "Reviewed quarterly performance. Client satisfied with returns.",
    "Client asked about {sector} exposure — exploring options.",
    "Routine check-in. Client mentioned upcoming {event}.",
    "Walked through tax-loss harvesting strategy. Client agreed to proceed.",
]

CALL_NOTE_TEMPLATES_DISENGAGED = [
    "Left voicemail — no callback.",
    "Brief call. Client seemed distracted, cut short.",
    "Client mentioned considering other advisors.",
    "Tried to schedule review meeting. Client declined — 'too busy.'",
    "Client unresponsive to email follow-up.",
]

ADVISOR_TITLES = [
    "Senior Relationship Manager",
    "Private Wealth Advisor",
    "Relationship Manager",
]


# ---------------------------------------------------------------------------
# Advisors (the RM whose book we manage, plus colleagues)
# ---------------------------------------------------------------------------

def _generate_advisors() -> list[dict]:
    advisors = []
    for i in range(N_ADVISORS):
        aid = f"A{i + 1:03d}"
        advisors.append({
            "advisor_id": aid,
            "name": fake.name(),
            "title": ADVISOR_TITLES[i % len(ADVISOR_TITLES)],
        })
    # The logged-in advisor is friendly and fixed for the demo narrative.
    advisors[0]["name"] = "Jordan Ellison"
    advisors[0]["title"] = "Senior Relationship Manager"
    return advisors


# ---------------------------------------------------------------------------
# Time-series builders
# ---------------------------------------------------------------------------

def _month_labels(n: int) -> list[str]:
    labels = []
    y, m = CURRENT_DATE.year, CURRENT_DATE.month
    for _ in range(n):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(labels))


def _week_labels(n: int) -> list[str]:
    labels = []
    d = CURRENT_DATE
    for _ in range(n):
        iso = d.isocalendar()
        labels.append(f"{iso[0]:04d}-W{iso[1]:02d}")
        d -= timedelta(days=7)
    return list(reversed(labels))


def _build_transactions(portfolio_value: int, change_pct: float, withdrawals_90d: int) -> list[dict]:
    """Monthly portfolio value + net flow, ending at portfolio_value with an
    overall drift matching change_pct. Recent withdrawals are weighted late."""
    months = _month_labels(N_TRANSACTION_MONTHS)
    start_value = portfolio_value / (1 + change_pct / 100.0)
    series = []
    for i, label in enumerate(months):
        frac = i / (len(months) - 1)
        # Smooth drift from start to end value + a little noise.
        base = start_value + (portfolio_value - start_value) * frac
        noise = base * random.uniform(-0.015, 0.015)
        value = int(max(500_000, base + noise))

        # Net flow: contributions early, withdrawals concentrated in the last 3 months.
        net_flow = int(base * random.uniform(-0.004, 0.006))
        if i >= len(months) - 3 and withdrawals_90d > 0:
            net_flow -= int(withdrawals_90d / 3)
        series.append({"month": label, "portfolio_value": value, "net_flow": net_flow})

    # Pin the last point exactly to the headline portfolio value.
    series[-1]["portfolio_value"] = portfolio_value
    return series


def _build_digital_behavior(login_change: float, email_change: float) -> list[dict]:
    """Weekly logins / email opens / app sessions trending with the deltas."""
    weeks = _week_labels(N_BEHAVIOR_WEEKS)
    base_logins = random.uniform(4, 12)
    base_opens = random.uniform(3, 9)
    series = []
    n = len(weeks)
    for i, label in enumerate(weeks):
        frac = i / (n - 1)
        login_mult = 1 + (login_change / 100.0) * frac
        open_mult = 1 + (email_change / 100.0) * frac
        logins = max(0, round(base_logins * login_mult + random.uniform(-1, 1)))
        opens = max(0, round(base_opens * open_mult + random.uniform(-1, 1)))
        sessions = max(0, round(logins * random.uniform(0.6, 1.1)))
        series.append({
            "week": label,
            "logins": logins,
            "email_opens": opens,
            "sessions": sessions,
        })
    return series


def _life_events_detail(events: list[str]) -> list[dict]:
    """Attach plausible recent dates to each life event."""
    detail = []
    for e in events:
        days_ago = random.randint(20, 240)
        detail.append({
            "type": e,
            "date": (CURRENT_DATE - timedelta(days=days_ago)).isoformat(),
        })
    return detail


# ---------------------------------------------------------------------------
# Market sentiment feed (5th data source, dated)
# ---------------------------------------------------------------------------

def _generate_market_data() -> tuple[list[dict], list[dict]]:
    """The market data (5th data source): a rich per-sector detail record with
    price history plus the reduced sentiment feed the DB/agent consume.

    Pulls live sector performance (real ETF proxies) when possible, falling back
    to a curated static feed otherwise — see backend/market_data.py. Passes the
    seeded ``random`` module so the fallback stays reproducible.
    """
    detail = build_market_detail(CURRENT_DATE, rng=random)
    feed = feed_from_detail(detail)
    return feed, detail


# ---------------------------------------------------------------------------
# Hero clients (hand-designed per SPEC §Hero clients)
# ---------------------------------------------------------------------------

def _hero_clients() -> list[dict]:
    # Priya is the flagship attrition story and must lead the morning dispatch:
    # a large, long-tenured client who has gone quiet (94 days), with engagement
    # falling and a recent withdrawal — the biggest retention fire on the book.
    priya = {
        "client_id": "C001",
        "name": "Priya Mehta",
        "portfolio_value": 20_000_000,
        "portfolio_change_pct": -4.2,
        "withdrawals_last_90_days": 250_000,
        "account_tenure_years": 12.0,
        "last_contact_note": "Discussed daughter's education fund transfer timeline. Client seemed uncertain about next steps.",
        "call_log": [
            {"date": "2026-03-28", "note": "Discussed daughter's education fund transfer timeline. Client seemed uncertain about next steps."},
            {"date": "2026-01-15", "note": "Brief call about year-end statements. Client asked about competitor rates."},
            {"date": "2025-11-02", "note": "Reviewed portfolio. Client mentioned daughter starting university next year."},
            {"date": "2025-08-20", "note": "Routine check-in. Client engaged, discussed muni bond ladder."},
        ],
        "days_since_last_contact": 94,
        "life_events": ["child_education"],
        "login_frequency_change": -28.0,
        "email_open_rate_change": -55.0,
        "market_exposure": ["muni_bonds", "tech_equities", "esg_funds"],
    }

    arjun = {
        "client_id": "C002",
        "name": "Arjun Rao",
        "portfolio_value": 22_000_000,
        "portfolio_change_pct": 22.0,
        "withdrawals_last_90_days": 0,
        "account_tenure_years": 4.5,
        "last_contact_note": "Client closed on a commercial property last month. Excited about diversifying into real estate funds.",
        "call_log": [
            {"date": "2026-05-25", "note": "Client closed on a commercial property last month. Excited about diversifying into real estate funds."},
            {"date": "2026-04-10", "note": "Discussed tech equity gains. Client open to taking some profit."},
            {"date": "2026-02-15", "note": "Quarterly review — strong performance. Client mentioned property search."},
        ],
        "days_since_last_contact": 36,
        "life_events": ["property_purchase"],
        "login_frequency_change": 15.0,
        "email_open_rate_change": 10.0,
        "market_exposure": ["tech_equities", "real_estate_funds", "private_equity"],
    }

    sharma = {
        "client_id": "C003",
        "name": "Vikram & Anita Sharma",
        "portfolio_value": 5_200_000,
        "portfolio_change_pct": 1.8,
        "withdrawals_last_90_days": 15_000,
        "account_tenure_years": 18.0,
        "last_contact_note": "Annual review. Everything on track, no changes requested.",
        "call_log": [
            {"date": "2026-05-20", "note": "Annual review. Everything on track, no changes requested."},
            {"date": "2025-11-10", "note": "Discussed estate planning. Client will think it over."},
        ],
        "days_since_last_contact": 41,
        "life_events": [],
        "login_frequency_change": -12.0,
        "email_open_rate_change": -18.0,
        "market_exposure": ["muni_bonds", "treasury_bonds"],
    }

    deepa = {
        "client_id": "C004",
        "name": "Deepa Krishnan",
        "portfolio_value": 14_000_000,
        "portfolio_change_pct": -8.5,
        "withdrawals_last_90_days": 450_000,
        "account_tenure_years": 4.0,
        "last_contact_note": "Client called about large redemption for business investment. Seemed frustrated with recent returns.",
        "call_log": [
            {"date": "2026-05-01", "note": "Client called about large redemption for business investment. Seemed frustrated with recent returns."},
            {"date": "2026-02-14", "note": "Left voicemail about market update. No callback."},
            {"date": "2025-12-05", "note": "Year-end review. Client quiet, asked minimal questions."},
        ],
        "days_since_last_contact": 61,
        "life_events": ["business_sale"],
        "login_frequency_change": -42.0,
        "email_open_rate_change": -60.0,
        "market_exposure": ["tech_equities", "emerging_markets", "private_equity"],
    }

    rahul = {
        "client_id": "C005",
        "name": "Rahul Kapoor",
        "portfolio_value": 31_000_000,
        "portfolio_change_pct": 18.5,
        "withdrawals_last_90_days": 0,
        "account_tenure_years": 9.0,
        "last_contact_note": "Client received a sizable inheritance. Wants to discuss allocation options soon.",
        "call_log": [
            {"date": "2026-06-18", "note": "Client received a sizable inheritance. Wants to discuss allocation options soon."},
            {"date": "2026-04-30", "note": "Reviewed portfolio. Client very pleased with performance."},
            {"date": "2026-02-10", "note": "Discussed ESG tilt. Client interested but wants more data."},
        ],
        "days_since_last_contact": 12,
        "life_events": ["inheritance"],
        "login_frequency_change": 25.0,
        "email_open_rate_change": 18.0,
        "market_exposure": ["tech_equities", "esg_funds", "real_estate_funds", "commodities"],
    }

    return [priya, arjun, sharma, deepa, rahul]


# ---------------------------------------------------------------------------
# Archetypes for internally-consistent random generation
# ---------------------------------------------------------------------------

ARCHETYPES = {
    "disengaging": {
        "weight": 0.20,
        # Capped just under 90 days so the +40 "no contact in >90 days" tier is
        # reserved for the hand-designed hero cases (Priya at 94). Random
        # churners still read as clearly at-risk without eclipsing the heroes.
        "days_since_last_contact": (50, 88),
        "login_frequency_change": (-45.0, -10.0),
        "email_open_rate_change": (-55.0, -10.0),
        "portfolio_change_pct": (-14.0, 3.0),
        "withdrawals_factor": (0.005, 0.03),
        # Keep churning clients mid-sized so the largest revenue-at-stake fire on
        # the book is a hero, not an anonymous random record.
        "portfolio_range": (1_500_000, 9_000_000),
        "life_events_pool": ["retirement", "divorce_settlement", "relocation"],
        "life_events_count": (0, 1),
        "tenure": (2.5, 20.0),
        "call_tone": "disengaged",
    },
    "growth": {
        "weight": 0.25,
        "days_since_last_contact": (10, 40),
        "login_frequency_change": (5.0, 35.0),
        "email_open_rate_change": (0.0, 28.0),
        "portfolio_change_pct": (8.0, 24.0),
        "withdrawals_factor": (0.0, 0.003),
        "life_events_pool": ["property_purchase", "inheritance", "business_sale"],
        "life_events_count": (0, 1),
        "tenure": (3.0, 15.0),
        "call_tone": "engaged",
    },
    "steady": {
        "weight": 0.35,
        "days_since_last_contact": (15, 55),
        "login_frequency_change": (-15.0, 12.0),
        "email_open_rate_change": (-15.0, 12.0),
        "portfolio_change_pct": (-5.0, 9.0),
        "withdrawals_factor": (0.0, 0.008),
        "life_events_pool": ["child_education", "retirement"],
        "life_events_count": (0, 1),
        "tenure": (5.0, 25.0),
        "call_tone": "engaged",
    },
    "new_exploring": {
        "weight": 0.20,
        "days_since_last_contact": (3, 25),
        "login_frequency_change": (10.0, 45.0),
        "email_open_rate_change": (5.0, 32.0),
        "portfolio_change_pct": (-3.0, 14.0),
        "withdrawals_factor": (0.0, 0.002),
        "life_events_pool": ["property_purchase", "child_education", "relocation"],
        "life_events_count": (0, 1),
        "tenure": (0.3, 2.5),
        "call_tone": "engaged",
    },
}


def _pick_archetype() -> str:
    r = random.random()
    cumulative = 0.0
    for name, cfg in ARCHETYPES.items():
        cumulative += cfg["weight"]
        if r <= cumulative:
            return name
    return "steady"


def _generate_call_log(tone: str, days_since: int) -> list[dict]:
    count = random.randint(1, 4)
    templates = CALL_NOTE_TEMPLATES_ENGAGED if tone == "engaged" else CALL_NOTE_TEMPLATES_DISENGAGED
    entries = []
    for i in range(count):
        note_date = CURRENT_DATE - timedelta(days=days_since + i * random.randint(25, 90))
        note = random.choice(templates).format(
            sector=random.choice(MARKET_SECTORS),
            event=random.choice(LIFE_EVENT_OPTIONS),
        )
        entries.append({"date": note_date.isoformat(), "note": note})
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def _generate_random_client(client_id: str) -> dict:
    archetype = _pick_archetype()
    cfg = ARCHETYPES[archetype]

    port_range = cfg.get("portfolio_range")
    if port_range:
        portfolio_value = int(random.uniform(*port_range))
    else:
        portfolio_value = int(random.lognormvariate(math.log(5_000_000), 0.7))
    portfolio_value = max(1_000_000, min(50_000_000, portfolio_value))

    days_since = random.randint(*cfg["days_since_last_contact"])
    login_change = round(random.uniform(*cfg["login_frequency_change"]), 1)
    email_change = round(random.uniform(*cfg["email_open_rate_change"]), 1)
    port_change = round(random.uniform(*cfg["portfolio_change_pct"]), 1)

    w_lo, w_hi = cfg["withdrawals_factor"]
    withdrawals = int(portfolio_value * random.uniform(w_lo, w_hi))

    tenure = round(random.uniform(*cfg["tenure"]), 1)

    n_events = random.randint(*cfg["life_events_count"])
    life_events = random.sample(cfg["life_events_pool"], min(n_events, len(cfg["life_events_pool"])))

    market_exposure = random.sample(MARKET_SECTORS, random.randint(2, 4))

    call_log = _generate_call_log(cfg["call_tone"], days_since)
    last_note = call_log[0]["note"] if call_log else ""

    return {
        "client_id": client_id,
        "name": fake.name(),
        "portfolio_value": portfolio_value,
        "portfolio_change_pct": port_change,
        "withdrawals_last_90_days": withdrawals,
        "account_tenure_years": tenure,
        "last_contact_note": last_note,
        "call_log": call_log,
        "days_since_last_contact": days_since,
        "life_events": life_events,
        "login_frequency_change": login_change,
        "email_open_rate_change": email_change,
        "market_exposure": market_exposure,
    }


def _enrich(client: dict, advisor_id: str) -> dict:
    """Attach advisor, time-series, and dated life events to a base record."""
    client["advisor_id"] = advisor_id
    client["email"] = fake.email()
    client["transactions"] = _build_transactions(
        client["portfolio_value"],
        client["portfolio_change_pct"],
        client["withdrawals_last_90_days"],
    )
    client["digital_behavior"] = _build_digital_behavior(
        client["login_frequency_change"],
        client["email_open_rate_change"],
    )
    client["life_events_detail"] = _life_events_detail(client["life_events"])
    return client


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate() -> tuple[list[dict], list[dict], list[dict]]:
    advisors = _generate_advisors()

    heroes = _hero_clients()
    hero_count = len(heroes)

    randoms = []
    for i in range(N_CLIENTS - hero_count):
        cid = f"C{i + hero_count + 1:03d}"
        randoms.append(_generate_random_client(cid))

    clients = heroes + randoms

    # Assign advisors: the primary advisor owns the heroes + the bulk of the book.
    other_advisors = [a["advisor_id"] for a in advisors if a["advisor_id"] != PRIMARY_ADVISOR_ID]
    for idx, c in enumerate(clients):
        if idx < hero_count or random.random() < 0.7 or not other_advisors:
            advisor_id = PRIMARY_ADVISOR_ID
        else:
            advisor_id = random.choice(other_advisors)
        _enrich(c, advisor_id)

    market, market_detail = _generate_market_data()
    return clients, advisors, market, market_detail


def main() -> None:
    clients, advisors, market, market_detail = generate()
    CLIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLIENTS_PATH.write_text(json.dumps(clients, indent=2), encoding="utf-8")
    ADVISORS_PATH.write_text(json.dumps(advisors, indent=2), encoding="utf-8")
    MARKET_PATH.write_text(json.dumps(market, indent=2), encoding="utf-8")
    MARKET_HISTORY_PATH.write_text(json.dumps(market_detail, indent=2), encoding="utf-8")

    print(f"Generated {len(clients)} clients, {len(advisors)} advisors, "
          f"{len(market)} market signals -> {CLIENTS_PATH.parent}")
    _print_top_signal(clients)


def _print_top_signal(clients: list[dict]) -> None:
    def _attrition_estimate(c: dict) -> int:
        score = 0
        if c["days_since_last_contact"] > 90:
            score += 40
        elif c["days_since_last_contact"] > 60:
            score += 20
        if c["login_frequency_change"] < -30:
            score += 20
        if c["email_open_rate_change"] < -40:
            score += 15
        if c["withdrawals_last_90_days"] > 100_000:
            score += 25
        if c["account_tenure_years"] < 2:
            score += 10
        return min(score, 100)

    def _upsell_estimate(c: dict) -> int:
        score = 0
        if c["portfolio_change_pct"] > 15:
            score += 35
        if "property_purchase" in c["life_events"]:
            score += 30
        if "inheritance" in c["life_events"]:
            score += 25
        if c["days_since_last_contact"] < 30:
            score += 15
        if c["account_tenure_years"] > 5:
            score += 10
        return min(score, 100)

    scored = []
    for c in clients:
        att = _attrition_estimate(c)
        ups = _upsell_estimate(c)
        scored.append((max(att, ups), att, ups, c))
    scored.sort(key=lambda x: x[0], reverse=True)

    print(f"\n{'Name':<26} {'Attrition':>9} {'Upsell':>7} {'Days':>5} {'Portfolio':>12} {'Life events'}")
    print("-" * 95)
    for _, att, ups, c in scored[:8]:
        events_str = ", ".join(c["life_events"]) if c["life_events"] else "—"
        print(
            f"{c['name']:<26} {att:>8}% {ups:>6}% {c['days_since_last_contact']:>5} "
            f"${c['portfolio_value']:>11,} {events_str}"
        )


if __name__ == "__main__":
    main()
