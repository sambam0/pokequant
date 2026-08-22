from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.config import get_settings
from pokequant.db.models import AlertDelivery, Decision, Listing, Valuation
from pokequant.money import format_sek
from pokequant.runtime import deals_send_allowed
from pokequant.services.decisions import record_decision
from pokequant.workflow.states import transition_listing

logger = logging.getLogger(__name__)

ALERT_BODY_MAX = 3900

CALLBACK_MAP = {
    "w": ("skip", "wrong", "n/a", "wrong_identity", True),
    "j": ("skip", "correct", "junk", None, False),
    "m": ("skip", "correct", "maybe", "borderline", False),
    "g": ("skip", "correct", "really_good", None, False),
    "b": ("buy", "correct", "really_good", None, False),
    "t": ("too_late", "correct", "maybe", "too_late", False),
}


def format_alert(listing: Listing, valuation: Valuation, watch_name: str) -> str:
    body = (
        f"Watchlist hit: {watch_name}\n"
        f"{listing.title}\n"
        f"Tradera landed: {format_sek(valuation.landed_cost_ore)}\n"
        f"External ref (eBay/PC): {format_sek(valuation.market_value_p50_ore)}\n"
        f"Max buy (< external): {format_sek(valuation.max_buy_ore)}\n"
        f"Cheaper than eBay/PC by: {(valuation.discount_bps or 0) / 100:.1f}%\n"
        f"Identity: {(valuation.identity_confidence or 0):.0%}\n"
        f"Thesis: {valuation.passed_thesis or 'none'}\n"
        f"Gates: {'PASS' if valuation.passes_hard_gates else 'FAIL ' + (valuation.gate_failures or '')}\n"
        f"{valuation.explanation or ''}\n"
        f"{listing.url}"
    )
    if len(body) > ALERT_BODY_MAX:
        body = body[: ALERT_BODY_MAX - 1] + "…"
    return body


def _inline_keyboard(listing_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Wrong card", "callback_data": f"w:{listing_id}"},
                {"text": "Junk", "callback_data": f"j:{listing_id}"},
            ],
            [
                {"text": "Maybe", "callback_data": f"m:{listing_id}"},
                {"text": "Good (would buy)", "callback_data": f"g:{listing_id}"},
            ],
            [
                {"text": "Bought", "callback_data": f"b:{listing_id}"},
                {"text": "Too late", "callback_data": f"t:{listing_id}"},
            ],
        ]
    }


def deliver_telegram_alert(
    session: Session,
    listing: Listing,
    valuation: Valuation,
    watch_name: str,
    *,
    dry_run: bool = False,
) -> AlertDelivery | None:
    settings = get_settings()
    if not dry_run and not deals_send_allowed():
        logger.info("Deals send blocked by pause state")
        return None
    text = format_alert(listing, valuation, watch_name)
    external_id = None
    token = settings.deals_bot_token
    chat_id = settings.deals_chat_id
    if dry_run or not token or not chat_id:
        logger.info("Telegram dry-run alert:\n%s", text)
    else:
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": _inline_keyboard(listing.id),
        }
        if settings.telegram_deals_thread_id:
            payload["message_thread_id"] = int(settings.telegram_deals_thread_id)
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        external_id = str(resp.json().get("result", {}).get("message_id", ""))

    if listing.workflow_state == "scored":
        listing.workflow_state = transition_listing(listing.workflow_state, "alerted")
    delivery = AlertDelivery(
        listing_id=listing.id,
        valuation_id=valuation.id,
        channel="telegram",
        external_message_id=external_id,
        payload_summary=text[:1000],
        delivered_at=datetime.now(timezone.utc),
    )
    session.add(delivery)
    audit(session, action="alert.telegram", entity_type="listing", entity_id=listing.id, details=watch_name)
    return delivery


def apply_callback(
    session: Session,
    callback_data: str,
    reviewer: str = "domain",
    *,
    callback_query_id: str | None = None,
) -> Decision | None:
    action, _, listing_id_s = callback_data.partition(":")
    try:
        listing_id = int(listing_id_s)
    except ValueError:
        return None
    listing = session.get(Listing, listing_id)
    if listing is None:
        return None
    if callback_query_id:
        existing = session.query(Decision).filter_by(callback_query_id=callback_query_id).one_or_none()
        if existing is not None:
            return existing
    alert = (
        session.query(AlertDelivery)
        .filter_by(listing_id=listing.id)
        .order_by(AlertDelivery.id.desc())
        .first()
    )
    valuation = None
    if alert and alert.valuation_id:
        valuation = session.get(Valuation, alert.valuation_id)
    mapped = CALLBACK_MAP.get(action)
    if mapped is None:
        # Legacy buy:/maybe:/junk:/wrong:
        legacy = {
            "buy": ("buy", "correct", "really_good", None, False),
            "maybe": ("skip", "correct", "maybe", "borderline", False),
            "junk": ("skip", "correct", "junk", None, False),
            "wrong": ("skip", "wrong", "n/a", "wrong_identity", True),
        }
        mapped = legacy.get(action)
    if mapped is None:
        return None
    intent, identity, deal, reason, false_match = mapped
    return record_decision(
        session,
        listing,
        intent=intent,
        identity_label=identity,
        deal_label=deal,
        quality_label=deal,
        reviewer=reviewer,
        reason_code=reason,
        valuation=valuation,
        alerted_at=alert.delivered_at if alert else None,
        false_match=false_match,
        callback_query_id=callback_query_id,
    )


def answer_callback_query(callback_query_id: str, *, text: str = "Recorded") -> None:
    settings = get_settings()
    token = settings.deals_bot_token
    if not token or not callback_query_id:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=15.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("answerCallbackQuery failed (old query may 400): %s", exc)


def send_raw(token: str, chat_id: str, text: str, *, thread_id: str = "") -> httpx.Response:
    payload: dict = {"chat_id": chat_id, "text": text[:3900]}
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    return httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=30.0,
    )
