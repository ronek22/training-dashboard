# Codex project instructions

The root agent owns architecture, decomposition, integration, and final verification.
Prefer specialized subagents for bounded exploration, implementation, testing, review, and technical research.

Do not delegate trivial work merely for parallelism.
Do not let multiple implementation agents edit the same files without explicit ownership boundaries.
User instructions always take precedence over this orchestration policy.

## UI redesign

For any frontend/UI work, follow `docs/design/REDESIGN.md` and match the page's artboard screenshot in `docs/design/screens/`. Work on branch `redesign-multisport`.
