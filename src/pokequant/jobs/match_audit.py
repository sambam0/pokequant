from __future__ import annotations

import re

from sqlalchemy.orm import Session

from pokequant.db.models import Listing, WatchlistItem
from pokequant.valuation.match import match_title_to_watchlist

NUMBER_IN_TITLE = re.compile(r"\b\d{1,3}\s*/\s*\d{1,3}\b")


def match_audit(session: Session) -> dict:
    watches = session.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).all()
    unmatched = session.query(Listing).filter(Listing.workflow_state == "rejected").all()
    misses = []
    for listing in unmatched:
        if not NUMBER_IN_TITLE.search(listing.title):
            continue
        hit = match_title_to_watchlist(listing.title, watches)
        if hit is None:
            misses.append({"id": listing.id, "title": listing.title, "external_id": listing.external_id})
    return {"unmatched": len(unmatched), "collector_number_misses": misses}
