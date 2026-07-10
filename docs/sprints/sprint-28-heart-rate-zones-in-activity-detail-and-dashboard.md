# Sprint 28: Heart-Rate Zones In Activity Detail And Dashboard

## Status

Current status:

- complete
- follows completed Sprint 27 app motion and transition system

Starting point:

- the app already stores explicit zone settings and threshold anchors from Sprint 21
- activity detail can already fetch and cache heart-rate streams through the Strava detail cache
- dashboard and goals already understand some zone-aware concepts, especially around zone 2, but athlete-facing review is still shallow
- an athlete can inspect raw heart-rate charts, but cannot yet see compact time-in-zone summaries per activity or across recent activity history

Implemented outcome:

- activity detail now shows compact heart-rate zone distribution from cached HR and time streams
- dashboard now summarizes recent zone totals with zone-2 emphasis and explicit coverage state
- Strava stream backfill now also populates cached stream detail needed for zone review on previously imported activities
- zone boundaries now follow the documented explicit HR ranges for running and cycling instead of inferred threshold percentages

Dependency note:

- Sprint 21 established the explicit zone foundation the app can trust
- Sprint 23 established on-demand activity detail and cached stream access
- Sprint 28 should turn those foundations into clearer athlete-facing heart-rate zone review before broader coaching or trend logic leans on them more heavily

## Objective

Add trustworthy heart-rate zone summaries to activity detail and dashboard surfaces so one workout and recent training history both show how much work actually happened in each zone, with explicit emphasis on zone 2.

This sprint should move the app from:

- `the app has heart-rate streams and explicit zones, but zone review still requires manual interpretation from charts`

to:

- `the app can summarize heart-rate zone distribution per activity and across recent activities, with zone-2 work clearly visible when data is trustworthy`

## Why This Sprint

That gap matters because:

- athletes doing aerobic-base work need fast visibility into how much zone-2 time they are actually accumulating
- raw heart-rate charts are useful, but too heavy for answering simple review questions such as `was this mostly zone 2?`
- dashboard-level zone summaries are a natural complement to activity detail because one explains a single session and the other explains accumulation
- explicit zones already exist, so the next step should consume them in a conservative, athlete-facing way

## User Story

As an athlete tracking aerobic effort, I want to see heart-rate zone distribution for one activity and across my recent activities, with zone 2 clearly highlighted, so I can quickly judge whether my sessions and weekly load match the work I intended to do.

## Sprint Scope

### In scope

- per-activity heart-rate zone breakdown in activity detail
- dashboard-level recent heart-rate zone summaries aggregated across activities
- explicit emphasis on zone 2 time and share
- conservative availability rules when heart-rate data or zone settings are missing

### Out of scope

- automatic threshold detection or automatic zone recalibration
- pace, power, and heart-rate mixed training-load models
- coaching decisions that automatically rewrite plans based on heart-rate zones
- deep historical reporting beyond the first useful recent summary window

## Product Outcome

After this sprint:

- an activity detail screen can show compact heart-rate time-in-zone distribution when data exists
- dashboard can summarize recent zone totals across multiple activities with zone 2 clearly emphasized
- missing-data states stay explicit instead of guessing or showing misleading totals
- the athlete can inspect both one-session intent and recent zone accumulation without leaving the app

## Proposed Feature Slice

### 1. Activity-detail heart-rate zone breakdown

Recommended first support:

- compute time spent in each heart-rate zone for one activity using cached heart-rate and time streams
- render compact per-zone bars, labels, minutes, and percentage share in activity detail
- explicitly call out zone 2 with stronger visual treatment and a short summary such as `Mostly zone 2` or `Limited zone 2 time`
- degrade cleanly when an activity lacks heart-rate data or time stream data

Recommended direction:

- keep the first per-activity breakdown compact and readable
- use the existing detail view rather than inventing a new analysis surface

### 2. Dashboard recent heart-rate zone accumulation

Recommended first support:

- aggregate recent activity zone totals across a conservative recent window such as last 7, 14, or 28 days
- highlight total zone-2 minutes or hours first, with full zone distribution as supporting context
- optionally separate count of zone-aware activities used in the summary so the athlete can judge confidence
- show explicit unavailable or partial states when too many recent activities lack heart-rate data

Recommended direction:

- the first dashboard read should answer `how much zone 2 have I actually done recently?`
- full zone distribution should support that answer rather than compete with it

### 3. Trust and availability rules

Recommended first support:

- only compute heart-rate zones when cached heart-rate and time streams are available for the relevant activity
- mark activity-level and dashboard-level summaries unavailable when required streams are missing
- expose whether summaries are complete, partial, or unavailable based on how many source activities had usable heart-rate data

Recommended direction:

- avoid hidden fallbacks or inferred zones
- if the system cannot trust the result, it should say so plainly

## Backend Deliverables

### 1. Activity-level zone summary contract

Likely targets:

- `backend/app/services/activities.py`
- `backend/app/services/metrics.py`

Deliver:

- reusable function for computing time-in-zone from activity streams and explicit documented HR zone boundaries
- normalized activity-detail payload fields for per-zone minutes, percentages, and summary state
- clear handling for missing heart-rate stream or missing time stream

### 2. Dashboard zone aggregation contract

Likely targets:

- `backend/app/services/dashboard.py`
- `backend/app/services/activities.py`

Deliver:

- recent aggregated heart-rate zone totals across activities
- explicit summary fields for zone-2 total time, zone-2 share, total eligible activities, and unavailable count
- compact dashboard payload shaped for frontend rendering rather than raw stream inspection

### 3. Coverage

Deliver:

- at least one case where a heart-rate-bearing activity returns usable per-zone detail
- at least one case where missing heart-rate streams keep the read unavailable
- at least one case where dashboard aggregation mixes usable and unusable activities and reports partial coverage explicitly

## Frontend Deliverables

### 1. Activity detail zone section

Likely targets:

- `frontend/src/views/ActivityDetail.vue`

Deliver:

- heart-rate zone summary block in activity detail
- compact distribution bars or cards with minutes and percentages
- stronger visual emphasis for zone 2 without hiding the rest of the distribution
- missing-data messaging when heart-rate zone analysis is unavailable

### 2. Dashboard zone summary

Likely targets:

- `frontend/src/views/Dashboard.vue`

Deliver:

- dashboard card or section for recent heart-rate zone accumulation
- zone-2-first summary with supporting full-zone context
- confidence or coverage note so the athlete knows how many activities contributed to the totals

## UX Notes

Recommended first rules:

- zone 2 should be visually primary, but the full zone breakdown should remain visible
- avoid turning the dashboard into a physiology report; keep the first card compact
- use time and percentage together where useful, because one without the other can mislead
- partial or unavailable states should be obvious and calm, not alarmist

Recommended first copy direction:

- `Zone 2 focus`
- `Recent zone distribution`
- `Based on 6 of 8 recent heart-rate activities`
- `Unavailable until cached heart-rate streams are available`

## Definition Of Done

Sprint 28 should be considered complete when:

- activity detail shows per-activity heart-rate zone summaries when data is available
- dashboard shows recent aggregated heart-rate zone totals with explicit zone-2 emphasis
- missing-data cases are explicit and conservative
- zone computations rely on explicit documented HR ranges rather than implicit guessing
- coverage includes available, unavailable, and partial-coverage cases
