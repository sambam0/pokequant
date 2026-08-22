from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pokequant.config import get_settings


def assert_production_database(url: str, app_env: str) -> None:
    if app_env == "production" and url.startswith("sqlite"):
        raise RuntimeError("APP_ENV=production rejects sqlite DATABASE_URL")


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    assert_production_database(settings.database_url, settings.app_env)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def __getattr__(name: str):
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
