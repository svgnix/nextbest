"""Engine 1 — Behavioral segmentation (KMeans k=4).

Pure, deterministic, no LLM. Assigns each client a segment {id, label}
and 2-3 lookalike client_ids based on nearest neighbors in feature space.
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from backend.config import SEED

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

FEATURE_KEYS = [
    "login_frequency_change",
    "email_open_rate_change",
    "days_since_last_contact",
    "withdrawals_log",
    "portfolio_change_pct",
    "life_events_count",
]


def _feature_vector(client: dict) -> list[float]:
    return [
        client["login_frequency_change"],
        client["email_open_rate_change"],
        float(client["days_since_last_contact"]),
        math.log1p(client["withdrawals_last_90_days"]),
        client["portfolio_change_pct"],
        float(len(client["life_events"])),
    ]


# ---------------------------------------------------------------------------
# Label derivation from centroid character
# ---------------------------------------------------------------------------

_LABEL_CANDIDATES = [
    "Disengaging",
    "Growth-minded",
    "Steady loyalist",
    "New & exploring",
]


def _assign_labels(centroids: np.ndarray) -> list[str]:
    """Map each centroid to a human label based on its dominant character.

    Heuristic: rank centroids by a composite signal and assign labels
    from most-disengaged to most-growth-oriented.
    """
    # Indices in feature vector: 0=login, 1=email, 2=days_since, 3=withdrawals_log, 4=port_change, 5=life_events
    scores = []
    for i, c in enumerate(centroids):
        engagement = -(c[0] + c[1]) + c[2] + c[3] - c[4] - c[5]
        scores.append((engagement, i))

    scores.sort(reverse=True)

    labels = [""] * len(centroids)
    for rank, (_, idx) in enumerate(scores):
        labels[idx] = _LABEL_CANDIDATES[rank]
    return labels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_segmentation(clients: list[dict]) -> list[dict]:
    """Segment all clients and return enriched records.

    Adds to each client dict:
      - segment: {id: int, label: str}
      - lookalikes: [client_id, ...]  (2-3 nearest neighbors)
    """
    X_raw = np.array([_feature_vector(c) for c in clients])

    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    km = KMeans(n_clusters=4, random_state=SEED, n_init=10)
    km.fit(X)

    labels = _assign_labels(km.cluster_centers_)

    nn = NearestNeighbors(n_neighbors=4, metric="euclidean")
    nn.fit(X)
    distances, indices = nn.kneighbors(X)

    enriched = []
    for i, client in enumerate(clients):
        cluster_id = int(km.labels_[i])
        neighbor_ids = [
            clients[j]["client_id"]
            for j in indices[i]
            if j != i
        ][:3]

        enriched.append({
            **client,
            "segment": {"id": cluster_id, "label": labels[cluster_id]},
            "lookalikes": neighbor_ids,
        })

    return enriched
