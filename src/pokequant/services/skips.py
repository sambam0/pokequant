from __future__ import annotations

import re

from sqlalchemy.orm import Session

from pokequant.config import get_settings
from pokequant.db.models import Decision, Listing, SkipCandidate
from pokequant.filters import FORBIDDEN_SKIP_TOKENS, is_forbidden_skip_token

TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
PROMOTE_SELLER_FLOOR = 10


def _tokens(title: str) -> list[str]:
    return TOKEN_RE.findall((title or "").lower())


def _char_4grams(title: str) -> list[str]:
    compact = re.sub(r"\s+", "", (title or "").lower())
    return [compact[i : i + 4] for i in range(len(compact) - 3)] if len(compact) >= 4 else []


def enqueue_skip_candidates(
    session: Session,
    listing: Listing,
    *,
    identity_label: str,
    deal_label: str,
) -> list[SkipCandidate]:
    """May not train on Telegram junk. Candidates: identity=wrong, unmatched rejected."""
    del deal_label
    if identity_label != "wrong":
        return []
    created: list[SkipCandidate] = []
    version = get_settings().skip_version
    for token in _tokens(listing.title):
        if is_forbidden_skip_token(token):
            continue
        created.extend(_upsert_candidate(session, token, "token", listing, version))
    for gram in _char_4grams(listing.title)[:8]:
        if any(bad in gram for bad in FORBIDDEN_SKIP_TOKENS):
            continue
        created.extend(_upsert_candidate(session, gram, "char4gram", listing, version))
    return created


def enqueue_from_rejected(session: Session, listing: Listing) -> list[SkipCandidate]:
    if listing.workflow_state != "rejected":
        return []
    return enqueue_skip_candidates(session, listing, identity_label="wrong", deal_label="n/a")


def _upsert_candidate(
    session: Session, pattern: str, pattern_type: str, listing: Listing, version: str
) -> list[SkipCandidate]:
    row = (
        session.query(SkipCandidate)
        .filter_by(pattern=pattern, skip_version=version)
        .one_or_none()
    )
    if row is None:
        row = SkipCandidate(
            pattern=pattern,
            pattern_type=pattern_type,
            source_code=listing.source_code,
            skip_version=version,
            status="queued",
            distinct_sellers=1 if listing.seller_key else 0,
        )
        session.add(row)
        return [row]
    if listing.seller_key:
        row.distinct_sellers = max(row.distinct_sellers, row.distinct_sellers)
    return []


def replay_skips(session: Session, *, days: int = 90) -> dict:
    """90-day replay. Never auto-ship. Fail if any historical really_good would drop."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    candidates = session.query(SkipCandidate).filter_by(status="queued").all()
    hits_good = (
        session.query(Decision)
        .filter(Decision.deal_label == "really_good", Decision.decided_at >= cutoff)
        .all()
    )
    blocked = 0
    ready = 0
    for cand in candidates:
        if cand.distinct_sellers < PROMOTE_SELLER_FLOOR:
            continue
        would_drop_good = False
        for dec in hits_good:
            listing = session.get(Listing, dec.listing_id)
            if listing and cand.pattern.lower() in listing.title.lower():
                would_drop_good = True
                break
        if would_drop_good:
            cand.status = "rejected"
            cand.notes = "replay hit historical really_good"
            blocked += 1
        else:
            ready += 1
            cand.notes = "replay clean; waiting for human ship"
    return {"ready": ready, "blocked": blocked, "auto_promoted": 0}
