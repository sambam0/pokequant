# How to get Tradera, Telegram, eBay, and PriceCharting credentials

Put all values in `.env` (copy from `.env.example`).

## 1. Tradera (buy-side scanning)

1. Open [Tradera API registration](https://api.tradera.com/register) and create a **developer** account (separate from your normal Tradera login if needed).
2. Create an **application** in the developer portal.
3. Copy:
   - `App Id` → `TRADERA_APP_ID`
   - `App Key` → `TRADERA_APP_KEY`
4. Start with the default daily budget (`TRADERA_DAILY_CALL_BUDGET=100`). Request a higher limit from Tradera only after the pilot is stable.
5. Docs: [Tradera developer docs](https://api.tradera.com/documentation) and [REST search](https://api.tradera.com/documentation/rest/search).

PokeQuant only uses read/search. It does **not** auto-bid or auto-buy.

## 2. Telegram — two bots (Deals ≠ Ops)

You need **two** tokens. Hermes `pq-ops` gateway and `pokequant telegram-poll` cannot share a token (HTTP 409).

1. In Telegram, open [@BotFather](https://t.me/BotFather).
2. Create **two** bots (`/newbot` twice): PokeQuant Deals and Hermes Ops.
3. Deals token → `TELEGRAM_DEALS_BOT_TOKEN`. Ops token → `TELEGRAM_OPS_BOT_TOKEN`.
4. **Both operators must press Start on both bots** before `mini-doctor` can DM them. Bots cannot initiate DMs.
5. Forum: add the Deals bot to the family group as a **forum admin** with post-in-topic. Set `TELEGRAM_DEALS_CHAT_ID` (group id) and `TELEGRAM_DEALS_THREAD_ID` (Deals topic). Same pattern for Ops (`TELEGRAM_OPS_CHAT_ID` / `TELEGRAM_OPS_THREAD_ID`).
6. Allowlist numeric user ids: `TELEGRAM_DEALS_ALLOWED_USER_IDS` and `TELEGRAM_OPS_ALLOWED_USER_IDS` (comma-separated).

### One-time setup (before `telegram-poll` is installed)

To learn a chat id **once**, before the Mini poller is running, you may open:

`https://api.telegram.org/bot<TELEGRAM_DEALS_BOT_TOKEN>/getUpdates`

Copy `"chat":{"id": ...}`. Do this **before** installing `com.pokequant.telegram-poll`, or you will 409 the poller.

### Production diagnosis

Do **not** paste `getUpdates` in a browser on the live Mini. That steals the poller. Prod diagnosis is `getWebhookInfo` (must be empty for Deals) plus `pokequant mini-doctor`.

`Bought` is the only Telegram path to workflow `purchased`. **Good (would buy)** is a deal label, not an acquisition.

```bash
pokequant scan --send-telegram
```

Without `--send-telegram`, alerts are logged locally (dry-run). Mini production path must pass `--send-telegram`.

## 3. eBay Browse (US/live ask comps)

1. Create an account at [eBay Developers Program](https://developer.ebay.com/).
2. Create a keyset / app → copy **Client ID** and **Client Secret**.
3. Put them in `.env`:
   - `EBAY_CLIENT_ID=`
   - `EBAY_CLIENT_SECRET=`
   - `EBAY_MARKETPLACE_ID=EBAY_US` (default)
4. PokeQuant fetches an **application access token** and uses the Browse API to search active listings for watchlist cards.
5. Note: sold-history (Marketplace Insights) is limited-release and not required for this “cheaper than eBay ask” rule.

## 4. PriceCharting (optional paid guide)

1. Create an account at [PriceCharting](https://www.pricecharting.com/).
2. Subscribe to **Legendary** if you want API/CSV (~USD 49/month).
3. Subscription page → **API/Download** → copy the 40-character token → `PRICECHARTING_API_TOKEN`.
4. Terms: internal business use only; do not publish their prices on a public shop.

If you skip PriceCharting for now, eBay alone still powers the “Tradera vs eBay” buy gate.

## Suggested `.env` block

```bash
TRADERA_APP_ID=
TRADERA_APP_KEY=
TELEGRAM_DEALS_BOT_TOKEN=
TELEGRAM_DEALS_CHAT_ID=
TELEGRAM_DEALS_THREAD_ID=
TELEGRAM_DEALS_ALLOWED_USER_IDS=
TELEGRAM_OPS_BOT_TOKEN=
TELEGRAM_OPS_CHAT_ID=
TELEGRAM_OPS_ALLOWED_USER_IDS=
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_US
PRICECHARTING_API_TOKEN=
USD_SEK_RATE=10.5
EUR_SEK_RATE=11.0
FX_AS_OF=2026-08-13
```

`USD_SEK_RATE` / `EUR_SEK_RATE` convert comps into SEK. Set `FX_AS_OF` (YYYY-MM-DD). Scoring rejects FX older than 7 days.
