from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

from pokequant.alerts.telegram_bot import send_raw
from pokequant.config import get_settings
from pokequant.jobs.telegram_poll import get_webhook_url
from pokequant.runtime import parse_supervised_ok, supervised_ok_hash, supervised_ok_present


def _ok(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "ok": passed, "detail": detail}


def which_pokequant() -> str:
    return shutil.which("pokequant") or ""


def pokequant_is_venv() -> bool:
    found = which_pokequant()
    if not found:
        return False
    resolved = Path(found).resolve()
    candidates = [
        Path(os.environ.get("HOME", "")) / "Poke" / ".venv" / "bin" / "pokequant",
        Path.cwd() / ".venv" / "bin" / "pokequant",
    ]
    return any(c.exists() and resolved == c.resolve() for c in candidates)


def _parse_tbd_docs() -> list[str]:
    missing = []
    root = Path.cwd()
    risk = (root / "docs" / "RISK_POLICY_v1.md").read_text(encoding="utf-8") if (root / "docs" / "RISK_POLICY_v1.md").exists() else "TBD"
    if "TBD" in risk:
        missing.append("RISK_POLICY_v1 still has TBD")
    charter = (root / "docs" / "PILOT_CHARTER.md").read_text(encoding="utf-8") if (root / "docs" / "PILOT_CHARTER.md").exists() else ""
    if "Pilot dates:\n" in charter or "Pilot dates: \n" in charter or "Pilot dates:" in charter and not any(
        line.split(":", 1)[-1].strip() for line in charter.splitlines() if line.startswith("Pilot dates:")
    ):
        missing.append("PILOT_CHARTER unsigned / dates empty")
    return missing


def run_mini_doctor(*, send_dms: bool = True) -> dict:
    settings = get_settings()
    checks: list[dict] = []

    tz = os.environ.get("TZ", "")
    checks.append(_ok("tz", tz == "Europe/Stockholm" or _os_tz_stockholm(), f"TZ={tz}"))

    deals = settings.deals_bot_token
    ops = settings.telegram_ops_bot_token
    checks.append(_ok("tokens_differ", bool(deals and ops and deals != ops), "Deals token must ≠ Ops token"))

    webhook = ""
    if deals:
        try:
            webhook = get_webhook_url(deals)
        except Exception as exc:  # noqa: BLE001
            webhook = f"error:{exc}"
    checks.append(_ok("deals_webhook_empty", webhook == "", webhook or "empty"))

    sqlite_ok = not (settings.app_env == "production" and settings.database_url.startswith("sqlite"))
    checks.append(_ok("production_sqlite_rejected", sqlite_ok, settings.database_url[:48]))

    checks.append(_ok("which_pokequant_venv", pokequant_is_venv(), which_pokequant()))

    listen = settings.web_listen_host == "127.0.0.1"
    checks.append(_ok("web_listen_127", listen, settings.web_listen_host))

    checks.append(_ok("web_secret_set", settings.secret_key not in {"", "change-me"} or settings.app_env != "production", "SECRET_KEY"))

    try:
        parse_supervised_ok()
        checks.append(_ok("supervised_ok_hash", bool(supervised_ok_hash()), supervised_ok_hash()[:16]))
    except Exception as exc:  # noqa: BLE001
        checks.append(_ok("supervised_ok_hash", False, str(exc)))

    doc_issues = _parse_tbd_docs()
    checks.append(_ok("charter_risk_filled", not doc_issues, "; ".join(doc_issues)))

    pg = _pg_isready()
    checks.append(_ok("postgres_ready", pg, "pg_isready"))

    alembic = _alembic_head()
    checks.append(_ok("alembic_head", alembic, "alembic current"))

    dump_ok, dump_detail = _dump_age_ok()
    checks.append(_ok("pg_dump_age", dump_ok, dump_detail))

    scripts_ok, scripts_detail = _hermes_scripts_only()
    checks.append(_ok("hermes_scripts_dir", scripts_ok, scripts_detail))

    if send_dms:
        dm_ok, dm_detail = _doctor_dms()
        checks.append(_ok("operator_dms", dm_ok, dm_detail))
    else:
        checks.append(_ok("operator_dms", True, "skipped"))

    failed = [c for c in checks if not c["ok"]]
    return {"ok": not failed, "failed": failed, "checks": checks}


def _os_tz_stockholm() -> bool:
    try:
        out = Path("/etc/localtime").resolve().as_posix()
        return "Stockholm" in out
    except OSError:
        return False


def _pg_isready() -> bool:
    exe = shutil.which("pg_isready")
    if not exe:
        return get_settings().app_env != "production"
    return subprocess.call([exe, "-q"]) == 0


def _alembic_head() -> bool:
    try:
        proc = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0 and "0003_grade_catalog" in (proc.stdout + proc.stderr)
    except Exception:  # noqa: BLE001
        return get_settings().app_env != "production"


def _dump_age_ok() -> tuple[bool, str]:
    stamp = Path("data/hermes/last_pg_dump")
    if not stamp.exists():
        return get_settings().app_env != "production", "no dump stamp"
    try:
        ts = datetime.fromisoformat(stamp.read_text(encoding="utf-8").strip())
    except ValueError:
        return False, "bad dump stamp"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    return age_h <= 25, f"{age_h:.1f}h"


def _hermes_scripts_only() -> tuple[bool, str]:
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes" / "profiles" / "pq-ops")
    scripts = home / "scripts"
    if not scripts.exists():
        return get_settings().app_env != "production", f"missing {scripts}"
    return True, str(scripts)


def _doctor_dms() -> tuple[bool, str]:
    settings = get_settings()
    deals_users = settings.deals_allowed_user_ids
    ops_users = settings.ops_allowed_user_ids
    users = sorted(set(deals_users + ops_users))
    if len(users) < 2:
        return False, "need both operator user ids"
    errors = []
    for token, label in (
        (settings.deals_bot_token, "deals"),
        (settings.telegram_ops_bot_token, "ops"),
    ):
        if not token:
            errors.append(f"{label} token missing")
            continue
        for uid in users:
            try:
                resp = send_raw(token, uid, f"mini-doctor {label} test DM")
                if resp.status_code == 403:
                    errors.append(f"403 {label}→{uid} (operator must /start)")
                elif resp.status_code >= 400:
                    errors.append(f"{resp.status_code} {label}→{uid}")
            except httpx.HTTPError as exc:
                errors.append(f"{label}→{uid}: {exc}")
    return (not errors, "; ".join(errors) or "dms ok")
