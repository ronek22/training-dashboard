# Recovery tracking and exercise suggestions

Recovery keeps an issue's symptoms, exercise routines, notes, and archive/reopen events together. The interface uses active and archived lists; resolving an issue records zero symptoms and archives it atomically. Reopening keeps the previous history.

## Exercise selection

The AI selects bounded routines from `backend/app/services/recovery_library.py`, using the affected area, reported symptoms, training context, and prior routines/check-ins. These are general movement suggestions, not diagnosis-specific rehabilitation protocols. Unsupported areas remain trackable; the assistant must not invent catalogue entries or dosage.

Location and symptom intensity are sufficient for the ordinary workflow. The old mandatory screening questionnaire and generic assessment gate are removed. Explicit urgent/emergency reports still prevent routine generation. Unknown answers remain unknown; the app does not fill in negative screening answers.

Saved exercise snapshots and recorded results remain historical records even when the catalogue changes. Current availability checks source-entry versions and area matching. New notes and routine symptom updates do not require repeated confirmation.

## Source references

New upper-back, lower-back, calf and shoulder options were checked against these primary sources on 2026-09-14:

- [NHS sitting exercises](https://www.nhs.uk/live-well/exercise/sitting-exercises/): seated upper-body turn.
- [NHS flexibility exercises](https://www.nhs.uk/live-well/exercise/flexibility-exercises/): side bend and calf stretch.
- [Leeds Teaching Hospitals shoulder exercises](https://www.leedsth.nhs.uk/patients/resources/shoulder-exercises/): stage-one shoulder-blade positioning.

Instructions are paraphrased and linked per exercise. Existing knee, ankle, hip and neck entries retain their original source references. Source attribution is not a claim of independent clinical review.

## Manual acceptance checks

1. Create an issue with an area and symptom score. Confirm it appears under Active without a screening questionnaire.
2. Enable AI sharing and request exercises. Check that the reply completes and the list includes instructions, repetitions and source links. Save the routine.
3. Add a symptom update and describe what helped. Link the completed routine if applicable; refresh and verify both the update and exercises remain.
4. Mark the issue resolved. Verify it moves to Archive with a zero-score update and retains notes and exercises.
5. Use “Symptoms returned” on the archived issue. Verify it returns to Active, retains earlier history, and accepts new updates/exercise requests.
6. Try an unsupported area and an unavailable AI helper. Confirm the app explains the limitation and keeps the issue/history.
7. Check the layout on the devices you use. Browser and mobile checks are intentionally left to the user for this redesign.

Restart the backend to apply the additive status-history schema and restart the AI helper to load the revised prompt. Existing history is preserved; archive/reopen events from before this change cannot be reconstructed.
