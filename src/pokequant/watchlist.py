from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.db.models import WatchlistItem, WatchlistMeta
from pokequant.expansion import assert_can_add_watchlist_items


def import_watchlist_csv(
    session: Session, path: str | Path, *, freeze: bool = True, force_identity_fix: bool = False
) -> int:
    assert_can_add_watchlist_items(session, force=force_identity_fix)
    path = Path(path)
    count = 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            watch_id = (row.get("watch_id") or "").strip()
            if not watch_id:
                continue
            item = session.query(WatchlistItem).filter_by(watch_id=watch_id).one_or_none()
            if item is None:
                item = WatchlistItem(watch_id=watch_id)
                session.add(item)
            item.name = row.get("name") or item.name
            item.set_code = row.get("set_code") or ""
            item.set_name = row.get("set_name") or ""
            item.collector_number = row.get("collector_number") or ""
            item.language = row.get("language") or "en"
            item.variant = row.get("variant") or "normal"
            item.tcgdex_id = row.get("tcgdex_id") or None
            item.search_aliases = row.get("search_aliases") or ""
            item.condition_floor = row.get("condition_floor") or "LP"
            item.priority = row.get("priority") or "core"
            item.min_discount_bps = int(row.get("min_discount_bps") or 2500)
            max_buy = row.get("max_buy_ore") or ""
            item.max_buy_ore = int(max_buy) if str(max_buy).strip() else None
            item.reference_source = row.get("reference_source") or "cardmarket"
            item.notes = row.get("notes") or ""
            if row.get("buy_thesis"):
                item.buy_thesis = row["buy_thesis"].strip()
            if row.get("grade_tier"):
                item.grade_tier = row["grade_tier"].strip()
            item.active = True
            item.frozen = freeze
            count += 1

    meta = session.query(WatchlistMeta).order_by(WatchlistMeta.id.desc()).first()
    if meta is None:
        meta = WatchlistMeta()
        session.add(meta)
    if freeze:
        meta.frozen_at = datetime.now(timezone.utc)
        meta.frozen_by = "import"
        meta.expansion_allowed = False
        meta.notes = f"Imported {count} rows from {path.name}"
    audit(session, action="watchlist.import", entity_type="watchlist", entity_id=path.name, details=f"count={count}")
    return count


def list_active_watchlist(session: Session) -> list[WatchlistItem]:
    return (
        session.query(WatchlistItem)
        .filter(WatchlistItem.active.is_(True))
        .order_by(WatchlistItem.priority.asc(), WatchlistItem.watch_id.asc())
        .all()
    )
