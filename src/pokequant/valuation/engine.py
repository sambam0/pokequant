from __future__ import annotations

from dataclasses import dataclass

from pokequant.config import get_settings
from pokequant.valuation.fees import FeeSchedule, get_fee_schedule, selling_fee_ore


@dataclass
class ValuationInput:
    asking_ore: int
    inbound_shipping_ore: int | None = 0
    buyer_fee_ore: int | None = 0
    import_cost_ore: int = 0
    comps_stale: bool = False
    fx_stale: bool = False
    listing_type: str = "bin"
    # External comps used for the buy gate (eBay / PriceCharting), in SEK öre.
    ebay_comp_ore: int = 0
    pricecharting_comp_ore: int = 0
    # Optional EU/resale reference for profit sizing (Cardmarket/TCGdex), not the buy gate.
    reference_p10_ore: int = 0
    reference_p50_ore: int = 0
    reference_p90_ore: int = 0
    identity_confidence: float = 0.0
    min_discount_bps: int = 0
    hard_max_buy_ore: int | None = None
    outbound_shipping_subsidy_ore: int = 0
    expected_vat_ore: int = 0
    min_identity_confidence: float = 0.75
    min_expected_profit_ore: int = 0
    require_cheaper_than_external: bool = True
    buy_thesis: str = "flip_raw"  # flip_raw | grade_upside | both
    grade_ev_ore: int = 0
    grade_max_buy_ore: int = 0
    grade_cost_ore: int = 0
    psa9_floor_profit_ore: int = 0
    min_grade_profit_ore: int = 0


@dataclass
class ValuationResult:
    market_value_p10_ore: int
    market_value_p50_ore: int
    market_value_p90_ore: int
    external_comp_ore: int
    ebay_comp_ore: int
    pricecharting_comp_ore: int
    expected_net_proceeds_ore: int
    landed_cost_ore: int
    expected_profit_ore: int
    max_buy_ore: int
    discount_bps: int
    identity_confidence: float
    passes_hard_gates: bool
    gate_failures: list[str]
    explanation: str
    model_version: str
    fee_schedule_version: str
    passed_thesis: str = ""
    grade_ev_ore: int = 0


def _external_comp(inp: ValuationInput) -> int:
    """Best available external ask/guide in SEK öre. Prefer the cheaper of eBay vs PriceCharting."""
    candidates = [c for c in (inp.ebay_comp_ore, inp.pricecharting_comp_ore) if c and c > 0]
    if not candidates:
        return 0
    return min(candidates)


def compute_valuation(inp: ValuationInput, schedule: FeeSchedule | None = None) -> ValuationResult:
    settings = get_settings()
    schedule = schedule or get_fee_schedule(settings.fee_schedule_version)

    external = _external_comp(inp)
    # Resale sizing still uses EU/ref if present; otherwise fall back to external comps.
    p10 = inp.reference_p10_ore or external or inp.reference_p50_ore
    p50 = inp.reference_p50_ore or external or inp.reference_p10_ore
    p90 = inp.reference_p90_ore or p50
    conservative = p10 if p10 > 0 else p50

    fee = selling_fee_ore(conservative, schedule) if conservative > 0 else 0
    payment_fee = (conservative * schedule.payment_fee_bps) // 10_000
    reserve = (conservative * schedule.return_fraud_reserve_bps) // 10_000

    expected_net = (
        conservative
        - fee
        - payment_fee
        - inp.outbound_shipping_subsidy_ore
        - schedule.packaging_ore
        - reserve
        - inp.expected_vat_ore
    )
    ship = 0 if inp.inbound_shipping_ore is None else inp.inbound_shipping_ore
    inbound_fee = 0 if inp.buyer_fee_ore is None else inp.buyer_fee_ore
    landed = inp.asking_ore + ship + inbound_fee + inp.import_cost_ore
    expected_profit = expected_net - landed - schedule.handling_ore

    # Buy ceiling: must be below the cheaper external market (eBay/PriceCharting).
    max_buy = external - 1 if external > 0 else 0
    if inp.hard_max_buy_ore is not None:
        max_buy = min(max_buy, inp.hard_max_buy_ore) if max_buy > 0 else inp.hard_max_buy_ore

    discount_bps = 0
    if external > 0:
        discount_bps = int(round((1 - (landed / external)) * 10_000))

    shared: list[str] = []
    if inp.listing_type == "auction":
        shared.append("auction_not_alerted")
    if inp.inbound_shipping_ore is None:
        shared.append("missing_shipping")
    if inp.buyer_fee_ore is None:
        shared.append("missing_buyer_fee")
    if inp.fx_stale:
        shared.append("stale_fx")
    if inp.identity_confidence < inp.min_identity_confidence:
        shared.append("identity_confidence")

    flip_failures = list(shared)
    if inp.comps_stale:
        flip_failures.append("stale_comps")
    if inp.require_cheaper_than_external:
        if external <= 0:
            flip_failures.append("missing_external_comp")
        elif landed >= external:
            flip_failures.append("landed_not_cheaper_than_external")
    if max_buy > 0 and max_buy < landed:
        flip_failures.append("max_buy_below_landed")
    if inp.min_expected_profit_ore and expected_profit < inp.min_expected_profit_ore:
        flip_failures.append("profit_floor")
    if inp.min_discount_bps and discount_bps < inp.min_discount_bps:
        flip_failures.append("min_discount")

    thesis = (inp.buy_thesis or "flip_raw").strip() or "flip_raw"
    grade_failures = list(shared)
    has_grade = thesis in {"grade_upside", "both"}
    if has_grade:
        if inp.grade_max_buy_ore <= 0 and inp.grade_ev_ore == 0 and inp.psa9_floor_profit_ore == 0:
            grade_failures.append("missing_grade_comp")
        else:
            grade_ok = inp.grade_ev_ore >= inp.min_grade_profit_ore or (
                inp.psa9_floor_profit_ore >= inp.min_grade_profit_ore
            )
            if not grade_ok:
                grade_failures.append("grade_ev_floor")
            if inp.grade_max_buy_ore > 0 and inp.grade_max_buy_ore < landed:
                grade_failures.append("grade_max_buy_below_landed")

    if thesis == "grade_upside":
        failures = grade_failures
        passed = "grade_upside" if not failures else ""
        if inp.grade_max_buy_ore > 0:
            max_buy = inp.grade_max_buy_ore
        if passed:
            expected_profit = inp.grade_ev_ore
    elif thesis == "both":
        flip_ok = not flip_failures
        grade_ok = has_grade and not grade_failures
        if flip_ok and grade_ok:
            failures = []
            passed = "both"
            if inp.grade_max_buy_ore > 0:
                max_buy = max(max_buy, inp.grade_max_buy_ore)
        elif flip_ok:
            failures = []
            passed = "flip_raw"
        elif grade_ok:
            failures = []
            passed = "grade_upside"
            if inp.grade_max_buy_ore > 0:
                max_buy = inp.grade_max_buy_ore
            expected_profit = inp.grade_ev_ore
        else:
            failures = list(dict.fromkeys(flip_failures + grade_failures))
            passed = ""
    else:
        failures = flip_failures
        passed = "flip_raw" if not failures else ""

    explanation = (
        f"landed_tradera={landed}; ebay={inp.ebay_comp_ore}; pricecharting={inp.pricecharting_comp_ore}; "
        f"external_comp={external}; cheaper_than_external={landed < external if external else False}; "
        f"max_buy={max_buy}; discount_bps={discount_bps}; resale_ref={conservative}; "
        f"thesis={thesis}; passed_thesis={passed or 'none'}; grade_ev={inp.grade_ev_ore}; "
        f"grade_cost={inp.grade_cost_ore}"
    )

    return ValuationResult(
        market_value_p10_ore=p10,
        market_value_p50_ore=p50,
        market_value_p90_ore=p90,
        external_comp_ore=external,
        ebay_comp_ore=inp.ebay_comp_ore,
        pricecharting_comp_ore=inp.pricecharting_comp_ore,
        expected_net_proceeds_ore=expected_net,
        landed_cost_ore=landed,
        expected_profit_ore=expected_profit,
        max_buy_ore=max_buy,
        discount_bps=discount_bps,
        identity_confidence=inp.identity_confidence,
        passes_hard_gates=len(failures) == 0,
        gate_failures=failures,
        explanation=explanation,
        model_version=settings.model_version,
        fee_schedule_version=schedule.version,
        passed_thesis=passed,
        grade_ev_ore=inp.grade_ev_ore,
    )
