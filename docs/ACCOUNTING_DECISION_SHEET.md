# Accounting Decision Sheet

This is an operational checklist for your Swedish accountant — not tax advice.  
Record written answers before encoding tax treatment codes in the software.

## Business setup

- [ ] Business form confirmed (enskild firma / other)
- [ ] VAT registration status / small-business exemption applicability
- [ ] F-tax status
- [ ] Bookkeeping system and export cadence

## Five example transactions to review

1. Used card bought from a Swedish private seller and resold on Tradera.
2. Mixed lot bought from a private seller, split into units, sold separately.
3. Sealed product bought from a VAT-registered retailer.
4. Marketplace resale with fees and shipping.
5. In-person event sale paid by cash / Swish / card.

## Questions for the accountant

1. When does VMB apply versus ordinary VAT?
2. What purchase evidence and seller-status proof are required?
3. How should mixed-lot cost be allocated when items sell separately?
4. How should VMB and ordinary-VAT inventory be separated in records?
5. How should marketplace fees, postage, packaging, grading, travel, refunds, and write-downs be recorded?
6. What receipt / cash-register rules apply at events and auctions?
7. Which online and in-person consumer return/complaint rules apply?
8. What fields and document retention are mandatory?
9. What bookkeeping export format and reconciliation frequency should we use?
10. Any special rules for cross-border EU purchases or imports?

## Tax treatment codes for software

Use only accountant-approved codes. The app stores the selected code; it never infers eligibility from marketplace name alone.

| Code | Meaning | When to use | Accountant notes |
| --- | --- | --- | --- |
| `VMB_ELIGIBLE` | Margin scheme candidate | Private seller, no deductible input VAT | |
| `ORDINARY_VAT` | Standard VAT treatment | Business seller / VAT invoice / non-eligible | |
| `VAT_EXEMPT_THRESHOLD` | Operating under exemption | Only if confirmed | |
| `IMPORT_SPECIAL` | Import / IOSS / customs case | Cross-border | |
| `UNSET` | Not yet classified | Block export until set | |

## Required provenance fields (encode in system)

- Seller type: `private` / `business`
- Seller country
- Invoice/receipt reference and evidence path
- Purchase price, inbound shipping, buyer fees (minor units + currency)
- Lot allocation method and parent lot ID
- VAT treatment code
- Sale gross, fees, shipping charged, refunds (never only net payout)
- Return/claim linkage without overwriting original sale

## Example export columns

`sale_id,inventory_id,sale_date,channel,gross_ore,shipping_charged_ore,marketplace_fee_ore,payment_fee_ore,postage_ore,packaging_ore,vat_code,purchase_id,landed_cost_ore,seller_type,evidence_refs`
