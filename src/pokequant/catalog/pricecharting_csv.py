from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.connectors.pricecharting import grade_row_from_mapping
from pokequant.db.models import GradeCatalog, PriceObservation
from pokequant.grading.score import score_grade_row
from pokequant.money import parse_fx_as_of

logger = logging.getLogger(__name__)

GRADE_CONDITIONS = (
    ("ungraded", "raw_usd_cents", "raw_ore"),
    ("psa8", "psa8_usd_cents", "psa8_ore"),
    ("psa9", "psa9_usd_cents", "psa9_ore"),
    ("psa10", "psa10_usd_cents", "psa10_ore"),
    ("bgs10", "bgs10_usd_cents", "bgs10_ore"),
    ("black_label", "black_label_usd_cents", "black_label_ore"),
)


def apply_score(row: GradeCatalog, score) -> None:
    row.raw_ore = score.raw_ore
    row.psa8_ore = score.psa8_ore
    row.psa9_ore = score.psa9_ore
    row.psa10_ore = score.psa10_ore
    row.bgs10_ore = score.bgs10_ore
    row.black_label_ore = score.black_label_ore
    row.gem_rate_psa10 = score.prior.psa10
    row.psa9_rate = score.prior.psa9
    row.psa8_rate = score.prior.psa8
    row.miss_rate = score.prior.miss
    row.prior_bucket = score.prior.bucket
    row.damage_flag = score.prior.damage
    row.spread_psa10 = score.spread_psa10
    row.ev_ore = score.ev_ore
    row.upside_if_10_mult = score.upside_if_10_mult
    row.grade_cost_ore = score.grade_cost_ore
    row.max_raw_buy_ore = score.max_raw_buy_ore
    row.psa9_floor_profit_ore = score.psa9_floor_profit_ore
    row.tier = score.tier
    row.drop_reason = score.drop_reason
    row.liquidity_flag = bool(score.psa9_ore)


def _write_observations(
    session: Session,
    row: GradeCatalog,
    *,
    now: datetime,
    path_name: str,
) -> int:
    settings = get_settings()
    written = 0
    for condition, usd_attr, ore_attr in GRADE_CONDITIONS:
        ore = int(getattr(row, ore_attr) or 0)
        usd = getattr(row, usd_attr)
        if ore <= 0:
            continue
        session.add(
            PriceObservation(
                source="pricecharting",
                status="guide",
                observed_at=now,
                available_to_model_at=now,
                currency="SEK",
                price_ore=ore,
                condition=condition,
                is_primary=condition == "ungraded",
                external_ref=f"pc:{row.pricecharting_id}",
                notes=f"pricecharting csv {path_name}; usd_cents={usd}; fx={settings.usd_sek_rate}",
                fx_rate_used=settings.usd_sek_rate,
                fx_as_of=parse_fx_as_of(settings.fx_as_of),
                comp_product_id=row.pricecharting_id,
            )
        )
        written += 1
    return written


def ingest_pricecharting_csv(session: Session, path: str | Path) -> dict[str, int]:
    """Ingest a Legendary PriceCharting CSV. Pokemon + hockey cards only."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    settings = get_settings()
    now = datetime.now(timezone.utc)
    stats = {
        "read": 0,
        "kept": 0,
        "scored": 0,
        "dropped": 0,
        "skipped_sport": 0,
        "observations": 0,
    }

    existing = {
        r.pricecharting_id: r
        for r in session.query(GradeCatalog).all()
    }

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            stats["read"] += 1
            parsed = grade_row_from_mapping(raw, prices_are_dollars=True)
            if parsed is None:
                stats["skipped_sport"] += 1
                continue
            row = existing.get(parsed.product_id)
            if row is None:
                row = GradeCatalog(pricecharting_id=parsed.product_id)
                session.add(row)
                existing[parsed.product_id] = row
            row.sport = parsed.sport
            row.product_name = parsed.product_name
            row.console_name = parsed.console_name
            row.genre = parsed.genre
            row.collector_number = parsed.collector_number
            row.release_date = parsed.release_date
            row.raw_usd_cents = parsed.raw_usd_cents
            row.psa8_usd_cents = parsed.psa8_usd_cents
            row.psa9_usd_cents = parsed.psa9_usd_cents
            row.psa10_usd_cents = parsed.psa10_usd_cents
            row.bgs10_usd_cents = parsed.bgs10_usd_cents
            row.black_label_usd_cents = parsed.black_label_usd_cents
            row.prices_as_of = now
            row.fx_rate_used = settings.usd_sek_rate
            score = score_grade_row(
                parsed,
                gem_rate_override=row.gem_rate_override,
                tier_override=row.tier_override,
            )
            apply_score(row, score)
            stats["kept"] += 1
            if score.tier:
                stats["scored"] += 1
            else:
                stats["dropped"] += 1
            stats["observations"] += _write_observations(session, row, now=now, path_name=path.name)

    audit(
        session,
        action="pricecharting.ingest_csv",
        entity_type="grade_catalog",
        entity_id=path.name,
        details=str(stats),
    )
    logger.info("Ingested PriceCharting CSV %s %s", path, stats)
    return stats


def rescore_catalog(session: Session) -> dict[str, int]:
    from pokequant.connectors.pricecharting import PriceChartingGradeRow

    stats = {"rescored": 0, "kept": 0, "dropped": 0}
    for row in session.query(GradeCatalog).all():
        parsed = PriceChartingGradeRow(
            product_id=row.pricecharting_id,
            product_name=row.product_name,
            console_name=row.console_name,
            genre=row.genre,
            sport=row.sport,
            collector_number=row.collector_number,
            release_date=row.release_date,
            raw_usd_cents=row.raw_usd_cents,
            psa8_usd_cents=row.psa8_usd_cents,
            psa9_usd_cents=row.psa9_usd_cents,
            psa10_usd_cents=row.psa10_usd_cents,
            bgs10_usd_cents=row.bgs10_usd_cents,
            black_label_usd_cents=row.black_label_usd_cents,
        )
        score = score_grade_row(
            parsed,
            gem_rate_override=row.gem_rate_override,
            tier_override=row.tier_override,
        )
        apply_score(row, score)
        stats["rescored"] += 1
        if score.tier:
            stats["kept"] += 1
        else:
            stats["dropped"] += 1
    return stats
