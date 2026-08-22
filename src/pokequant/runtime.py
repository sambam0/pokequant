from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pokequant.config import get_settings

VALID_STATES = frozenset(
    {"unsupervised", "running", "paused", "paused_fb", "throttle_alerts", "quota_exhausted"}
)
PAUSE_WRITERS = frozenset({"cli", "telegram", "watchdog", "scan"})


def _state_path() -> Path:
    return Path(get_settings().hermes_state_path)


def _supervised_path() -> Path:
    return Path(get_settings().supervised_ok_path)


def read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"status": "unsupervised", "updated_at": "", "reason": "missing state.json"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "unsupervised", "updated_at": "", "reason": "corrupt state.json"}
    status = str(data.get("status") or "unsupervised")
    if status not in VALID_STATES:
        status = "unsupervised"
    data["status"] = status
    return data


def write_state(status: str, *, reason: str = "", actor: str = "cli") -> dict:
    if status not in VALID_STATES:
        raise ValueError(f"invalid pause status {status!r}")
    if actor not in PAUSE_WRITERS and actor != "system":
        raise ValueError(f"invalid pause actor {actor!r}")
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "actor": actor,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def supervised_ok_present() -> bool:
    path = _supervised_path()
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").strip()
    return bool(text) and not text.startswith("#")


def supervised_ok_hash() -> str:
    path = _supervised_path()
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8").strip().encode("utf-8")
    if not raw:
        return ""
    return hashlib.sha256(raw).hexdigest()


def parse_supervised_ok() -> dict:
    """SUPERVISED_OK must contain charter_date= and operators=Name1,Name2 (hashed as file)."""
    path = _supervised_path()
    if not path.exists():
        raise RuntimeError("SUPERVISED_OK missing")
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    if not fields.get("charter_date"):
        raise RuntimeError("SUPERVISED_OK missing charter_date")
    operators = [x.strip() for x in fields.get("operators", "").split(",") if x.strip()]
    if len(operators) < 2:
        raise RuntimeError("SUPERVISED_OK requires both operator names")
    fields["hash"] = supervised_ok_hash()
    return fields


def effective_status() -> str:
    if not supervised_ok_present():
        return "unsupervised"
    try:
        parse_supervised_ok()
    except RuntimeError:
        return "unsupervised"
    return read_state().get("status") or "unsupervised"


def ingest_allowed(status: str | None = None) -> bool:
    status = status or effective_status()
    return status in {"running", "throttle_alerts", "quota_exhausted", "paused_fb"}


def deals_send_allowed(status: str | None = None) -> bool:
    status = status or effective_status()
    return status == "running"


def scan_allowed(status: str | None = None) -> bool:
    status = status or effective_status()
    return status in {"running", "throttle_alerts"}


def pause(*, reason: str = "", actor: str = "cli") -> dict:
    return write_state("paused", reason=reason or "manual pause", actor=actor)


def resume(*, actor: str = "cli") -> dict:
    if not supervised_ok_present():
        return write_state("unsupervised", reason="SUPERVISED_OK missing", actor=actor)
    return write_state("running", reason="manual resume", actor=actor)
