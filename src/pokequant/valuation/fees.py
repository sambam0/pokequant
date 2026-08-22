from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeSchedule:
    version: str
    selling_fee_bps: int
    selling_fee_min_ore: int
    selling_fee_max_ore: int | None
    payment_fee_bps: int = 0
    packaging_ore: int = 1500
    return_fraud_reserve_bps: int = 300
    handling_ore: int = 2000
    target_profit_ore: int = 5000
    risk_reserve_ore: int = 2000


# Tradera business collectibles: ~8% commission, min 2.40 SEK, max 160 SEK (ex VAT).
# MVP uses inclusive-ish defaults; adjust via FEE_SCHEDULE_VERSION / settings later.
TRADERA_BUSINESS_2026 = FeeSchedule(
    version="tradera-business-2026",
    selling_fee_bps=800,
    selling_fee_min_ore=240,
    selling_fee_max_ore=16000,
    payment_fee_bps=0,
    packaging_ore=1500,
    return_fraud_reserve_bps=300,
    handling_ore=2000,
    target_profit_ore=5000,
    risk_reserve_ore=2000,
)

SCHEDULES = {
    TRADERA_BUSINESS_2026.version: TRADERA_BUSINESS_2026,
}


def get_fee_schedule(version: str) -> FeeSchedule:
    return SCHEDULES.get(version, TRADERA_BUSINESS_2026)


def selling_fee_ore(gross_ore: int, schedule: FeeSchedule) -> int:
    fee = (gross_ore * schedule.selling_fee_bps) // 10_000
    fee = max(fee, schedule.selling_fee_min_ore)
    if schedule.selling_fee_max_ore is not None:
        fee = min(fee, schedule.selling_fee_max_ore)
    return fee
