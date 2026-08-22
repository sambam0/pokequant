# Risk Policy v1

Version: 1.0  
Currency: SEK  
Applies to: frozen ~100-card watchlist pilot

Replace the placeholder numbers with values appropriate to your cash flow before the first purchase.

## Capital limits

| Limit | Value (SEK) | Notes |
| --- | --- | --- |
| Total pilot purchasing budget | TBD | Hard ceiling |
| Max capital deployed per week | TBD | |
| Max landed cost per item | TBD | |
| Max landed cost per lot | TBD | Lots are out of scanner scope unless jointly approved |
| Max exposure per seller | TBD | Default discussion starter: ≤20% of pilot capital |
| Joint-approval threshold | TBD | Above this, both operators must approve |
| Pilot stop-loss | TBD | Pause buying if realized + marked losses exceed this |

## Capital buckets

| Bucket | Cap of pilot capital | Use |
| --- | --- | --- |
| Core | ≤70% | Liquid watchlist cards with strong comps |
| Opportunistic | ≤20% | Larger discount, more condition/liquidity uncertainty |
| Experimental | ≤10% | Sealed/new sets/lots; learning only |

## Profit and timing floors

| Rule | Value |
| --- | --- |
| Minimum conservative expected net profit | TBD SEK |
| Minimum expected profit per operator hour | TBD SEK |
| Maximum expected days to sale | TBD |
| Minimum discount vs EU reference after costs | TBD % |
| Returns/fraud reserve | TBD % of expected proceeds |
| Condition-downgrade reserve | TBD % |
| Stale-inventory reserve | TBD % |

## Hard gates (no purchase unless exception logged)

1. Listing matches a frozen watchlist identity with acceptable confidence.
2. `max_buy_price >= landed_cost`.
3. Expected profit exceeds the SEK floor at the conservative case.
4. Downside loss is within the per-item limit.
5. Category/seller/bucket exposure remains under caps.
6. Condition floor from photos is met, or labeled `need_photos` instead of buy.
7. Authenticity uncertainty ⇒ no purchase unless jointly approved.

## Exception log

Every override needs: linked opportunity/purchase ID, who approved, why, financial impact, and preventive follow-up.
