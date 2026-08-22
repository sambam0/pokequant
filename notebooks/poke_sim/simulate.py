"""Monte Carlo pack opening and analytical slot EV."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from poke_sim.packs import DATA_DIR


def load_cards(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA_DIR / "cards" / "sample_values.csv"
    df = pd.read_csv(path)
    required = {"card_id", "name", "rarity", "market_value_sek"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"cards CSV missing columns: {sorted(missing)}")
    return df


def load_slot_odds(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA_DIR / "odds" / "sample_slot_odds.csv"
    df = pd.read_csv(path)
    required = {"slot", "rarity", "weight"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"odds CSV missing columns: {sorted(missing)}")
    return df


def _rarity_mean_values(cards: pd.DataFrame) -> dict[str, float]:
    return cards.groupby("rarity")["market_value_sek"].mean().to_dict()


def analytical_slot_ev(
    cards: pd.DataFrame,
    odds: pd.DataFrame,
    slot_counts: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Expected value per slot type and total pack EV.

    If slot_counts is None, each distinct slot name counts as 1.
    """
    means = _rarity_mean_values(cards)
    rows = []
    for slot, group in odds.groupby("slot"):
        weights = group["weight"].astype(float).to_numpy()
        weights = weights / weights.sum()
        ev = 0.0
        for rarity, w in zip(group["rarity"], weights):
            if rarity not in means:
                raise KeyError(f"No cards with rarity={rarity!r} in cards table")
            ev += w * means[rarity]
        count = 1 if slot_counts is None else int(slot_counts.get(slot, 0))
        rows.append(
            {
                "slot": slot,
                "count": count,
                "ev_per_slot": ev,
                "ev_total": ev * count,
            }
        )
    return pd.DataFrame(rows)


def simulate_pack_openings(
    cards: pd.DataFrame,
    odds: pd.DataFrame,
    slot_counts: dict[str, int],
    n: int = 10_000,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Simulate n pack openings; return total opened value per pack."""
    rng = rng or np.random.default_rng()
    by_rarity = {
        rarity: group["market_value_sek"].to_numpy(dtype=float)
        for rarity, group in cards.groupby("rarity")
    }
    slot_specs: list[tuple[str, np.ndarray, np.ndarray]] = []
    for slot, count in slot_counts.items():
        group = odds.loc[odds["slot"] == slot]
        if group.empty:
            raise KeyError(f"No odds rows for slot={slot!r}")
        rarities = group["rarity"].to_numpy()
        weights = group["weight"].astype(float).to_numpy()
        weights = weights / weights.sum()
        for _ in range(count):
            slot_specs.append((slot, rarities, weights))

    totals = np.zeros(n, dtype=float)
    for i in range(n):
        value = 0.0
        for _slot, rarities, weights in slot_specs:
            rarity = rng.choice(rarities, p=weights)
            pool = by_rarity[str(rarity)]
            value += float(rng.choice(pool))
        totals[i] = value

    return pd.DataFrame({"opened_value_sek": totals})
