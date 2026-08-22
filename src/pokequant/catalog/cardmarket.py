from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.db.models import PriceObservation, Product, WatchlistItem
from pokequant.money import eur_to_sek_ore, to_ore

logger = logging.getLogger(__name__)


def ingest_price_guide_csv(
    session: Session,
    path: str | Path,
    *,
    sek_per_eur: float = 11.0,
    id_product_col: str = "idProduct",
    trend_col: str = "Trend Price",
) -> int:
    """
    Ingest a sanctioned Cardmarket price-guide CSV download.
    Place the downloaded file under data/cardmarket/ and call this.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    # Map watchlist tcgdex/cardmarket product ids if present in notes/external refs.
    watch_by_ext = {
        w.tcgdex_id: w
        for w in session.query(WatchlistItem).filter(WatchlistItem.tcgdex_id.is_not(None)).all()
    }
    products = {p.tcgdex_id: p for p in session.query(Product).filter(Product.tcgdex_id.is_not(None)).all()}

    count = 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ext = (row.get(id_product_col) or "").strip()
            trend = row.get(trend_col) or row.get("trend") or row.get("Trend")
            if not ext or trend in (None, ""):
                continue
            # Only store rows that map to known products/watchlist for MVP scope.
            product = products.get(ext)
            watch = watch_by_ext.get(ext)
            if product is None and watch is None:
                continue
            try:
                eur_cents = to_ore(float(str(trend).replace(",", ".")), currency="EUR")
            except ValueError:
                continue
            now = datetime.now(timezone.utc)
            session.add(
                PriceObservation(
                    product_id=product.id if product else None,
                    watchlist_item_id=watch.id if watch else None,
                    source="cardmarket",
                    status="guide",
                    observed_at=now,
                    available_to_model_at=now,
                    currency="SEK",
                    price_ore=eur_to_sek_ore(eur_cents, sek_per_eur=sek_per_eur),
                    condition="NM",
                    is_primary=True,
                    external_ref=ext,
                    notes=f"cardmarket csv {path.name}; fx={sek_per_eur}",
                )
            )
            count += 1

    audit(
        session,
        action="cardmarket.ingest_csv",
        entity_type="price_observation",
        entity_id=path.name,
        details=f"count={count}",
    )
    logger.info("Ingested %s Cardmarket price rows from %s", count, path)
    return count


def default_download_dir() -> Path:
    return Path(get_settings().cardmarket_download_dir)
