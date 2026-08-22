"""Box-level chase probability helpers."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


def p_from_print_run(serials: float, print_run_boxes: float) -> float:
    """Approximate per-box hit probability for print-run limited serials.

    Assumes serials are spread uniformly across the print run and each box is
    an independent Bernoulli trial with at most one modeled hit.
    """
    if print_run_boxes <= 0:
        raise ValueError("print_run_boxes must be positive")
    if serials < 0:
        raise ValueError("serials must be non-negative")
    return float(min(1.0, serials / print_run_boxes))


def p_from_rate(hits_per_box: float) -> float:
    """Convert expected hits per box into P(at least one hit in a box).

    Uses 1 - exp(-λ) so rates above 1 stay valid (Poisson / rare-event model).
    For λ << 1 this is ≈ λ.
    """
    if hits_per_box < 0:
        raise ValueError("hits_per_box must be non-negative")
    return float(1.0 - math.exp(-hits_per_box))


def prob_at_least_one(p_box: float, n_boxes: int | float) -> float:
    """P(at least one hit in n independent boxes)."""
    if not 0.0 <= p_box <= 1.0:
        raise ValueError("p_box must be in [0, 1]")
    n = int(n_boxes)
    if n < 0:
        raise ValueError("n_boxes must be non-negative")
    if n == 0:
        return 0.0
    if p_box == 0.0:
        return 0.0
    if p_box == 1.0:
        return 1.0
    return float(1.0 - (1.0 - p_box) ** n)


def boxes_for_probability(p_box: float, target: float) -> int:
    """Minimal boxes for P(at least one) >= target."""
    if not 0.0 < target < 1.0:
        raise ValueError("target must be in (0, 1)")
    if not 0.0 <= p_box <= 1.0:
        raise ValueError("p_box must be in [0, 1]")
    if p_box == 0.0:
        raise ValueError("p_box is 0; target probability is unreachable")
    if p_box == 1.0:
        return 1
    # 1 - (1-p)^k >= target  =>  k >= log(1-target) / log(1-p)
    k = math.log(1.0 - target) / math.log(1.0 - p_box)
    return int(math.ceil(k))


def spend_curve(
    retail: float,
    p_box: float,
    targets: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
) -> pd.DataFrame:
    """Table of boxes and spend needed for each hit-probability target."""
    rows = []
    for t in targets:
        boxes = boxes_for_probability(p_box, t)
        rows.append(
            {
                "target_prob": t,
                "target_pct": f"{100 * t:.0f}%",
                "boxes": boxes,
                "spend": boxes * retail,
                "p_box": p_box,
            }
        )
    return pd.DataFrame(rows)


def print_run_sweep(
    serials: float,
    print_runs: Iterable[float],
    retail: float,
    targets: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
    label: str = "chase",
) -> pd.DataFrame:
    """For each assumed print run, compute spend curves for all targets."""
    frames = []
    for n in print_runs:
        p = p_from_print_run(serials, n)
        curve = spend_curve(retail, p, targets)
        curve.insert(0, "print_run_boxes", int(n))
        curve.insert(1, "label", label)
        curve.insert(2, "serials", serials)
        frames.append(curve)
    return pd.concat(frames, ignore_index=True)


def simulate_boxes_until_hit(
    p_box: float,
    n_trials: int = 10_000,
    rng: np.random.Generator | None = None,
    max_boxes: int = 1_000_000,
) -> pd.DataFrame:
    """Monte Carlo: boxes opened until first hit (geometric distribution)."""
    if not 0.0 < p_box <= 1.0:
        raise ValueError("p_box must be in (0, 1]")
    rng = rng or np.random.default_rng()
    # Geometric with success probability p: number of trials until first success
    draws = rng.geometric(p_box, size=n_trials)
    draws = np.minimum(draws, max_boxes)
    return pd.DataFrame({"boxes_until_hit": draws})
