# Workflow Pilot (Manual Labels Before Automation)

Run this before trusting the bot. Use only watchlist cards.

## Goal

Produce labeled examples so the scanner can be judged by precision:

- `really_good` — underpriced + quality good enough that brother would buy
- `maybe` — borderline price/photos/timing
- `junk` — wrong card, bad quality, or not cheap after costs

## Process

1. Load the frozen watchlist.
2. Manually find 20–50 real marketplace opportunities for those cards.
3. Log each opportunity in [`data/pilot/opportunities_template.csv`](../data/pilot/opportunities_template.csv).
4. Cap the expert-review queue at 20 open items.
5. Review high-velocity leads within 2 hours; ordinary within 1 business day.
6. Purchase only a safe subset that passes Risk Policy v1.
7. Receive, inspect, and record outcomes for any purchases.

## SLAs

| Event | SLA |
| --- | --- |
| High-velocity review | ≤ 2 hours |
| Ordinary review | ≤ 1 business day |
| Evidence request | ≤ 4 working hours |
| Close unanswered evidence | 48 hours unless strategic |
| Parcel receiving | same day |
| Inspection | ≤ 48 hours after receipt |

## Success for this pilot stage

- [ ] ≥20 complete decision records on watchlist cards
- [ ] Labels use `really_good` / `maybe` / `junk`
- [ ] Reason codes populated for skips/rejects
- [ ] Several purchases have full acquisition → inventory trails if capital allows
- [ ] Ready to turn on Tradera alerts against the same frozen list
