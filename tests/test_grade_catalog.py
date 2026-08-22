from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pokequant.catalog.pricecharting_csv import ingest_pricecharting_csv
from pokequant.connectors.pricecharting import classify_sport, grade_row_from_mapping
from pokequant.db.base import Base
from pokequant.db.models import GradeCatalog, WatchlistItem
from pokequant.grading.export import apply_targets, generated_watch_id, select_targets
from pokequant.grading.priors import GemPrior, gem_prior
from pokequant.grading.score import assign_tier, score_prices

FIXTURE = Path(__file__).parent / "fixtures" / "pricecharting_sample.csv"


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_classify_sport():
    assert classify_sport("Pokemon Card", "Pokemon Card", "Pikachu") == "pokemon"
    assert classify_sport("Hockey Card", "Hockey Card", "Gretzky") == "hockey"
    assert classify_sport("NES", "Platform", "Mario") is None


def test_parse_csv_row_maps_psa10_and_black_label():
    row = grade_row_from_mapping(
        {
            "id": "104",
            "console-name": "Pokemon Card",
            "product-name": "Charizard Holo Base Set #4",
            "genre": "Pokemon Card",
            "loose-price": "400.00",
            "graded-price": "800.00",
            "manual-only-price": "3500.00",
            "bgs-10-price": "4000.00",
            "condition-20-price": "20000.00",
        },
        prices_are_dollars=True,
    )
    assert row is not None
    assert row.sport == "pokemon"
    assert row.collector_number == "4"
    assert row.raw_usd_cents == 400_00
    assert row.psa9_usd_cents == 800_00
    assert row.psa10_usd_cents == 3500_00
    assert row.black_label_usd_cents == 20000_00


def test_black_label_spread_is_not_workhorse():
    prior = gem_prior(
        sport="hockey",
        product_name="Wayne Gretzky 1990 Upper Deck",
        console_name="Hockey Card",
        release_date="1990-09-01",
    )
    assert prior.damage is True
    assert prior.psa10 < 0.08
    score = score_prices(
        raw_usd_cents=20_00,
        psa8_usd_cents=28_00,
        psa9_usd_cents=40_00,
        psa10_usd_cents=200_00,
        black_label_usd_cents=2000_00,
        sport="hockey",
        product_name="Wayne Gretzky 1990 Upper Deck",
        console_name="Hockey Card",
        release_date="1990-09-01",
    )
    assert score.tier == "moonshot"
    assert score.tier != "workhorse"
    tier, _ = assign_tier(
        prior=GemPrior(0.04, 0.20, 0.30, 0.46, True, "vintage_holo"),
        ev_ore=-10_000,
        upside_if_10_mult=8.0,
        spread_psa10=10.0,
        drop_reason="",
    )
    assert tier == "moonshot"


def test_ingest_fixture_assigns_tiers_and_skips_non_cards():
    session = make_session()
    stats = ingest_pricecharting_csv(session, FIXTURE)
    session.commit()
    assert stats["kept"] == 7
    assert stats["skipped_sport"] >= 1

    by_id = {r.pricecharting_id: r for r in session.query(GradeCatalog).all()}
    assert by_id["101"].tier == "workhorse"
    assert by_id["102"].tier in {"hunt", "workhorse"}
    assert by_id["104"].tier == "moonshot"
    assert by_id["201"].tier == "moonshot"
    assert by_id["202"].tier is None
    assert by_id["202"].drop_reason == "low_gem_weak_upside"
    assert by_id["301"].drop_reason == "missing_psa10_or_raw"
    assert "401" not in by_id


def test_export_applies_gt_watchlist_and_replaces_stale():
    session = make_session()
    ingest_pricecharting_csv(session, FIXTURE)
    stale = WatchlistItem(
        watch_id="GT-999",
        name="Stale",
        search_aliases="stale",
        active=True,
        buy_thesis="grade_upside",
        grade_tier="hunt",
    )
    session.add(stale)
    session.commit()

    rows = select_targets(session, per_tier=40)
    stats = apply_targets(session, rows, replace_generated=True)
    session.commit()
    assert stats["upserted"] == len(rows)
    assert stats["deactivated"] == 1
    assert session.query(WatchlistItem).filter_by(watch_id="GT-999").one().active is False

    gretzky = session.query(WatchlistItem).filter_by(watch_id=generated_watch_id("201")).one()
    assert gretzky.buy_thesis == "grade_upside"
    assert gretzky.grade_tier == "moonshot"
    assert gretzky.priority == "experimental"
    assert "gretzky" in gretzky.search_aliases.lower()
