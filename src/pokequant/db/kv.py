from __future__ import annotations

from sqlalchemy.orm import Session

from pokequant.db.models import AppKv


def kv_get(session: Session, key: str, default: str = "") -> str:
    row = session.get(AppKv, key)
    return row.value if row else default


def kv_set(session: Session, key: str, value: str) -> AppKv:
    row = session.get(AppKv, key)
    if row is None:
        row = AppKv(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    return row
