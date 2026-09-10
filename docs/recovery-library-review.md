# Recovery Exercise Release Review

## Current State

The Recovery workflow is implemented, but generated exercises are release-gated. `backend/app/services/recovery_library.py` intentionally contains no approved exercises and no screening review record. There is no user-facing or environment-variable switch that marks unreviewed material approved.

Athletes can already record symptoms, use AI intake conversations, review care guidance, keep check-in history, and opt into sharing compact issue summaries with coaching. The routine-generation, validation, explicit-save, versioning, and follow-up code is present and tested with a test-only entry. It does not prescribe exercises in the shipping configuration.

## Review Required Before Exercise Release

A qualified clinician must review the actual screening questions, routing logic, eligible population, supported presentations, exclusions, and escalation wording. The current warning-sign examples are not a validated screening instrument. A negative screen must never be framed as medical clearance.

The clinician must also review each exercise's instructions, dosage bounds, frequency, stop conditions, contraindications, and supported locations against that screening scope. If suitability needs information not captured by the current intake (for example age, comorbidities, or a particular restriction), add that information and server-side eligibility checks before enabling the entry. Do not rely on an AI prompt to enforce additional contraindications.

Record the review in version-controlled code with:

- reviewer name and qualification;
- actual review date and review-due date;
- an evidence reference to the completed review;
- an incremented exercise version whenever instructions, eligibility, or dose changes.

The `ClinicalReview` and `ReviewedExercise` models define the exact schema. Missing, invalid, future-dated, or expired reviews are excluded. Duplicate IDs invalidate the library. HTTPS source links, explicit normalized location names, and bounded sets/repetitions are required. The current selection contract supports repetition-based exercises; add a reviewed hold-duration contract before adding stretches that require timed holds.

## Candidate Source Material

These public resources may inform a professional review. They are not already-approved library entries, and their publication does not establish suitability for this app's symptom-based selection:

- [NHS sitting exercises](https://www.nhs.uk/live-well/exercise/sitting-exercises/)
- [NHS flexibility exercises](https://www.nhs.uk/live-well/exercise/flexibility-exercises/)
- [NHS post-exercise stretches](https://www.nhs.uk/live-well/exercise/how-to-stretch-after-exercising/)

Consulted on 2026-09-07. No exercise instructions from these pages have been copied into an active prescription library.

## Engineering Verification Before Enabling Entries

Test unanswered and contradictory screening answers, each escalation, newly reported symptoms, outdated replies, withdrawn/expired reviews, unsupported locations, invalid/duplicate exercise IDs, dosage bounds, and stale routine saves. Verify that worsening follow-ups pause saved guidance and that app deletion removes associated data. Run real-model evaluations with clinician-reviewed scenarios before release; deterministic fixture tests verify transport and validation, not the clinical quality of model behavior.

Routine availability is re-evaluated when an issue is read or a draft is saved. A saved routine cannot remain usable after its library entry is withdrawn or its version changes. Historical routines and completion records remain available as history.
