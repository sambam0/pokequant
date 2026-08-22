from __future__ import annotations

from dataclasses import dataclass

from pokequant.config import get_settings
from pokequant.connectors.pricecharting import PriceChartingGradeRow
from pokequant.grading.costs import GradeCosts, grading_costs, net_after_sell
from pokequant.grading.priors import GemPrior, gem_prior
from pokequant.money import usd_to_sek_ore

TIERS = ("workhorse", "hunt", "moonshot")


@dataclass(frozen=True)
class GradeScore:
    ev_ore: int
    upside_if_10_ore: int
    upside_if_10_mult: float
    spread_psa10: float
    psa9_floor_profit_ore: int
    grade_cost_ore: int
    max_raw_buy_ore: int
    expected_net_ore: int
    prior: GemPrior
    costs: GradeCosts
    tier: str | None
    drop_reason: str
    raw_ore: int
    psa8_ore: int
    psa9_ore: int
    psa10_ore: int
    bgs10_ore: int
    black_label_ore: int


def _usd_ore(cents: int | None, rate: float) -> int:
    if not cents:
        return 0
    return usd_to_sek_ore(cents, rate)


def expected_net_ore(*, psa10: int, psa9: int, psa8: int, raw: int, prior: GemPrior) -> int:
    return int(
        round(
            prior.psa10 * net_after_sell(psa10)
            + prior.psa9 * net_after_sell(psa9)
            + prior.psa8 * net_after_sell(psa8)
            + prior.miss * net_after_sell(raw)
        )
    )


def score_at_buy(
    *,
    raw_buy_ore: int,
    psa10_ore: int,
    psa9_ore: int,
    psa8_ore: int,
    raw_ore: int,
    prior: GemPrior,
    costs: GradeCosts,
) -> tuple[int, int, float, int, int]:
    """Return ev, upside_if_10, upside_mult, psa9_floor_profit, expected_net."""
    expected_net = expected_net_ore(
        psa10=psa10_ore, psa9=psa9_ore, psa8=psa8_ore, raw=raw_ore, prior=prior
    )
    ev = expected_net - raw_buy_ore - costs.total_ore
    psa10_net = net_after_sell(psa10_ore)
    upside = psa10_net - raw_buy_ore - costs.total_ore
    denom = raw_buy_ore + costs.total_ore
    mult = (psa10_net / denom) if denom > 0 else 0.0
    p9_floor = net_after_sell(psa9_ore) - raw_buy_ore - costs.total_ore
    return ev, upside, mult, p9_floor, expected_net


def assign_tier(
    *,
    prior: GemPrior,
    upside_if_10_mult: float,
    spread_psa10: float,
    drop_reason: str,
    ev_ore: int = 0,
    tier_override: str | None = None,
) -> tuple[str | None, str]:
    del ev_ore
    if drop_reason:
        return None, drop_reason
    if tier_override in TIERS:
        return tier_override, ""

    low_gem = prior.psa10 < 0.08
    if prior.damage or low_gem:
        if upside_if_10_mult >= 3.0 or spread_psa10 >= 4.0:
            return "moonshot", ""
        return None, "low_gem_weak_upside"

    if prior.psa10 >= 0.18 and 1.5 <= upside_if_10_mult <= 2.8:
        return "workhorse", ""
    if upside_if_10_mult >= 3.0:
        return "hunt" if prior.psa10 >= 0.10 else "moonshot"
    if prior.psa10 >= 0.10 and upside_if_10_mult >= 2.2:
        return "hunt", ""
    if upside_if_10_mult >= 1.5:
        return "workhorse", ""
    return None, "ev_not_actionable"


def score_prices(
    *,
    raw_usd_cents: int | None,
    psa8_usd_cents: int | None,
    psa9_usd_cents: int | None,
    psa10_usd_cents: int | None,
    bgs10_usd_cents: int | None = None,
    black_label_usd_cents: int | None = None,
    sport: str,
    product_name: str,
    console_name: str = "",
    genre: str = "",
    release_date: str = "",
    gem_rate_override: float | None = None,
    tier_override: str | None = None,
    raw_buy_ore: int | None = None,
    usd_sek_rate: float | None = None,
) -> GradeScore:
    settings = get_settings()
    rate = usd_sek_rate if usd_sek_rate is not None else settings.usd_sek_rate
    prior = gem_prior(
        sport=sport,
        product_name=product_name,
        console_name=console_name,
        genre=genre,
        release_date=release_date,
        gem_rate_override=gem_rate_override,
    )
    raw_ore = _usd_ore(raw_usd_cents, rate)
    psa10_ore = _usd_ore(psa10_usd_cents, rate)
    psa9_ore = _usd_ore(psa9_usd_cents, rate)
    psa8_ore = _usd_ore(psa8_usd_cents, rate) or raw_ore
    bgs10_ore = _usd_ore(bgs10_usd_cents, rate)
    black_ore = _usd_ore(black_label_usd_cents, rate)

    drop = ""
    if not raw_usd_cents or not psa10_usd_cents:
        drop = "missing_psa10_or_raw"
    elif not psa9_usd_cents:
        drop = "missing_psa9_floor"

    declared = psa9_usd_cents or raw_usd_cents or 0
    costs = grading_costs(declared_usd_cents=declared, raw_ore=raw_ore)
    buy = raw_ore if raw_buy_ore is None else raw_buy_ore
    ev, upside, mult, p9_floor, expected_net = score_at_buy(
        raw_buy_ore=buy,
        psa10_ore=psa10_ore,
        psa9_ore=psa9_ore or raw_ore,
        psa8_ore=psa8_ore,
        raw_ore=raw_ore,
        prior=prior,
        costs=costs,
    )
    spread = (psa10_ore / raw_ore) if raw_ore > 0 else 0.0
    max_buy = expected_net - costs.total_ore - settings.grade_min_profit_ore

    if not drop and mult < settings.grade_min_upside_mult:
        drop = "upside_vanishes_after_costs"

    tier, drop = assign_tier(
        prior=prior,
        ev_ore=ev,
        upside_if_10_mult=mult,
        spread_psa10=spread,
        drop_reason=drop,
        tier_override=tier_override,
    )
    return GradeScore(
        ev_ore=ev,
        upside_if_10_ore=upside,
        upside_if_10_mult=mult,
        spread_psa10=spread,
        psa9_floor_profit_ore=p9_floor,
        grade_cost_ore=costs.total_ore,
        max_raw_buy_ore=max(max_buy, 0),
        expected_net_ore=expected_net,
        prior=prior,
        costs=costs,
        tier=tier,
        drop_reason=drop,
        raw_ore=raw_ore,
        psa8_ore=psa8_ore,
        psa9_ore=psa9_ore,
        psa10_ore=psa10_ore,
        bgs10_ore=bgs10_ore,
        black_label_ore=black_ore,
    )


def score_grade_row(row: PriceChartingGradeRow, **kwargs: object) -> GradeScore:
    return score_prices(
        raw_usd_cents=row.raw_usd_cents,
        psa8_usd_cents=row.psa8_usd_cents,
        psa9_usd_cents=row.psa9_usd_cents,
        psa10_usd_cents=row.psa10_usd_cents,
        bgs10_usd_cents=row.bgs10_usd_cents,
        black_label_usd_cents=row.black_label_usd_cents,
        sport=row.sport,
        product_name=row.product_name,
        console_name=row.console_name,
        genre=row.genre,
        release_date=row.release_date,
        **kwargs,  # type: ignore[arg-type]
    )
