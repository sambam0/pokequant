from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.db.models import GradeCatalog, WatchlistItem
from pokequant.money import format_sek

TIER_PRIORITY = {
    "workhorse": "core",
    "hunt": "opportunistic",
    "moonshot": "experimental",
}
TIER_THESIS = {
    "workhorse": "both",
    "hunt": "grade_upside",
    "moonshot": "grade_upside",
}


def generated_watch_id(pricecharting_id: str) -> str:
    return f"GT-{pricecharting_id}"[:32]


def _aliases(row: GradeCatalog) -> str:
    name = row.product_name.strip()
    aliases = [name]
    if row.collector_number:
        aliases.append(f"{name} {row.collector_number}")
        aliases.append(f"{name} #{row.collector_number}")
    console = row.console_name.replace("Pokemon", "").replace("Hockey", "").strip()
    if console and console.lower() not in name.lower():
        aliases.append(f"{name} {console}")
    # De-dupe, keep order, cap length for Hermes aliases.
    seen: set[str] = set()
    out: list[str] = []
    for alias in aliases:
        key = alias.lower()
        if key in seen or len(alias) > 80:
            continue
        seen.add(key)
        out.append(alias)
    return ";".join(out[:4])


def _notes(row: GradeCatalog) -> str:
    thesis = TIER_THESIS.get(row.tier or "", "grade_upside")
    return (
        f"tier={row.tier}; thesis={thesis}; sport={row.sport}; "
        f"psa10_mult={row.upside_if_10_mult:.2f}x; spread={row.spread_psa10:.2f}x; "
        f"ev={format_sek(row.ev_ore)}; max_raw_buy={format_sek(row.max_raw_buy_ore)}; "
        f"pc={row.pricecharting_id}; gem_p10={row.gem_rate_psa10:.0%}"
    )


def select_targets(session: Session, *, per_tier: int = 40) -> list[GradeCatalog]:
    picked: list[GradeCatalog] = []
    for tier in ("workhorse", "hunt", "moonshot"):
        rows = (
            session.query(GradeCatalog)
            .filter(GradeCatalog.tier == tier, GradeCatalog.drop_reason == "")
            .order_by(GradeCatalog.ev_ore.desc(), GradeCatalog.upside_if_10_mult.desc())
            .limit(per_tier)
            .all()
        )
        picked.extend(rows)
    return picked


def export_targets_csv(rows: list[GradeCatalog], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "watch_id",
        "name",
        "set_code",
        "set_name",
        "collector_number",
        "language",
        "variant",
        "tcgdex_id",
        "search_aliases",
        "condition_floor",
        "priority",
        "min_discount_bps",
        "max_buy_ore",
        "reference_source",
        "notes",
        "buy_thesis",
        "grade_tier",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            thesis = TIER_THESIS.get(row.tier or "", "grade_upside")
            writer.writerow(
                {
                    "watch_id": generated_watch_id(row.pricecharting_id),
                    "name": row.product_name,
                    "set_code": row.console_name[:64],
                    "set_name": row.console_name,
                    "collector_number": row.collector_number,
                    "language": "en",
                    "variant": "holo" if "holo" in row.product_name.lower() else "normal",
                    "tcgdex_id": "",
                    "search_aliases": _aliases(row),
                    "condition_floor": "LP",
                    "priority": TIER_PRIORITY.get(row.tier or "", "opportunistic"),
                    "min_discount_bps": 0 if thesis != "flip_raw" else 2500,
                    "max_buy_ore": row.max_raw_buy_ore or "",
                    "reference_source": "pricecharting",
                    "notes": _notes(row),
                    "buy_thesis": thesis,
                    "grade_tier": row.tier or "",
                }
            )
    return path


def apply_targets(
    session: Session,
    rows: list[GradeCatalog],
    *,
    replace_generated: bool = True,
) -> dict[str, int]:
    """Upsert GT-* watchlist rows. Does not touch brother-curated WATCH-* ids."""
    keep_ids = {generated_watch_id(r.pricecharting_id) for r in rows}
    deactivated = 0
    if replace_generated:
        existing = (
            session.query(WatchlistItem)
            .filter(WatchlistItem.watch_id.like("GT-%"))
            .all()
        )
        for item in existing:
            if item.watch_id not in keep_ids and item.active:
                item.active = False
                deactivated += 1

    upserted = 0
    for row in rows:
        watch_id = generated_watch_id(row.pricecharting_id)
        item = session.query(WatchlistItem).filter_by(watch_id=watch_id).one_or_none()
        if item is None:
            item = WatchlistItem(watch_id=watch_id)
            session.add(item)
        item.name = row.product_name
        item.set_code = (row.console_name or "")[:64]
        item.set_name = row.console_name
        item.collector_number = row.collector_number
        item.language = "en"
        item.variant = "holo" if "holo" in row.product_name.lower() else "normal"
        item.tcgdex_id = None
        item.search_aliases = _aliases(row)
        item.condition_floor = "LP"
        item.priority = TIER_PRIORITY.get(row.tier or "", "opportunistic")
        item.min_discount_bps = 0 if TIER_THESIS.get(row.tier or "") != "flip_raw" else 2500
        item.max_buy_ore = row.max_raw_buy_ore or None
        item.reference_source = "pricecharting"
        item.notes = _notes(row)
        item.active = True
        item.frozen = True
        item.buy_thesis = TIER_THESIS.get(row.tier or "", "grade_upside")
        item.grade_tier = row.tier
        item.grade_catalog_id = row.id
        upserted += 1

    audit(
        session,
        action="grade_targets.export",
        entity_type="watchlist",
        entity_id="GT",
        details=f"upserted={upserted}; deactivated={deactivated}",
    )
    return {"upserted": upserted, "deactivated": deactivated, "targets": len(rows)}
