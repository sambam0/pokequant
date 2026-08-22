from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from pokequant.db.models import WatchlistItem


@dataclass
class MatchResult:
    watchlist_item: WatchlistItem
    confidence: float
    matched_alias: str


def _aliases(item: WatchlistItem) -> list[str]:
    parts = [item.name, f"{item.name} {item.collector_number}", f"{item.name} {item.set_name}"]
    if item.search_aliases:
        parts.extend(a.strip() for a in item.search_aliases.split(";") if a.strip())
    return [p.lower() for p in parts if p]


def match_title_to_watchlist(title: str, items: list[WatchlistItem]) -> MatchResult | None:
    """Conservative fuzzy match: require collector number or strong alias hit."""
    hay = title.lower()
    best: MatchResult | None = None

    for item in items:
        if not item.active:
            continue
        number = (item.collector_number or "").lower()
        number_hit = bool(number) and (
            number in hay
            or f"{number}/" in hay
            or f"/{number}" in hay
            or f" {number} " in f" {hay} "
        )
        alias_score = 0.0
        matched_alias = ""
        for alias in _aliases(item):
            score = fuzz.partial_ratio(alias, hay) / 100.0
            if score > alias_score:
                alias_score = score
                matched_alias = alias

        # Lots: card name alone without number is low confidence.
        if "lott" in hay or "lot " in hay or "bulk" in hay or "samling" in hay:
            if not number_hit:
                continue
            confidence = min(0.7, alias_score)
        elif number_hit and alias_score >= 0.7:
            confidence = min(0.95, 0.75 + alias_score * 0.2)
        elif number_hit:
            confidence = 0.8
        elif alias_score >= 0.92 and item.name.lower() in hay:
            confidence = 0.72
        else:
            continue

        if best is None or confidence > best.confidence:
            best = MatchResult(watchlist_item=item, confidence=confidence, matched_alias=matched_alias)

    return best
