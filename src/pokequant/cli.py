from __future__ import annotations

import argparse
import json
from pathlib import Path

from pokequant.catalog.cardmarket import ingest_price_guide_csv
from pokequant.catalog.pricecharting_csv import ingest_pricecharting_csv, rescore_catalog
from pokequant.catalog.tcgdex import TCGdexClient
from pokequant.config import get_settings
from pokequant.db.base import Base
from pokequant.db.session import SessionLocal, get_engine
from pokequant.expansion import plan_expansion
from pokequant.filters import should_drop
from pokequant.grading.export import apply_targets, export_targets_csv, select_targets
from pokequant.jobs.doctor import run_mini_doctor
from pokequant.jobs.match_audit import match_audit
from pokequant.jobs.scan import ensure_tradera_source, run_watchlist_scan
from pokequant.jobs.telegram_poll import run_poll_loop
from pokequant.runtime import effective_status, pause, read_state, resume
from pokequant.services.aliases import propose_aliases
from pokequant.services.comps import sync_external_comps
from pokequant.services.ingest import compact_snapshots
from pokequant.services.precision import compute_precision
from pokequant.services.skips import replay_skips
from pokequant.watchlist import import_watchlist_csv, list_active_watchlist


def cmd_init_db(_: argparse.Namespace) -> None:
    if get_settings().app_env == "production":
        raise SystemExit("init-db is forbidden in production; use alembic upgrade head")
    Base.metadata.create_all(bind=get_engine())
    print("Database tables created.")


def cmd_watchlist_import(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        count = import_watchlist_csv(
            session, args.path, freeze=not args.unfreeze, force_identity_fix=args.force_identity_fix
        )
        session.commit()
        print(f"Imported {count} watchlist rows from {args.path}")


def cmd_watchlist_list(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        items = list_active_watchlist(session)
        for item in items:
            print(f"{item.watch_id}\t{item.priority}\t{item.name}\t{item.set_code}\t{item.collector_number}")
        print(f"Total: {len(items)}")


def cmd_sync_tcgdex(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        ids = [w.tcgdex_id for w in list_active_watchlist(session) if w.tcgdex_id]
        client = TCGdexClient()
        n = client.sync_watchlist_prices(session, ids)
        session.commit()
        print(f"Synced prices for {n} cards via TCGdex")


def cmd_ingest_cardmarket(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        n = ingest_price_guide_csv(session, args.path)
        session.commit()
        print(f"Ingested {n} Cardmarket rows")


def cmd_ingest_pc_csv(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        stats = ingest_pricecharting_csv(session, args.path)
        session.commit()
        print(json.dumps(stats, indent=2))


def cmd_grade_targets(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        if args.grade_targets_cmd == "rescore":
            print(json.dumps(rescore_catalog(session), indent=2))
            session.commit()
            return
        rows = select_targets(session, per_tier=args.per_tier)
        if args.grade_targets_cmd == "list":
            for row in rows:
                print(
                    f"{row.tier}\t{row.sport}\t{row.ev_ore}\t{row.upside_if_10_mult:.2f}x\t"
                    f"{row.product_name}\t{row.pricecharting_id}"
                )
            print(f"Total: {len(rows)}")
            return
        path = args.path or Path("data/watchlist/grade_targets.csv")
        export_targets_csv(rows, path)
        stats = {"csv": str(path), "targets": len(rows)}
        if args.apply:
            stats.update(apply_targets(session, rows, replace_generated=not args.keep_stale))
            session.commit()
        print(json.dumps(stats, indent=2))


def cmd_sync_comps(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        stats = sync_external_comps(session)
        session.commit()
        print(json.dumps(stats, indent=2))
        if not stats.get("ok", True):
            raise SystemExit(1)


def cmd_scan(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        if args.sync_comps:
            stats = sync_external_comps(session)
            session.commit()
            print("comps:", json.dumps(stats))
            if not stats.get("ok", True) and args.send_telegram:
                raise SystemExit("sync-comps failed; refusing --send-telegram")
        result = run_watchlist_scan(
            session, dry_run_alerts=not args.send_telegram, send_telegram=args.send_telegram
        )
        print(json.dumps(result, indent=2))
        if result.get("error") in {"quota_exhausted"}:
            raise SystemExit(2)


def cmd_precision(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        snap = compute_precision(session, source=args.source)
        session.commit()
        print(
            json.dumps(
                {
                    "source_code": snap.source_code,
                    "identity_labeled": snap.identity_labeled_count,
                    "deal_labeled": snap.deal_labeled_count,
                    "really_good_rate": snap.really_good_rate,
                    "false_match_rate": snap.false_match_rate,
                    "gate_passed": snap.gate_passed,
                    "median_decision_seconds": snap.median_decision_seconds,
                },
                indent=2,
            )
        )


def cmd_expansion(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        plan = plan_expansion(session)
        print(json.dumps(plan.__dict__, indent=2))


def cmd_hermes_queries(_: argparse.Namespace) -> None:
    from pokequant.services.scout import hermes_queries

    with SessionLocal() as session:
        source = ensure_tradera_source(session)
        arms, budget = hermes_queries(session, source)
        session.commit()
        print(
            json.dumps(
                {
                    "search_slots": budget.search_slots,
                    "hydrate_reserve": budget.hydrate_reserve,
                    "remaining": budget.remaining,
                    "ticks_left": budget.ticks_left,
                    "core_cycle_hours": budget.core_cycle_hours,
                    "aliases": [a.key for a in arms],
                },
                indent=2,
            )
        )


def cmd_hermes_seen(args: argparse.Namespace) -> None:
    from pokequant.db.models import Listing

    with SessionLocal() as session:
        q = session.query(Listing)
        if args.source:
            q = q.filter_by(source_code=args.source)
        if args.external_id:
            q = q.filter_by(external_id=args.external_id)
        rows = q.order_by(Listing.last_seen_at.desc()).limit(args.limit).all()
        for row in rows:
            print(
                f"{row.source_code}\t{row.external_id}\t{row.price_ore}\t{row.shipping_ore}\t"
                f"{row.raw_hash[:12]}\t{row.workflow_state}\t{row.last_seen_at}"
            )


def cmd_hermes_pause(args: argparse.Namespace) -> None:
    print(json.dumps(pause(reason=args.reason or "manual"), indent=2))


def cmd_hermes_resume(_: argparse.Namespace) -> None:
    print(json.dumps(resume(), indent=2))


def cmd_hermes_status(_: argparse.Namespace) -> None:
    print(json.dumps({"effective": effective_status(), "file": read_state()}, indent=2))


def cmd_should_drop(args: argparse.Namespace) -> None:
    result = should_drop(args.title, args.source)
    print(json.dumps({"drop": type(result).__name__, **getattr(result, "__dict__", {})}))


def cmd_replay_skips(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        stats = replay_skips(session)
        session.commit()
        print(json.dumps(stats, indent=2))


def cmd_alias_miner(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        rows = propose_aliases(session)
        session.commit()
        print(json.dumps([{"id": r.id, "alias": r.proposed_alias, "status": r.status} for r in rows], indent=2))


def cmd_match_audit(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        print(json.dumps(match_audit(session), indent=2, default=str))


def cmd_telegram_poll(_: argparse.Namespace) -> None:
    run_poll_loop()


def cmd_mini_doctor(args: argparse.Namespace) -> None:
    report = run_mini_doctor(send_dms=not args.skip_dms)
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


def cmd_snapshot_compact(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        n = compact_snapshots(session)
        session.commit()
        print(json.dumps({"removed": n}))


def cmd_watchdog(_: argparse.Namespace) -> None:
    from pokequant.jobs.watchdog import run_watchdog

    report = run_watchdog()
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


def cmd_morning_digest(_: argparse.Namespace) -> None:
    from pokequant.db.models import AliasProposal, Listing
    from pokequant.jobs.scan import ensure_tradera_source
    from pokequant.quota import compute_slot_budget
    from pokequant.services.scout import ensure_scout_arms

    with SessionLocal() as session:
        source = ensure_tradera_source(session)
        ensure_scout_arms(session)
        budget = compute_slot_budget(
            session,
            source,
            n_core_arms=sum(1 for a in ensure_scout_arms(session) if a.arm_class == "core"),
        )
        wip = session.query(Listing).filter(Listing.workflow_state == "alerted").count()
        pending = session.query(AliasProposal).filter(AliasProposal.status.in_(["queued", "needs_human"])).count()
        dump = Path("data/hermes/last_pg_dump")
        dump_age = dump.read_text(encoding="utf-8").strip() if dump.exists() else "missing"
        print(
            json.dumps(
                {
                    "core_cycle_hours": budget.core_cycle_hours,
                    "remaining_calls": budget.remaining,
                    "pending_aliases": pending,
                    "wip": wip,
                    "dump_stamp": dump_age,
                    "state": effective_status(),
                },
                indent=2,
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pokequant", description="PokeQuant CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-db", help="Create database tables (dev only)")
    p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("watchlist")
    wsub = p.add_subparsers(dest="watchlist_cmd", required=True)
    wi = wsub.add_parser("import", help="Import watchlist CSV")
    wi.add_argument("path", type=Path)
    wi.add_argument("--unfreeze", action="store_true")
    wi.add_argument("--force-identity-fix", action="store_true")
    wi.set_defaults(func=cmd_watchlist_import)
    wl = wsub.add_parser("list")
    wl.set_defaults(func=cmd_watchlist_list)

    p = sub.add_parser("sync-tcgdex", help="Pull TCGdex/Cardmarket guide prices for watchlist")
    p.set_defaults(func=cmd_sync_tcgdex)

    p = sub.add_parser("ingest-cardmarket", help="Ingest sanctioned Cardmarket CSV download")
    p.add_argument("path", type=Path)
    p.set_defaults(func=cmd_ingest_cardmarket)

    p = sub.add_parser(
        "ingest-pc-csv", help="Ingest Legendary PriceCharting CSV (Pokemon + hockey)"
    )
    p.add_argument("path", type=Path)
    p.set_defaults(func=cmd_ingest_pc_csv)

    gt = sub.add_parser("grade-targets", help="Rank and export grade-spread watchlist targets")
    gtsub = gt.add_subparsers(dest="grade_targets_cmd", required=True)
    gtl = gtsub.add_parser("list", help="Show top targets per tier")
    gtl.add_argument("--per-tier", type=int, default=40)
    gtl.set_defaults(func=cmd_grade_targets)
    gte = gtsub.add_parser("export", help="Write GT-* CSV and optionally apply to the watchlist")
    gte.add_argument("--per-tier", type=int, default=40)
    gte.add_argument("--path", type=Path, default=None)
    gte.add_argument("--apply", action="store_true", help="Upsert GT-* watchlist rows for Hermes")
    gte.add_argument("--keep-stale", action="store_true", help="Do not deactivate old GT-* rows")
    gte.set_defaults(func=cmd_grade_targets)
    gtr = gtsub.add_parser("rescore", help="Recompute EV/tiers after prior overrides")
    gtr.set_defaults(func=cmd_grade_targets)

    p = sub.add_parser("sync-comps", help="Fetch eBay + PriceCharting comps for the watchlist")
    p.set_defaults(func=cmd_sync_comps)

    p = sub.add_parser("scan", help="Scan Tradera for watchlist deals")
    p.add_argument("--send-telegram", action="store_true", help="Actually send Telegram alerts")
    p.add_argument("--sync-comps", action="store_true", help="Refresh eBay/PriceCharting comps before scoring")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("precision", help="Compute rolling precision gate metrics")
    p.add_argument("--source", default="tradera")
    p.set_defaults(func=cmd_precision)

    p = sub.add_parser("expansion", help="Show whether expansion is allowed and next steps")
    p.set_defaults(func=cmd_expansion)

    p = sub.add_parser("hermes-queries", help="Round-robin aliases for this tick (no Thompson)")
    p.set_defaults(func=cmd_hermes_queries)

    p = sub.add_parser("hermes-seen", help="Seen tuple: source, id, price, shipping, hash, state")
    p.add_argument("--source", default="")
    p.add_argument("--external-id", default="")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_hermes_seen)

    hp = sub.add_parser("hermes")
    hsub = hp.add_subparsers(dest="hermes_cmd", required=True)
    hpause = hsub.add_parser("pause")
    hpause.add_argument("--reason", default="")
    hpause.set_defaults(func=cmd_hermes_pause)
    hresume = hsub.add_parser("resume")
    hresume.set_defaults(func=cmd_hermes_resume)
    hstatus = hsub.add_parser("status")
    hstatus.set_defaults(func=cmd_hermes_status)

    p = sub.add_parser("should-drop", help="Run the single ingest skip layer")
    p.add_argument("title")
    p.add_argument("--source", default="tradera")
    p.set_defaults(func=cmd_should_drop)

    p = sub.add_parser("replay-skips", help="90-day skip replay (no auto-ship)")
    p.set_defaults(func=cmd_replay_skips)

    p = sub.add_parser("alias-miner", help="Queue alias proposals only")
    p.set_defaults(func=cmd_alias_miner)

    p = sub.add_parser("match-audit", help="Unmatched + collector-number-in-title misses")
    p.set_defaults(func=cmd_match_audit)

    p = sub.add_parser("telegram-poll", help="Long-poll Deals bot getUpdates")
    p.set_defaults(func=cmd_telegram_poll)

    p = sub.add_parser("mini-doctor", help="Mini host hard-gate checks")
    p.add_argument("--skip-dms", action="store_true")
    p.set_defaults(func=cmd_mini_doctor)

    p = sub.add_parser("snapshot-compact", help="Drop older identical-hash snapshots")
    p.set_defaults(func=cmd_snapshot_compact)

    p = sub.add_parser("watchdog", help="OS watchdog checks + fail-closed paging")
    p.set_defaults(func=cmd_watchdog)

    p = sub.add_parser("morning-digest", help="Ops digest JSON")
    p.set_defaults(func=cmd_morning_digest)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
