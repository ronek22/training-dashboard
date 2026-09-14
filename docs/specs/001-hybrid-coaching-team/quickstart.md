# Validation

Run backend/.venv/bin/python -m unittest backend.tests.test_team_coaching backend.tests.test_weekly_reviews from repository root (temporary databases). Run npm run build in frontend. Verify Dashboard loading, empty, success, error/retry, keyboard expansion, source links and 390px layout with synthetic fixtures. Adjacent demanding run/ride/lower-strength sessions must identify dates and evidence; plan records remain unchanged.

## Recorded verification

### 2026-09-14 missing-review follow-up

- Explicitly approved live Sunday-review retry saved 2026-09-07; browser confirmed it is the latest completed review. Prior review timestamps remain unchanged.
- Added two backend tests for missing/saved status, empty history, Warsaw Sunday cutoff and DST; 44 focused tests now pass. Production build passed.
- Browser verified the actual saved week, mocked missing-week notice, latest-available label, Check again clearing the notice, and no horizontal overflow at 390px. Only unrelated favicon.ico 404 appeared in console.
- This does not establish live quality of the separate four-call team-analysis workflow.

### Initial implementation

- 42 focused tests passed: `backend/.venv/bin/python -m unittest backend.tests.test_team_analysis backend.tests.test_team_coaching backend.tests.test_weekly_reviews scripts.test_team_coaching_helper scripts.test_codex_planning_helper scripts.test_sunday_review`.
- Production frontend build passed.
- Desktop panel visually inspected; keyboard Enter opens and closes specialist evidence.
- Application smoke suite: 55 of 58 passed. All three failures reproduced in an isolated archive of unchanged HEAD: date-dependent activity stats fixture, obsolete Fitbod source label expectation, and goal-support assertion. They are not introduced by this feature.
- Browser checks exposed an existing implicit Dashboard grid track expanding on mobile; an explicit `minmax(0, 1fr)` track was added. Desktop and 390px rechecks passed with no horizontal overflow.
- Synthetic failed generation retained the prior report; retry succeeded and cleared the alert. Stale notice and empty-state behavior verified. Enter opens and closes specialist evidence.
- Consolidated UI verified with synthetic facts: dashboard has only one compact review and no specialist essay; Open review navigates to the detail page with three linked session marks; Completed weeks shows Sunday history without the current HEAD COACH narrative. Desktop and phone screenshots visually inspected.
- No synthetic review was persisted. Real generation was blocked by automatic approval because it transmits potentially sensitive training/recovery context through the existing AI connection; explicit user permission is pending. Do not claim live output quality has been verified.
