from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pokequant.alerts.telegram_bot import send_raw
from pokequant.config import get_settings
from pokequant.jobs.doctor import _dump_age_ok, _pg_isready
from pokequant.runtime import effective_status


def _pgrep(pattern: str) -> bool:
    return subprocess.call(["pgrep", "-f", pattern], stdout=subprocess.DEVNULL) == 0


def run_watchdog() -> dict:
    settings = get_settings()
    failures: list[str] = []
    if not _pg_isready():
        failures.append("postgres down")
    if not _pgrep("telegram-poll"):
        failures.append("telegram-poll not running")
    if not _pgrep("hermes") and settings.app_env == "production":
        failures.append("hermes gateway not running")
    hb = Path("data/hermes/heartbeat")
    if hb.exists():
        try:
            ts = datetime.fromisoformat(hb.read_text(encoding="utf-8").strip())
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age > 6:
                failures.append(f"heartbeat stale {age:.1f}h")
        except ValueError:
            failures.append("heartbeat unreadable")
    else:
        failures.append("heartbeat missing")
    usage = shutil.disk_usage(str(Path.cwd()))
    pct = 100 * (1 - usage.free / usage.total)
    if pct > 90:
        failures.append(f"disk {pct:.0f}%")
    dump_ok, dump_detail = _dump_age_ok()
    if not dump_ok:
        failures.append(f"pg_dump {dump_detail}")
    status = effective_status()
    report = {"ok": not failures, "failures": failures, "state": status}
    if failures:
        text = "WATCHDOG FAIL\n" + "\n".join(failures) + f"\nstate={status}"
        _page(settings, text)
    return report


def _page(settings, text: str) -> None:
    token = settings.telegram_ops_bot_token or settings.deals_bot_token
    if not token:
        return
    if settings.telegram_ops_chat_id:
        try:
            send_raw(token, settings.telegram_ops_chat_id, text, thread_id=settings.telegram_ops_thread_id)
        except Exception:
            pass
    for uid in settings.ops_allowed_user_ids or settings.deals_allowed_user_ids:
        try:
            resp = send_raw(token, uid, text)
            if resp.status_code == 403:
                other = settings.deals_bot_token if token != settings.deals_bot_token else settings.telegram_ops_bot_token
                if other:
                    send_raw(other, uid, text)
        except Exception:
            pass
