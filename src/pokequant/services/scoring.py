from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from pokequant.config import get_settings
from pokequant.db.models import GradeCatalog, Listing, PriceObservation, Valuation, WatchlistItem
from pokequant.grading.score import score_prices
from pokequant.money import fx_age_days, parse_fx_as_of
from pokequant.services.comps import latest_external_comps
from pokequant.valuation.engine import ValuationInput, compute_valuation
from pokequant.valuation.match import match_title_to_watchlist
from pokequant.workflow.states import transition_listing


def latest_eu_reference_ore(session: Session, watch: WatchlistItem) -> tuple[int, int, int]:
    """Optional Cardmarket/TCGdex refs for resale sizing (not the buy gate)."""
    rows = (
        session.query(PriceObservation)
        .filter(PriceObservation.watchlist_item_id == watch.id)
        .filter(PriceObservation.source.in_(["cardmarket", "tcgdex"]))
        .order_by(PriceObservation.observed_at.desc())
        .limit(5)
        .all()
    )
    if not rows and watch.tcgdex_id:
        rows = (
            session.query(PriceObservation)
            .filter(PriceObservation.external_ref == watch.tcgdex_id)
            .filter(PriceObservation.source.in_(["cardmarket", "tcgdex"]))
            .order_by(PriceObservation.observed_at.desc())
            .limit(5)
            .all()
        )
    if not rows:
        return 0, 0, 0
    prices = sorted(r.price_ore for r in rows)
    return prices[0], prices[len(prices) // 2], prices[-1]


def _fx_stale(session: Session, watch: WatchlistItem) -> bool:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    rows = (
        session.query(PriceObservation)
        .filter(PriceObservation.watchlist_item_id == watch.id)
        .filter(PriceObservation.source.in_(["ebay", "pricecharting"]))
        .order_by(PriceObservation.observed_at.desc())
        .all()
    )
    used = [r for r in rows if r.fx_rate_used is not None]
    if not used:
        return False
    as_of = None
    for row in used:
        if row.fx_as_of is not None:
            as_of = row.fx_as_of
            break
    if as_of is None:
        as_of = parse_fx_as_of(settings.fx_as_of)
    age = fx_age_days(as_of, now=now)
    if age is None:
        return True
    return age > settings.fx_max_age_days


def _comps_stale(ebay_at: datetime | None, pc_at: datetime | None) -> bool:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.comps_stale_hours)
    if ebay_at is None or pc_at is None:
        return True
    if ebay_at.tzinfo is None:
        ebay_at = ebay_at.replace(tzinfo=timezone.utc)
    if pc_at.tzinfo is None:
        pc_at = pc_at.replace(tzinfo=timezone.utc)
    return ebay_at < cutoff or pc_at < cutoff


def convert_listing_currency(price_ore: int | None, currency: str) -> tuple[int | None, str | None]:
    """SEK as-is. EUR/USD via dated rates. Other / missing rate → reject."""
    if price_ore is None:
        return None, "missing_price"
    cur = (currency or "").upper()
    if not cur:
        return None, "missing_currency"
    if cur == "SEK":
        return price_ore, None
    settings = get_settings()
    as_of = parse_fx_as_of(settings.fx_as_of)
    if as_of is None or fx_age_days(as_of) is None:
        return None, "missing_fx"
    if fx_age_days(as_of) > settings.fx_max_age_days:
        return None, "stale_fx"
    if cur == "EUR":
        major = price_ore / 100.0
        return int(round(major * settings.eur_sek_rate * 100)), None
    if cur == "USD":
        major = price_ore / 100.0
        return int(round(major * settings.usd_sek_rate * 100)), None
    return None, "unsupported_currency"


def score_listing(session: Session, listing: Listing, watch_items: list[WatchlistItem]) -> Valuation | None:
    if listing.listing_type == "auction":
        return None
    if listing.workflow_state == "expired" or listing.status == "ended":
        return None

    match = match_title_to_watchlist(listing.title, watch_items)
    if match is None:
        if listing.workflow_state == "discovered":
            listing.workflow_state = transition_listing(listing.workflow_state, "rejected")
        return None

    listing.watchlist_item_id = match.watchlist_item.id
    listing.match_confidence = match.confidence
    listing.matched_alias = match.matched_alias
    if listing.workflow_state == "discovered":
        listing.workflow_state = transition_listing(listing.workflow_state, "matched")

    if listing.listing_type == "auction":
        return None

    watch = match.watchlist_item
    ebay_ore, pc_ore, ebay_at, pc_at = latest_external_comps(session, watch)
    p10, p50, p90 = latest_eu_reference_ore(session, watch)
    asking, fx_err = convert_listing_currency(listing.price_ore, listing.currency)
    thesis = watch.buy_thesis or "flip_raw"
    if asking is None:
        result_fail = compute_valuation(
            ValuationInput(
                asking_ore=listing.price_ore or 0,
                inbound_shipping_ore=listing.shipping_ore,
                buyer_fee_ore=listing.buyer_fee_ore,
                ebay_comp_ore=ebay_ore,
                pricecharting_comp_ore=pc_ore,
                identity_confidence=match.confidence,
                min_discount_bps=watch.min_discount_bps,
                hard_max_buy_ore=watch.max_buy_ore,
                listing_type=listing.listing_type,
                fx_stale=fx_err == "stale_fx",
                buy_thesis=thesis,
                require_cheaper_than_external=thesis != "grade_upside",
                **_grade_kwargs(session, watch, listing.price_ore or 0, listing),
            )
        )
        result_fail.gate_failures.append(fx_err or "currency")
        result_fail.passes_hard_gates = False
        asking = listing.price_ore or 0
        result = result_fail
    else:
        result = compute_valuation(
            ValuationInput(
                asking_ore=asking,
                inbound_shipping_ore=listing.shipping_ore,
                buyer_fee_ore=listing.buyer_fee_ore,
                ebay_comp_ore=ebay_ore,
                pricecharting_comp_ore=pc_ore,
                reference_p10_ore=p10,
                reference_p50_ore=p50,
                reference_p90_ore=p90,
                identity_confidence=match.confidence,
                min_discount_bps=watch.min_discount_bps,
                hard_max_buy_ore=watch.max_buy_ore,
                min_expected_profit_ore=0,
                require_cheaper_than_external=thesis != "grade_upside",
                comps_stale=_comps_stale(ebay_at, pc_at),
                fx_stale=_fx_stale(session, watch),
                listing_type=listing.listing_type,
                buy_thesis=thesis,
                **_grade_kwargs(
                    session,
                    watch,
                    asking if asking is not None else (listing.price_ore or 0),
                    listing,
                ),
            )
        )

    valuation = Valuation(
        listing_id=listing.id,
        watchlist_item_id=watch.id,
        model_version=result.model_version,
        fee_schedule_version=result.fee_schedule_version,
        market_value_p10_ore=result.market_value_p10_ore,
        market_value_p50_ore=result.market_value_p50_ore,
        market_value_p90_ore=result.market_value_p90_ore,
        expected_net_proceeds_ore=result.expected_net_proceeds_ore,
        landed_cost_ore=result.landed_cost_ore,
        expected_profit_ore=result.expected_profit_ore,
        max_buy_ore=result.max_buy_ore,
        discount_bps=result.discount_bps,
        identity_confidence=result.identity_confidence,
        passes_hard_gates=result.passes_hard_gates,
        gate_failures=",".join(result.gate_failures),
        explanation=result.explanation + f"; alias={match.matched_alias}",
        passed_thesis=result.passed_thesis,
        grade_ev_ore=result.grade_ev_ore,
    )
    session.add(valuation)
    if listing.workflow_state == "matched":
        listing.workflow_state = transition_listing(listing.workflow_state, "scored")
    elif listing.workflow_state in {"below_threshold", "discovered"}:
        if listing.workflow_state == "discovered":
            listing.workflow_state = transition_listing(listing.workflow_state, "matched")
            listing.workflow_state = transition_listing(listing.workflow_state, "scored")
        elif listing.workflow_state == "below_threshold":
            listing.workflow_state = transition_listing(listing.workflow_state, "scored")
    if result.passes_hard_gates:
        return valuation
    if listing.workflow_state == "scored":
        listing.workflow_state = transition_listing(listing.workflow_state, "below_threshold")
    return valuation


def _grade_kwargs(
    session: Session, watch: WatchlistItem, asking_ore: int, listing: Listing
) -> dict:
    settings = get_settings()
    empty = {
        "grade_ev_ore": 0,
        "grade_max_buy_ore": 0,
        "grade_cost_ore": 0,
        "psa9_floor_profit_ore": 0,
        "min_grade_profit_ore": settings.grade_min_profit_ore,
    }
    thesis = watch.buy_thesis or "flip_raw"
    if thesis not in {"grade_upside", "both"}:
        return empty
    catalog = None
    if watch.grade_catalog_id:
        catalog = session.get(GradeCatalog, watch.grade_catalog_id)
    if catalog is None or not catalog.psa10_usd_cents or not catalog.raw_usd_cents:
        return empty
    ship = 0 if listing.shipping_ore is None else listing.shipping_ore
    inbound = 0 if listing.buyer_fee_ore is None else listing.buyer_fee_ore
    landed = asking_ore + ship + inbound
    score = score_prices(
        raw_usd_cents=catalog.raw_usd_cents,
        psa8_usd_cents=catalog.psa8_usd_cents,
        psa9_usd_cents=catalog.psa9_usd_cents,
        psa10_usd_cents=catalog.psa10_usd_cents,
        bgs10_usd_cents=catalog.bgs10_usd_cents,
        black_label_usd_cents=catalog.black_label_usd_cents,
        sport=catalog.sport,
        product_name=catalog.product_name,
        console_name=catalog.console_name,
        genre=catalog.genre,
        release_date=catalog.release_date,
        gem_rate_override=catalog.gem_rate_override,
        raw_buy_ore=landed,
    )
    return {
        "grade_ev_ore": score.ev_ore,
        "grade_max_buy_ore": score.max_raw_buy_ore or watch.max_buy_ore or 0,
        "grade_cost_ore": score.grade_cost_ore,
        "psa9_floor_profit_ore": score.psa9_floor_profit_ore,
        "min_grade_profit_ore": settings.grade_min_profit_ore,
    }
