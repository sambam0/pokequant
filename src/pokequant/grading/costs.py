from __future__ import annotations

from dataclasses import dataclass

from pokequant.config import get_settings
from pokequant.money import usd_to_sek_ore


@dataclass(frozen=True)
class GradeCosts:
    grading_fee_ore: int
    ship_out_ore: int
    ship_return_ore: int
    time_reserve_ore: int

    @property
    def total_ore(self) -> int:
        return (
            self.grading_fee_ore + self.ship_out_ore + self.ship_return_ore + self.time_reserve_ore
        )


def psa_fee_usd_cents(declared_usd_cents: int) -> int:
    settings = get_settings()
    if declared_usd_cents <= 50_000:
        return settings.psa_fee_under_500_usd_cents
    if declared_usd_cents <= 250_000:
        return settings.psa_fee_under_2500_usd_cents
    return settings.psa_fee_over_2500_usd_cents


def grading_costs(*, declared_usd_cents: int, raw_ore: int) -> GradeCosts:
    """Sweden → PSA round trip plus a small capital-time reserve on raw."""
    settings = get_settings()
    fee_usd = psa_fee_usd_cents(max(declared_usd_cents, 0))
    fee_ore = usd_to_sek_ore(fee_usd, settings.usd_sek_rate)
    reserve = (max(raw_ore, 0) * settings.grade_time_reserve_bps) // 10_000
    return GradeCosts(
        grading_fee_ore=fee_ore,
        ship_out_ore=settings.sweden_to_psa_ship_ore,
        ship_return_ore=settings.psa_return_ship_ore,
        time_reserve_ore=reserve,
    )


def net_after_sell(gross_ore: int) -> int:
    """Conservative eBay-ish net after selling a graded (or raw leftover) card."""
    settings = get_settings()
    if gross_ore <= 0:
        return 0
    fee = (gross_ore * settings.grade_sell_fee_bps) // 10_000
    reserve = (gross_ore * 300) // 10_000
    return max(gross_ore - fee - reserve - 1500, 0)
