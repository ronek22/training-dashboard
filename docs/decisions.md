# Decisions

This file records durable project decisions that should influence future work.

## 2026-06-25

### Documentation location

- Planning and decision documents should live under `docs/`.
- Root-level project documentation should stay minimal and point into `docs/`.

### Product direction

- The dashboard should evolve toward a lightweight coaching system.
- Near-term product work should prioritize adaptive planning, feedback loops, and clearer coaching workflows over broad new integrations.

### Planning workflow

- Future roadmaps, sprint plans, and implementation decision records should be saved in `docs/`.
- If a design or product decision is likely to affect later implementation choices, it should be added here.

### Backend architecture direction

- The backend should move away from the single-file `main.py` structure.
- Refactoring should be incremental, behavior-preserving, and organized around routers, services, repositories, models, and shared DB setup.
- Do not introduce heavy abstractions such as generic repositories or DI frameworks unless a real need appears.

### Sprint 3 product focus

- The next product sprint should prioritize the feedback loop over broader goal-planning work.
- Post-workout feedback should attach to activities directly instead of living as a separate date-only journal stream.
- Recovery guidance should start with deterministic and explainable rules before any more advanced scoring approach.
