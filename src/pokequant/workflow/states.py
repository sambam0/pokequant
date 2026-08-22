from __future__ import annotations

LISTING_TRANSITIONS: dict[str, set[str]] = {
    "discovered": {"matched", "rejected", "duplicate", "expired"},
    "matched": {"scored", "rejected", "expired"},
    "scored": {"alerted", "rejected", "below_threshold", "expired"},
    "alerted": {"decided", "expired", "discovered"},
    "decided": {"purchased", "closed", "discovered"},
    "below_threshold": {"discovered", "scored", "closed", "expired"},
    "rejected": {"closed", "discovered"},
    "duplicate": {"closed"},
    "expired": set(),
    "purchased": set(),
    "closed": {"discovered"},
}

INVENTORY_TRANSITIONS: dict[str, set[str]] = {
    "receiving": {"quarantine", "ready", "inspecting"},
    "inspecting": {"quarantine", "ready"},
    "quarantine": {"ready", "returned_to_seller", "write_off"},
    "ready": {"listed", "reserved", "stale"},
    "listed": {"reserved", "sold", "ready", "stale"},
    "reserved": {"sold", "listed", "ready"},
    "sold": {"returned"},
    "returned": {"quarantine", "ready", "write_off"},
    "stale": {"ready", "listed", "write_off"},
    "returned_to_seller": set(),
    "write_off": set(),
}

REOPENABLE_STATES = frozenset({"closed", "below_threshold", "alerted", "decided", "rejected"})
NEVER_REOPEN = frozenset({"purchased"})


class InvalidTransition(ValueError):
    pass


def transition(current: str, new: str, table: dict[str, set[str]]) -> str:
    allowed = table.get(current, set())
    if new == current:
        return current
    if new not in allowed:
        raise InvalidTransition(f"Cannot transition from {current!r} to {new!r}")
    return new


def transition_listing(current: str, new: str) -> str:
    return transition(current, new, LISTING_TRANSITIONS)


def transition_inventory(current: str, new: str) -> str:
    return transition(current, new, INVENTORY_TRANSITIONS)
