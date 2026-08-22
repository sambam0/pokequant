from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from pokequant.db.models import QueryPull, ScoutArm, WatchlistItem
from pokequant.quota import SlotBudget, compute_slot_budget
from pokequant.watchlist import list_active_watchlist


def _dumps(values: list) -> str:
    return json.dumps(values)


def _loads(raw: str) -> list:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def ensure_scout_arms(session: Session, *, source: str = "tradera") -> list[ScoutArm]:
    """One arm per unique search_aliases token (or name). Core first."""
    watches = list_active_watchlist(session)
    by_key: dict[str, ScoutArm] = {
        a.key: a for a in session.query(ScoutArm).filter_by(source=source, status="active").all()
    }
    for watch in watches:
        aliases = [a.strip() for a in (watch.search_aliases or "").split(";") if a.strip()]
        if not aliases:
            aliases = [watch.name]
        arm_class = "core" if watch.priority == "core" else "opportunistic"
        for alias in aliases:
            arm = by_key.get(alias)
            if arm is None:
                arm = ScoutArm(
                    source=source,
                    arm_type="alias",
                    key=alias,
                    arm_class=arm_class,
                    watch_ids_json=_dumps([watch.watch_id]),
                )
                session.add(arm)
                session.flush()
                by_key[alias] = arm
            else:
                ids = _loads(arm.watch_ids_json)
                if watch.watch_id not in ids:
                    ids.append(watch.watch_id)
                    arm.watch_ids_json = _dumps(ids)
                if arm_class == "core":
                    arm.arm_class = "core"
    return list(by_key.values())


def select_round_robin_arms(
    session: Session,
    search_slots: int,
    *,
    source: str = "tradera",
) -> list[ScoutArm]:
    """Core round-robin by last_pulled_at, then opportunistic leftover. No Thompson."""
    if search_slots <= 0:
        return []
    ensure_scout_arms(session, source=source)
    core = (
        session.query(ScoutArm)
        .filter_by(source=source, status="active", arm_class="core")
        .order_by(ScoutArm.last_pulled_at.is_(None).desc(), ScoutArm.last_pulled_at.asc(), ScoutArm.id.asc())
        .all()
    )
    picked: list[ScoutArm] = []
    for arm in core:
        if len(picked) >= search_slots:
            break
        picked.append(arm)
    if len(picked) < search_slots:
        leftover = (
            session.query(ScoutArm)
            .filter_by(source=source, status="active", arm_class="opportunistic")
            .order_by(ScoutArm.last_pulled_at.is_(None).desc(), ScoutArm.last_pulled_at.asc(), ScoutArm.id.asc())
            .all()
        )
        for arm in leftover:
            if len(picked) >= search_slots:
                break
            if arm not in picked:
                picked.append(arm)
    return picked


def hermes_queries(session: Session, source_obj, *, n_core_arms: int | None = None) -> tuple[list[ScoutArm], SlotBudget]:
    n_core = n_core_arms
    if n_core is None:
        n_core = (
            session.query(ScoutArm)
            .filter_by(source=source_obj.code, status="active", arm_class="core")
            .count()
        )
    budget = compute_slot_budget(session, source_obj, n_core_arms=n_core)
    arms = select_round_robin_arms(session, budget.search_slots, source=source_obj.code)
    return arms, budget


def start_query_pull(session: Session, arm: ScoutArm) -> QueryPull:
    now = datetime.now(timezone.utc)
    pull = QueryPull(
        arm_id=arm.id,
        pulled_at=now,
        reward=None,
        reward_status="pending",
        reward_reason="",
    )
    session.add(pull)
    arm.last_pulled_at = now
    arm.n_pulls += 1
    session.flush()
    return pull


def finish_query_pull(
    session: Session,
    pull: QueryPull,
    *,
    listing_ids: list[int],
    n_new: int,
    n_alerted: int,
) -> QueryPull:
    pull.listing_ids_json = _dumps(listing_ids)
    pull.n_new = n_new
    pull.n_alerted = n_alerted
    arm = session.get(ScoutArm, pull.arm_id)
    if arm:
        arm.n_new_total += n_new
    if not listing_ids:
        pull.reward = None
        pull.reward_status = "censored"
        pull.reward_reason = "empty_pull"
        pull.resolved_at = datetime.now(timezone.utc)
        if arm:
            arm.n_censored += 1
    elif n_alerted == 0:
        pull.reward = None
        pull.reward_status = "censored"
        pull.reward_reason = "never_alerted"
        pull.resolved_at = datetime.now(timezone.utc)
        if arm:
            arm.n_censored += 1
    return pull


def credit_decision(session: Session, listing, *, deal_label: str, identity_label: str) -> None:
    """Credit one pull per listing. identity=wrong is a no-op for the query log."""
    if identity_label == "wrong":
        return
    if listing.query_pull_id is None:
        return
    pull = session.get(QueryPull, listing.query_pull_id)
    if pull is None:
        return
    credited = set(_loads(pull.credited_decision_ids_json))
    if deal_label == "really_good":
        pull.reward = 1
        pull.reward_status = "resolved"
        pull.reward_reason = "really_good"
        pull.resolved_at = datetime.now(timezone.utc)
        arm = session.get(ScoutArm, pull.arm_id)
        if arm and pull.reward == 1:
            if pull.id not in credited:
                arm.n_reward_1 += 1
                arm.n_resolved += 1
    # Fully labeled non-hits resolved later by resolve_labeled_pulls.


def resolve_labeled_pulls(session: Session) -> int:
    """If every alerted listing on a pull is labeled and none are really_good → r=0."""
    from pokequant.db.models import Decision, Listing

    resolved = 0
    pulls = session.query(QueryPull).filter_by(reward_status="pending").all()
    for pull in pulls:
        listing_ids = _loads(pull.listing_ids_json)
        if not listing_ids:
            continue
        listings = session.query(Listing).filter(Listing.id.in_(listing_ids)).all()
        alerted = [lst for lst in listings if lst.workflow_state in {"alerted", "decided", "closed", "purchased"}]
        if not alerted:
            continue
        all_labeled = True
        any_hit = False
        for lst in alerted:
            dec = (
                session.query(Decision)
                .filter(Decision.listing_id == lst.id)
                .order_by(Decision.id.desc())
                .first()
            )
            if dec is None:
                all_labeled = False
                break
            if dec.deal_label == "really_good":
                any_hit = True
        if all_labeled and not any_hit:
            pull.reward = 0
            pull.reward_status = "resolved"
            pull.reward_reason = "labeled_non_hit"
            pull.resolved_at = datetime.now(timezone.utc)
            arm = session.get(ScoutArm, pull.arm_id)
            if arm:
                arm.n_resolved += 1
            resolved += 1
    return resolved
