# Training Dashboard Roadmap V2

## Purpose

This roadmap is the active product and engineering plan for the next growth stage of the dashboard.

It is intentionally pragmatic:

- prioritize features that materially improve planning and coaching quality
- keep changes aligned with the current FastAPI + SQLite + Vue architecture
- prefer inspectable, deterministic product behavior over opaque automation

## Current State

The app already supports:

- activity history and filtering
- Strava import
- personal metrics
- coach notes
- weekly plans
- plan vs completed comparison
- goal visibility, forecasting, and planning pressure
- modality restrictions and restriction-aware coaching
- MCP read/write access for ChatGPT and Claude
- one-shot weekly coaching plus explicit plan-diff approval

Current implementation status:

- roadmap V1 is complete as the first coaching-workflow foundation
- the app can already compare planned vs completed work, explain weekly pressure, and propose deterministic adjustments
- explicit athlete modeling is now in place, but richer goal modeling is still shallow
- goals are still mostly accumulation-based rather than performance-based or process-based
- MCP context is useful and now includes a durable athlete brief, but richer goal meaning is still too limited

The main gap is that the app now understands the athlete better than it understands the athlete's goals.

## Product Direction

Target outcome:

1. know who the athlete is and what they are optimizing for
2. support richer goal types without collapsing into a generic free-form blob
3. track progress using rules that match the goal type
4. make weekly planning and coaching explicitly reflect those goals and constraints
5. expose the same context cleanly to MCP and chat surfaces

That implies four product pillars for this roadmap generation:

- athlete model
- richer goals
- goal-aware planning
- structured coaching context

## Priority Order

## Phase 6: Model The Athlete And Goals More Explicitly

Goal: stop treating athlete context and goals as lightweight metadata when they now drive planning quality.

### 20. Athlete profile and planning preferences

Why:

- coaching quality is capped when the app has to infer whether the athlete is endurance-focused, hybrid, strength-biased, or general fitness oriented
- chat and MCP guidance becomes more reliable when it can read a stable athlete brief instead of reconstructing one from scattered rows
- some weekly decisions depend more on training context than on any single goal

Scope:

- add a persisted athlete profile with fields like:
  - primary focus such as `endurance`, `hybrid`, `strength`, or `general_fitness`
  - preferred modalities and secondary modalities
  - current season or emphasis block
  - weekly availability or preferred long-session days
  - free-form planning notes for important context
- expose this profile in app reads and MCP/context reads
- keep the first version lightweight and editable

Implementation notes:

- likely starts in `backend/app/services/settings.py` and `backend/app/repositories/settings.py`
- the first storage shape can stay settings-backed rather than requiring a new deep profile model
- the frontend surface can begin as a compact profile card or modal rather than a large settings system

Recommended Sprint 15 role:

- implemented as the athlete-context foundation sprint

### 21. Richer goal definitions

Why:

- current goals are useful for totals, but they do not represent many real athlete targets
- runners and cyclists often care about performance benchmarks or process targets, not just raw totals
- richer goals are necessary before planning can become meaningfully goal-type aware

Scope:

- support multiple goal families such as:
  - accumulation goals like total distance, time, or activity count
  - event-performance goals like `run 10k under 40 minutes`
  - benchmark goals like `hold 300W for 10 minutes`
  - process goals like `spend 6 hours per week in Z2`
  - frequency goals like `lift twice per week`
- add structured goal fields rather than storing arbitrary prose as the canonical source of truth
- keep creation and editing understandable in the UI

Implementation notes:

- this likely requires expanding `backend/app/models/goals.py`, `backend/app/repositories/goals.py`, and `backend/app/services/goals.py`
- the first schema should be explicit enough to validate and forecast, but not so abstract that every goal becomes a mini programming language
- the UI should steer users into a few supported goal templates instead of a fully generic builder

Recommended Sprint 16 role:

- this should follow athlete profile work once stable context exists

### 22. Goal-specific progress engines and forecasts

Why:

- once richer goal types exist, one progress formula is no longer enough
- a `sub-40 10k` goal should not be evaluated like a `6 hours of Z2 per week` goal
- coaching trust depends on forecasts that match what the goal actually means

Scope:

- add goal-family-specific evaluation and forecast rules
- support concepts such as:
  - best effort or benchmark achievement for performance goals
  - rolling weekly totals for process goals
  - target-date readiness and gap summaries for event goals
  - frequency completion for habit goals
- expose clearer risk states and `what matters next` summaries

Implementation notes:

- likely centered in `backend/app/services/goals.py`
- reuse existing goal-risk and planning-guidance contracts where possible instead of replacing them
- stay deterministic and explainable even if the calculations become more specialized

Recommended Sprint 16 role:

- this should be the secondary slice after richer goal definitions exist

## Phase 7: Make Planning Truly Goal-Type Aware

Goal: make weekly planning reflect the actual demands of the athlete's goal mix rather than only broad modality pressure.

### 23. Goal-to-session requirement mapping

Why:

- richer goals only matter if the plan can translate them into relevant session types
- the app should understand that a 10k performance goal, a Z2 volume goal, and a strength-frequency goal imply different weekly structure

Scope:

- map goal families to session requirements and preferred weekly patterns
- show which planned sessions contribute to which goal requirements
- surface missing goal-supporting work more explicitly in Plan and Dashboard

Implementation notes:

- likely spans `backend/app/services/plans.py`, `backend/app/services/goals.py`, and `backend/app/services/coaching.py`
- start with conservative mappings and explicit rationale instead of trying to auto-generate perfect training theory

Recommended Sprint 17 role:

- this should be the first planning-upgrade sprint after richer goals exist

### 24. Hybrid priority and conflict management

Why:

- hybrid athletes often have competing demands across running, riding, and strength
- the app should tell the truth when goals compete instead of treating all pressure as equally actionable

Scope:

- allow explicit priority ordering across goals or modalities
- surface conflicts such as:
  - run-performance goal vs lower-body strength fatigue
  - cycling volume goal vs limited weekly availability
  - process-goal overload across too many modalities
- make constrained or deprioritized goals visible rather than silently ignored

Implementation notes:

- likely spans `backend/app/services/goals.py`, `backend/app/services/coaching.py`, and `frontend/src/views/Goals.vue`
- this should build on the existing constrained-goal pattern instead of inventing a separate conflict model from scratch

Recommended Sprint 17 role:

- this should be the second slice in the same planning-quality phase

### 25. Goal-aware week generation and adjustment

Why:

- the app can currently coach around the week, but it still does not shape the week deeply from goal requirements
- once athlete profile and richer goals exist, weekly adjustments should reflect those structures directly

Scope:

- use athlete focus, goal family, and goal priority in weekly coaching previews
- improve week adjustment suggestions so they protect key requirements and deprioritize lower-value work
- explain how a changed session affects goal progress

Implementation notes:

- likely centered in `backend/app/services/coaching.py` and `backend/app/services/plans.py`
- the first slice should remain recommendation-oriented and approval-based, not autonomous

Recommended Sprint 18 role:

- this should close the goal-aware planning phase

## Phase 8: Improve Coaching And MCP Context

Goal: reduce prompt reconstruction and make chat guidance use richer structured context by default.

### 26. Deterministic athlete brief for MCP

Why:

- chat quality improves when the model gets one compact, durable athlete brief instead of several fragmented reads
- this becomes more important once profile, richer goals, restrictions, and recent patterns all matter together

Scope:

- expose one structured MCP/context payload that combines:
  - athlete profile
  - active goals with goal-family-specific progress summaries
  - modality restrictions
  - recent execution and recovery summary
  - current planning risks and priorities
- keep the payload deterministic and compact

Implementation notes:

- likely spans `backend/app/services/mcp.py`, `backend/app/services/dashboard.py`, and `backend/app/services/goals.py`
- this should package existing reads rather than creating a second source of truth

Recommended Sprint 19 role:

- this should be the first post-planning sprint now that Sprint 18 closed the goal-aware planning phase

### 27. Goal-aware coaching explanations

Why:

- users should be able to see why a recommendation helps a specific goal
- richer goals and hybrid priorities are only trustworthy if the app can explain the tradeoff clearly

Scope:

- make coaching rationale explicitly reference athlete focus, goal type, and priority
- distinguish:
  - work that advances the primary goal
  - work that maintains a secondary goal
  - work that is being reduced because of restriction, fatigue, or conflict
- surface these explanations in Dashboard, Plan, and MCP responses

Implementation notes:

- likely centered in `backend/app/services/coaching.py`
- explanations should stay short, structured, and tied to deterministic inputs

Recommended Sprint 19 role:

- this should pair naturally with the deterministic athlete brief work in the same sprint

### 28. Natural-language goal capture into structured drafts

Why:

- users often think in natural language first, even if the saved goal should stay structured
- this can make advanced goal creation more practical without making the data model vague

Scope:

- accept natural-language goal ideas and convert them into structured draft goals
- require explicit user review before save
- support examples like:
  - `run 10k in under 40 minutes by October`
  - `hold 300W for 10 minutes`
  - `do 6 hours of Z2 riding per week`

Implementation notes:

- the generated draft should map into the same goal schema used for manual creation
- this can begin as an MCP-oriented helper before a full in-app wizard exists

Recommended Sprint 20 role:

- this should follow once Sprint 19 has cleaned up coaching context packaging and explanation structure

## Phase 9: Build Better Performance Data Foundations

Goal: support advanced goals and coaching with better derived training signals, not just raw imported activities.

### 29. Derived performance metrics and best efforts

Why:

- performance goals need benchmark signals the app does not currently compute explicitly
- power, pace, and duration benchmarks should become first-class reads rather than ad hoc interpretation

Scope:

- derive and store compact best-effort or benchmark summaries where practical
- support examples like:
  - best recent 5k / 10k run
  - best recent 10-minute power
  - recent longest Z2 block
- expose these as reusable backend reads

Implementation notes:

- likely starts in `backend/app/services/activities.py`, `backend/app/services/metrics.py`, and `backend/app/services/goals.py`
- keep storage additive and compact rather than building a large sports-science engine immediately

Recommended Sprint 21 role:

- this should be the first Phase 9 data-foundation sprint after the Phase 8 context work lands

### 30. Zones and threshold management

Why:

- process goals like `6 hours in Z2` require stable definitions of zones or threshold references
- the app should not guess these implicitly from untrusted data

Scope:

- support user-defined or imported training zones and threshold anchors
- expose which goals or sessions depend on those definitions
- use them conservatively in goal evaluation and coaching summaries

Implementation notes:

- likely spans `backend/app/services/settings.py`, `backend/app/services/goals.py`, and `frontend/src/views/Goals.vue`
- manual-first support is acceptable before any automated detection work

Recommended Sprint 21 role:

- this should pair naturally with derived metrics in the same sprint if scope stays tight, otherwise become the first split candidate

### 31. Benchmark sessions and test-result visibility

Why:

- some advanced goals improve when the app can intentionally schedule or recognize benchmark efforts
- users need a clean way to see whether they are actually improving in the dimension they care about

Scope:

- support benchmark or test-session tagging
- show benchmark history and changes over time
- connect benchmark results back to performance-oriented goals

Implementation notes:

- likely spans `backend/app/services/plans.py`, `backend/app/services/activities.py`, and `frontend/src/views/Plan.vue`
- this should start as a lightweight tagging and summary layer, not a full periodization engine

Recommended Sprint 22 role:

- this should close the initial performance-data foundation phase

## Cross-Cutting Engineering Track

Goal: keep the next roadmap sustainable as schemas and coaching rules become more specialized.

### 32. Deeper coverage for goal and coaching contracts

Why:

- richer goals and athlete context will increase branching and edge cases quickly
- the current smoke-heavy coverage is not enough for confident evolution of goal-family-specific logic

Scope:

- add focused service-level coverage for goals, planning, and coaching behavior
- lock down structured response contracts that MCP and frontend both depend on
- prioritize tests around forecasts, conflicts, and structured goal parsing

Implementation notes:

- likely centered in `backend/tests/test_app_smoke.py` first, then more focused service-level tests if the repo needs them

## Suggested Build Sequence

This is the recommended implementation order:

1. Athlete profile and planning preferences
2. Richer goal definitions
3. Goal-specific progress engines and forecasts
4. Goal-to-session requirement mapping
5. Hybrid priority and conflict management
6. Goal-aware week generation and adjustment
7. Deterministic athlete brief for MCP plus goal-aware coaching explanations
8. Natural-language goal capture into structured drafts
9. Derived performance metrics and best efforts
10. Zones and threshold management
11. Benchmark sessions and test-result visibility

## Recommended Next Sprint

If only one sprint is available, do this:

### Sprint Goal

Start with Sprint 21 derived performance metrics and zones foundation.

### Scope

- add derived performance metrics that summarize recent capability from stored activities
- establish zones-oriented foundations that later benchmark and coaching features can reuse
- keep the derived layer deterministic and reusable across dashboard, goals, and coaching flows
- make the profile useful for coaching without waiting for richer goal families

Current interpretation:

- the next highest-value gap is not another coaching surface, but better durable athlete context
- richer goals will be more useful if profile, priorities, and planning notes already exist
- this is the cleanest way to improve both in-app planning and MCP chat quality at the same time

### Definition of done

- the user can persist and edit an athlete profile
- dashboard and MCP reads expose the profile in a compact structured way
- coaching can reference athlete focus and planning notes without relying on prompt reconstruction alone

## Risks And Constraints

- do not turn goals into an unbounded generic schema that is impossible to validate
- keep richer goal families template-driven and explicit
- avoid building a large sports-science engine before the product proves which advanced metrics matter most
- preserve approval-based plan changes instead of introducing autonomous rewrites

## Out Of Scope For Now

These ideas are reasonable but should wait:

- social competition or public sharing
- third-party wearable expansion beyond what current integrations justify
- automatic threshold detection from raw files as a first step
- ML-heavy performance prediction
- fully autonomous training plans with no user review

## Working Principle

When choosing between features, prefer the one that:

1. makes athlete intent more explicit
2. improves weekly planning or coaching quality in a way the user can inspect
3. keeps structured data usable across UI, backend, and MCP
4. avoids overgeneralizing before real product patterns are visible
