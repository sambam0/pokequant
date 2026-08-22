"""Magnificent Maestros box EV / profitability model."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from poke_sim.chase import p_from_print_run, prob_at_least_one
from poke_sim.packs import load_product


def _band(prices: dict[str, dict[str, float]], key: str, scenario: str) -> float:
    return float(prices[key][scenario])


def box_ev_breakdown(
    product: dict[str, Any] | None = None,
    *,
    print_run_boxes: float = 150_000,
    price_scenario: str = "base",
    bonus_starlight_rate: float = 0.07,
    bonus3_extended_rate: float = 0.12,
) -> pd.DataFrame:
    """Analytical expected value per box by slot (SEK).

    Chase slot 5: each of 3 pack chase cards is GMR with p = serials / (3 * print_run),
    else drawn from standard/extended/starlight weights.
    Bonus cards: mostly Secret; optional Starlight upgrade; slot 3 may be reprint EA.
    """
    product = product or load_product("magnificent_maestros")
    prices = product["price_bands_sek"]
    serials = float(product["chase"]["total_serials_region"])
    p_gmr_card = min(1.0, serials / (3.0 * print_run_boxes))

    chase_w = product["slots"]["pack"][-1]["outcomes"]
    w_sum = sum(chase_w.values())
    w_std = chase_w["standard_ur"] / w_sum
    w_ext = chase_w["extended_ur"] / w_sum
    w_str = chase_w["extended_starlight"] / w_sum

    rows: list[dict[str, Any]] = []

    def add(slot: str, count: float, unit_ev: float, notes: str = "") -> None:
        rows.append(
            {
                "slot": slot,
                "count": count,
                "unit_ev_sek": unit_ev,
                "ev_sek": count * unit_ev,
                "notes": notes,
            }
        )

    add("reprints_ur", 3, _band(prices, "reprints_ur", price_scenario))
    add("new_archetype_ur", 3, _band(prices, "new_archetype_ur", price_scenario))
    add("foil_upgrade_ur", 3, _band(prices, "foil_upgrade_ur", price_scenario))
    add("chibi_or_anime_ur", 3, _band(prices, "chibi_or_anime_ur", price_scenario))

    unit_chase = (
        p_gmr_card * _band(prices, "gmr_average", price_scenario)
        + (1 - p_gmr_card)
        * (
            w_std * _band(prices, "chase_standard_ur", price_scenario)
            + w_ext * _band(prices, "chase_extended_ur", price_scenario)
            + w_str * _band(prices, "chase_extended_starlight", price_scenario)
        )
    )
    add(
        "chase_slot_x3",
        3,
        unit_chase,
        notes=f"p_gmr_per_card={p_gmr_card:.6f}; print_run={int(print_run_boxes)}",
    )

    # Bonus slots 1–2: secret with starlight upgrade
    secret = _band(prices, "bonus_secret", price_scenario)
    star = _band(prices, "bonus_starlight", price_scenario)
    unit_b12 = (1 - bonus_starlight_rate) * secret + bonus_starlight_rate * star
    add("bonus_secret_1_2", 2, unit_b12, notes=f"starlight_rate={bonus_starlight_rate}")

    # Bonus slot 3: may also be reprint extended art
    ext = _band(prices, "bonus_extended_ur", price_scenario)
    unit_b3 = (
        bonus3_extended_rate * ext
        + (1 - bonus3_extended_rate)
        * ((1 - bonus_starlight_rate) * secret + bonus_starlight_rate * star)
    )
    add(
        "bonus_secret_3",
        1,
        unit_b3,
        notes=f"extended_rate={bonus3_extended_rate}, starlight_rate={bonus_starlight_rate}",
    )

    return pd.DataFrame(rows)


def box_ev_total(
    product: dict[str, Any] | None = None,
    **kwargs: Any,
) -> float:
    return float(box_ev_breakdown(product, **kwargs)["ev_sek"].sum())


def profitability_table(
    retail: float,
    print_runs: list[float],
    price_scenarios: list[str] | None = None,
    product: dict[str, Any] | None = None,
) -> pd.DataFrame:
    product = product or load_product("magnificent_maestros")
    price_scenarios = price_scenarios or ["bear", "base", "bull"]
    rows = []
    serials = float(product["chase"]["total_serials_region"])
    for n in print_runs:
        p_any = p_from_print_run(serials, n)
        for scen in price_scenarios:
            ev = box_ev_total(product, print_run_boxes=n, price_scenario=scen)
            rows.append(
                {
                    "print_run_boxes": int(n),
                    "price_scenario": scen,
                    "p_box_any_gmr": p_any,
                    "box_ev_sek": ev,
                    "retail_sek": retail,
                    "edge_sek": ev - retail,
                    "edge_pct": (ev - retail) / retail,
                    "gmr_ev_contribution": p_any
                    * float(product["price_bands_sek"]["gmr_average"][scen]),
                }
            )
    return pd.DataFrame(rows)


def simulate_portfolio(
    n_boxes: int,
    *,
    print_run_boxes: float = 150_000,
    price_scenario: str = "base",
    retail: float | None = None,
    n_trials: int = 5_000,
    rng: np.random.Generator | None = None,
    product: dict[str, Any] | None = None,
    bonus_starlight_rate: float = 0.07,
    bonus3_extended_rate: float = 0.12,
) -> pd.DataFrame:
    """Monte Carlo portfolio value for buying n_boxes (independent boxes)."""
    product = product or load_product("magnificent_maestros")
    retail = float(retail if retail is not None else product["retail_price_sek"])
    prices = product["price_bands_sek"]
    rng = rng or np.random.default_rng()

    serials = float(product["chase"]["total_serials_region"])
    p_gmr_card = min(1.0, serials / (3.0 * print_run_boxes))
    chase_w = product["slots"]["pack"][-1]["outcomes"]
    w = np.array(
        [chase_w["standard_ur"], chase_w["extended_ur"], chase_w["extended_starlight"]],
        dtype=float,
    )
    w /= w.sum()
    chase_vals = np.array(
        [
            _band(prices, "chase_standard_ur", price_scenario),
            _band(prices, "chase_extended_ur", price_scenario),
            _band(prices, "chase_extended_starlight", price_scenario),
        ]
    )
    gmr_val = _band(prices, "gmr_average", price_scenario)

    bulk = (
        3 * _band(prices, "reprints_ur", price_scenario)
        + 3 * _band(prices, "new_archetype_ur", price_scenario)
        + 3 * _band(prices, "foil_upgrade_ur", price_scenario)
        + 3 * _band(prices, "chibi_or_anime_ur", price_scenario)
    )
    secret = _band(prices, "bonus_secret", price_scenario)
    star = _band(prices, "bonus_starlight", price_scenario)
    ext = _band(prices, "bonus_extended_ur", price_scenario)

    totals = np.zeros(n_trials)
    gmr_counts = np.zeros(n_trials)
    star_counts = np.zeros(n_trials)
    ext_counts = np.zeros(n_trials)

    for t in range(n_trials):
        value = bulk * n_boxes
        gmrs = 0
        stars = 0
        exts = 0
        for _ in range(n_boxes):
            # 3 chase slots
            for _c in range(3):
                if rng.random() < p_gmr_card:
                    value += gmr_val
                    gmrs += 1
                else:
                    idx = rng.choice(3, p=w)
                    value += chase_vals[idx]
                    if idx == 1:
                        exts += 1
                    elif idx == 2:
                        stars += 1
            # bonus 1–2
            for _b in range(2):
                if rng.random() < bonus_starlight_rate:
                    value += star
                    stars += 1
                else:
                    value += secret
            # bonus 3
            if rng.random() < bonus3_extended_rate:
                value += ext
                exts += 1
            elif rng.random() < bonus_starlight_rate:
                value += star
                stars += 1
            else:
                value += secret
        totals[t] = value
        gmr_counts[t] = gmrs
        star_counts[t] = stars
        ext_counts[t] = exts

    cost = n_boxes * retail
    profit = totals - cost
    return pd.DataFrame(
        {
            "opened_value_sek": totals,
            "profit_sek": profit,
            "gmr_count": gmr_counts,
            "starlight_count": star_counts,
            "extended_count": ext_counts,
            "cost_sek": cost,
            "n_boxes": n_boxes,
        }
    )


def portfolio_summary(sim: pd.DataFrame) -> dict[str, float]:
    p = sim["profit_sek"]
    return {
        "n_boxes": float(sim["n_boxes"].iloc[0]),
        "cost_sek": float(sim["cost_sek"].iloc[0]),
        "mean_value": float(sim["opened_value_sek"].mean()),
        "mean_profit": float(p.mean()),
        "median_profit": float(p.median()),
        "p5_profit": float(np.percentile(p, 5)),
        "p95_profit": float(np.percentile(p, 95)),
        "prob_profit": float((p > 0).mean()),
        "mean_gmr": float(sim["gmr_count"].mean()),
        "prob_any_gmr": float((sim["gmr_count"] > 0).mean()),
        "mean_starlights": float(sim["starlight_count"].mean()),
        "mean_extended": float(sim["extended_count"].mean()),
    }


def scale_table(
    box_counts: list[int],
    **kwargs: Any,
) -> pd.DataFrame:
    rows = []
    for n in box_counts:
        sim = simulate_portfolio(n, **kwargs)
        rows.append(portfolio_summary(sim))
    return pd.DataFrame(rows)
