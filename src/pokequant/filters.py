from __future__ import annotations

from dataclasses import dataclass

from pokequant.config import get_settings

# Never auto-promote these as skip patterns (lots are identity noise, not a shippable skip).
FORBIDDEN_SKIP_TOKENS = frozenset({"lott", "samling", "bulk", "lot"})


@dataclass(frozen=True)
class Drop:
    reason: str


@dataclass(frozen=True)
class Keep:
    pass


DropOrKeep = Drop | Keep


def should_drop(title: str, source_code: str, skip_version: str | None = None) -> DropOrKeep:
    """Single skip layer at ingest. Hermes must not copy regexes into SKILL.md."""
    del skip_version
    hay = (title or "").lower()
    if source_code not in {"tradera"}:
        if source_code == "facebook":
            return Drop("facebook_v15_blocked")
        return Drop("source_not_v1")
    if not hay.strip():
        return Drop("empty_title")
    return Keep()


def is_forbidden_skip_token(token: str) -> bool:
    return token.strip().lower() in FORBIDDEN_SKIP_TOKENS


def skip_version() -> str:
    return get_settings().skip_version
