from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from pokequant.config import get_settings
from pokequant.connectors.base import NormalizedListing
from pokequant.money import to_ore

logger = logging.getLogger(__name__)

BIN_ITEM_TYPES = frozenset(
    {
        "purebuyitnow",
        "shopitem",
        "auctionwithbuynow",
        "buyitnow",
        "fixedprice",
        "shop",
    }
)
AUCTION_ITEM_TYPES = frozenset({"auction", "pureauction"})
PAGE_SIZE_DEFAULT = 50


class QuotaExhausted(RuntimeError):
    def __init__(self, retry_after: datetime | None = None) -> None:
        super().__init__("Tradera API quota exhausted (HTTP 429)")
        self.retry_after = retry_after


class ExtractError(RuntimeError):
    pass


class TraderaClient:
    """Tradera REST API v4 search + selective item lookup (read-only)."""

    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
        base_url: str = "https://api.tradera.com/v4",
        client: httpx.Client | None = None,
        *,
        on_call: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.app_id = app_id if app_id is not None else settings.tradera_app_id
        self.app_key = app_key if app_key is not None else settings.tradera_app_key
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)
        self.calls_made = 0
        self.on_call = on_call  # optional callback(endpoint, status)
        self.advanced_ok: bool | None = None
        self.last_truncated = False
        self.extractor_version = settings.extractor_version

    def _headers(self) -> dict[str, str]:
        return {
            "X-App-Id": self.app_id,
            "X-App-Key": self.app_key,
            "Accept": "application/json",
        }

    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)

    def _raise_for_quota(self, resp: httpx.Response) -> None:
        if resp.status_code != 429:
            return
        retry_after = None
        raw = resp.headers.get("Retry-After")
        if raw:
            try:
                retry_after = datetime.now(timezone.utc) + timedelta(seconds=int(raw))
            except ValueError:
                retry_after = datetime.now(timezone.utc) + timedelta(minutes=60)
        else:
            retry_after = datetime.now(timezone.utc) + timedelta(minutes=60)
        raise QuotaExhausted(retry_after)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        resp = self._client.request(method, url, headers=self._headers(), **kwargs)
        self.calls_made += 1
        if self.on_call:
            self.on_call(url, resp.status_code)
        self._raise_for_quota(resp)
        return resp

    def search(self, query: str, *, page: int = 1) -> list[NormalizedListing]:
        if not self.configured():
            raise RuntimeError("Tradera credentials not configured")
        settings = get_settings()
        items, truncated = self._search_page(query, page=page, category_id=settings.tradera_category_id)
        self.last_truncated = truncated
        return [self._normalize(item, truncated=truncated) for item in items]

    def _search_page(
        self, query: str, *, page: int, category_id: str
    ) -> tuple[list[dict[str, Any]], bool]:
        if self.advanced_ok is not False:
            try:
                items, truncated = self._search_advanced(query, page=page, category_id=category_id)
                self.advanced_ok = True
                return items, truncated
            except (httpx.HTTPStatusError, ExtractError, ValueError) as exc:
                logger.info("Tradera advanced search unavailable (%s); falling back to GET /search", exc)
                self.advanced_ok = False
        return self._search_get(query, page=page, category_id=category_id)

    def _search_get(
        self, query: str, *, page: int, category_id: str
    ) -> tuple[list[dict[str, Any]], bool]:
        url = f"{self.base_url}/search"
        params: dict[str, Any] = {
            "query": query,
            "pageNumber": page,
            "sortBy": "EndDateDescending",
        }
        if category_id:
            params["categoryId"] = category_id
        resp = self._request("GET", url, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = self._extract_items(data)
        page_size = get_settings().tradera_page_size or PAGE_SIZE_DEFAULT
        truncated = len(items) >= page_size
        return items, truncated

    def _search_advanced(
        self, query: str, *, page: int, category_id: str
    ) -> tuple[list[dict[str, Any]], bool]:
        url = f"{self.base_url}/search/advanced"
        payload: dict[str, Any] = {
            "query": query,
            "pageNumber": page,
            "itemType": "BuyItNow",
            "sortBy": "EndDateDescending",
        }
        if category_id:
            payload["categoryId"] = category_id
        resp = self._request("POST", url, json=payload)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError("advanced search rejected", request=resp.request, response=resp)
        data = resp.json()
        items = self._extract_items(data)
        page_size = get_settings().tradera_page_size or PAGE_SIZE_DEFAULT
        return items, len(items) >= page_size

    def get_item(self, item_id: str) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("Tradera credentials not configured")
        url = f"{self.base_url}/items/{item_id}"
        resp = self._request("GET", url)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ExtractError("item payload is not an object")
        return data

    def hydrate(self, listing: NormalizedListing) -> NormalizedListing:
        payload = self.get_item(listing.external_id)
        return self._merge_item(listing, payload)

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if not isinstance(data, dict):
            return []
        for key in ("items", "Items", "results", "Results", "searchResult", "SearchResult"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                for inner in ("items", "Items", "item", "Item"):
                    maybe = value.get(inner)
                    if isinstance(maybe, list):
                        return [x for x in maybe if isinstance(x, dict)]
        return []

    def _normalize(self, item: dict[str, Any], *, truncated: bool = False) -> NormalizedListing:
        external_id = str(
            item.get("itemId")
            or item.get("ItemId")
            or item.get("id")
            or item.get("Id")
            or item.get("shortId")
            or ""
        )
        if not external_id:
            raise ExtractError("search item missing required itemId")
        title = str(item.get("shortDescription") or item.get("title") or item.get("Title") or "")
        if not title:
            raise ExtractError(f"search item {external_id} missing required title")
        currency = _currency_of(item)
        listing_type, bin_price = _listing_type_and_bin(item)
        shipping_ore = _optional_money(item.get("shippingCost") or item.get("ShippingCost"))
        buyer_fee_ore = _optional_money(
            item.get("buyerProtectionFee") or item.get("buyerFee") or item.get("BuyerFee")
        )
        url = str(
            item.get("itemUrl")
            or item.get("url")
            or item.get("Url")
            or f"https://www.tradera.com/item/{external_id}"
        )
        images = item.get("imageUrls") or item.get("ImageUrls") or item.get("images") or []
        if isinstance(images, str):
            image_urls = [images]
        else:
            image_urls = [str(x) for x in images]
        is_ended = bool(item.get("isEnded") or item.get("IsEnded"))
        payload = json.dumps(item, sort_keys=True, default=str)
        seller_type = "business" if item.get("isShopItem") or listing_type == "shop" else "private"
        return NormalizedListing(
            source_code="tradera",
            external_id=external_id,
            url=url,
            title=title,
            description=str(item.get("longDescription") or item.get("description") or ""),
            currency=currency,
            price_ore=bin_price,
            shipping_ore=shipping_ore,
            buyer_fee_ore=buyer_fee_ore,
            seller_type=seller_type,
            seller_key=str(item.get("sellerMemberId") or item.get("sellerId") or "") or None,
            image_urls=image_urls,
            status="ended" if is_ended else "active",
            source_timestamp=datetime.now(timezone.utc),
            raw_payload=payload,
            raw_hash=hashlib.sha256(payload.encode()).hexdigest(),
            listing_type=listing_type,
            fulfillment="unknown" if shipping_ore is None else "shipping",
            extractor_version=self.extractor_version,
            truncated=truncated,
            is_ended=is_ended,
        )

    def _merge_item(self, listing: NormalizedListing, item: dict[str, Any]) -> NormalizedListing:
        shipping = _shipping_from_item(item)
        buyer_fee = _optional_money(
            item.get("buyerProtectionFee") or item.get("buyerFee") or item.get("BuyerFee")
        )
        currency = _currency_of(item) or listing.currency
        listing_type, bin_price = _listing_type_and_bin(item)
        payload = json.dumps(item, sort_keys=True, default=str)
        return NormalizedListing(
            source_code=listing.source_code,
            external_id=listing.external_id,
            url=listing.url or str(item.get("itemUrl") or listing.url),
            title=str(item.get("shortDescription") or item.get("title") or listing.title),
            description=str(item.get("longDescription") or item.get("description") or listing.description),
            currency=currency,
            price_ore=bin_price if bin_price is not None else listing.price_ore,
            shipping_ore=shipping if shipping is not None else listing.shipping_ore,
            buyer_fee_ore=buyer_fee if buyer_fee is not None else listing.buyer_fee_ore,
            seller_type=listing.seller_type,
            seller_key=listing.seller_key,
            image_urls=listing.image_urls,
            status=listing.status,
            source_timestamp=datetime.now(timezone.utc),
            raw_payload=payload,
            raw_hash=hashlib.sha256(payload.encode()).hexdigest(),
            listing_type=listing_type if listing_type != "unknown" else listing.listing_type,
            fulfillment="shipping" if shipping is not None else listing.fulfillment,
            extractor_version=self.extractor_version,
            scout_arm_id=listing.scout_arm_id,
            query_pull_id=listing.query_pull_id,
            is_ended=listing.is_ended or bool(item.get("isEnded") or item.get("IsEnded")),
        )


def _currency_of(item: dict[str, Any]) -> str:
    raw = item.get("currency") or item.get("Currency")
    if isinstance(raw, dict):
        raw = raw.get("code") or raw.get("CurrencyCode")
    price = item.get("price") or item.get("buyItNowPrice") or item.get("BuyItNowPrice")
    if not raw and isinstance(price, dict):
        raw = price.get("currency") or price.get("currencyCode")
    return str(raw or "").upper()


def _optional_money(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        raw = raw.get("amount") or raw.get("value")
        if raw is None:
            return None
    try:
        return to_ore(raw)
    except (TypeError, ValueError):
        return None


def _listing_type_and_bin(item: dict[str, Any]) -> tuple[str, int | None]:
    item_type = str(item.get("itemType") or item.get("ItemType") or "").replace(" ", "").lower()
    bin_raw = item.get("buyItNowPrice") or item.get("BuyItNowPrice")
    if bin_raw is None and item_type in BIN_ITEM_TYPES:
        bin_raw = item.get("price") or item.get("Price")
    # Never use nextBid / maxBid as a BIN price.
    bin_price = _optional_money(bin_raw)
    if item_type in AUCTION_ITEM_TYPES and bin_price is None:
        return "auction", None
    if item_type in {"auctionwithbuynow"} or (item_type in AUCTION_ITEM_TYPES and bin_price is not None):
        return "auction_with_bin", bin_price
    if item_type in {"shopitem", "shop"} or item.get("isShopItem"):
        return "shop", bin_price
    if item_type in BIN_ITEM_TYPES or bin_price is not None:
        return "bin", bin_price
    if item_type in AUCTION_ITEM_TYPES:
        return "auction", None
    return "unknown", bin_price


def _shipping_from_item(item: dict[str, Any]) -> int | None:
    direct = _optional_money(item.get("shippingCost") or item.get("ShippingCost"))
    if direct is not None:
        return direct
    options = item.get("shippingOptions") or item.get("ShippingOptions") or []
    if isinstance(options, list) and options:
        first = options[0] if isinstance(options[0], dict) else {}
        return _optional_money(
            first.get("cost") or first.get("shippingCost") or first.get("price") or first.get("amount")
        )
    return None


def is_bin_listing(listing: NormalizedListing) -> bool:
    return listing.listing_type in {"bin", "shop", "auction_with_bin"} and listing.price_ore is not None


def build_watchlist_queries(aliases_by_priority: list[tuple[str, str]]) -> list[str]:
    """One alias per call. Do not pack OR-queries."""
    core = [a for p, a in aliases_by_priority if p == "core"]
    opp = [a for p, a in aliases_by_priority if p != "core"]
    ordered: list[str] = []
    for alias in core + opp:
        alias = alias.strip()
        if alias and alias not in ordered:
            ordered.append(alias)
    return ordered
