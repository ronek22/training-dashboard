# Feature Specification: Hybrid coaching team

**Created**: 2026-09-11
**Status**: Implemented and synthetic checks passed; real AI review awaits data-transmission permission
**Input**: Implement running, cycling, and strength specialists coordinated by HEAD COACH in the existing app.

## User Scenarios & Testing

### User Story 1 — Understand the whole week (P1)

As an athlete I can read one HEAD COACH assessment and inspect each discipline's evidence.
Independent test: open the dashboard with synthetic training across all three sports.
Acceptance: one compact dashboard entry opens all three reports in Weekly review; adjacent demanding sessions across sports produce an explained conflict; restrictions and recovery take precedence over increases.

### User Story 2 — Trust the evidence (P1)

As an athlete I can distinguish recorded activity, missing measurements, and interpretation.
Independent test: an empty week and a week with missing intent/duration remain explicitly uncertain.
Acceptance: no activity is not called undertraining; only the selected week's elapsed days are counted; prior comparison uses matching weekdays; more than 12 activities are included.

### User Story 3 — Reuse the review (P2)

As an athlete my Sunday review can use the same specialist evidence while my saved plan stays under my control.
Independent test: request historical Sunday context and weekly coaching through HTTP/MCP.
Acceptance: historical evidence excludes later activities; existing response fields and saved review history remain compatible; viewing reports does not edit plans.

### Edge Cases

No plan, no activities, missing intensity, incomplete week, future records, generic strength without sets, indoor cycling, repeated reads, API failure and small screens.

## Requirements

- **FR-001**: Produce three specialist reports with recorded totals, evidence, limitations, and recommendations.
- **FR-002**: HEAD COACH resolves cross-sport scheduling conflicts and prioritizes existing recovery, restrictions, and goals.
- **FR-003**: Use the same bounded week and preceding four weeks for all specialists; clearly label week-to-date comparisons.
- **FR-004**: Missing measurements stay distinct from zero; conclusions must not claim predicted adaptation or calibrated confidence.
- **FR-005**: Display one headline, priorities, and expandable specialists with loading, retry, and empty states; support keyboard and narrow screens.
- **FR-006**: Share reports with weekly coaching and Sunday review context without changing saved plans or past reviews.
- **FR-007**: Lead with one actionable HEAD COACH call and its reason; the deeper review centers one next-week change rather than repeating daily workout guidance. Give each specialist a short interpretation. Format durations as hours/minutes, keep evidence behind optional disclosures, and avoid generic repeated goal reminders.

## Key Entities

Team review: week, cutoff, specialist reports, head assessment. Specialist report: sport, evidence totals, supporting sessions, risks, limitations, recommendations. Conflict: involved sessions, dates, explanation.

## Success Criteria

- **SC-001**: All three specialists and one HEAD COACH are inspectable from the dashboard.
- **SC-002**: Synthetic adjacent demanding run/ride/strength sessions identify the involved dates and activities.
- **SC-003**: Empty, incomplete, future, and missing-data cases produce no unsupported improvement or undertraining claims.
- **SC-004**: Reading reports leaves all plan and historical review records unchanged.

## Assumptions

The initial deterministic calculations remain the evidence foundation. Following athlete feedback on 2026-09-13, the user-facing review now uses three separate AI specialist calls and a HEAD COACH synthesis through the existing local helper. New chat modes, automatic plan edits, and physiological outcome prediction remain outside this slice. Existing daily AI assessment remains available. Related work: [weekly coaching](../../sprints/sprint-7-one-shot-coaching.md), [retrospectives](../../sprints/sprint-35-weekly-retrospectives-and-data-quality-inbox.md).

## Deeper review acceptance (2026-09-13)

- **FR-008**: On request, run independent AI specialist reviews against one shared snapshot, then HEAD COACH resolves their tradeoffs against goals and the saved plan. Return one next-week change and a success check. Persist the result, flag changed inputs, validate citations, retain the last successful result on failure, and never change plans as part of analysis.
- Show actual analysis or an explicit invitation to request it; deterministic stock sentences must not masquerade as the deeper review.

## Consolidated visual review acceptance (2026-09-13)

- **FR-009**: Dashboard contains one compact Weekly review entry, not full HEAD COACH and Sunday-review narratives. A dedicated `/weekly-review` page presents This week and Completed weeks views, preserving Sunday history and scheduling.
- **FR-010**: Visualize recorded time allocation by sport with labeled durations and a seven-day session grid linked to source activities. Missing duration remains explicit; allocation is not presented as physiological load, a target, or goal progress. Both dashboard and detail view fit 390px screens.
