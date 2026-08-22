"""Controlled expansion after the 50% precision gate."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from pokequant.db.models import WatchlistItem, WatchlistMeta
from pokequant.services.precision import expansion_allowed


@dataclass
class ExpansionPlan:
    allowed: bool
    reason: str
    next_sources: list[str]
    next_actions: list[str]


def plan_expansion(session: Session) -> ExpansionPlan:
    if not expansion_allowed(session):
        return ExpansionPlan(
            allowed=False,
            reason="Precision gate not passed; keep the frozen ~100-card watchlist.",
            next_sources=[],
            next_actions=[
                "Tune matching thresholds and min_discount_bps",
                "Reduce false matches / lot noise",
                "Keep labeling alerts as really_good / maybe / junk",
            ],
        )

    count = session.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).count()
    return ExpansionPlan(
        allowed=True,
        reason="Precision gate passed. Expand one dimension at a time.",
        next_sources=[
            "Add more watchlist cards (same Tradera source)",
            "eBay Browse active listings (if useful)",
            "Licensed retailer feeds",
            "Manual Blocket/Facebook quick-add only",
        ],
        next_actions=[
            f"Current active watchlist size: {count}",
            "Increase watchlist in batches of 25 after each weekly precision check",
            "Do not enable prohibited scrapers",
            "Re-freeze and re-measure precision after each expansion batch",
        ],
    )


def assert_can_add_watchlist_items(session: Session, *, force: bool = False) -> None:
    meta = session.query(WatchlistMeta).order_by(WatchlistMeta.id.desc()).first()
    if force:
        return
    if meta and meta.frozen_at and not meta.expansion_allowed:
        raise RuntimeError(
            "Watchlist is frozen until precision gate passes. "
            "Use force=True only for identity-error corrections."
        )
