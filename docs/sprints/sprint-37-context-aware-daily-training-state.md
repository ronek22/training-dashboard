# Sprint 37 — Context-aware daily training state

Status: implemented

## Outcome

The Today dashboard augments deterministic load and readiness metrics with a prominent “Today’s coaching insight” interpretation of the athlete's whole current context.

## Behavior

- On the first Today visit for a distinct daily context, the local Codex helper requests a read-only assessment grounded in recent context, plan, goals, restrictions, recovery, notes, and strength work.
- The result contains a headline, short assessment, next step, and explicit confidence.
- The coaching copy must synthesize patterns, tradeoffs, plan implications, and uncertainty rather than restating the load tiles, check-in values, activities, or deterministic readiness summary already visible beside it.
- The structured result explicitly distinguishes ordinary execution advice from evidence that supports replacing or materially reducing tomorrow's saved session.
- When a change is recommended and tomorrow has an editable planned session, the insight offers an “Adapt tomorrow’s plan” action. The athlete's click authorizes a Codex revision constrained to tomorrow only; all other days are preserved, the result is saved, and the dashboard refreshes against the new plan.
- Explicit change language in the coaching next step (for example postpone, replace, skip, shorten, or reduce) acts as a defensive UI fallback when a model response contains an inconsistent structured recommendation flag.
- A targeted revision snapshots the saved week before and after Codex runs. Success is reported only when the target day changed and every non-target day remained identical; a clean model exit without a database mutation is treated as failure.
- Recent coaching context includes a compact exercise-level summary for linked TrainLog/Fitbod strength sessions. The daily assessment must inspect it—or explicitly call the full strength-context tool—before claiming that strength detail is missing.
- Coaching insight uses stale-while-refresh behavior: an exact context-key match returns immediately without a model call, while changed load, activities, recovery, or plan data keeps the previous insight visible until its replacement is ready.
- The browser caches the result for that context so ordinary revisits do not create repeated model calls.
- Today's activity IDs, load/readiness state, subjective recovery, and plan-completion state form the cache key. Adding an activity or materially changing recovery state therefore triggers a fresh assessment on the next Today load.
- A manual refresh remains available.
- Deterministic readiness and load metrics remain visible and usable when the helper is unavailable or the assessment fails.
- The duplicate activity streak is omitted from training state because it is already visible in the navigation.
- When activities exist today, the training-call card uses its otherwise empty lower area for a compact completed-session strip with totals and links to activity detail. This visually balances the taller coaching card and grounds the day's decision in completed work.
- Before training is completed, that same lower area presents the saved workout as a structured “How to execute it” guide: prescription, execution cues, and a stop/adjust guardrail. The hero summary stays concise instead of repeating the full workout paragraph.

## Guardrails

- The assessment prompt allows only read-only `training_dashboard` tools and cannot alter plans or athlete data.
- Model output is parsed and length-validated as a strict JSON contract before it reaches the UI.
- The insight is framed as coaching context, not a medical diagnosis.

## Verification

- Helper unit tests cover request validation, read-only prompt constraints, and structured-result validation.
- The production frontend build succeeds.
