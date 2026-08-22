from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pokequant.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    access_tier: Mapped[str] = mapped_column(String(32), default="production")  # production|permission|manual|paid
    access_basis: Mapped[str] = mapped_column(Text, default="")
    daily_call_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quota_exhausted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    api_calls: Mapped[list[SourceApiCall]] = relationship(back_populates="source")


class SourceApiCall(Base):
    """Rolling 24h Tradera (and later) REST call log. Do not use per-process counters."""

    __tablename__ = "source_api_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    endpoint: Mapped[str] = mapped_column(String(128), default="")
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    source: Mapped[Source] = relationship(back_populates="api_calls")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tcgdex_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    set_code: Mapped[str] = mapped_column(String(64), default="")
    set_name: Mapped[str] = mapped_column(String(255), default="")
    collector_number: Mapped[str] = mapped_column(String(32), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    variant: Mapped[str] = mapped_column(String(64), default="normal")
    rarity: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="pokemon_single")


class WatchlistItem(Base, TimestampMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watch_id", name="uq_watch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[str] = mapped_column(String(32), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    set_code: Mapped[str] = mapped_column(String(64), default="")
    set_name: Mapped[str] = mapped_column(String(255), default="")
    collector_number: Mapped[str] = mapped_column(String(32), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    variant: Mapped[str] = mapped_column(String(64), default="normal")
    tcgdex_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    search_aliases: Mapped[str] = mapped_column(Text, default="")
    condition_floor: Mapped[str] = mapped_column(String(16), default="LP")
    priority: Mapped[str] = mapped_column(String(32), default="core")  # core|opportunistic
    min_discount_bps: Mapped[int] = mapped_column(Integer, default=2500)
    max_buy_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_source: Mapped[str] = mapped_column(String(64), default="cardmarket")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    frozen: Mapped[bool] = mapped_column(Boolean, default=True)
    buy_thesis: Mapped[str] = mapped_column(String(32), default="flip_raw")  # flip_raw|grade_upside|both
    grade_tier: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    grade_catalog_id: Mapped[Optional[int]] = mapped_column(ForeignKey("grade_catalog.id"), nullable=True)

    product: Mapped[Optional[Product]] = relationship()
    grade_catalog: Mapped[Optional["GradeCatalog"]] = relationship()


class WatchlistMeta(Base, TimestampMixin):
    __tablename__ = "watchlist_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    expansion_allowed: Mapped[bool] = mapped_column(Boolean, default=False)


class ScoutArm(Base, TimestampMixin):
    __tablename__ = "scout_arms"
    __table_args__ = (UniqueConstraint("source", "key", name="uq_scout_arm_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    arm_type: Mapped[str] = mapped_column(String(32), default="alias")
    key: Mapped[str] = mapped_column(String(255), index=True)
    watch_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    arm_class: Mapped[str] = mapped_column(String(32), default="core")  # core|opportunistic
    last_pulled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    n_pulls: Mapped[int] = mapped_column(Integer, default=0)
    n_resolved: Mapped[int] = mapped_column(Integer, default=0)
    n_reward_1: Mapped[int] = mapped_column(Integer, default=0)
    n_censored: Mapped[int] = mapped_column(Integer, default=0)
    n_new_total: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="active")


class QueryPull(Base, TimestampMixin):
    __tablename__ = "query_pulls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arm_id: Mapped[int] = mapped_column(ForeignKey("scout_arms.id"), index=True)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    listing_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    n_new: Mapped[int] = mapped_column(Integer, default=0)
    n_alerted: Mapped[int] = mapped_column(Integer, default=0)
    reward: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reward_status: Mapped[str] = mapped_column(String(32), default="pending")
    reward_reason: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    credited_decision_ids_json: Mapped[str] = mapped_column(Text, default="[]")

    arm: Mapped[ScoutArm] = relationship()


class Listing(Base, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_code", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_code: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    currency: Mapped[str] = mapped_column(String(8), default="")
    price_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shipping_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    buyer_fee_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seller_type: Mapped[str] = mapped_column(String(32), default="unknown")
    seller_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_urls: Mapped[str] = mapped_column(Text, default="")  # newline-separated
    status: Mapped[str] = mapped_column(String(32), default="active")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_hash: Mapped[str] = mapped_column(String(64), default="")
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    workflow_state: Mapped[str] = mapped_column(String(32), default="discovered")
    fulfillment: Mapped[str] = mapped_column(String(32), default="unknown")
    listing_type: Mapped[str] = mapped_column(String(32), default="unknown")
    scout_arm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scout_arms.id"), nullable=True)
    query_pull_id: Mapped[Optional[int]] = mapped_column(ForeignKey("query_pulls.id"), nullable=True)
    extractor_version: Mapped[str] = mapped_column(String(64), default="")
    matched_alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    watchlist_item: Mapped[Optional[WatchlistItem]] = relationship()
    snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="listing")
    valuations: Mapped[list[Valuation]] = relationship(back_populates="listing")
    decisions: Mapped[list[Decision]] = relationship(back_populates="listing")


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available_to_model_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    price_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shipping_ore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    raw_payload: Mapped[str] = mapped_column(Text, default="")
    raw_hash: Mapped[str] = mapped_column(String(64), default="")

    listing: Mapped[Listing] = relationship(back_populates="snapshots")


class PriceObservation(Base, TimestampMixin):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # cardmarket|tcgdex|pricecharting|tradera|manual
    status: Mapped[str] = mapped_column(String(32), default="guide")  # guide|sold|active|paid|cancelled|returned
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available_to_model_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    price_ore: Mapped[int] = mapped_column(Integer)
    shipping_ore: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    external_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    fx_rate_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fx_as_of: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    comp_product_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class Valuation(Base, TimestampMixin):
    __tablename__ = "valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    fee_schedule_version: Mapped[str] = mapped_column(String(64))
    market_value_p10_ore: Mapped[int] = mapped_column(Integer)
    market_value_p50_ore: Mapped[int] = mapped_column(Integer)
    market_value_p90_ore: Mapped[int] = mapped_column(Integer)
    expected_net_proceeds_ore: Mapped[int] = mapped_column(Integer)
    landed_cost_ore: Mapped[int] = mapped_column(Integer)
    expected_profit_ore: Mapped[int] = mapped_column(Integer)
    max_buy_ore: Mapped[int] = mapped_column(Integer)
    discount_bps: Mapped[int] = mapped_column(Integer, default=0)
    identity_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    passes_hard_gates: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_failures: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    passed_thesis: Mapped[str] = mapped_column(String(32), default="")
    grade_ev_ore: Mapped[int] = mapped_column(Integer, default=0)

    listing: Mapped[Listing] = relationship(back_populates="valuations")


class GradeCatalog(Base, TimestampMixin):
    """Licensed PriceCharting grade ladder + EV score. Keyed by PriceCharting id."""

    __tablename__ = "grade_catalog"
    __table_args__ = (UniqueConstraint("pricecharting_id", name="uq_grade_catalog_pc_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricecharting_id: Mapped[str] = mapped_column(String(64), index=True)
    sport: Mapped[str] = mapped_column(String(16), index=True)  # pokemon|hockey
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    console_name: Mapped[str] = mapped_column(String(255), default="")
    genre: Mapped[str] = mapped_column(String(128), default="")
    collector_number: Mapped[str] = mapped_column(String(32), default="")
    release_date: Mapped[str] = mapped_column(String(32), default="")
    raw_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    psa8_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    psa9_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    psa10_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bgs10_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    black_label_usd_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_ore: Mapped[int] = mapped_column(Integer, default=0)
    psa8_ore: Mapped[int] = mapped_column(Integer, default=0)
    psa9_ore: Mapped[int] = mapped_column(Integer, default=0)
    psa10_ore: Mapped[int] = mapped_column(Integer, default=0)
    bgs10_ore: Mapped[int] = mapped_column(Integer, default=0)
    black_label_ore: Mapped[int] = mapped_column(Integer, default=0)
    gem_rate_psa10: Mapped[float] = mapped_column(Float, default=0.0)
    psa9_rate: Mapped[float] = mapped_column(Float, default=0.0)
    psa8_rate: Mapped[float] = mapped_column(Float, default=0.0)
    miss_rate: Mapped[float] = mapped_column(Float, default=0.0)
    prior_bucket: Mapped[str] = mapped_column(String(32), default="")
    damage_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    gem_rate_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier_override: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    spread_psa10: Mapped[float] = mapped_column(Float, default=0.0)
    ev_ore: Mapped[int] = mapped_column(Integer, default=0)
    upside_if_10_mult: Mapped[float] = mapped_column(Float, default=0.0)
    grade_cost_ore: Mapped[int] = mapped_column(Integer, default=0)
    max_raw_buy_ore: Mapped[int] = mapped_column(Integer, default=0)
    psa9_floor_profit_ore: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    drop_reason: Mapped[str] = mapped_column(String(64), default="")
    prices_as_of: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fx_rate_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    valuation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("valuations.id"), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(128), default="domain")
    intent: Mapped[str] = mapped_column(String(32))  # buy|skip|need_photos|watch|too_late
    quality_label: Mapped[str] = mapped_column(String(32), default="n/a")  # legacy alias of deal_label
    identity_label: Mapped[str] = mapped_column(String(32), default="n/a")  # correct|wrong|n/a
    deal_label: Mapped[str] = mapped_column(String(32), default="n/a")  # really_good|maybe|junk|n/a
    reason_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    alerted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    false_match: Mapped[bool] = mapped_column(Boolean, default=False)
    callback_query_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    passes_hard_gates: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gate_failures: Mapped[str] = mapped_column(Text, default="")
    match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    matched_alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scout_arm_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    query_pull_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_code: Mapped[str] = mapped_column(String(64), default="")

    listing: Mapped[Listing] = relationship(back_populates="decisions")


class Purchase(Base, TimestampMixin):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    listing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("listings.id"), nullable=True)
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    seller_type: Mapped[str] = mapped_column(String(32), default="private")
    seller_country: Mapped[str] = mapped_column(String(8), default="SE")
    currency: Mapped[str] = mapped_column(String(8), default="SEK")
    purchase_price_ore: Mapped[int] = mapped_column(Integer)
    buyer_fee_ore: Mapped[int] = mapped_column(Integer, default=0)
    inbound_shipping_ore: Mapped[int] = mapped_column(Integer, default=0)
    import_cost_ore: Mapped[int] = mapped_column(Integer, default=0)
    landed_cost_ore: Mapped[int] = mapped_column(Integer)
    vat_code: Mapped[str] = mapped_column(String(32), default="UNSET")
    evidence_refs: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[str] = mapped_column(String(128), default="")
    exception_notes: Mapped[str] = mapped_column(Text, default="")
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expected_arrival_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_state: Mapped[str] = mapped_column(String(32), default="purchased")


class Lot(Base, TimestampMixin):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    total_landed_cost_ore: Mapped[int] = mapped_column(Integer)
    allocation_method: Mapped[str] = mapped_column(String(64), default="equal")
    notes: Mapped[str] = mapped_column(Text, default="")


class InventoryUnit(Base, TimestampMixin):
    __tablename__ = "inventory_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchases.id"), nullable=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lots.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    identity_name: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(16), default="en")
    variant: Mapped[str] = mapped_column(String(64), default="normal")
    condition: Mapped[str] = mapped_column(String(32), default="NM")
    defects: Mapped[str] = mapped_column(Text, default="")
    authenticity_status: Mapped[str] = mapped_column(String(32), default="pending")
    allocated_cost_ore: Mapped[int] = mapped_column(Integer, default=0)
    vat_code: Mapped[str] = mapped_column(String(32), default="UNSET")
    location: Mapped[str] = mapped_column(String(64), default="RECEIVING")
    state: Mapped[str] = mapped_column(String(32), default="receiving")
    # receiving|quarantine|ready|listed|reserved|sold|stale


class Inspection(Base, TimestampMixin):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_unit_id: Mapped[int] = mapped_column(ForeignKey("inventory_units.id"), index=True)
    inspector: Mapped[str] = mapped_column(String(128))
    blind: Mapped[bool] = mapped_column(Boolean, default=False)
    predicted_condition: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    observed_condition: Mapped[str] = mapped_column(String(32))
    authenticity_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    mismatch: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    photo_refs: Mapped[str] = mapped_column(Text, default="")
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingForSale(Base, TimestampMixin):
    __tablename__ = "listings_for_sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_unit_id: Mapped[int] = mapped_column(ForeignKey("inventory_units.id"), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    external_listing_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    asking_ore: Mapped[int] = mapped_column(Integer)
    min_acceptable_ore: Mapped[int] = mapped_column(Integer)
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(32), default="active")


class Sale(Base, TimestampMixin):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    inventory_unit_id: Mapped[int] = mapped_column(ForeignKey("inventory_units.id"), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    currency: Mapped[str] = mapped_column(String(8), default="SEK")
    gross_ore: Mapped[int] = mapped_column(Integer)
    shipping_charged_ore: Mapped[int] = mapped_column(Integer, default=0)
    marketplace_fee_ore: Mapped[int] = mapped_column(Integer, default=0)
    payment_fee_ore: Mapped[int] = mapped_column(Integer, default=0)
    postage_ore: Mapped[int] = mapped_column(Integer, default=0)
    packaging_ore: Mapped[int] = mapped_column(Integer, default=0)
    vat_code: Mapped[str] = mapped_column(String(32), default="UNSET")
    settlement_state: Mapped[str] = mapped_column(String(32), default="provisional")
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    buyer_country: Mapped[str] = mapped_column(String(8), default="SE")
    notes: Mapped[str] = mapped_column(Text, default="")


class ReturnRecord(Base, TimestampMixin):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    inventory_unit_id: Mapped[int] = mapped_column(ForeignKey("inventory_units.id"))
    reason: Mapped[str] = mapped_column(String(128), default="")
    refund_ore: Mapped[int] = mapped_column(Integer, default=0)
    added_shipping_ore: Mapped[int] = mapped_column(Integer, default=0)
    condition_change: Mapped[str] = mapped_column(Text, default="")
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64))
    amount_ore: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="SEK")
    incurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str] = mapped_column(Text, default="")
    linked_sale_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales.id"), nullable=True)
    linked_purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchases.id"), nullable=True)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255), default="")
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(Text, default="")


class AlertDelivery(Base, TimestampMixin):
    __tablename__ = "alert_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    valuation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("valuations.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    external_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload_summary: Mapped[str] = mapped_column(Text, default="")
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrecisionSnapshot(Base, TimestampMixin):
    __tablename__ = "precision_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_size: Mapped[int] = mapped_column(Integer)
    labeled_count: Mapped[int] = mapped_column(Integer)
    really_good_count: Mapped[int] = mapped_column(Integer)
    maybe_count: Mapped[int] = mapped_column(Integer)
    junk_count: Mapped[int] = mapped_column(Integer)
    false_match_count: Mapped[int] = mapped_column(Integer)
    really_good_rate: Mapped[float] = mapped_column(Float)
    false_match_rate: Mapped[float] = mapped_column(Float)
    median_decision_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    source_code: Mapped[str] = mapped_column(String(64), default="tradera", index=True)
    identity_labeled_count: Mapped[int] = mapped_column(Integer, default=0)
    deal_labeled_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)


class AppKv(Base, TimestampMixin):
    __tablename__ = "app_kv"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class SkipCandidate(Base, TimestampMixin):
    __tablename__ = "skip_candidates"
    __table_args__ = (UniqueConstraint("pattern", "skip_version", name="uq_skip_pattern_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(255))
    pattern_type: Mapped[str] = mapped_column(String(32), default="token")
    source_code: Mapped[str] = mapped_column(String(64), default="tradera")
    distinct_sellers: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|rejected|shipped
    skip_version: Mapped[str] = mapped_column(String(32), default="skip-v1")
    notes: Mapped[str] = mapped_column(Text, default="")


class AliasProposal(Base, TimestampMixin):
    __tablename__ = "watchlist_alias_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist_items.id"), nullable=True)
    proposed_alias: Mapped[str] = mapped_column(String(255))
    title_sample: Mapped[str] = mapped_column(Text, default="")
    seller_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    distinct_sellers: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|needs_human|approved|rejected
    needs_human: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
