# Weekly team contract

GET /coaching/weekly and MCP coach_this_week add team_coaching with all three specialists. Window is current Monday through Warsaw today, independent of plan date. Existing fields remain.

GET /reviews/weekly/context adds historical team_coaching capped at today, without current recovery. Sunday generator receives it; saved review format remains compatible.

GET /coaching/team-analysis returns context_key, week_start, through_date, nullable saved review, stale, facts and evidence labels. GET /coaching/team-analysis/context returns the stable bounded snapshot. PUT validates exactly three distinct specialists, bounded text, known evidence IDs and unchanged snapshot hash; a stale write returns 409 without replacing the last successful review.

Helper POST /team-review queues or reuses an active job. GET /team-review/{id} returns queued/running/succeeded/failed and progress message. Three specialist calls precede head synthesis and one validated save.

Dashboard contains a compact Weekly review entry with a recorded-time chart. `/weekly-review` shows full analysis, source-linked session timing and Plan navigation; `?view=completed` shows saved Sunday history. Reading or generating a review cannot save a plan.
