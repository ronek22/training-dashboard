# Tasks: Hybrid coaching team

## Phase 1: Setup
- [x] T001 Define spec, design and contracts in docs/specs/001-hybrid-coaching-team/.

## Phase 2: Foundations
- [x] T002 Add complete activity range reads in backend/app/repositories/activities.py and bounded strength detail in backend/app/services/strength.py.

## Phase 3: US1 — Weekly team
- [x] T003 [US1] Implement specialists and arbitration in backend/app/services/coaches/ (FR-001, FR-002).
- [x] T004 [US1] Render HEAD COACH, priorities and disclosures in frontend/src/components/TeamCoaching.vue and frontend/src/views/Dashboard.vue (FR-005).

## Phase 4: US2 — Evidence
- [x] T005 [US2] Verify nullable totals, missing intent, date boundaries and baseline with backend/tests/test_team_coaching.py (FR-003, FR-004).

## Phase 5: US3 — Integration
- [x] T006 [US3] Add team payload to backend/app/services/coaching.py, backend/app/services/weekly_reviews.py and scripts/sunday_review.py; test HTTP/MCP compatibility and no plan mutations (FR-006).

## Phase 6: Verification
- [x] T007 Build frontend, verify keyboard/responsive/retry flows, run backend regressions, and update docs/current-state.md and feature quickstart.md.

## Dependencies and delivery

T001 → T002 → T003; T004 and T006 can proceed independently after T003. T005 verifies evidence before final T007. Deliver shared facts, reports, integrations, then verified UI.

## Phase 7: Athlete feedback
- [x] T008 [US1] Turn report facts into concise takeaways and a next-session action in backend/app/services/coaches/presentation.py and head.py; redesign frontend/src/components/TeamCoaching.vue around that decision with optional evidence (FR-007).

## Phase 8: Deeper coaching review
- [x] T009 [US1] Implement snapshot validation and saved AI review in backend/app/models/team_analysis.py, backend/app/services/team_analysis.py and backend/app/routers/coaching.py (FR-008).
- [x] T010 [US1] Add three specialist calls followed by head synthesis in scripts/team_coaching_helper.py and scripts/codex_planning_helper.py (FR-008).
- [x] T011 [US1] Display substantive verdict, tradeoff, one next-week change and success check in frontend/src/components/TeamCoaching.vue, with stale/loading/retry/resume states (FR-008).
- [ ] T012 Verify persistence, stale snapshot rejection, evidence references, staged orchestration and live review with tests and browser checks; update docs/current-state.md. Synthetic checks and documentation complete; real review blocked pending explicit permission to transmit training/recovery context through the AI connection.

## Phase 9: Consolidated visual review
- [x] T013 Replace competing dashboard panels with compact TeamCoaching and dedicated views/WeeklyReview.vue, retaining SundayReview history under Completed weeks (FR-009).
- [x] T014 Add components/TrainingWeekVisual.vue with labeled sport-time allocation and linked seven-day session grid; verify desktop/mobile, navigation and no duplicate narratives (FR-010).
