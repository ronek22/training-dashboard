# Working with coding agents without burning tokens

The repository is large (about 117k lines), so what an agent reads matters more than what it
writes. `AGENTS.md` (also loaded by Claude Code through `CLAUDE.md`) holds the rules agents
follow. This page lists the habits on your side that keep a session cheap.

- **One task per session.** Start a fresh session (or `/clear`) when you switch tasks. A long
  session resends everything said so far on every turn.
- **Name the place.** "Fix the Food page carb tile" or "`services/food_targets.py`" lets the
  agent go straight there. "Check what we can improve" makes it read the whole repository.
- **Ask for one feature, not a batch.** Each feature then gets its own focused tests and a
  short shipped entry.
- **Pick the effort for the job.** Mechanical edits (renames, copy, a moved component) do not
  need the strongest model or high reasoning effort; switch it in the app or with `/model`
  before you start.
- **Let the summary do the work.** `just check`, `just test-backend` and `npm test` print only a
  summary when they pass. Use `just test-backend-verbose` when you want per-test names and
  warnings yourself.

## What changed to support this (2026-10-25)

- Test and build output: a passing backend run printed ~240 KB of request logs; it now prints
  ~29 KB, and the frontend tests ~260 bytes.
- `docs/current-state.md` went from 141 KB to a 7 KB index; full entries are in `docs/shipped/`.
- The daily ideas review stops right away when nothing changed since its last run, and lists
  existing ideas compactly instead of reading the 97 KB catalog.
- Codex subagents default to medium reasoning effort (worker: high) with at most two at once,
  and `AGENTS.md` asks agents to work inline.
- `views/Plan.vue` went from 5,439 to ~2,040 lines (styles in `plan/Plan.css`, pure helpers in `plan/plan-helpers.mjs`, the coaching-context section in `components/PlanInsights.vue`), and `tests/test_app_smoke.py` became five `test_smoke_*.py` files.
