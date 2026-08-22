# Pack / box chase sims

Jupyter workspace for:

1. **Box chase odds** — how many boxes (and spend) for a target chance at ultra-rares (e.g. Yu-Gi-Oh Grand Master Rares).
2. **Pack/box EV** — expected opened value vs retail when you supply card values and pull rates.

Currency defaults to **SEK**. Edit retail in `data/products/*.yaml`.

## Setup

```bash
cd notebooks
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook
```

Open `01_boxes_to_chase.ipynb` first for Grand Master Rare math.

## Product configs

| File | Notes |
|------|--------|
| `data/products/magnificent_monsters.yaml` | 3-pack tuckbox + print-run serial chase (GMR) |
| `data/products/magnificent_maestros.yaml` | Same structure, Nov 2026 sequel |
| `data/products/sample_pokemon_booster.yaml` | 36-pack box with fixed SIR-style rate |

## Assumptions (read before trusting numbers)

- **Grand Master Rare**: Konami prints 100 serials × 18 cards = **1,800** for the Europe distribution pool (E suffix). There is **no official per-box rate**. Odds require an assumed total print run of boxes.
- Model treats each box as an independent Bernoulli trial with `p ≈ serials / print_run_boxes`. Real collation may clump; case mapping is ignored.
- Americas and Europe pools are separate — use Europe-pool numbers for EU buys.
- “60 boxes” from chatbots is not a Konami fact; it only holds for a specific print-run assumption (see notebook sweep).
- Buying singles is often cheaper than ripping for serials. These tools show spend-to-probability, not a buy recommendation.

## Notebooks

- `01_boxes_to_chase.ipynb` — primary: boxes/spend vs hit %
- `02_pack_or_box_ev.ipynb` — opened-value EV vs retail
- `03_compare_products.ipynb` — side-by-side cost-to-X% and EV edge
- `04_maestros_profitability.ipynb` — Magnificent Maestros print-run, price bands, P&L by box count
