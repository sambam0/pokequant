from __future__ import annotations

import logging
import time

import httpx
from sqlalchemy.orm import Session

from pokequant.alerts.telegram_bot import answer_callback_query, apply_callback
from pokequant.config import get_settings
from pokequant.db.kv import kv_get, kv_set

logger = logging.getLogger(__name__)

OFFSET_KEY = "telegram_update_offset"


def delete_webhook(token: str) -> None:
    """Drop the webhook without dropping pending updates (keep callbacks from downtime)."""
    httpx.get(
        f"https://api.telegram.org/bot{token}/deleteWebhook",
        params={"drop_pending_updates": "false"},
        timeout=30.0,
    ).raise_for_status()


def get_webhook_url(token: str) -> str:
    resp = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=30.0)
    resp.raise_for_status()
    return str(resp.json().get("result", {}).get("url") or "")


def reviewer_from_user(user: dict | None) -> str:
    if not user:
        return "telegram"
    uid = str(user.get("id") or "")
    name = user.get("username") or user.get("first_name") or uid
    return f"{name}:{uid}" if uid else str(name)


def user_allowed(user_id: str) -> bool:
    allowed = get_settings().deals_allowed_user_ids
    if not allowed:
        return True
    return str(user_id) in allowed


def handle_update(session: Session, update: dict) -> None:
    callback = update.get("callback_query") or {}
    if not callback:
        return
    from_user = callback.get("from") or {}
    user_id = str(from_user.get("id") or "")
    cqid = str(callback.get("id") or "")
    data = str(callback.get("data") or "")
    if not user_allowed(user_id):
        answer_callback_query(cqid, text="Not allowed")
        return
    apply_callback(session, data, reviewer=reviewer_from_user(from_user), callback_query_id=cqid or None)
    session.commit()
    answer_callback_query(cqid)


def poll_once(session: Session, *, token: str | None = None, timeout: int = 25) -> int:
    settings = get_settings()
    token = token or settings.deals_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_DEALS_BOT_TOKEN / TELEGRAM_BOT_TOKEN missing")
    offset_raw = kv_get(session, OFFSET_KEY, "0")
    try:
        offset = int(offset_raw or "0")
    except ValueError:
        offset = 0
    resp = httpx.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"offset": offset + 1 if offset else 0, "timeout": timeout, "allowed_updates": ["callback_query"]},
        timeout=timeout + 10,
    )
    if resp.status_code == 409:
        raise RuntimeError("getUpdates 409 — another poller or leftover getUpdates in a browser")
    resp.raise_for_status()
    updates = resp.json().get("result") or []
    last_id = offset
    for update in updates:
        last_id = max(last_id, int(update.get("update_id") or 0))
        handle_update(session, update)
        kv_set(session, OFFSET_KEY, str(last_id))
        session.commit()
    return len(updates)


def run_poll_loop(*, sleep_s: float = 1.0) -> None:
    from pokequant.db.session import get_session_factory

    settings = get_settings()
    token = settings.deals_bot_token
    if not token:
        raise RuntimeError("Deals bot token missing")
    delete_webhook(token)
    factory = get_session_factory()
    logger.info("telegram-poll started")
    while True:
        session = factory()
        try:
            n = poll_once(session, token=token)
            if n == 0:
                time.sleep(sleep_s)
        except Exception:
            logger.exception("telegram-poll iteration failed")
            time.sleep(5)
        finally:
            session.close()
