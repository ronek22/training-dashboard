# Implementation Plan: Hybrid coaching team

**Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

## Summary

Use deterministic specialist evidence, three AI analyses and HEAD COACH synthesis in one visual weekly-review experience, with historical Sunday review context.

## Technical Context

Python/FastAPI/SQLite, Vue 3/Vite, unittest and browser verification. No new runtime dependencies; reuse app_settings for per-week AI report persistence. Read five weeks without display limits; compare matching weekdays. Reuse existing strength source preference and exercise classification. Keep missing totals nullable. Same/adjacent-day demanding sessions are scheduling flags, not physiological predictions.

## Constitution Check

All five principles pass before and after design: acceptance criteria defined; no plan writes; evidence and limitations explicit; shared HTTP/MCP service; temporary test databases plus keyboard/responsive checks.

## Project Structure

- backend/app/repositories/activities.py: bounded activity reads.
- backend/app/services/strength.py: reusable bounded strength detail.
- backend/app/services/coaches/: common facts, running, cycling, strength, head coordinator.
- backend/app/services/coaches/presentation.py: athlete-facing takeaways and next-session instructions; adjusted sessions omit the original duration/distance prescription.
- backend/app/services/coaching.py: additive team_coaching via HTTP and MCP.
- backend/app/services/weekly_reviews.py and scripts/sunday_review.py: historical evidence integration.
- frontend/src/components/TeamCoaching.vue and frontend/src/views/Dashboard.vue: weekly review UI.
- backend/tests/test_team_coaching.py: boundary and integration coverage.

## Delivery

### Deeper review refinement

Use `scripts/team_coaching_helper.py` for three concurrent specialist calls and one sequential HEAD COACH call through the existing runner. `backend/app/services/team_analysis.py` builds a stable, complete snapshot; validates and stores the report through the settings repository by week. `backend/app/models/team_analysis.py` defines bounded output schemas. Add read/context/save routes under `/coaching/team-analysis` and a `/team-review` helper job. UI displays actual generated analysis and saves the in-flight job ID for navigation recovery. Inputs are hashed; changed data marks cached output stale and rejects an obsolete write. Existing per-week review storage retains the last successful result on failed regeneration.

Facts, specialists/arbitration, integrations/UI, verification/docs. Current reports reuse existing goals/recovery/restrictions; historical reports omit current recovery. Existing snapshots and immutable reviews remain compatible.

Athlete feedback refinement: one call/reason and an upcoming workout replace generic priority lists. Three compact sport summaries lead with useful interpretation; evidence is optional. Explicitly constrain the Dashboard grid track to avoid min-content expansion on narrow screens.

Latest refinement supersedes the full dashboard panel: `TeamCoaching.vue` has a compact dashboard mode, `TrainingWeekVisual.vue` renders measured time allocation and session timing from existing facts, and `views/WeeklyReview.vue` separates current analysis from completed Sunday history in one route. No new chart dependencies, invented scores, or changes to the Sunday scheduler.
