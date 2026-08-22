from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./pokequant.db"
    tradera_app_id: str = ""
    tradera_app_key: str = ""
    tradera_daily_call_budget: int = 100
    tradera_tick_minutes: int = 120
    tradera_hydrate_reserve: int = 2
    tradera_category_id: str = ""
    tradera_page_size: int = 50
    extractor_version: str = "tradera-rest-v4-2026-08"

    # Deals bot (PokeQuant). Legacy TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID still work.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_deals_bot_token: str = ""
    telegram_deals_chat_id: str = ""
    telegram_deals_thread_id: str = ""
    telegram_deals_allowed_user_ids: str = ""

    # Ops bot (Hermes pq-ops). Must differ from the Deals token.
    telegram_ops_bot_token: str = ""
    telegram_ops_chat_id: str = ""
    telegram_ops_thread_id: str = ""
    telegram_ops_allowed_user_ids: str = ""
    telegram_allowed_users: str = ""

    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_marketplace_id: str = "EBAY_US"
    usd_sek_rate: float = 10.5
    eur_sek_rate: float = 11.0
    fx_as_of: str = ""  # YYYY-MM-DD; scoring rejects when older than fx_max_age_days
    fx_max_age_days: int = 7
    comps_stale_hours: int = 36

    tcgdex_base_url: str = "https://api.tcgdex.net/v2"
    cardmarket_download_dir: str = "./data/cardmarket"
    pricecharting_api_token: str = ""
    secret_key: str = "change-me"
    app_env: str = "development"
    log_level: str = "INFO"
    model_version: str = "valuation-v1"
    fee_schedule_version: str = "tradera-business-2026"
    precision_min_labeled: int = 40
    precision_min_really_good_rate: float = 0.50
    precision_max_false_match_rate: float = 0.10
    review_wip_limit: int = 20
    alert_daily_cap: int = 10
    alert_realert_hours: int = 12
    material_drop_bps: int = 500
    skip_version: str = "skip-v1"
    supervised_ok_path: str = "data/hermes/SUPERVISED_OK"
    hermes_state_path: str = "data/hermes/state.json"
    facebook_permission_path: str = "data/hermes/FACEBOOK_WRITTEN_PERMISSION"
    poke_home: str = Field(default="")
    web_listen_host: str = "127.0.0.1"

    # Sweden → PSA grade-upside costs (öre / USD cents). Tune without code changes.
    psa_fee_under_500_usd_cents: int = 2500
    psa_fee_under_2500_usd_cents: int = 5000
    psa_fee_over_2500_usd_cents: int = 7500
    sweden_to_psa_ship_ore: int = 25000
    psa_return_ship_ore: int = 20000
    grade_time_reserve_bps: int = 200
    grade_sell_fee_bps: int = 1300
    grade_min_profit_ore: int = 5000
    grade_min_upside_mult: float = 1.15

    @property
    def deals_bot_token(self) -> str:
        return self.telegram_deals_bot_token or self.telegram_bot_token

    @property
    def deals_chat_id(self) -> str:
        return self.telegram_deals_chat_id or self.telegram_chat_id

    @property
    def deals_allowed_user_ids(self) -> list[str]:
        raw = self.telegram_deals_allowed_user_ids or self.telegram_allowed_users
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def ops_allowed_user_ids(self) -> list[str]:
        raw = self.telegram_ops_allowed_user_ids or self.telegram_allowed_users
        return [x.strip() for x in raw.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
