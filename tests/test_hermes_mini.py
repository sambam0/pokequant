from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pokequant.alerts.telegram_bot import apply_callback, format_alert
from pokequant.connectors.base import NormalizedListing
from pokequant.connectors.ebay import GRADED_TITLE_RE
from pokequant.connectors.tradera import TraderaClient, is_bin_listing
from pokequant.db.base import Base
from pokequant.db.models import (
    AlertDelivery,
    Decision,
    Listing,
    PrecisionSnapshot,
    PriceObservation,
    ScoutArm,
    Valuation,
    WatchlistItem,
)
from pokequant.db.session import assert_production_database
from pokequant.filters import should_drop
from pokequant.jobs.doctor import pokequant_is_venv, which_pokequant
from pokequant.jobs.scan import run_watchlist_scan
from pokequant.services.comps import sync_external_comps
from pokequant.services.decisions import record_decision
from pokequant.services.ingest import IngestRejected, upsert_listing
from pokequant.services.precision import compute_precision, latest_precision
from pokequant.services.scoring import score_listing
from pokequant.services.scout import select_round_robin_arms
from pokequant.services.skips import enqueue_skip_candidates
from pokequant.valuation.engine import ValuationInput, compute_valuation
from pokequant.workflow.states import transition_listing


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def seed_watch(session, *, watch_id="WATCH-001"):
    watch = WatchlistItem(
        watch_id=watch_id,
        name="Charizard",
        set_code="base1",
        set_name="Base Set",
        collector_number="4",
        search_aliases="charizard 4/102",
        min_discount_bps=1000,
        priority="core",
        active=True,
        frozen=True,
    )
    session.add(watch)
    session.flush()
    now = datetime.now(timezone.utc)
    for src, price in (("ebay", 400_00), ("pricecharting", 380_00)):
        session.add(
            PriceObservation(
                watchlist_item_id=watch.id,
                source=src,
                status="active" if src == "ebay" else "guide",
                observed_at=now,
                currency="SEK",
                price_ore=price,
                is_primary=True,
            )
        )
    session.commit()
    return watch


def bin_listing(**kwargs) -> NormalizedListing:
    defaults = dict(
        source_code="tradera",
        external_id="999",
        url="https://www.tradera.com/item/999",
        title="Pokemon Charizard 4/102 Holo",
        currency="SEK",
        price_ore=180_00,
        shipping_ore=49_00,
        buyer_fee_ore=0,
        listing_type="bin",
        raw_hash="xyz",
    )
    defaults.update(kwargs)
    return NormalizedListing(**defaults)


def test_auction_not_alerted():
    session = make_session()
    seed_watch(session)
    result = run_watchlist_scan(
        session,
        dry_run_alerts=True,
        use_fixture=[
            bin_listing(
                external_id="auc",
                listing_type="auction",
                price_ore=None,
                shipping_ore=None,
                raw_hash="auc",
            )
        ],
    )
    assert result["alerted"] == 0
    listing = session.query(Listing).one()
    assert listing.listing_type == "auction"
    assert listing.workflow_state != "alerted"


def test_shipping_null_not_zero():
    result = compute_valuation(
        ValuationInput(
            asking_ore=100_00,
            inbound_shipping_ore=None,
            buyer_fee_ore=0,
            ebay_comp_ore=300_00,
            pricecharting_comp_ore=280_00,
            identity_confidence=0.9,
        )
    )
    assert "missing_shipping" in result.gate_failures
    assert result.passes_hard_gates is False


def test_tradera_normalize_auction_ignores_next_bid():
    client = TraderaClient(app_id="x", app_key="y")
    raw = json.loads(Path("tests/fixtures/tradera_search_auction.json").read_text())
    listing = client._normalize(raw["items"][0])
    assert listing.listing_type == "auction"
    assert listing.price_ore is None
    assert not is_bin_listing(listing)


def test_tradera_normalize_bin_from_fixture():
    client = TraderaClient(app_id="x", app_key="y")
    raw = json.loads(Path("tests/fixtures/tradera_search_bin.json").read_text())
    listing = client._normalize(raw["items"][0])
    assert listing.listing_type == "bin"
    assert listing.currency == "SEK"
    assert listing.shipping_ore is None
    assert is_bin_listing(listing)


def test_telegram_callback_idempotent_and_bought_only_purchases():
    session = make_session()
    seed_watch(session)
    run_watchlist_scan(session, dry_run_alerts=True, use_fixture=[bin_listing()])
    listing = session.query(Listing).one()
    valuation = session.query(Valuation).one()
    session.add(
        AlertDelivery(listing_id=listing.id, valuation_id=valuation.id, channel="telegram")
    )
    session.commit()

    first = apply_callback(session, f"g:{listing.id}", reviewer="sam:1", callback_query_id="cq-1")
    session.commit()
    listing = session.get(Listing, listing.id)
    assert first.intent == "skip"
    assert first.deal_label == "really_good"
    assert listing.workflow_state == "closed"

    again = apply_callback(session, f"g:{listing.id}", reviewer="sam:1", callback_query_id="cq-1")
    assert again.id == first.id
    assert session.query(Decision).count() == 1

    listing2_norm = bin_listing(external_id="1000", raw_hash="other")
    run_watchlist_scan(session, dry_run_alerts=True, use_fixture=[listing2_norm])
    listing2 = session.query(Listing).filter_by(external_id="1000").one()
    val2 = session.query(Valuation).filter_by(listing_id=listing2.id).one()
    session.add(AlertDelivery(listing_id=listing2.id, valuation_id=val2.id, channel="telegram"))
    session.commit()
    bought = apply_callback(session, f"b:{listing2.id}", reviewer="sam:1", callback_query_id="cq-2")
    assert bought.intent == "buy"
    assert session.get(Listing, listing2.id).workflow_state == "purchased"


def test_alert_body_has_no_image_url_and_is_truncated():
    listing = Listing(
        source_code="tradera",
        external_id="1",
        url="https://www.tradera.com/item/1",
        title="x",
        price_ore=1,
        image_urls="https://cdn.example/secret.jpg",
    )
    valuation = Valuation(
        listing_id=0,
        model_version="v",
        fee_schedule_version="f",
        market_value_p10_ore=1,
        market_value_p50_ore=1,
        market_value_p90_ore=1,
        expected_net_proceeds_ore=1,
        landed_cost_ore=1,
        expected_profit_ore=1,
        max_buy_ore=1,
        explanation="e" * 5000,
        discount_bps=0,
        identity_confidence=0.9,
        passes_hard_gates=True,
        gate_failures="",
    )
    text = format_alert(listing, valuation, "Charizard")
    assert "secret.jpg" not in text
    assert len(text) <= 3900


def test_skip_miner_ignores_really_good_and_telegram_junk():
    session = make_session()
    listing = Listing(
        source_code="tradera",
        external_id="1",
        url="https://example.com/1",
        title="charizard japanese lot filler xyzzy",
        price_ore=1,
        seller_key="s1",
        workflow_state="closed",
    )
    session.add(listing)
    session.flush()
    assert enqueue_skip_candidates(session, listing, identity_label="correct", deal_label="junk") == []
    assert enqueue_skip_candidates(session, listing, identity_label="correct", deal_label="really_good") == []
    created = enqueue_skip_candidates(session, listing, identity_label="wrong", deal_label="n/a")
    assert created
    assert all("lot" not in c.pattern for c in created)


def test_round_robin_respects_slots():
    session = make_session()
    now = datetime.now(timezone.utc)
    for i, key in enumerate(["a", "b", "c", "d"]):
        session.add(
            ScoutArm(
                source="tradera",
                key=key,
                arm_class="core",
                last_pulled_at=now - timedelta(hours=4 - i) if i else None,
            )
        )
    session.commit()
    picked = select_round_robin_arms(session, 2, source="tradera")
    assert len(picked) == 2
    assert picked[0].key == "a"
    assert picked[1].key == "b"


def test_price_drop_reopens_below_threshold():
    session = make_session()
    seed_watch(session)
    run_watchlist_scan(
        session,
        dry_run_alerts=True,
        use_fixture=[bin_listing(price_ore=400_00, shipping_ore=0, raw_hash="h1")],
    )
    listing = session.query(Listing).one()
    assert listing.workflow_state == "below_threshold"
    upsert_listing(session, bin_listing(price_ore=100_00, shipping_ore=0, raw_hash="h2"))
    listing = session.query(Listing).one()
    assert listing.workflow_state == "discovered"


def test_facebook_junk_does_not_move_tradera_precision():
    session = make_session()
    for i in range(40):
        listing = Listing(
            source_code="tradera",
            external_id=f"t{i}",
            url=f"https://example.com/t{i}",
            title="x",
            price_ore=100,
            workflow_state="closed",
        )
        session.add(listing)
        session.flush()
        session.add(
            Decision(
                listing_id=listing.id,
                intent="skip",
                quality_label="really_good",
                identity_label="correct",
                deal_label="really_good",
                source_code="tradera",
            )
        )
    first = compute_precision(session, window=40, source="tradera")
    session.flush()
    for i in range(40):
        listing = Listing(
            source_code="facebook",
            external_id=f"f{i}",
            url=f"https://example.com/f{i}",
            title="junk",
            price_ore=100,
            workflow_state="closed",
        )
        session.add(listing)
        session.flush()
        session.add(
            Decision(
                listing_id=listing.id,
                intent="skip",
                quality_label="junk",
                identity_label="correct",
                deal_label="junk",
                source_code="facebook",
            )
        )
    second = compute_precision(session, window=40, source="tradera")
    assert first.gate_passed is True
    assert second.gate_passed is True
    assert second.really_good_rate == first.really_good_rate


def test_dashboard_get_does_not_insert_precision_snapshot():
    from fastapi.testclient import TestClient

    from pokequant.db.session import get_session
    from pokequant.web.app import app

    session = make_session()
    seed_watch(session)

    def override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override
    try:
        client = TestClient(app)
        before = session.query(PrecisionSnapshot).count()
        resp = client.get("/")
        assert resp.status_code == 200
        assert session.query(PrecisionSnapshot).count() == before
        assert latest_precision(session) is None
    finally:
        app.dependency_overrides.clear()


def test_production_sqlite_rejected():
    try:
        assert_production_database("sqlite+pysqlite:///./pokequant.db", "production")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    assert_production_database("postgresql+psycopg://x", "production")


def test_sync_comps_nonzero_on_missing():
    session = make_session()
    seed_watch(session)
    # Wipe comps so the watch is missing both sources after a no-credential sync.
    session.query(PriceObservation).delete()
    session.commit()
    stats = sync_external_comps(session)
    assert stats["ok"] is False
    assert stats["missing"] >= 1


def test_facebook_ingest_blocked():
    session = make_session()
    try:
        upsert_listing(
            session,
            NormalizedListing(
                source_code="facebook",
                external_id="fb1",
                url="https://facebook.com/1",
                title="Charizard 4/102",
                currency="SEK",
                price_ore=100,
                listing_type="bin",
            ),
        )
        assert False, "expected reject"
    except IngestRejected:
        pass


def test_should_drop_facebook():
    result = should_drop("anything", "facebook")
    assert type(result).__name__ == "Drop"


def test_which_pokequant_helper_runs():
    assert isinstance(which_pokequant(), str)
    assert isinstance(pokequant_is_venv(), bool)


def test_answer_callback_query_posts():
    from unittest.mock import patch

    from pokequant.alerts.telegram_bot import answer_callback_query
    from pokequant.config import get_settings

    get_settings.cache_clear()
    with patch("pokequant.alerts.telegram_bot.get_settings") as gs, patch(
        "pokequant.alerts.telegram_bot.httpx.post"
    ) as post:
        gs.return_value.deals_bot_token = "tok"
        post.return_value = type("R", (), {"raise_for_status": lambda self: None})()
        answer_callback_query("cq-99", text="Recorded")
        assert post.called
        url = post.call_args.args[0]
        assert url.endswith("/answerCallbackQuery")


def test_ebay_skips_graded_titles():
    assert GRADED_TITLE_RE.search("Charizard PSA 10")
    assert GRADED_TITLE_RE.search("slab charizard")
    assert not GRADED_TITLE_RE.search("Charizard 4/102 holo")


def test_score_auction_never_creates_valuation():
    session = make_session()
    watch = seed_watch(session)
    listing = Listing(
        source_code="tradera",
        external_id="a",
        url="https://example.com/a",
        title="Pokemon Charizard 4/102 Holo",
        currency="SEK",
        price_ore=None,
        listing_type="auction",
        workflow_state="discovered",
    )
    session.add(listing)
    session.flush()
    assert score_listing(session, listing, [watch]) is None
    assert session.query(Valuation).count() == 0


def test_wrong_excluded_from_deal_rate():
    session = make_session()
    listing = Listing(
        source_code="tradera",
        external_id="1",
        url="https://example.com/1",
        title="x",
        price_ore=1,
        workflow_state="closed",
    )
    session.add(listing)
    session.flush()
    session.add(
        Decision(
            listing_id=listing.id,
            intent="skip",
            quality_label="junk",
            identity_label="wrong",
            deal_label="n/a",
            source_code="tradera",
        )
    )
    snap = compute_precision(session, window=40, source="tradera")
    assert snap.identity_labeled_count == 1
    assert snap.deal_labeled_count == 0
    assert snap.false_match_rate == 1.0
    assert snap.really_good_rate == 0.0
