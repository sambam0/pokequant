# Frozen 100-Card Watchlist Guide

The scanner monitors only cards on this list until the precision gate passes.

## Rules

1. Brother curates ~100 exact cards he knows well.
2. The list is frozen. Replace only for identity errors (wrong set/number), not weekly taste changes.
3. Prefer liquid, identifiable singles over vague names or lots.
4. Priority `core` cards get Tradera search budget first.

## Required fields per card

| Field | Example |
| --- | --- |
| watch_id | WATCH-001 |
| name | Charizard |
| set_code | base1 |
| set_name | Base Set |
| collector_number | 4 |
| language | en |
| variant | holo |
| tcgdex_id | base1-4 |
| search_aliases | charizard 4/102;charizard holo base |
| condition_floor | LP |
| priority | core |
| min_discount_bps | 2500 (25% under EU reference after costs) |
| max_buy_ore | optional hard ceiling in öre |
| reference_source | cardmarket |
| notes | |

## Templates

- CSV template: [`data/watchlist/watchlist_template.csv`](../data/watchlist/watchlist_template.csv)
- Import into the app with: `pokequant watchlist import data/watchlist/watchlist.csv`

## Acceptance for Phase A

- [ ] ~100 rows with exact identity fields
- [ ] Aliases cover Swedish/English misspellings brother expects
- [ ] Condition floors and discount/max-buy rules filled
- [ ] List marked frozen (`frozen_at` set in app/settings)
