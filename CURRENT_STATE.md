# Essentials — Current State

Updated: 2026-08-24

## What works now

- Pump.fun/Solana discovery through official `gmgn-cli`.
- Startup baseline, creation-time freshness protection and SQLite/in-flight dedup.
- Defensive Stage 1: market cap `$50,000–$250,000`, fee `>=5`, renowned/KOL count `>=3`, social presence.
- Meaningful-holder cleanup and Top10 concentration gate `<=35%`.
- Top30 two-stage Smart Money analysis: `<1600` 7d transactions, positive all-time realized PnL, portfolio `>=$5,000`, minimum five SMART wallets.
- Required Lightning/MVP quality gate with current-holding threshold `$4,900` and MVP realized-profit threshold `$19,000`.
- Atomic Telegram card/reply delivery with persisted message coordinates.
- Results market-cap tracking, milestones and `/stats`.
- Full test suite: 228 passed at the latest code verification.

## Latest changes

- Token tickers are displayed without leading `$` in user-visible card, Smart Money, Results and `/stats` output.
- The holders/smarts line is rendered as `total holders <value> | smarts <value>` without visual hyphens.
- `/stats` Top10 tickers are uniformly bold and link to the original card when valid coordinates exist.
- Permanent documentation workflow now uses `AGENTS.md`, `PROJECT_CONTEXT.md`, `CHANGELOG_AI.md` and `CURRENT_STATE.md`, with GitHub `origin/main` as durable history.

## Current TODO

- Clarify whether the requested KOL `>2` task differs from existing `renowned_count >=3`.
- Identify the reported syntax problem; current test suite does not reproduce one.
- Add a pre-alert price-drop/dead-token filter.
- Add dev holdings maximum 2% gate.
- Add migration rules: minimum two launches and one migration.
- For migrated tokens, require minimum three fees/«взятки».
- Add linked-network validation beyond existing `chain=sol` query restriction.
- Add explicit community validation beyond generic social presence.
- Track GMGN social updates.
- Remove token images from alerts while preserving text fallback behavior.
- Preserve Smart Money `⚡`/`⚡⚡` behavior in future changes.
- Define and implement the requested new price scanner; existing `ResultsTracker` remains active.

## Next task

НЕ ОПРЕДЕЛЕНА В КОДЕ. The owner must select and specify one item from Current TODO.

## Repository state

- Branch: `main`.
- Remote: `origin` → `https://github.com/MihailDvoryashin-web/essentials.git`.
- The local worktree currently contains pre-existing modified and untracked project files; future commits must remain task-scoped.
