from __future__ import annotations

from statistics import median

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.db.models import Decision, PrecisionSnapshot, WatchlistMeta


def _identity_set(decisions: list[Decision]) -> list[Decision]:
    return [d for d in decisions if d.identity_label in {"correct", "wrong"}]


def _deal_set(decisions: list[Decision]) -> list[Decision]:
    return [
        d
        for d in decisions
        if d.identity_label == "correct" and d.deal_label in {"really_good", "maybe", "junk"}
    ]


def latest_precision(session: Session, *, source: str = "tradera") -> PrecisionSnapshot | None:
    return (
        session.query(PrecisionSnapshot)
        .filter(PrecisionSnapshot.source_code == source)
        .order_by(PrecisionSnapshot.id.desc())
        .first()
    )


def compute_precision(
    session: Session, *, window: int | None = None, source: str = "tradera"
) -> PrecisionSnapshot:
    """Two-rate precision. wrong is not in D. Writes a snapshot — CLI/cron only."""
    settings = get_settings()
    window = window or settings.precision_min_labeled
    decisions = (
        session.query(Decision)
        .filter(Decision.source_code == source)
        .order_by(Decision.decided_at.desc())
        .all()
    )
    # Backfill source_code from listing when older rows were written without it.
    if not decisions:
        decisions = (
            session.query(Decision)
            .order_by(Decision.decided_at.desc())
            .all()
        )
        decisions = [d for d in decisions if (d.source_code or _listing_source(session, d)) == source]

    identity = _identity_set(decisions)
    deal = _deal_set(decisions)
    identity = identity[: max(window, len(identity))]
    deal = deal[:window]

    i_n = len(identity)
    d_n = len(deal)
    wrong = sum(1 for d in identity if d.identity_label == "wrong")
    really_good = sum(1 for d in deal if d.deal_label == "really_good")
    maybe = sum(1 for d in deal if d.deal_label == "maybe")
    junk = sum(1 for d in deal if d.deal_label == "junk")
    false_rate = (wrong / i_n) if i_n else 0.0
    good_rate = (really_good / d_n) if d_n else 0.0

    latencies = []
    for d in deal:
        if d.alerted_at and d.decided_at:
            latencies.append((d.decided_at - d.alerted_at).total_seconds())
    med_latency = float(median(latencies)) if latencies else None

    gate_passed = (
        source == "tradera"
        and i_n >= settings.precision_min_labeled
        and d_n >= settings.precision_min_labeled
        and good_rate >= settings.precision_min_really_good_rate
        and false_rate <= settings.precision_max_false_match_rate
    )

    snap = PrecisionSnapshot(
        window_size=window,
        labeled_count=d_n,
        really_good_count=really_good,
        maybe_count=maybe,
        junk_count=junk,
        false_match_count=wrong,
        really_good_rate=good_rate,
        false_match_rate=false_rate,
        median_decision_seconds=med_latency,
        gate_passed=gate_passed,
        notes=f"two-rate source={source} |I|={i_n} |D|={d_n}",
        source_code=source,
        identity_labeled_count=i_n,
        deal_labeled_count=d_n,
        wrong_count=wrong,
    )
    session.add(snap)

    if source == "tradera":
        meta = session.query(WatchlistMeta).order_by(WatchlistMeta.id.desc()).first()
        if meta is None:
            meta = WatchlistMeta()
            session.add(meta)
        meta.expansion_allowed = gate_passed
        if gate_passed:
            meta.notes = f"Precision gate passed: good={good_rate:.1%} I={i_n} D={d_n}"
    audit(
        session,
        action="precision.compute",
        entity_type="precision_snapshot",
        entity_id=source,
        details=f"good={good_rate:.3f}; false={false_rate:.3f}; I={i_n}; D={d_n}; gate={gate_passed}",
    )
    return snap


def _listing_source(session: Session, decision: Decision) -> str:
    listing = decision.listing
    if listing is not None:
        return listing.source_code
    from pokequant.db.models import Listing

    row = session.get(Listing, decision.listing_id)
    return row.source_code if row else ""


def expansion_allowed(session: Session) -> bool:
    meta = session.query(WatchlistMeta).order_by(WatchlistMeta.id.desc()).first()
    return bool(meta and meta.expansion_allowed)
