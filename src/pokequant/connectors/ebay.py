from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from pokequant.config import get_settings
from pokequant.money import to_ore

logger = logging.getLogger(__name__)

GRADED_TITLE_RE = re.compile(r"\b(psa|bgs|cgc|sgc|graded|slab)\b", re.IGNORECASE)


class EbayBrowseClient:
    """eBay Browse API — active listing asks (not sold history)."""

    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    browse_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        marketplace_id: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.client_id = client_id if client_id is not None else settings.ebay_client_id
        self.client_secret = client_secret if client_secret is not None else settings.ebay_client_secret
        self.marketplace_id = marketplace_id or settings.ebay_marketplace_id
        self._client = client or httpx.Client(timeout=30.0)
        self._token: str | None = None

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _access_token(self) -> str:
        if self._token:
            return self._token
        if not self.configured():
            raise RuntimeError("eBay credentials not configured")
        resp = self._client.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        self._token = str(resp.json()["access_token"])
        return self._token

    def search_lowest_ask_usd_cents(self, query: str, *, limit: int = 10) -> int | None:
        """Return lowest active ask in USD cents, or None if no hits."""
        token = self._access_token()
        resp = self._client.get(
            self.browse_url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()
        items = resp.json().get("itemSummaries") or []
        prices: list[int] = []
        for item in items:
            title = str(item.get("title") or "")
            if GRADED_TITLE_RE.search(title):
                continue
            price = self._item_price_usd_cents(item)
            if price is not None:
                prices.append(price)
        if not prices:
            return None
        return min(prices)

    @staticmethod
    def _item_price_usd_cents(item: dict[str, Any]) -> int | None:
        price = item.get("price") or {}
        value = price.get("value")
        currency = (price.get("currency") or "USD").upper()
        if value is None:
            return None
        cents = to_ore(value, currency=currency)
        # Shipping can matter; include if present.
        shipping = item.get("shippingOptions") or []
        if shipping:
            cost = (shipping[0].get("shippingCost") or {}).get("value")
            if cost is not None:
                cents += to_ore(cost, currency=currency)
        if currency != "USD":
            # MVP: only trust USD marketplace asks for the US comparison gate.
            return None
        return cents
