# Essentials Development Rules

These instructions apply to the entire repository.

## Source of truth

- Current production code and tests define actual behavior.
- `PROJECT_CONTEXT.md` is the maintained architecture and behavior map.
- `CURRENT_STATE.md` is the concise handoff snapshot.
- `CHANGELOG_AI.md` is the append-only AI development history.
- GitHub `origin/main` is the durable project-history repository.
- If behavior is not confirmed by code, write `НЕ НАЙДЕНО В КОДЕ`; do not infer it.

## Required workflow after every code change

1. Make only the requested, minimal code changes.
2. Run the relevant targeted tests.
3. Run the full test suite when shared production behavior, architecture, filters, formatting, persistence, or pipeline changes.
4. Update only affected sections of `PROJECT_CONTEXT.md` and prepend a dated entry to `Recent Changes`.
5. Update `CURRENT_STATE.md` with current behavior, latest changes, TODO and next task.
6. Prepend a dated entry to `CHANGELOG_AI.md` using its required Task / Files changed / Logic changed / Tests format.
7. Run `git diff --check` and inspect `git status`.
8. Stage only files belonging to the current task. Never stage `.env`, credentials, `.DS_Store`, database files, caches, or unrelated user changes.
9. Commit with `type: short description`, for example `fix: remove dollar symbol from token tickers`.
10. Push the task commit to `origin/main`.
11. Report the commit hash and push result. If commit or push fails, report the exact blocker and do not claim GitHub synchronization succeeded.

## Documentation history

- Do not delete historical changelog or completed-change entries.
- Move confirmed completed tasks from Current TODO to Completed Changes.
- Do not mark work completed unless code and tests confirm it.
- Small code changes still require all three documentation files to be updated.

## Safety

- Never commit or print secret values.
- Preserve unrelated dirty-worktree changes.
- Do not run the production bot, send Telegram messages, trade, or call mutation endpoints unless the user explicitly requests it.
