from pokequant.db.models import WatchlistItem
from pokequant.valuation.match import match_title_to_watchlist
from pokequant.workflow.states import InvalidTransition, transition_listing


def test_match_requires_number_or_strong_alias():
    item = WatchlistItem(
        watch_id="WATCH-001",
        name="Charizard",
        collector_number="4",
        set_name="Base Set",
        search_aliases="charizard 4/102;charizard holo base",
        active=True,
    )
    hit = match_title_to_watchlist("Pokemon Charizard 4/102 Holo Base Set", [item])
    assert hit is not None
    assert hit.confidence >= 0.8

    lot = match_title_to_watchlist("Pokemon lott samling charizard bulk", [item])
    assert lot is None


def test_listing_state_machine():
    assert transition_listing("discovered", "matched") == "matched"
    assert transition_listing("closed", "discovered") == "discovered"
    assert transition_listing("below_threshold", "discovered") == "discovered"
    try:
        transition_listing("discovered", "alerted")
        assert False, "expected InvalidTransition"
    except InvalidTransition:
        pass
    try:
        transition_listing("purchased", "discovered")
        assert False, "purchased must never reopen"
    except InvalidTransition:
        pass
