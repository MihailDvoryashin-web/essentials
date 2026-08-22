# Essentials — Stage 1

Polls GMGN's official Trenches API through `gmgn-cli`, applies the Stage 1 filter, and sends one Telegram token card per Solana contract address.

## Stage 1 behavior

GMGN performs these filters server-side:

- chain `sol`, launchpad `Pump.fun`;
- inclusive market cap `$50,000–$250,000`;
- `total_fee >= 5` SOL;
- `renowned_count >= 1` (GMGN KOL count).

The service then requires `has_at_least_one_social == true` locally and repeats every condition defensively before sending. It does not perform holder, wallet PnL, smart-wallet classification, HITTER/CONSISTENT/BOTH, or results tracking.

CA deduplication is persistent in SQLite. A CA is recorded only after Telegram accepts the alert. The default poll interval is 60 seconds.

## Setup

Requirements: Python 3.9+, Node/npm, and a GMGN API key authorized for the official CLI.

```bash
./scripts/bootstrap.sh
cp .env.example .env  # only if bootstrap did not create it
```

Fill in `.env`, then run:

```bash
.venv/bin/essentials
```

`SOLANA_RPC_URL` selects the Solana RPC used to resolve Metaplex token metadata.
It defaults to the public mainnet endpoint; a dedicated RPC is recommended for production.

Or use Docker:

```bash
docker compose up -d --build
```

## Telegram keyboard

The full CA is displayed in the card caption as Telegram HTML code. Terminal custom emoji IDs are optional environment variables.

GMGN and Padre use the token CA. Axiom is created only when GMGN supplies `market_address`/`pair_address`/`pool_address`; the CA is never substituted into its market route.

The Bot API restricts `icon_custom_emoji_id` to eligible bots/chats. Leave the corresponding ID empty if the bot does not meet those requirements.

## Tests

```bash
.venv/bin/pytest
```

Send one test token card to the configured Telegram topic without querying GMGN or starting the scanner:

```bash
.venv/bin/python scripts/test_alert.py
```

Fetch one current Stage 1 candidate from GMGN and send one live production-format card without starting polling or writing SQLite state:

```bash
.venv/bin/python scripts/test_live_alert.py
```
