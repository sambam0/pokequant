"""Hermes Mini v1 schema: nullable shipping, scout arms, split Decision labels.

Revision ID: 0002_hermes_mini
Revises: 0001_initial
Create Date: 2026-08-13

Mini never init-db / create_all. This revision is explicit ALTER/CREATE.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_hermes_mini"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("quota_exhausted_until", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "source_api_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("endpoint", sa.String(128), nullable=False, server_default=""),
        sa.Column("http_status", sa.Integer(), nullable=True),
    )
    op.create_index("ix_source_api_calls_source_id", "source_api_calls", ["source_id"])
    op.create_index("ix_source_api_calls_called_at", "source_api_calls", ["called_at"])

    op.create_table(
        "scout_arms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("arm_type", sa.String(32), nullable=False, server_default="alias"),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("watch_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("arm_class", sa.String(32), nullable=False, server_default="core"),
        sa.Column("last_pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("n_pulls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_resolved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_reward_1", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_censored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_new_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "key", name="uq_scout_arm_source_key"),
    )
    op.create_index("ix_scout_arms_source", "scout_arms", ["source"])
    op.create_index("ix_scout_arms_key", "scout_arms", ["key"])

    op.create_table(
        "query_pulls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arm_id", sa.Integer(), sa.ForeignKey("scout_arms.id"), nullable=False),
        sa.Column("pulled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("listing_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("n_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_alerted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward", sa.Integer(), nullable=True),
        sa.Column("reward_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reward_reason", sa.String(64), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credited_decision_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_query_pulls_arm_id", "query_pulls", ["arm_id"])

    with op.batch_alter_table("listings") as batch:
        batch.alter_column("price_ore", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("shipping_ore", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("buyer_fee_ore", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("fulfillment", sa.String(32), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("listing_type", sa.String(32), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("scout_arm_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("query_pull_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("extractor_version", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("matched_alias", sa.String(255), nullable=True))
        batch.create_foreign_key("fk_listings_scout_arm", "scout_arms", ["scout_arm_id"], ["id"])
        batch.create_foreign_key("fk_listings_query_pull", "query_pulls", ["query_pull_id"], ["id"])

    with op.batch_alter_table("listing_snapshots") as batch:
        batch.alter_column("price_ore", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("shipping_ore", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("price_observations") as batch:
        batch.add_column(sa.Column("fx_rate_used", sa.Float(), nullable=True))
        batch.add_column(sa.Column("fx_as_of", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("comp_product_id", sa.String(128), nullable=True))

    with op.batch_alter_table("decisions") as batch:
        batch.add_column(sa.Column("identity_label", sa.String(32), nullable=False, server_default="n/a"))
        batch.add_column(sa.Column("deal_label", sa.String(32), nullable=False, server_default="n/a"))
        batch.add_column(sa.Column("callback_query_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("passes_hard_gates", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("gate_failures", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("match_confidence", sa.Float(), nullable=True))
        batch.add_column(sa.Column("matched_alias", sa.String(255), nullable=True))
        batch.add_column(sa.Column("scout_arm_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("query_pull_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source_code", sa.String(64), nullable=False, server_default=""))
        batch.create_unique_constraint("uq_decisions_callback_query_id", ["callback_query_id"])

    with op.batch_alter_table("precision_snapshots") as batch:
        batch.add_column(sa.Column("source_code", sa.String(64), nullable=False, server_default="tradera"))
        batch.add_column(sa.Column("identity_labeled_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("deal_labeled_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"))
        batch.create_index("ix_precision_snapshots_source_code", ["source_code"])

    op.create_table(
        "app_kv",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "skip_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern", sa.String(255), nullable=False),
        sa.Column("pattern_type", sa.String(32), nullable=False, server_default="token"),
        sa.Column("source_code", sa.String(64), nullable=False, server_default="tradera"),
        sa.Column("distinct_sellers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("skip_version", sa.String(32), nullable=False, server_default="skip-v1"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pattern", "skip_version", name="uq_skip_pattern_version"),
    )

    op.create_table(
        "watchlist_alias_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("watchlist_item_id", sa.Integer(), sa.ForeignKey("watchlist_items.id"), nullable=True),
        sa.Column("proposed_alias", sa.String(255), nullable=False),
        sa.Column("title_sample", sa.Text(), nullable=False, server_default=""),
        sa.Column("seller_key", sa.String(128), nullable=True),
        sa.Column("distinct_sellers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("needs_human", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("watchlist_alias_proposals")
    op.drop_table("skip_candidates")
    op.drop_table("app_kv")
    with op.batch_alter_table("precision_snapshots") as batch:
        batch.drop_index("ix_precision_snapshots_source_code")
        batch.drop_column("wrong_count")
        batch.drop_column("deal_labeled_count")
        batch.drop_column("identity_labeled_count")
        batch.drop_column("source_code")
    with op.batch_alter_table("decisions") as batch:
        batch.drop_constraint("uq_decisions_callback_query_id", type_="unique")
        for col in (
            "identity_label",
            "deal_label",
            "callback_query_id",
            "passes_hard_gates",
            "gate_failures",
            "match_confidence",
            "matched_alias",
            "scout_arm_id",
            "query_pull_id",
            "source_code",
        ):
            batch.drop_column(col)
    with op.batch_alter_table("price_observations") as batch:
        batch.drop_column("comp_product_id")
        batch.drop_column("fx_as_of")
        batch.drop_column("fx_rate_used")
    with op.batch_alter_table("listing_snapshots") as batch:
        batch.alter_column("shipping_ore", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("price_ore", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("listings") as batch:
        batch.drop_constraint("fk_listings_query_pull", type_="foreignkey")
        batch.drop_constraint("fk_listings_scout_arm", type_="foreignkey")
        for col in (
            "fulfillment",
            "listing_type",
            "scout_arm_id",
            "query_pull_id",
            "extractor_version",
            "matched_alias",
        ):
            batch.drop_column(col)
        batch.alter_column("buyer_fee_ore", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("shipping_ore", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("price_ore", existing_type=sa.Integer(), nullable=False)
    op.drop_table("query_pulls")
    op.drop_table("scout_arms")
    op.drop_table("source_api_calls")
    op.drop_column("sources", "quota_exhausted_until")
