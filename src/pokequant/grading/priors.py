from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_VINTAGE_SET_TOKENS = (
    "base set",
    "jungle",
    "fossil",
    "team rocket",
    "gym heroes",
    "gym challenge",
    "neo genesis",
    "neo discovery",
    "neo revelation",
    "neo destiny",
    "wotc",
    "wizards",
    "1st edition",
    "first edition",
    "shadowless",
)

_HOLO_TOKENS = ("holo", "holofoil", "holofoil", "reverse holo")
_TEXTURED_TOKENS = (
    "alt art",
    "special illustration",
    "illustration rare",
    "sar",
    "sir",
    "textured",
    "rainbow rare",
    "gold star",
    "on-card auto",
    "autograph",
)


@dataclass(frozen=True)
class GemPrior:
    psa10: float
    psa9: float
    psa8: float
    miss: float
    damage: bool
    bucket: str

    def with_psa10(self, rate: float) -> GemPrior:
        rate = min(max(rate, 0.01), 0.60)
        rest = max(1.0 - rate, 0.01)
        scale = rest / max(self.psa9 + self.psa8 + self.miss, 0.01)
        return GemPrior(
            psa10=rate,
            psa9=self.psa9 * scale,
            psa8=self.psa8 * scale,
            miss=self.miss * scale,
            damage=self.damage,
            bucket=self.bucket,
        )


def _hay(product_name: str, console_name: str, genre: str) -> str:
    return f"{product_name} {console_name} {genre}".lower()


def _release_year(release_date: str, hay: str) -> int | None:
    if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
        year = int(release_date[:4])
        if 1980 <= year <= 2035:
            return year
    match = _YEAR_RE.search(hay)
    return int(match.group(0)) if match else None


def gem_prior(
    *,
    sport: str,
    product_name: str,
    console_name: str = "",
    genre: str = "",
    release_date: str = "",
    gem_rate_override: float | None = None,
) -> GemPrior:
    hay = _hay(product_name, console_name, genre)
    year = _release_year(release_date, hay)
    vintage_set = any(token in hay for token in _VINTAGE_SET_TOKENS)
    vintage_year = year is not None and year < 2004
    hockey_90s = sport == "hockey" and year is not None and 1989 <= year <= 1999
    holo = any(token in hay for token in _HOLO_TOKENS)
    textured = any(token in hay for token in _TEXTURED_TOKENS)

    if ((vintage_set or vintage_year) and holo) or hockey_90s:
        prior = GemPrior(0.05, 0.25, 0.35, 0.35, True, "vintage_holo")
    elif vintage_set or vintage_year:
        prior = GemPrior(0.10, 0.30, 0.30, 0.30, True, "vintage")
    elif textured:
        prior = GemPrior(0.12, 0.35, 0.28, 0.25, False, "textured")
    elif holo:
        prior = GemPrior(0.16, 0.38, 0.26, 0.20, False, "modern_holo")
    else:
        prior = GemPrior(0.22, 0.40, 0.23, 0.15, False, "modern_clean")

    if gem_rate_override is not None:
        return prior.with_psa10(gem_rate_override)
    return prior
