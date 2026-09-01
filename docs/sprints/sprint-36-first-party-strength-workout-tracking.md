# Sprint 36: First-Party Strength Workout Tracking

## Status

- completed
- follows the retrospective Fitbod strength import and analytics foundation

## Objective

Let the athlete define reusable strength workouts, perform them set by set in TrainLog, and attach a separately recorded Apple Watch activity after HealthFit imports it.

## Delivered

- Activity Detail now resolves an explicitly linked TrainLog session before falling back to Fitbod enrichment, so completed first-party sets, repetitions, and loads appear alongside Apple Watch heart-rate and calorie data.

- reusable workout templates with ordered exercises
- per-exercise targets for sets, repetitions, weight, rest duration, and notes
- a live session runner that snapshots the template so later template edits do not rewrite history
- actual repetition and load capture per set
- rest countdowns based on durable timestamps
- manual switching between exercises and sets without discarding incomplete work
- prevention of multiple simultaneous active strength sessions
- completed and abandoned session history
- post-workout candidate matching to imported `WeightTraining` and `Workout` activities within two days
- explicit Apple Watch activity attachment and unlinking
- linked activity summaries for duration, average heart rate, maximum heart rate, and calories
- exercise autocomplete across imported Fitbod and first-party TrainLog history
- opt-in set, rep, and weight targets derived from the latest recorded work sets
- live session exercise additions with the same history search and target suggestions
- an optional two-tone audible cue when a rest countdown finishes
- a responsive Workout Studio redesign with a focused workout library, compact session log, and quieter template management actions

## Data Boundary

The first-party session owns exercise structure and performed sets. The imported Apple Watch/HealthFit activity remains the source of truth for physiological and device-recorded data. Linking connects the two records without copying heart-rate streams or creating a second activity.

## Deliberate Follow-Ups

- automatic match suggestions using start-time and duration confidence once imported activity timestamps are normalized consistently
- direct watch companion controls and mirrored rest timers
- per-set RPE, warm-up sets, supersets, and exercise substitutions
- inclusion of first-party sessions in the cross-session progression analytics currently based on Fitbod history
- richer linked heart-rate charts inside the completed session review
