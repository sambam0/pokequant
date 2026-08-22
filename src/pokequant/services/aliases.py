from __future__ import annotations

import re

from sqlalchemy.orm import Session

from pokequant.db.models import AliasProposal, Listing, WatchlistItem

NUMBER_RE = re.compile(r"\b(\d{1,3})\s*/\s*\d{1,3}\b|\b(\d{1,3})\b")


def _has_collector_and_set(title: str, watch: WatchlistItem) -> bool:
    hay = title.lower()
    number = (watch.collector_number or "").lower()
    set_token = (watch.set_code or watch.set_name or "").lower()
    has_number = bool(number) and (number in hay or bool(NUMBER_RE.search(hay)))
    has_set = bool(set_token) and any(tok and tok in hay for tok in set_token.replace("-", " ").split())
    return has_number and has_set


def propose_aliases(session: Session) -> list[AliasProposal]:
    """Queue only. Hermes never writes aliases. Human approves → search_aliases."""
    unmatched = (
        session.query(Listing)
        .filter(Listing.workflow_state == "rejected", Listing.source_code == "tradera")
        .all()
    )
    watches = session.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    created: list[AliasProposal] = []
    for listing in unmatched:
        for watch in watches:
            if not watch.collector_number:
                continue
            if watch.collector_number.lower() not in listing.title.lower():
                continue
            alias = listing.title.strip()[:120]
            existing = (
                session.query(AliasProposal)
                .filter_by(proposed_alias=alias, watchlist_item_id=watch.id)
                .one_or_none()
            )
            if existing:
                if listing.seller_key and listing.seller_key != existing.seller_key:
                    existing.distinct_sellers = max(existing.distinct_sellers, 2)
                continue
            needs_human = not _has_collector_and_set(listing.title, watch)
            row = AliasProposal(
                watchlist_item_id=watch.id,
                proposed_alias=alias,
                title_sample=listing.title,
                seller_key=listing.seller_key,
                distinct_sellers=1 if listing.seller_key else 0,
                status="needs_human" if needs_human else "queued",
                needs_human=needs_human,
            )
            session.add(row)
            created.append(row)
    return created


def approve_alias(session: Session, proposal_id: int) -> WatchlistItem | None:
    row = session.get(AliasProposal, proposal_id)
    if row is None or row.watchlist_item_id is None:
        return None
    if row.distinct_sellers < 2 or not row.seller_key:
        row.status = "needs_human"
        row.needs_human = True
        return None
    watch = session.get(WatchlistItem, row.watchlist_item_id)
    if watch is None:
        return None
    aliases = [a.strip() for a in (watch.search_aliases or "").split(";") if a.strip()]
    if row.proposed_alias not in aliases:
        aliases.append(row.proposed_alias)
        watch.search_aliases = ";".join(aliases)
    row.status = "approved"
    return watch
