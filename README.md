# PokeQuant

Human-in-the-loop watchlist deal scanner and inventory OS for a two-person Swedish Pokémon reselling pilot.

**Core loop:** brother freezes ~100 cards → bot scans Tradera for those only → Telegram/web review → label `really_good` / `maybe` / `junk` → expand only after **50%+ really_good** on ≥40 labeled alerts.

## Buy rule (comps)

For each Tradera hit:

1. Build **Tradera landed cost** = price + shipping (+ buyer fees).
2. Compare to **eBay** active ask (incl. shipping when available) and **PriceCharting** ungraded guide, converted to SEK.
3. Alert / pass only if Tradera landed is **cheaper** than the cheaper of those external comps.
4. If Tradera is equal/more expensive → reject (`landed_not_cheaper_than_external`).

Brother still confirms condition/quality before buying.

## Quick start

```bash
cd /Users/samuelantoncich/Poke
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Fill credentials — see docs/CREDENTIALS_SETUP.md

pokequant init-db
pokequant watchlist import data/watchlist/watchlist_template.csv
pokequant sync-comps           # eBay + PriceCharting
pokequant scan --sync-comps    # Tradera scan + score vs external comps
pokequant precision
uvicorn pokequant.web.app:app --reload
```

Open http://127.0.0.1:8000

## Docs

- [Credentials setup](docs/CREDENTIALS_SETUP.md) ← Tradera, Telegram, eBay, PriceCharting
- [Pilot charter](docs/PILOT_CHARTER.md)
- [Risk policy v1](docs/RISK_POLICY_v1.md)
- [Accounting decision sheet](docs/ACCOUNTING_DECISION_SHEET.md)
- [Watchlist guide](docs/WATCHLIST_GUIDE.md)
- [Workflow pilot](docs/WORKFLOW_PILOT.md)
- [Phase A playbook](PHASE_A_PLAYBOOK.md)

## CLI

| Command | Purpose |
| --- | --- |
| `pokequant init-db` | Create tables |
| `pokequant watchlist import PATH` | Import/freeze watchlist CSV |
| `pokequant watchlist list` | Show active cards |
| `pokequant sync-comps` | Fetch eBay + PriceCharting comps (buy gate) |
| `pokequant sync-tcgdex` | Optional EU Cardmarket-via-TCGdex prices |
| `pokequant ingest-cardmarket PATH` | Ingest sanctioned Cardmarket CSV |
| `pokequant scan [--sync-comps] [--send-telegram]` | Scan Tradera vs eBay/PC (quota-shaped) |
| `pokequant hermes-queries` | This tick's round-robin aliases + slot math |
| `pokequant telegram-poll` | Deals bot getUpdates (LaunchAgent) |
| `pokequant mini-doctor` | Mini host hard gates |
| `pokequant hermes pause\|resume` | Pause state machine (never `hermes cron pause`) |
| `pokequant precision --source tradera` | Two-rate precision (writes snapshot; GET is read-only) |
| `pokequant expansion` | Whether expansion is allowed + next steps |

## Precision gate

Keep the same ~100 cards until:

- ≥40 labeled alerts
- ≥50% `really_good`
- ≤10% false match (`wrong_identity`)

Then `pokequant expansion` will unlock next steps.

## Tests

```bash
pytest -q
```

## Notes

- No auto-purchasing. Telegram/web buttons only record decisions.
- Blocket/Facebook automation is intentionally out of scope.
- PriceCharting is optional secondary reference; do not use as sole Swedish fair value.
- Money is stored as integer öre/cents.
