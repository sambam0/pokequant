# Expansion policy

Do not grow beyond the frozen ~100-card watchlist until:

```bash
pokequant precision
# gate_passed: true
# labeled >= 40, really_good_rate >= 0.50, false_match_rate <= 0.10
```

When the gate passes:

```bash
pokequant expansion
```

## Allowed next steps (one at a time)

1. Add more watchlist cards in batches of ~25; re-measure precision.
2. eBay Browse for active listings (sold history only if Marketplace Insights approved).
3. Licensed retailer / affiliate feeds.
4. Manual Blocket / Facebook / Vinted quick-add only (no scraping).

## Never without written permission

- Blocket systematic robots/indexing
- Facebook Playwright / proxy automation
- Cardmarket page scraping (use sanctioned downloads / TCGdex)
