from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.connectors.ebay import GRADED_TITLE_RE, EbayBrowseClient
from pokequant.connectors.pricecharting import PriceChartingClient
from pokequant.db.kv import kv_set
from pokequant.db.models import PriceObservation, WatchlistItem
from pokequant.money import parse_fx_as_of, usd_to_sek_ore
from pokequant.watchlist import list_active_watchlist

logger = logging.getLogger(__name__)

KV_LAST_SYNC_OK = "last_sync_comps_ok"
KV_LAST_SYNC_AT = "last_sync_comps_at"


class CompSyncError(RuntimeError):
    pass


def usd_cents_to_sek_ore(usd_cents: int, usd_sek_rate: float | None = None) -> int:
    rate = usd_sek_rate if usd_sek_rate is not None else get_settings().usd_sek_rate
    return usd_to_sek_ore(usd_cents, rate)


def _query_for_watch(watch: WatchlistItem) -> str:
    aliases = [a.strip() for a in (watch.search_aliases or "").split(";") if a.strip()]
    if aliases:
        return aliases[0]
    parts = [watch.name, watch.set_name, watch.collector_number, watch.variant]
    return " ".join(p for p in parts if p)


def _fx_as_of() -> datetime | None:
    return parse_fx_as_of(get_settings().fx_as_of)


def product_name_matches_watch(name: str, watch: WatchlistItem) -> bool:
    hay = (name or "").lower()
    number = (watch.collector_number or "").lower()
    set_token = (watch.set_code or watch.set_name or "").lower()
    has_number = bool(number) and number in hay
    has_set = bool(set_token) and any(tok and tok in hay for tok in set_token.replace("-", " ").split())
    return has_number or has_set


def sync_external_comps(session: Session, *, watches: list[WatchlistItem] | None = None) -> dict:
    """Fetch eBay + PriceCharting comps. Exits nonzero (via stats['ok']=False) if any watch is stale/missing."""
    settings = get_settings()
    watches = watches if watches is not None else list_active_watchlist(session)
    now = datetime.now(timezone.utc)
    fx_as_of = _fx_as_of()
    stats = {
        "ebay": 0,
        "pricecharting": 0,
        "skipped": 0,
        "missing": 0,
        "stale": 0,
        "rejected": 0,
        "ok": True,
        "errors": [],
    }

    if settings.app_env == "production":
        if not settings.ebay_client_id or not settings.ebay_client_secret:
            stats["ok"] = False
            stats["errors"].append("missing_ebay_credentials")
        if not settings.pricecharting_api_token:
            stats["ok"] = False
            stats["errors"].append("missing_pricecharting_credentials")
        if fx_as_of is None:
            stats["ok"] = False
            stats["errors"].append("missing_fx_as_of")

    ebay = EbayBrowseClient()
    pc = PriceChartingClient()

    for watch in watches:
        query = _query_for_watch(watch)
        got_ebay = False
        got_pc = False

        if ebay.configured():
            try:
                usd_cents = ebay.search_lowest_ask_usd_cents(query)
                if usd_cents:
                    session.add(
                        PriceObservation(
                            watchlist_item_id=watch.id,
                            source="ebay",
                            status="active",
                            observed_at=now,
                            available_to_model_at=now,
                            currency="SEK",
                            price_ore=usd_cents_to_sek_ore(usd_cents),
                            condition="unknown",
                            is_primary=True,
                            external_ref=query,
                            notes=f"ebay browse lowest ask+ship; usd_cents={usd_cents}; fx={settings.usd_sek_rate}",
                            fx_rate_used=settings.usd_sek_rate,
                            fx_as_of=fx_as_of,
                        )
                    )
                    stats["ebay"] += 1
                    got_ebay = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("eBay comp failed for %s: %s", watch.watch_id, exc)
                stats["errors"].append(f"ebay:{watch.watch_id}")
        else:
            logger.info("eBay not configured; skipping")

        if pc.configured():
            try:
                hit = pc.search_ungraded(query)
                if hit and product_name_matches_watch(hit.name, watch):
                    session.add(
                        PriceObservation(
                            watchlist_item_id=watch.id,
                            source="pricecharting",
                            status="guide",
                            observed_at=now,
                            available_to_model_at=now,
                            currency="SEK",
                            price_ore=usd_cents_to_sek_ore(hit.usd_cents),
                            condition="ungraded",
                            is_primary=True,
                            external_ref=query,
                            notes=f"pricecharting ungraded; usd_cents={hit.usd_cents}; fx={settings.usd_sek_rate}",
                            fx_rate_used=settings.usd_sek_rate,
                            fx_as_of=fx_as_of,
                            comp_product_id=hit.product_id,
                        )
                    )
                    stats["pricecharting"] += 1
                    got_pc = True
                elif hit:
                    logger.warning(
                        "PriceCharting name mismatch for %s: %r", watch.watch_id, hit.name
                    )
                    stats["rejected"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("PriceCharting comp failed for %s: %s", watch.watch_id, exc)
                stats["errors"].append(f"pricecharting:{watch.watch_id}")

        if not got_ebay or not got_pc:
            stats["missing"] += 1
            stats["ok"] = False

    cutoff = now - timedelta(hours=settings.comps_stale_hours)
    for watch in watches:
        ebay_row, pc_row = _latest_pair(session, watch)
        if ebay_row is None or pc_row is None:
            continue
        ebay_at = ebay_row.observed_at
        pc_at = pc_row.observed_at
        if ebay_at.tzinfo is None:
            ebay_at = ebay_at.replace(tzinfo=timezone.utc)
        if pc_at.tzinfo is None:
            pc_at = pc_at.replace(tzinfo=timezone.utc)
        if ebay_at < cutoff or pc_at < cutoff:
            stats["stale"] += 1
            stats["ok"] = False

    kv_set(session, KV_LAST_SYNC_OK, "1" if stats["ok"] else "0")
    kv_set(session, KV_LAST_SYNC_AT, now.isoformat())
    audit(session, action="comps.sync_external", entity_type="price_observation", entity_id="batch", details=str(stats))
    return stats


def last_sync_comps_ok(session: Session) -> bool:
    from pokequant.db.kv import kv_get

    return kv_get(session, KV_LAST_SYNC_OK) == "1"


def _latest_pair(
    session: Session, watch: WatchlistItem
) -> tuple[PriceObservation | None, PriceObservation | None]:
    ebay = (
        session.query(PriceObservation)
        .filter(
            PriceObservation.watchlist_item_id == watch.id,
            PriceObservation.source == "ebay",
        )
        .order_by(PriceObservation.observed_at.desc())
        .first()
    )
    pc = (
        session.query(PriceObservation)
        .filter(
            PriceObservation.watchlist_item_id == watch.id,
            PriceObservation.source == "pricecharting",
        )
        .order_by(PriceObservation.observed_at.desc())
        .first()
    )
    return ebay, pc


def latest_external_comps(
    session: Session, watch: WatchlistItem
) -> tuple[int, int, datetime | None, datetime | None]:
    """Return (ebay_ore, pricecharting_ore, ebay_at, pc_at)."""
    ebay, pc = _latest_pair(session, watch)
    return (
        ebay.price_ore if ebay else 0,
        pc.price_ore if pc else 0,
        ebay.observed_at if ebay else None,
        pc.observed_at if pc else None,
    )


# Re-export for tests that imported the regex from here later.
__all__ = [
    "CompSyncError",
    "GRADED_TITLE_RE",
    "last_sync_comps_ok",
    "latest_external_comps",
    "product_name_matches_watch",
    "sync_external_comps",
    "usd_cents_to_sek_ore",
]
