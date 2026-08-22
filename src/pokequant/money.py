"""Money helpers: store SEK/EUR as integer minor units (öre / cents)."""

from __future__ import annotations

from datetime import date, datetime, timezone


def to_ore(amount: float | int | str, *, currency: str = "SEK") -> int:
    """Convert major units to minor units."""
    value = float(amount)
    return int(round(value * 100))


def from_ore(ore: int) -> float:
    return ore / 100.0


def format_sek(ore: int | None) -> str:
    if ore is None:
        return "—"
    return f"{from_ore(ore):,.2f} SEK".replace(",", " ")


def eur_to_sek_ore(eur_cents: int, sek_per_eur: float = 11.0) -> int:
    """Simple FX helper; pass a dated rate in production."""
    eur = eur_cents / 100.0
    return to_ore(eur * sek_per_eur, currency="SEK")


def usd_to_sek_ore(usd_cents: int, sek_per_usd: float) -> int:
    usd = usd_cents / 100.0
    return to_ore(usd * sek_per_usd, currency="SEK")


def parse_fx_as_of(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        d = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def fx_age_days(fx_as_of: datetime | None, *, now: datetime | None = None) -> float | None:
    if fx_as_of is None:
        return None
    now = now or datetime.now(timezone.utc)
    if fx_as_of.tzinfo is None:
        fx_as_of = fx_as_of.replace(tzinfo=timezone.utc)
    return (now - fx_as_of).total_seconds() / 86400
