from pokequant.valuation.engine import ValuationInput, compute_valuation
from pokequant.valuation.fees import TRADERA_BUSINESS_2026, selling_fee_ore


def test_selling_fee_min_and_max():
    assert selling_fee_ore(1000, TRADERA_BUSINESS_2026) == 240
    assert selling_fee_ore(10_000_000, TRADERA_BUSINESS_2026) == 16000


def test_buy_when_tradera_cheaper_than_ebay():
    result = compute_valuation(
        ValuationInput(
            asking_ore=100_00,
            inbound_shipping_ore=49_00,
            ebay_comp_ore=300_00,
            pricecharting_comp_ore=280_00,
            identity_confidence=0.9,
        )
    )
    # landed 149 < external min(300,280)=280
    assert result.landed_cost_ore == 149_00
    assert result.external_comp_ore == 280_00
    assert result.passes_hard_gates is True


def test_reject_when_tradera_more_expensive_than_ebay():
    result = compute_valuation(
        ValuationInput(
            asking_ore=250_00,
            inbound_shipping_ore=49_00,
            ebay_comp_ore=200_00,
            pricecharting_comp_ore=220_00,
            identity_confidence=0.9,
        )
    )
    assert result.landed_cost_ore == 299_00
    assert result.passes_hard_gates is False
    assert "landed_not_cheaper_than_external" in result.gate_failures


def test_fails_without_external_comp():
    result = compute_valuation(
        ValuationInput(
            asking_ore=100_00,
            identity_confidence=0.9,
        )
    )
    assert result.passes_hard_gates is False
    assert "missing_external_comp" in result.gate_failures
    assert result.passed_thesis == ""


def test_grade_upside_passes_when_raw_is_not_cheaper():
    result = compute_valuation(
        ValuationInput(
            asking_ore=250_00,
            inbound_shipping_ore=49_00,
            ebay_comp_ore=200_00,
            pricecharting_comp_ore=220_00,
            identity_confidence=0.9,
            buy_thesis="grade_upside",
            require_cheaper_than_external=False,
            grade_ev_ore=80_00,
            grade_max_buy_ore=400_00,
            grade_cost_ore=70_00,
            psa9_floor_profit_ore=20_00,
            min_grade_profit_ore=50_00,
        )
    )
    assert result.passes_hard_gates is True
    assert result.passed_thesis == "grade_upside"
    assert "landed_not_cheaper_than_external" not in result.gate_failures


def test_both_thesis_flip_still_works_without_grade():
    result = compute_valuation(
        ValuationInput(
            asking_ore=100_00,
            inbound_shipping_ore=49_00,
            ebay_comp_ore=300_00,
            pricecharting_comp_ore=280_00,
            identity_confidence=0.9,
            buy_thesis="both",
        )
    )
    assert result.passes_hard_gates is True
    assert result.passed_thesis == "flip_raw"
