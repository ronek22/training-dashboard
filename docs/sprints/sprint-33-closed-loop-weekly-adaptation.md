# Sprint 33: Closed-Loop Weekly Adaptation

## Status

Current status:

- proposed
- follows proposed Sprint 32 planned-vs-actual workout quality

Starting point:

- the app already provides deterministic weekly coaching, plan-diff previews, and explicit approval before write
- recent product work should soon expose readiness, goal-readiness, and execution-quality context
- adaptation logic is still stronger at explaining broad pressure and completion than at protecting key work based on current readiness and session quality

Dependency note:

- Sprint 7 and Sprint 8 created the coaching and approval workflow foundation
- Sprint 17 and Sprint 18 created requirement-aware and template-aware planning behavior
- Sprint 30 through Sprint 32 should produce the extra context this sprint needs
- the next step should use that context to improve recommendation quality without becoming autonomous

## Objective

Improve weekly coaching and adjustment previews so they make clearer, more goal-aware tradeoffs using readiness and execution-quality evidence.

This sprint should move the app from:

- `the app can suggest weekly changes, but tradeoffs are still relatively broad`

to:

- `the app can explain which sessions should be protected, reduced, postponed, or replaced based on readiness, goal gaps, and recent execution quality`

## Why This Sprint

That gap matters because:

- users need more than a generic `adjust the week` recommendation when recovery and goal demands are competing
- strong planning products explain the cost of moving or dropping a session
- hybrid athletes especially need explicit tradeoff language instead of silent prioritization
- this is the point where review intelligence becomes better next-week decisions

## User Story

As an athlete reviewing the current week, I want coaching suggestions to reflect my readiness, goal gaps, and workout execution quality, so proposed changes feel realistic and clearly justified.

## Sprint Scope

### In scope

- readiness-aware and execution-aware weekly coaching recommendations
- clearer session protection and deprioritization logic in adjustment previews
- explicit explanations of how a proposed change affects goals and short-term strain
- no-autowrite continuation of the existing approval flow

### Out of scope

- autonomous plan edits without approval
- long-horizon macrocycle planning automation
- fully free-form AI-driven weekly replanning
- new goal families or deep new settings systems

## Product Outcome

After this sprint:

- weekly coaching recommendations feel more context-aware and specific
- plan adjustment previews can tell the user why a key session is protected or why a lower-value session is being cut
- the user can inspect tradeoffs between recovery, primary goals, and secondary goals more clearly
- the coaching loop becomes more practically useful, not just more verbose

## Proposed Feature Slice

### 1. Better tradeoff logic

Recommended first support:

- protect high-value sessions for the most important goal when readiness allows
- substitute, postpone, or reduce lower-value sessions when readiness is strained
- react differently when a key session was completed poorly versus skipped entirely
- respect strength rotation continuity when hybrid tradeoffs are made

Recommended direction:

- keep the rule set explicit and inspectable
- optimize for believable decisions rather than ambitious optimization

### 2. Richer adjustment explanations

Recommended first support:

- explain the effect of a proposed change on:
  - short-term readiness
  - primary goal support
  - secondary goal maintenance
  - strength continuity where relevant
- distinguish `protected because it matters` from `removed because it is currently lower value`

Recommended direction:

- explanations should stay structured and compact
- one strong reason is better than five weak ones

### 3. Preview integration

Recommended first support:

- show stronger rationale in dashboard coaching summaries and plan-diff review
- preserve the existing approval interaction pattern
- optionally show explicit `tradeoff` or `cost` cues in the diff preview

Recommended direction:

- focus on better preview quality rather than new editing mechanics

## Backend Deliverables

### 1. Adaptation logic upgrades

Likely targets:

- `backend/app/services/coaching.py`
- `backend/app/services/plans.py`

Deliver:

- readiness-aware session prioritization
- execution-quality-aware recommendation branching
- structured tradeoff explanations for preview payloads

### 2. Contract refinements

Likely targets:

- `backend/app/services/coaching.py`

Deliver:

- stable fields for protected sessions, reduced sessions, replacements, and tradeoff notes
- backward-compatible evolution of the current weekly coaching contract where practical

### 3. Coverage

Deliver:

- at least one case where strained readiness reduces lower-value work
- at least one case where a primary-goal session is protected
- at least one case where poor execution changes the next recommendation differently than a missed session

## Frontend Deliverables

### 1. Coaching and diff review visibility

Likely targets:

- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Plan.vue`

Deliver:

- clearer coaching rationale presentation
- tradeoff or cost cues in plan-diff review
- preserved explicit approval workflow

## UX Notes

Recommended first rules:

- never hide the tradeoff behind a generic recommendation label
- explain `why this session moved` in direct language
- keep change previews compact enough to scan quickly
- avoid making the system sound overly authoritative

Recommended first copy direction:

- `Protected for primary goal support`
- `Reduced to lower short-term strain`
- `Maintains strength continuity while preserving run quality`
- `Suggested because the last key session drifted off target`

## Definition Of Done

Sprint 33 should be considered complete when:

- weekly coaching can use readiness and execution-quality context in its recommendations
- plan-diff previews expose clearer tradeoff explanations
- approval-based plan writing remains intact
- at least a few core hybrid tradeoff cases are covered deterministically
