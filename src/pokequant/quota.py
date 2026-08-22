from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy.orm import Session

from pokequant.config import get_settings
from pokequant.db.models import Source, SourceApiCall


@dataclass(frozen=True)
class SlotBudget:
    remaining: int
    ticks_left: int
    slots: int
    search_slots: int
    hydrate_reserve: int
    tick_minutes: int
    core_cycle_hours: float
    budget: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def rolling_calls(session: Session, source: Source, *, now: datetime | None = None) -> list[SourceApiCall]:
    now = now or _now()
    cutoff = now - timedelta(hours=24)
    return (
        session.query(SourceApiCall)
        .filter(SourceApiCall.source_id == source.id, SourceApiCall.called_at > cutoff)
        .order_by(SourceApiCall.called_at.asc())
        .all()
    )


def record_api_call(
    session: Session,
    source: Source,
    *,
    endpoint: str,
    http_status: int | None = None,
    now: datetime | None = None,
) -> SourceApiCall:
    row = SourceApiCall(
        source_id=source.id,
        called_at=now or _now(),
        endpoint=endpoint,
        http_status=http_status,
    )
    session.add(row)
    source.last_success_at = row.called_at if (http_status or 0) < 400 else source.last_success_at
    return row


def compute_slot_budget(
    session: Session,
    source: Source,
    *,
    n_core_arms: int = 0,
    now: datetime | None = None,
) -> SlotBudget:
    settings = get_settings()
    now = now or _now()
    budget = source.daily_call_budget or settings.tradera_daily_call_budget
    tick_minutes = settings.tradera_tick_minutes
    if budget >= 500 and tick_minutes > 20:
        # Operators may still pin 120m at 100/day; only advertise 20m after quota ≥500.
        pass
    calls = rolling_calls(session, source, now=now)
    remaining = max(0, budget - len(calls))
    if remaining <= 0:
        return SlotBudget(
            remaining=0,
            ticks_left=1,
            slots=0,
            search_slots=0,
            hydrate_reserve=settings.tradera_hydrate_reserve,
            tick_minutes=tick_minutes,
            core_cycle_hours=0.0,
            budget=budget,
        )
    if calls:
        oldest = min(c.called_at for c in calls)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        minutes_until_oldest_expires = ((oldest + timedelta(hours=24)) - now).total_seconds() / 60
        minutes_until_oldest_expires = max(1.0, minutes_until_oldest_expires)
    else:
        minutes_until_oldest_expires = 24 * 60
    ticks_left = max(1, ceil(minutes_until_oldest_expires / tick_minutes))
    slots = max(1, remaining // ticks_left)
    hydrate_reserve = min(settings.tradera_hydrate_reserve, max(0, slots - 1))
    search_slots = max(0, slots - hydrate_reserve)
    if search_slots == 0 and slots >= 1:
        search_slots = 1
        hydrate_reserve = slots - 1
    cycle_hours = 0.0
    if search_slots and n_core_arms:
        cycle_hours = ceil(n_core_arms / search_slots) * (tick_minutes / 60)
    return SlotBudget(
        remaining=remaining,
        ticks_left=ticks_left,
        slots=slots,
        search_slots=search_slots,
        hydrate_reserve=hydrate_reserve,
        tick_minutes=tick_minutes,
        core_cycle_hours=cycle_hours,
        budget=budget,
    )


def reserve_before_call(session: Session, source: Source, *, now: datetime | None = None) -> bool:
    """Return False if the rolling 24h budget is already spent or 429 cooldown is active."""
    now = now or _now()
    if source.quota_exhausted_until is not None:
        until = source.quota_exhausted_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until > now:
            return False
    budget = source.daily_call_budget or get_settings().tradera_daily_call_budget
    return len(rolling_calls(session, source, now=now)) < budget
