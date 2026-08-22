"""EV helpers for pack/box openings."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd


def pack_ev_from_slots(slots: Sequence[Mapping]) -> float:
    """Sum of count × expected_value_sek over slot definitions.

    Each slot mapping needs keys: count, expected_value_sek.
    """
    total = 0.0
    for slot in slots:
        total += float(slot["count"]) * float(slot["expected_value_sek"])
    return total


def edge(ev: float, retail: float) -> float:
    return float(ev - retail)


def edge_pct(ev: float, retail: float) -> float:
    if retail == 0:
        raise ValueError("retail must be non-zero for edge_pct")
    return float((ev - retail) / retail)


def summarize_openings(
    values: np.ndarray | pd.Series,
    retail: float,
) -> dict[str, float]:
    """Summary stats for a vector of opened values."""
    arr = np.asarray(values, dtype=float)
    return {
        "mean_ev": float(arr.mean()),
        "median": float(np.median(arr)),
        "p5": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
        "hit_rate_vs_retail": float((arr >= retail).mean()),
        "edge": edge(float(arr.mean()), retail),
        "edge_pct": edge_pct(float(arr.mean()), retail),
        "retail": float(retail),
        "n": float(len(arr)),
    }
