# Phase A Playbook: Two-Week Operating Baseline

## Purpose

Phase A turns your brother’s existing expertise into a repeatable, measurable operating process before software automates it.

At the end of two weeks, you should know:

- How opportunities are discovered, evaluated, purchased, received, listed, sold, and reconciled.
- Which decisions require domain expertise and which calculations can later be automated.
- The real net economics after fees, shipping, returns, VAT treatment, and operator time.
- Which records your accountant needs.
- Whether you can safely move into Phase B: building the inventory source of truth.

Phase A is not intended to maximize purchase volume, build scraping bots, launch Shopify, or test every category.

## Pilot scope

Use these boundaries unless both operators explicitly change them:

- Duration: 14 calendar days.
- Category: Pokémon singles only for the scanner pilot (sealed only if explicitly on the watchlist).
- **Watchlist:** brother delivers a frozen list of about **100 specific cards** the bot will later scan; Phase A only researches listings for those cards.
- Sources: existing relationships, events, manual marketplace searches, native saved searches, and Tradera.
- Purchases: human-approved only.
- Target: evaluate 20–50 genuine opportunities on the watchlist and purchase only a safe subset.
- Expansion rule: do **not** grow beyond those ~100 cards until the automated bot later hits **50%+ `really_good` alerts** with enough sample size (see main plan).
- Existing inventory: audit it, but report it separately from new pilot purchases unless acquisition costs are reliable.
- Currency: SEK.
- Transaction owner: your brother’s currently registered business unless your written agreement says otherwise.

## Watchlist setup (Day 1–2 deliverable)

Brother creates the frozen ~100-card list before broad deal hunting. For each card:

- Exact identity: set, collector number, language, variant/foil/edition.
- Swedish/English search aliases and common misspellings.
- Minimum acceptable condition (e.g. NM–LP).
- Rough max buy or minimum discount vs EU reference.
- Priority: core vs opportunistic.

You (tech) put the list into a `Watchlist` sheet with one row per card and a stable `WATCH-001` … `WATCH-100` ID. Freeze the list. Only fix identity errors; do not swap cards mid-pilot for convenience.

When reviewing opportunities in Phase A, label each as:

- `really_good` — underpriced + quality good enough that he would buy
- `maybe` — borderline price/photos/timing
- `junk` — wrong card, bad quality, not actually cheap after costs

These labels become the training/acceptance metric for the bot. The bot later succeeds when ~50%+ of its alerts are `really_good`, not when it sends more notifications.

## Roles

### Technology and operations owner

You are responsible for:

- Maintaining the opportunity log and required fields.
- Capturing comparable-price evidence and calculating costs.
- Assigning IDs, controlling workflow states, and checking data completeness.
- Monitoring capital limits and flagging policy exceptions.
- Receiving/inventory records, metrics, and weekly reconciliation.
- Recording what should eventually be automated.

You may veto a purchase when required evidence is missing, the economics fail, or a risk limit is exceeded.

### Domain and merchandising owner

Your brother is responsible for:

- Product identity, variant, condition, authenticity, and completeness.
- Deciding whether comparable items are genuinely comparable.
- Estimating demand, likely resale channel, and expected time-to-sale.
- Approving titles, condition statements, defects, and resale prices.
- Managing seller/collector relationships.

He may not override financial or exposure limits without recording an exception.

### Joint decisions

Both approve:

- Any purchase above the agreed joint-approval threshold.
- Mixed lots, weak provenance, low liquidity, or meaningful authenticity uncertainty.
- Purchases outside the Pokémon pilot.
- Exceptions to capital, profit, or seller-exposure limits.
- Returns, write-offs, or disputes above the agreed threshold.

## Minimal tools and physical setup

Do not buy extensive software during Phase A. Use:

- One shared spreadsheet with tabs described below.
- One shared evidence folder with access limited to both operators.
- A dedicated email address for business/platform receipts if one does not already exist.
- Numbered removable labels or archival-safe sleeves.
- Clearly labelled physical locations: `RECEIVING`, `QUARANTINE`, `READY`, `LISTED`, and `SOLD`.
- Consistent photo area with neutral background and angled light.
- Parcel scale and ruler.
- Optional barcode/QR labels only if already available; plain IDs are sufficient.

Do not use the spreadsheet as the legal bookkeeping ledger. It is the pilot operating record and should later export to the accountant-approved system.

## Identifier rules

Assign IDs immediately:

- Opportunity: `OP-YYYYMMDD-001`
- Purchase: `PO-YYYYMMDD-001`
- Lot: `LOT-YYYYMMDD-001`
- Inventory unit: `INV-YYYYMMDD-001`
- Sale: `SO-YYYYMMDD-001`
- Return/claim: `RT-YYYYMMDD-001`

Never reuse an ID. If a marketplace listing is relisted, connect the new source listing to the same opportunity or inventory unit rather than overwriting history.

## Day-by-day schedule

### Day 1: Kickoff and pilot charter

Schedule a 90-minute meeting. Complete the charter before reviewing any new deals.

Decide:

- Pilot start/end dates.
- Business/entity through which purchases and sales occur.
- Who contributes purchasing capital.
- How each person is compensated during the pilot.
- Who owns inventory, software, data, accounts, brand, and customer list.
- What happens to unsold pilot inventory if the partnership stops.
- Who absorbs returns, fraud, losses, and write-downs.
- Which decisions require both people.
- Weekly review time.

Use this charter:

```text
Pilot name:
Pilot dates:
Operating business/entity:
Pilot category:
Purchasing capital contributed by:
Inventory owned by:
Technology/IP owned by:
Data/accounts/customer relationships owned by:
Technology operator compensation:
Domain operator compensation:
Profit definition:
Loss/return responsibility:
Joint-approval threshold:
Pilot stop-loss:
Exit treatment for unsold inventory:
Weekly review time:
Signatures and date:
```

This is a practical pilot agreement, not a replacement for legal advice. If the longer-term ownership arrangement is unclear, resolve it before scaling.

### Day 2: Risk policy and accountant packet

#### Risk policy

Agree on:

- Total pilot purchasing budget.
- Maximum capital deployed per week.
- Maximum landed cost per item.
- Maximum landed cost per lot.
- Maximum exposure to one seller.
- Minimum expected net profit in SEK.
- Minimum profit per operator hour.
- Maximum acceptable expected days to sale.
- Joint-approval threshold.
- Pilot stop-loss.

A conservative discussion starter—not a universal recommendation—is:

- Core/liquid inventory: up to 70% of pilot capital.
- Opportunistic inventory: up to 20%.
- Experimental inventory: no more than 10%.
- One item: no more than 10% of pilot capital.
- One seller: no more than 20% of pilot capital.
- Any authenticity uncertainty: no purchase unless resolved.
- Any missing landed-cost input: no purchase.

Replace these values with limits appropriate to the business’s actual cash flow and risk tolerance.

#### Accountant packet

Prepare five examples:

1. Used card bought from a Swedish private seller.
2. Mixed lot bought from a private seller and split into multiple units.
3. Sealed product bought from a VAT-registered retailer.
4. Marketplace resale with fees and shipping.
5. In-person event sale paid through cash, Swish, or card.

Ask the accountant:

- Is the business VAT-registered, exempt, or approaching a relevant turnover threshold?
- When does VMB apply, and what purchase evidence is required?
- How should mixed-lot cost be allocated?
- How should VMB and ordinary-VAT inventory be separated?
- How should marketplace fees, postage, packaging, grading, travel, refunds, and write-downs be recorded?
- What receipt/cash-register rules apply at events and auctions?
- Which online and in-person consumer return/complaint rules apply?
- What fields and document retention are mandatory?
- What bookkeeping export format and reconciliation frequency should be used?
- Are there special requirements for cross-border EU purchases or imports?

Record written answers and examples. The future software should store an accountant-selected tax code, not guess tax treatment.

### Day 3: Opening inventory audit

Physically count existing inventory.

For each item or unresolved lot, capture:

- Inventory ID.
- Product identity and possible alternatives.
- Set, collector number, language, variant, raw/graded, grader/certificate.
- Condition and confidence.
- Quantity and physical location.
- Acquisition date, source, seller type, cost, shipping, and evidence.
- VAT/VMB treatment if known.
- Current channel, asking price, and listing date.
- Conservative net realizable value.
- Status: `needs inspection`, `needs research`, `ready`, `listed`, `reserved`, or `stale`.

If cost or provenance is unknown, write `unknown`; do not invent an estimate and present it as historical fact.

Reconcile the physical count against every active marketplace listing. Remove or pause listings for items that cannot be located.

### Days 3–10: Opportunity evaluation

Create one record for every reviewed opportunity, including rejected deals.

Capture:

- Opportunity ID and discovery timestamp.
- Source, source listing ID, URL, seller type, and screenshots.
- Asking price, buyer fee, inbound shipping, currency, and FX source/date.
- Proposed exact identity and alternative candidates.
- Language, edition, variant, raw/graded, completeness, and authentication status.
- Condition range and photo-evidence completeness.
- Comparable sources, observation dates, match quality, and low/central/high values.
- When logging comps, prefer this order: Tradera sold/ended → Cardmarket trend/AVG (EU) → PriceCharting ungraded/graded (US/eBay secondary) → active asks.
- Record PriceCharting separately as a secondary reference in USD; do not use a raw PriceCharting number (even FX-converted) as the Swedish `max_buy_price`.
- Expected selling channel and time-to-sale.
- Expected selling fees, payment fees, outbound shipping, packaging, VAT/tax input, returns/fraud reserve, and handling time.
- Conservative net proceeds, landed cost, expected profit, downside, and maximum buy price.
- Decision, reviewer, decision timestamp, and reason.
- Actual purchase price when applicable.

Use these decision values:

- `reject`
- `request evidence`
- `watch`
- `approve`
- `approve exception`
- `too late`

Use structured reason codes:

- `wrong identity`
- `condition uncertainty`
- `authenticity risk`
- `missing evidence`
- `insufficient profit`
- `low liquidity`
- `seller risk`
- `capital limit`
- `duplicate`
- `outside scope`
- `missed due to latency`

#### Review queue rules

- Maximum 20 opportunities awaiting expert review.
- High-velocity opportunity reviewed within two hours.
- Ordinary opportunity reviewed within one business day.
- Evidence request sent within four working hours.
- Unanswered evidence request closed after 48 hours unless marked strategic.
- Contradictory identity information enters quarantine; fuzzy matching cannot confirm an item.

#### Photo evidence request

For cards, request:

- Front and back, straight-on.
- All corners.
- All edges.
- Surface under angled light.
- Collector/set number and identifying marks.
- Close-ups of creases, dents, scratches, whitening, ink, or water damage.
- Slab label, certificate number, and holder details when graded.
- Timestamped video or live inspection for high-value items when appropriate.

For sealed products, add:

- Every seal and seam.
- Top, bottom, and all sides.
- EAN/UPC and product identifiers.
- Tears, dents, crushing, fading, or suspected rewrapping.

### Days 4–14: Controlled purchases and receiving

Buy only opportunities that pass the risk policy. Do not purchase all reviewed opportunities just to increase sample size.

Before purchase:

- Freeze the valuation, comparable evidence, condition probabilities, costs, and model/rule version.
- Record who approved and any exception.
- Save checkout/payment evidence.

On arrival:

1. Move parcel to `RECEIVING`.
2. Photograph or video unopened high-value parcels.
3. Record arrival date, package condition, and weight.
4. Match contents to the purchase record.
5. Inspect within 48 hours.
6. Where practical, let the domain owner inspect without seeing the predicted grade.
7. Record observed defects separately from the final condition label.
8. Assign inventory IDs and physical locations.
9. Allocate lot cost using the accountant-approved method.
10. Move approved inventory to `READY`.

Move anything mismatched, damaged, substituted, incomplete, or questionable to `QUARANTINE`. Do not list it until the claim, return, or authentication question is resolved.

### Days 5–14: Pricing, listing, and events

For each ready inventory unit:

- Select the resale channel based on likely net proceeds, time-to-sale, return/fraud risk, and operator work.
- Preserve the minimum net-proceeds floor.
- Use photos of the actual item.
- Describe observed defects directly; do not hide them inside a grade.
- Record listing ID, channel, list date, asking price, minimum acceptable price, and review date.
- Reserve inventory centrally as soon as it is committed to a buyer.

For an event:

- Create an event manifest listing every inventory ID and opening price.
- Check stock out before leaving and back in after returning.
- Record discount, payment method, and buyer receipt reference.
- Reconcile cash, Swish, card totals, and remaining physical inventory the same day.

### Day 7: Midpoint review

Hold a 45-minute review:

- Is either operator bypassing required fields?
- Is the 20-item WIP limit appropriate?
- Which fields are unclear or never used?
- Which opportunities are repeatedly rejected, and why?
- Are comparable items being selected consistently?
- Are the profit and time-to-sale assumptions conservative?
- Are any risk limits creating exceptions?
- What process failure should be fixed immediately?

Change only urgent process defects. Version any changed rule and do not rewrite earlier decisions.

### Day 14: Baseline and Phase B decision

Freeze the Phase A data and calculate the metrics below.

Hold a 60-minute review:

1. What improved compared with the previous informal process?
2. Where did domain judgment matter most?
3. Which repetitive steps should Phase B automate?
4. Which inputs were unavailable or unreliable?
5. Which risks were underestimated?
6. Did both operators follow the process?
7. Should you proceed, repeat Phase A, narrow the category, or stop?

## Spreadsheet structure

### `Settings`

Store:

- Pilot dates and budget.
- Risk limits.
- Standard reserves.
- Operator hourly-cost assumptions.
- Current fee schedules and effective dates.
- Allowed channels and categories.
- Reason/status values.

### `Opportunities`

One row per opportunity with all discovery, identity, condition, comparable, cost, valuation, decision, reviewer, and timing fields.

### `Comparable observations`

One row per comparable:

- Opportunity/product ID.
- Source and source record (`tradera`, `cardmarket`, `pricecharting`, `ebay`, `manual`, etc.).
- Active/sold/paid/cancelled/returned status, or `guide` for PriceCharting/Cardmarket aggregates.
- Observation and ingestion timestamps.
- Product/condition match score.
- Item price, shipping, buyer fee, currency, and SEK conversion.
- Whether it is primary (EU/SE) or secondary (US/global) evidence.
- Included/excluded status and reason.

**PriceCharting during Phase A:** use the free/app site manually when researching. Note ungraded vs graded tier, language/set match, and URL. Do not subscribe to Legendary API (~USD 49/month) until Phase C+ proves you need automated graded/US checks often enough to justify it. Keep any PriceCharting figures internal; do not publish them on a public shop page.

### `Purchases`

One row per purchase:

- Purchase ID and linked opportunity.
- Seller type/country.
- Prices, fees, shipping, tax input, payment date, and evidence.
- Approval and exception.
- Expected arrival and actual arrival.

### `Inventory`

One row per inventory unit:

- Inventory and parent lot IDs.
- Verified identity, condition, defects, and confidence.
- Allocated landed cost and accounting code.
- Physical location and state.
- Current channel/listing/reservation.

### `Sales and returns`

Store gross sale value and every fee/cost separately:

- Sale and inventory IDs.
- Channel, customer type/country, order/listing ID.
- Item price and shipping charged.
- Marketplace, payment, promoted-listing, postage, packaging, and other costs.
- VAT/accounting code.
- Settlement state/date.
- Return/refund/claim and added costs.

### `Exceptions`

Record:

- Linked record.
- Exception type and severity.
- Owner and deadline.
- Resolution.
- Financial impact.
- Preventive process change.

## Calculation guide

Use formulas approved by the accountant for VAT/tax inputs.

```text
landed_cost =
  purchase_price
  + buyer_fee
  + inbound_shipping
  + insurance
  + import_or_nonrecoverable_tax
  + preparation_or_grading

expected_net_proceeds =
  conservative_resale
  + shipping_charged_to_buyer
  - selling_fee
  - payment_fee
  - promoted_listing_fee
  - outbound_postage
  - packaging
  - expected_return_or_fraud_loss
  - VAT_or_tax_cost

expected_profit =
  expected_net_proceeds
  - landed_cost
  - operator_time_cost

max_buy_price =
  expected_net_proceeds
  - nonpurchase_costs
  - target_profit
  - risk_reserve

capital_days =
  landed_cost × days_held

profit_per_operator_hour =
  realized_or_updated_profit / total_operator_hours
```

Report estimated and realized values separately. Unsold stock has no realized profit.

## End-of-day checklist

- [ ] All reviewed opportunities have decisions and reasons.
- [ ] Purchases have evidence and approvals.
- [ ] Received parcels have been logged.
- [ ] Quarantined items are physically separated.
- [ ] Listed/reserved/sold states match physical stock.
- [ ] Event and marketplace sales are recorded gross with separate fees.
- [ ] WIP queue is at or below 20.
- [ ] Exceptions have owners and deadlines.

## Weekly reconciliation checklist

- [ ] Count physical inventory and investigate differences.
- [ ] Reconcile sales to platform orders.
- [ ] Reconcile platform payouts to bank.
- [ ] Reconcile cash/Swish/card event totals.
- [ ] Review unsettled sales, returns, and claims.
- [ ] Review stale inventory.
- [ ] Confirm fee schedules and accounting codes remain current.
- [ ] Back up/export the pilot sheet and evidence index.

## Phase A metrics

Measure:

- Opportunities reviewed per sourcing hour.
- Median minutes from discovery to decision.
- Percentage of alerts/opportunities judged relevant.
- Purchase conversion.
- Rejection reasons.
- Condition forecast versus received condition.
- Identity/authenticity disagreement.
- Expected versus realized or updated conservative net profit.
- Profit per operator hour.
- Capital-days and expected days to sale.
- Inventory age and reconciliation differences.
- Return, dispute, fraud, and write-down rate.
- Percentage of required fields complete.

Do not use alert count, gross sales, or optimistic inventory value as success metrics.

## Exit criteria

Proceed to Phase B only when:

- [ ] Pilot charter and ownership are documented.
- [ ] Accountant-approved record/tax requirements are written.
- [ ] Risk Policy v1 is signed.
- [ ] Existing inventory is physically reconciled.
- [ ] At least 20 opportunities have complete decision records.
- [ ] Several purchases have full acquisition-to-inventory trails.
- [ ] Any sale/return completed during the period is fully traceable.
- [ ] Both operators can follow the workflow without verbal reconstruction.
- [ ] Missing or ambiguous fields have been resolved.
- [ ] The specific Phase B screens and automations can be named from observed pain.

Repeat or narrow Phase A when records remain incomplete, limits are routinely overridden, inventory cannot be reconciled, or accounting treatment is unresolved.

## First 48 hours

To start immediately:

1. Book the 90-minute kickoff with your brother.
2. Copy and complete the pilot charter.
3. Set the total pilot budget and stop-loss.
4. Book/send the accountant question packet.
5. Create the shared sheet with the listed tabs.
6. Label the five physical inventory states.
7. Choose the first 10–20 existing items for the opening audit.
8. Select five representative marketplace opportunities and complete the form manually.
9. Schedule the Day 7 and Day 14 reviews.

Do not begin Phase B implementation until the Phase A exit criteria are reviewed together.
