from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.db.models import PriceObservation, Product
from pokequant.money import eur_to_sek_ore, to_ore

logger = logging.getLogger(__name__)


class TCGdexClient:
    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.tcgdex_base_url).rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)

    def get_card(self, card_id: str, lang: str = "en") -> dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/{lang}/cards/{card_id}")
        resp.raise_for_status()
        return resp.json()

    def upsert_product_from_card(self, session: Session, card: dict[str, Any]) -> Product:
        tcgdex_id = str(card.get("id") or "")
        product = session.query(Product).filter_by(tcgdex_id=tcgdex_id).one_or_none()
        set_obj = card.get("set") or {}
        if product is None:
            product = Product(tcgdex_id=tcgdex_id)
            session.add(product)
        product.name = str(card.get("name") or product.name or tcgdex_id)
        product.set_code = str(set_obj.get("id") or "")
        product.set_name = str(set_obj.get("name") or "")
        product.collector_number = str(card.get("localId") or "")
        product.rarity = card.get("rarity")
        product.image_url = card.get("image")
        product.category = "pokemon_single"
        return product

    def sync_watchlist_prices(self, session: Session, tcgdex_ids: list[str], *, sek_per_eur: float = 11.0) -> int:
        from datetime import datetime, timezone

        count = 0
        for card_id in tcgdex_ids:
            if not card_id:
                continue
            try:
                card = self.get_card(card_id)
            except httpx.HTTPError as exc:
                logger.warning("TCGdex fetch failed for %s: %s", card_id, exc)
                continue
            product = self.upsert_product_from_card(session, card)
            pricing = (card.get("pricing") or {}).get("cardmarket") or {}
            trend = pricing.get("trend") or pricing.get("trend-holo") or pricing.get("avg")
            if trend is None:
                continue
            # TCGdex prices are EUR major units.
            eur_cents = to_ore(trend, currency="EUR")
            sek_ore = eur_to_sek_ore(eur_cents, sek_per_eur=sek_per_eur)
            now = datetime.now(timezone.utc)
            session.add(
                PriceObservation(
                    product_id=product.id,
                    source="tcgdex",
                    status="guide",
                    observed_at=now,
                    available_to_model_at=now,
                    currency="SEK",
                    price_ore=sek_ore,
                    condition="NM",
                    is_primary=True,
                    external_ref=card_id,
                    notes=f"cardmarket trend via tcgdex; fx={sek_per_eur}",
                )
            )
            count += 1
        audit(session, action="tcgdex.sync_prices", entity_type="price_observation", entity_id="batch", details=f"count={count}")
        return count
