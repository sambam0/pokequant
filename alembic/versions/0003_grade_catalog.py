"""Grade catalog, dual buy thesis, valuation thesis fields.

Revision ID: 0003_grade_catalog
Revises: 0002_hermes_mini
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_grade_catalog"
down_revision: Union[str, None] = "0002_hermes_mini"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grade_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pricecharting_id", sa.String(64), nullable=False),
        sa.Column("sport", sa.String(16), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("console_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("genre", sa.String(128), nullable=False, server_default=""),
        sa.Column("collector_number", sa.String(32), nullable=False, server_default=""),
        sa.Column("release_date", sa.String(32), nullable=False, server_default=""),
        sa.Column("raw_usd_cents", sa.Integer(), nullable=True),
        sa.Column("psa8_usd_cents", sa.Integer(), nullable=True),
        sa.Column("psa9_usd_cents", sa.Integer(), nullable=True),
        sa.Column("psa10_usd_cents", sa.Integer(), nullable=True),
        sa.Column("bgs10_usd_cents", sa.Integer(), nullable=True),
        sa.Column("black_label_usd_cents", sa.Integer(), nullable=True),
        sa.Column("raw_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("psa8_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("psa9_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("psa10_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bgs10_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("black_label_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gem_rate_psa10", sa.Float(), nullable=False, server_default="0"),
        sa.Column("psa9_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("psa8_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("miss_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prior_bucket", sa.String(32), nullable=False, server_default=""),
        sa.Column("damage_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("liquidity_flag", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("gem_rate_override", sa.Float(), nullable=True),
        sa.Column("tier_override", sa.String(32), nullable=True),
        sa.Column("spread_psa10", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ev_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upside_if_10_mult", sa.Float(), nullable=False, server_default="0"),
        sa.Column("grade_cost_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_raw_buy_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("psa9_floor_profit_ore", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(32), nullable=True),
        sa.Column("drop_reason", sa.String(64), nullable=False, server_default=""),
        sa.Column("prices_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fx_rate_used", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pricecharting_id", name="uq_grade_catalog_pc_id"),
    )
    op.create_index("ix_grade_catalog_pricecharting_id", "grade_catalog", ["pricecharting_id"])
    op.create_index("ix_grade_catalog_sport", "grade_catalog", ["sport"])
    op.create_index("ix_grade_catalog_product_name", "grade_catalog", ["product_name"])
    op.create_index("ix_grade_catalog_tier", "grade_catalog", ["tier"])

    with op.batch_alter_table("watchlist_items") as batch:
        batch.add_column(sa.Column("buy_thesis", sa.String(32), nullable=False, server_default="flip_raw"))
        batch.add_column(sa.Column("grade_tier", sa.String(32), nullable=True))
        batch.add_column(sa.Column("grade_catalog_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_watchlist_grade_catalog", "grade_catalog", ["grade_catalog_id"], ["id"])

    with op.batch_alter_table("valuations") as batch:
        batch.add_column(sa.Column("passed_thesis", sa.String(32), nullable=False, server_default=""))
        batch.add_column(sa.Column("grade_ev_ore", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("valuations") as batch:
        batch.drop_column("grade_ev_ore")
        batch.drop_column("passed_thesis")
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_constraint("fk_watchlist_grade_catalog", type_="foreignkey")
        batch.drop_column("grade_catalog_id")
        batch.drop_column("grade_tier")
        batch.drop_column("buy_thesis")
    op.drop_index("ix_grade_catalog_tier", table_name="grade_catalog")
    op.drop_index("ix_grade_catalog_product_name", table_name="grade_catalog")
    op.drop_index("ix_grade_catalog_sport", table_name="grade_catalog")
    op.drop_index("ix_grade_catalog_pricecharting_id", table_name="grade_catalog")
    op.drop_table("grade_catalog")
