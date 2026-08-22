from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.connectors.base import NormalizedListing
from pokequant.db.models import Listing, ListingSnapshot, Source
from pokequant.filters import Drop, should_drop
from pokequant.workflow.states import NEVER_REOPEN, REOPENABLE_STATES, transition_listing


class IngestRejected(ValueError):
    pass


def facebook_ingest_allowed() -> bool:
    settings = get_settings()
    return Path(settings.facebook_permission_path).exists()


def assert_source_allowed(session: Session, source_code: str) -> None:
    if source_code == "tradera":
        return
    if source_code == "facebook":
        source = session.query(Source).filter_by(code="facebook").one_or_none()
        if (
            source
            and source.access_tier == "production"
            and facebook_ingest_allowed()
        ):
            return
        raise IngestRejected("facebook ingest blocked until written EXPANSION permission")
    raise IngestRejected(f"source {source_code!r} is not enabled in v1")


def validate_normalized(normalized: NormalizedListing) -> None:
    if not normalized.external_id:
        raise IngestRejected("missing external_id")
    if not normalized.url:
        raise IngestRejected("missing url")
    if not normalized.title:
        raise IngestRejected("missing title")
    if not normalized.currency:
        raise IngestRejected("missing currency")
    if normalized.listing_type in {"bin", "shop", "auction_with_bin"}:
        if normalized.price_ore is None or normalized.price_ore <= 0:
            raise IngestRejected("BIN listing missing price_ore")


def _material_drop(listing: Listing, normalized: NormalizedListing) -> bool:
    settings = get_settings()
    old_price = listing.price_ore
    new_price = normalized.price_ore
    if old_price and new_price is not None and old_price > 0:
        drop_bps = int(round((1 - (new_price / old_price)) * 10_000))
        if drop_bps >= settings.material_drop_bps:
            return True
    old_ship = listing.shipping_ore
    new_ship = normalized.shipping_ore
    if old_ship and new_ship is not None and old_ship > 0:
        drop_bps = int(round((1 - (new_ship / old_ship)) * 10_000))
        if drop_bps >= settings.material_drop_bps:
            return True
    watch = listing.watchlist_item
    if watch and watch.max_buy_ore and new_price is not None:
        old_landed = (old_price or 0) + (listing.shipping_ore or 0)
        new_landed = new_price + (new_ship or 0)
        if old_landed >= watch.max_buy_ore > new_landed:
            return True
    return False


def upsert_listing(session: Session, normalized: NormalizedListing) -> Listing:
    assert_source_allowed(session, normalized.source_code)
    validate_normalized(normalized)
    drop = should_drop(normalized.title, normalized.source_code, get_settings().skip_version)
    if isinstance(drop, Drop):
        raise IngestRejected(drop.reason)

    listing = (
        session.query(Listing)
        .filter_by(source_code=normalized.source_code, external_id=normalized.external_id)
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    created = False
    if listing is None:
        listing = Listing(
            source_code=normalized.source_code,
            external_id=normalized.external_id,
            url=normalized.url,
            title=normalized.title,
            workflow_state="discovered",
            first_seen_at=now,
        )
        session.add(listing)
        created = True

    prev_hash = listing.raw_hash
    prev_price = listing.price_ore
    prev_shipping = listing.shipping_ore

    if listing.workflow_state not in NEVER_REOPEN and listing.workflow_state in REOPENABLE_STATES:
        if _material_drop(listing, normalized):
            listing.workflow_state = transition_listing(listing.workflow_state, "discovered")

    listing.url = normalized.url
    listing.title = normalized.title
    listing.description = normalized.description
    listing.currency = normalized.currency
    listing.price_ore = normalized.price_ore
    listing.shipping_ore = normalized.shipping_ore
    listing.buyer_fee_ore = normalized.buyer_fee_ore
    listing.seller_type = normalized.seller_type
    listing.seller_key = normalized.seller_key
    listing.image_urls = "\n".join(normalized.image_urls)
    listing.status = normalized.status
    listing.last_seen_at = now
    listing.source_timestamp = normalized.source_timestamp
    listing.raw_hash = normalized.raw_hash
    listing.listing_type = normalized.listing_type or listing.listing_type
    if listing.listing_type == "unknown" and normalized.price_ore:
        listing.listing_type = "bin"
    listing.fulfillment = normalized.fulfillment or listing.fulfillment
    listing.extractor_version = normalized.extractor_version or listing.extractor_version
    if normalized.scout_arm_id and listing.scout_arm_id is None:
        listing.scout_arm_id = normalized.scout_arm_id
    if normalized.query_pull_id and listing.query_pull_id is None:
        listing.query_pull_id = normalized.query_pull_id

    if normalized.is_ended or normalized.status == "ended":
        listing.status = "ended"
        if listing.workflow_state not in NEVER_REOPEN | {"expired"}:
            listing.workflow_state = transition_listing(listing.workflow_state, "expired")

    hash_changed = created or prev_hash != normalized.raw_hash
    price_changed = created or prev_price != normalized.price_ore or prev_shipping != normalized.shipping_ore
    if hash_changed or price_changed:
        session.add(
            ListingSnapshot(
                listing=listing,
                observed_at=normalized.source_timestamp or now,
                ingested_at=now,
                available_to_model_at=now,
                price_ore=normalized.price_ore,
                shipping_ore=normalized.shipping_ore,
                status=normalized.status,
                raw_payload=normalized.raw_payload,
                raw_hash=normalized.raw_hash,
            )
        )
    audit(
        session,
        action="listing.upsert" if not created else "listing.create",
        entity_type="listing",
        entity_id=f"{normalized.source_code}:{normalized.external_id}",
        details=normalized.title[:200],
    )
    return listing


def enqueue_rejected(session: Session, listing: Listing) -> None:
    from pokequant.services.skips import enqueue_from_rejected

    enqueue_from_rejected(session, listing)


def mark_duplicate(session: Session, listing: Listing) -> None:
    listing.workflow_state = transition_listing(listing.workflow_state, "duplicate")
    listing.workflow_state = transition_listing(listing.workflow_state, "closed")


def compact_snapshots(session: Session, *, keep_days: int = 30) -> int:
    """Drop older identical-hash snapshots; keep latest per listing."""
    from datetime import timedelta

    from sqlalchemy import func

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    latest_ids = {
        row[0]
        for row in session.query(func.max(ListingSnapshot.id)).group_by(ListingSnapshot.listing_id).all()
    }
    stale = (
        session.query(ListingSnapshot)
        .filter(ListingSnapshot.ingested_at < cutoff)
        .filter(ListingSnapshot.id.notin_(latest_ids) if latest_ids else True)
        .all()
    )
    removed = 0
    for snap in stale:
        session.delete(snap)
        removed += 1
    return removed
