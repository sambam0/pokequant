from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pokequant.connectors.base import NormalizedListing
from pokequant.db.base import Base
from pokequant.db.models import Listing, PriceObservation, Valuation, WatchlistItem
from pokequant.inventory.service import create_purchase, inspect_unit, receive_unit, record_sale
from pokequant.jobs.scan import run_watchlist_scan
from pokequant.services.decisions import record_decision
from pokequant.services.precision import compute_precision


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def seed_watch_and_price(session):
    watch = WatchlistItem(
        watch_id="WATCH-001",
        name="Charizard",
        set_code="base1",
        collector_number="4",
        search_aliases="charizard 4/102",
        min_discount_bps=1000,
        priority="core",
        active=True,
        frozen=True,
    )
    session.add(watch)
    session.flush()
    session.add(
        PriceObservation(
            watchlist_item_id=watch.id,
            source="ebay",
            status="active",
            observed_at=datetime.now(timezone.utc),
            currency="SEK",
            price_ore=400_00,
            is_primary=True,
        )
    )
    session.add(
        PriceObservation(
            watchlist_item_id=watch.id,
            source="pricecharting",
            status="guide",
            observed_at=datetime.now(timezone.utc),
            currency="SEK",
            price_ore=380_00,
            is_primary=True,
        )
    )
    session.commit()
    return watch


def test_scan_alert_buy_inventory_and_precision_gate():
    session = make_session()
    watch = seed_watch_and_price(session)

    result = run_watchlist_scan(
        session,
        dry_run_alerts=True,
        use_fixture=[
            NormalizedListing(
                source_code="tradera",
                external_id="999",
                url="https://www.tradera.com/item/999",
                title="Pokemon Charizard 4/102 Holo",
                currency="SEK",
                price_ore=180_00,
                shipping_ore=0,
                buyer_fee_ore=0,
                listing_type="bin",
                raw_hash="xyz",
            )
        ],
    )
    assert result["alerted"] == 1

    listing = session.query(Listing).one()
    valuation = session.query(Valuation).one()
    assert listing.workflow_state == "alerted"
    assert valuation.passes_hard_gates is True

    record_decision(session, listing, intent="buy", quality_label="really_good", valuation=valuation)
    purchase = create_purchase(
        session,
        purchase_code="PO-1",
        purchase_price_ore=180_00,
        listing_id=listing.id,
        watchlist_item_id=watch.id,
        vat_code="VMB_ELIGIBLE",
    )
    session.flush()
    unit = receive_unit(
        session,
        inventory_code="INV-1",
        purchase=purchase,
        identity_name="Charizard 4/102",
    )
    inspect_unit(session, unit, inspector="domain", observed_condition="NM", authenticity_ok=True)
    sale = record_sale(
        session,
        unit,
        sale_code="SO-1",
        channel="tradera",
        gross_ore=320_00,
        marketplace_fee_ore=2560,
    )
    session.commit()
    assert unit.state == "sold"
    assert sale.gross_ore == 320_00

    snap = compute_precision(session, window=40)
    assert snap.labeled_count == 1
    assert snap.really_good_rate == 1.0
    assert snap.gate_passed is False  # need >= 40 labeled


def test_precision_gate_passes_with_enough_labels():
    session = make_session()
    from pokequant.db.models import Decision

    for i in range(40):
        listing = Listing(
            source_code="tradera",
            external_id=str(i),
            url=f"https://example.com/{i}",
            title="x",
            price_ore=100,
            workflow_state="closed",
        )
        session.add(listing)
        session.flush()
        session.add(
            Decision(
                listing_id=listing.id,
                intent="buy" if i < 25 else "skip",
                quality_label="really_good" if i < 25 else "junk",
                identity_label="correct",
                deal_label="really_good" if i < 25 else "junk",
                source_code="tradera",
                false_match=False,
            )
        )
    session.commit()
    snap = compute_precision(session, window=40)
    assert snap.gate_passed is True
    assert snap.really_good_rate >= 0.5
