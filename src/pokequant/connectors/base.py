from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedListing:
    source_code: str
    external_id: str
    url: str
    title: str
    description: str = ""
    currency: str = ""
    price_ore: int | None = None
    shipping_ore: int | None = None
    buyer_fee_ore: int | None = None
    seller_type: str = "unknown"
    seller_key: str | None = None
    image_urls: list[str] = field(default_factory=list)
    status: str = "active"
    source_timestamp: datetime | None = None
    raw_payload: str = ""
    raw_hash: str = ""
    listing_type: str = "unknown"
    fulfillment: str = "unknown"
    extractor_version: str = ""
    scout_arm_id: int | None = None
    query_pull_id: int | None = None
    truncated: bool = False
    is_ended: bool = False
