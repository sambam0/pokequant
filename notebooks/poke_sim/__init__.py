"""Helpers for box chase odds and pack/box EV simulations."""

from poke_sim.chase import (
    boxes_for_probability,
    p_from_print_run,
    p_from_rate,
    prob_at_least_one,
    print_run_sweep,
    simulate_boxes_until_hit,
    spend_curve,
)
from poke_sim.economics import edge, edge_pct, pack_ev_from_slots, summarize_openings
from poke_sim.packs import DATA_DIR, load_product, load_products, products_dir
from poke_sim.simulate import (
    analytical_slot_ev,
    load_cards,
    load_slot_odds,
    simulate_pack_openings,
)
from poke_sim.maestros import (
    box_ev_breakdown,
    box_ev_total,
    portfolio_summary,
    profitability_table,
    scale_table,
    simulate_portfolio,
)

__all__ = [
    "DATA_DIR",
    "analytical_slot_ev",
    "boxes_for_probability",
    "edge",
    "edge_pct",
    "load_cards",
    "load_product",
    "load_products",
    "load_slot_odds",
    "p_from_print_run",
    "p_from_rate",
    "pack_ev_from_slots",
    "print_run_sweep",
    "prob_at_least_one",
    "products_dir",
    "simulate_boxes_until_hit",
    "simulate_pack_openings",
    "spend_curve",
    "summarize_openings",
    "box_ev_breakdown",
    "box_ev_total",
    "portfolio_summary",
    "profitability_table",
    "scale_table",
    "simulate_portfolio",
]
