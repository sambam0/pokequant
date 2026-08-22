from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from pokequant.config import get_settings
from pokequant.money import to_ore

logger = logging.getLogger(__name__)

# PriceCharting card-guide keys (Prices API + Legendary CSV headers).
PC_RAW = "loose-price"
PC_PSA8 = "new-price"
PC_PSA9 = "graded-price"
PC_PSA10 = "manual-only-price"
PC_BGS10 = "bgs-10-price"
PC_BLACK_LABEL = "condition-20-price"

_POKEMON_MARKERS = ("pokemon", "pokémon")
_HOCKEY_MARKERS = ("hockey", "nhl")
_COLLECTOR_RE = re.compile(r"#\s*(\d+[a-zA-Z]?)\b|(\d+)\s*/\s*\d+")


@dataclass(frozen=True)
class PriceChartingHit:
    usd_cents: int
    name: str
    product_id: str


@dataclass(frozen=True)
class PriceChartingGradeRow:
    """One PriceCharting card with the raw → gem ladder (USD cents)."""

    product_id: str
    product_name: str
    console_name: str
    genre: str
    sport: str
    collector_number: str
    release_date: str
    raw_usd_cents: int | None
    psa8_usd_cents: int | None
    psa9_usd_cents: int | None
    psa10_usd_cents: int | None
    bgs10_usd_cents: int | None
    black_label_usd_cents: int | None


def normalize_pc_header(name: str) -> str:
    return re.sub(r"[\s_]+", "-", (name or "").strip().lower())


def parse_csv_usd_cents(raw: Any) -> int | None:
    """Legendary CSV stores dollars with two decimals. Blank/zero means no print."""
    if raw is None:
        return None
    text = str(raw).replace("$", "").replace(",", "").strip()
    if text in {"", "-", "n/a", "na", "none"}:
        return None
    try:
        cents = int(round(float(text) * 100))
    except ValueError:
        return None
    return cents if cents > 0 else None


def parse_api_usd_cents(raw: Any) -> int | None:
    """Prices API stores integer pennies."""
    if raw is None or raw == "":
        return None
    try:
        cents = int(raw)
    except (TypeError, ValueError):
        try:
            cents = to_ore(raw, currency="USD")
        except (TypeError, ValueError):
            return None
    return cents if cents > 0 else None


def classify_sport(console_name: str = "", genre: str = "", product_name: str = "") -> str | None:
    hay = f"{console_name} {genre} {product_name}".lower()
    if any(token in hay for token in _POKEMON_MARKERS):
        return "pokemon"
    if any(token in hay for token in _HOCKEY_MARKERS):
        return "hockey"
    return None


def extract_collector_number(product_name: str) -> str:
    match = _COLLECTOR_RE.search(product_name or "")
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def row_get(row: dict[str, Any], *keys: str) -> Any:
    normalized = {normalize_pc_header(k): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(normalize_pc_header(key))
        if value not in (None, ""):
            return value
    return None


def grade_row_from_mapping(
    row: dict[str, Any], *, prices_are_dollars: bool
) -> PriceChartingGradeRow | None:
    parse = parse_csv_usd_cents if prices_are_dollars else parse_api_usd_cents
    product_id = str(row_get(row, "id", "product-id") or "").strip()
    name = str(row_get(row, "product-name", "name") or "").strip()
    if not product_id or not name:
        return None
    console = str(row_get(row, "console-name", "console") or "").strip()
    genre = str(row_get(row, "genre") or "").strip()
    sport = classify_sport(console, genre, name)
    if sport is None:
        return None
    return PriceChartingGradeRow(
        product_id=product_id,
        product_name=name,
        console_name=console,
        genre=genre,
        sport=sport,
        collector_number=extract_collector_number(name),
        release_date=str(row_get(row, "release-date") or "").strip(),
        raw_usd_cents=parse(row_get(row, PC_RAW, "ungraded-price")),
        psa8_usd_cents=parse(row_get(row, PC_PSA8)),
        psa9_usd_cents=parse(row_get(row, PC_PSA9)),
        psa10_usd_cents=parse(row_get(row, PC_PSA10)),
        bgs10_usd_cents=parse(row_get(row, PC_BGS10)),
        black_label_usd_cents=parse(row_get(row, PC_BLACK_LABEL)),
    )


class PriceChartingClient:
    """PriceCharting Prices API — current guide values (Legendary token)."""

    base_url = "https://www.pricecharting.com"

    def __init__(self, token: str | None = None, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.token = token if token is not None else settings.pricecharting_api_token
        self._client = client or httpx.Client(timeout=30.0)

    def configured(self) -> bool:
        return bool(self.token)

    def search_ungraded(self, query: str) -> PriceChartingHit | None:
        if not self.configured():
            raise RuntimeError("PriceCharting token not configured")
        resp = self._client.get(
            f"{self.base_url}/api/products",
            params={"t": self.token, "q": query},
        )
        resp.raise_for_status()
        data = resp.json()
        products = self._extract_products(data)
        if not products:
            return None
        product = products[0]
        raw = (
            product.get("loose-price")
            or product.get("ungraded-price")
            or product.get("cib-price")
            or product.get("new-price")
        )
        if raw is None:
            return None
        try:
            pennies = int(raw)
        except (TypeError, ValueError):
            pennies = to_ore(raw, currency="USD")
        if pennies <= 0:
            return None
        name = str(product.get("product-name") or product.get("name") or "")
        product_id = str(product.get("id") or product.get("product-id") or "")
        logger.info("pricecharting match query=%r product_id=%s name=%r", query, product_id, name)
        return PriceChartingHit(usd_cents=pennies, name=name, product_id=product_id)

    def parse_product_grades(self, product: dict[str, Any]) -> PriceChartingGradeRow | None:
        return grade_row_from_mapping(product, prices_are_dollars=False)

    def search_ungraded_usd_cents(self, query: str) -> int | None:
        hit = self.search_ungraded(query)
        return hit.usd_cents if hit else None

    @staticmethod
    def _extract_products(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if not isinstance(data, dict):
            return []
        if data.get("status") == "error":
            logger.warning("PriceCharting error: %s", data.get("error-message"))
            return []
        for key in ("products", "Products", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        if "id" in data and ("loose-price" in data or "product-name" in data):
            return [data]
        return []
