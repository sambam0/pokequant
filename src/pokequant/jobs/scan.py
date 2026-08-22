from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.alerts.telegram_bot import deliver_telegram_alert
from pokequant.config import get_settings
from pokequant.connectors.base import NormalizedListing
from pokequant.connectors.tradera import (
    QuotaExhausted,
    TraderaClient,
    is_bin_listing,
)
from pokequant.db.kv import kv_set
from pokequant.db.models import Listing, Source
from pokequant.quota import compute_slot_budget, record_api_call, reserve_before_call
from pokequant.runtime import (
    deals_send_allowed,
    effective_status,
    scan_allowed,
    write_state,
)
from pokequant.services.comps import last_sync_comps_ok
from pokequant.services.ingest import IngestRejected, enqueue_rejected, upsert_listing
from pokequant.services.scoring import score_listing
from pokequant.services.scout import (
    ensure_scout_arms,
    finish_query_pull,
    hermes_queries,
    start_query_pull,
)
from pokequant.watchlist import list_active_watchlist
from pokequant.workflow.states import transition_listing

logger = logging.getLogger(__name__)

HEARTBEAT_PATH = Path("data/hermes/heartbeat")


def touch_heartbeat() -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def ensure_tradera_source(session: Session) -> Source:
    source = session.query(Source).filter_by(code="tradera").one_or_none()
    if source is None:
        source = Source(
            code="tradera",
            name="Tradera",
            access_tier="production",
            access_basis="Official REST API v4 app credentials",
            daily_call_budget=get_settings().tradera_daily_call_budget,
        )
        session.add(source)
        session.flush()
    return source


def ensure_facebook_source(session: Session) -> Source:
    source = session.query(Source).filter_by(code="facebook").one_or_none()
    if source is None:
        source = Source(
            code="facebook",
            name="Facebook Marketplace",
            access_tier="permission",
            access_basis="v1.5 — written EXPANSION permission required",
            daily_call_budget=0,
        )
        session.add(source)
        session.flush()
    return source


def _should_realert(session: Session, listing: Listing) -> bool:
    settings = get_settings()
    if listing.workflow_state in {"purchased"}:
        return False
    if listing.workflow_state not in {"alerted", "scored", "below_threshold", "discovered", "matched"}:
        if listing.workflow_state in {"decided", "closed"}:
            return False
    from pokequant.db.models import AlertDelivery

    last = (
        session.query(AlertDelivery)
        .filter_by(listing_id=listing.id)
        .order_by(AlertDelivery.id.desc())
        .first()
    )
    if last is None:
        return True
    delivered = last.delivered_at
    if delivered.tzinfo is None:
        delivered = delivered.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - delivered >= timedelta(hours=settings.alert_realert_hours)


def _alerts_today(session: Session) -> int:
    from pokequant.db.models import AlertDelivery

    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return session.query(AlertDelivery).filter(AlertDelivery.delivered_at >= start).count()


def _wip_open(session: Session) -> int:
    return session.query(Listing).filter(Listing.workflow_state == "alerted").count()


def run_watchlist_scan(
    session: Session,
    *,
    dry_run_alerts: bool = True,
    use_fixture: list | None = None,
    send_telegram: bool = False,
) -> dict:
    settings = get_settings()
    dry_run_alerts = dry_run_alerts and not send_telegram
    status = effective_status()
    if use_fixture is None and not scan_allowed(status):
        return {"error": f"scan blocked by state={status}"}

    source = ensure_tradera_source(session)
    ensure_facebook_source(session)
    watch_items = list_active_watchlist(session)
    if not watch_items:
        return {"error": "watchlist empty"}

    ensure_scout_arms(session, source="tradera")
    session.flush()

    if use_fixture is None and send_telegram and not last_sync_comps_ok(session):
        return {"error": "last sync-comps failed; refusing --send-telegram"}

    if source.quota_exhausted_until:
        until = source.quota_exhausted_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until > datetime.now(timezone.utc):
            write_state("quota_exhausted", reason="429 cooldown", actor="scan")
            return {"error": "quota_exhausted", "until": until.isoformat()}

    arms, budget = hermes_queries(session, source)
    client: TraderaClient | None = None
    listings: list[NormalizedListing] = []
    calls = 0
    truncated_any = False

    if use_fixture is not None:
        listings = use_fixture
    else:
        client = TraderaClient(
            on_call=lambda url, status_code: record_api_call(
                session, source, endpoint=url, http_status=status_code
            )
        )
        if not client.configured():
            return {"error": "TRADERA_APP_ID/TRADERA_APP_KEY not configured"}
        try:
            for arm in arms:
                if not reserve_before_call(session, source):
                    break
                pull = start_query_pull(session, arm)
                found = client.search(arm.key)
                if client.last_truncated:
                    truncated_any = True
                listing_ids: list[int] = []
                n_new = 0
                for normalized in found:
                    normalized.scout_arm_id = arm.id
                    normalized.query_pull_id = pull.id
                    listings.append(normalized)
                finish_query_pull(session, pull, listing_ids=listing_ids, n_new=n_new, n_alerted=0)
            calls = client.calls_made
        except QuotaExhausted as exc:
            source.quota_exhausted_until = exc.retry_after
            write_state("quota_exhausted", reason="HTTP 429", actor="scan")
            session.commit()
            raise

    alerted = 0
    scored = 0
    ingested = 0
    skipped_auction = 0
    hydrate_used = 0
    matched_pending_hydrate: list[tuple[Listing, NormalizedListing]] = []

    for normalized in listings:
        try:
            listing = upsert_listing(session, normalized)
        except IngestRejected as exc:
            logger.info("ingest rejected %s: %s", normalized.external_id, exc)
            continue
        session.flush()
        ingested += 1
        if listing.query_pull_id is None and normalized.query_pull_id:
            listing.query_pull_id = normalized.query_pull_id
        if listing.workflow_state == "expired":
            continue
        if listing.listing_type == "auction" or (
            not is_bin_listing(normalized) and listing.listing_type == "auction"
        ):
            skipped_auction += 1
            continue
        if not is_bin_listing(normalized) and listing.listing_type not in {"bin", "shop", "auction_with_bin"}:
            if normalized.price_ore is None:
                listing.listing_type = "auction"
                skipped_auction += 1
                continue

        if listing.workflow_state == "purchased":
            continue

        match_watch = None
        from pokequant.valuation.match import match_title_to_watchlist

        match = match_title_to_watchlist(listing.title, watch_items)
        if match is None:
            if listing.workflow_state == "discovered":
                listing.workflow_state = transition_listing(listing.workflow_state, "rejected")
                enqueue_rejected(session, listing)
            continue
        match_watch = match
        listing.watchlist_item_id = match.watchlist_item.id
        listing.match_confidence = match.confidence
        listing.matched_alias = match.matched_alias

        needs_hydrate = listing.shipping_ore is None or listing.buyer_fee_ore is None
        if needs_hydrate and client is not None and hydrate_used < budget.hydrate_reserve:
            if reserve_before_call(session, source):
                try:
                    hydrated = client.hydrate(normalized)
                    listing = upsert_listing(session, hydrated)
                    hydrate_used += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("item hydrate failed %s: %s", listing.external_id, exc)
                    matched_pending_hydrate.append((listing, normalized))
                    continue
        elif needs_hydrate and client is not None:
            matched_pending_hydrate.append((listing, normalized))
            continue

        if listing.workflow_state in {"alerted", "decided", "purchased"} and not _should_realert(
            session, listing
        ):
            continue

        valuation = score_listing(session, listing, watch_items)
        session.flush()
        if valuation is None:
            continue
        scored += 1
        if not valuation.passes_hard_gates:
            continue
        if not _should_realert(session, listing) and listing.workflow_state == "alerted":
            continue

        settings_cap = settings.alert_daily_cap
        if _alerts_today(session) >= settings_cap or _wip_open(session) >= settings.review_wip_limit:
            write_state("throttle_alerts", reason="daily cap or review WIP", actor="scan")
            if not dry_run_alerts:
                continue
        if not dry_run_alerts and not deals_send_allowed():
            continue

        watch_name = match_watch.watchlist_item.name if match_watch else "?"
        delivery = deliver_telegram_alert(
            session, listing, valuation, watch_name, dry_run=dry_run_alerts
        )
        if delivery is not None:
            alerted += 1
            session.commit()  # commit-per-alert so a crash cannot replay alerted
        del match_watch

    touch_heartbeat()
    kv_set(session, "last_scan_at", datetime.now(timezone.utc).isoformat())
    session.commit()
    return {
        "queries": len(arms),
        "search_slots": budget.search_slots,
        "hydrate_reserve": budget.hydrate_reserve,
        "api_calls": calls if client else 0,
        "listings": len(listings),
        "ingested": ingested,
        "scored": scored,
        "alerted": alerted,
        "auction_skipped": skipped_auction,
        "hydrate_used": hydrate_used,
        "hydrate_deferred": len(matched_pending_hydrate),
        "truncated": truncated_any,
        "core_cycle_hours": budget.core_cycle_hours,
        "remaining_calls": budget.remaining,
        "state": effective_status(),
    }
