from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.db.models import Decision, Listing, Valuation
from pokequant.services.scout import credit_decision, resolve_labeled_pulls
from pokequant.services.skips import enqueue_skip_candidates
from pokequant.workflow.states import transition_listing


def record_decision(
    session: Session,
    listing: Listing,
    *,
    intent: str,
    quality_label: str | None = None,
    identity_label: str | None = None,
    deal_label: str | None = None,
    reviewer: str = "domain",
    reason_code: str | None = None,
    notes: str = "",
    valuation: Valuation | None = None,
    alerted_at: datetime | None = None,
    false_match: bool = False,
    callback_query_id: str | None = None,
) -> Decision:
    if callback_query_id:
        existing = session.query(Decision).filter_by(callback_query_id=callback_query_id).one_or_none()
        if existing is not None:
            return existing

    identity = identity_label or ("wrong" if false_match or reason_code == "wrong_identity" else "correct")
    deal = deal_label or quality_label or "n/a"
    if identity == "wrong":
        deal = "n/a"
    quality = deal if deal != "n/a" else (quality_label or "junk")

    if listing.workflow_state == "alerted":
        listing.workflow_state = transition_listing(listing.workflow_state, "decided")

    snapshot_valuation = valuation
    decision = Decision(
        listing_id=listing.id,
        valuation_id=snapshot_valuation.id if snapshot_valuation else None,
        reviewer=reviewer,
        intent=intent,
        quality_label=quality,
        identity_label=identity,
        deal_label=deal,
        reason_code=reason_code,
        notes=notes,
        decided_at=datetime.now(timezone.utc),
        alerted_at=alerted_at,
        false_match=false_match or identity == "wrong",
        callback_query_id=callback_query_id,
        passes_hard_gates=snapshot_valuation.passes_hard_gates if snapshot_valuation else None,
        gate_failures=snapshot_valuation.gate_failures if snapshot_valuation else "",
        match_confidence=listing.match_confidence,
        matched_alias=listing.matched_alias,
        scout_arm_id=listing.scout_arm_id,
        query_pull_id=listing.query_pull_id,
        source_code=listing.source_code,
    )
    session.add(decision)
    if intent == "buy":
        listing.workflow_state = transition_listing(listing.workflow_state, "purchased")
    elif listing.workflow_state in {"decided", "alerted"}:
        listing.workflow_state = transition_listing(listing.workflow_state, "closed")
    audit(
        session,
        action="decision.record",
        entity_type="listing",
        entity_id=listing.id,
        actor=reviewer,
        details=f"{intent}/{identity}/{deal}/{reason_code or '-'}",
    )
    session.flush()
    credit_decision(session, listing, deal_label=deal, identity_label=identity)
    enqueue_skip_candidates(session, listing, identity_label=identity, deal_label=deal)
    resolve_labeled_pulls(session)
    return decision
