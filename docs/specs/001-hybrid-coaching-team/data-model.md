# Data model

Evidence report: version, window (Monday, Sunday, cutoff, timezone, partial), specialists and deterministic head_coach. Specialist: sport, status, nullable totals, baseline, activity evidence, risks, recommendations, limitations and data quality.

AI review: context_key (SHA-256), week_start, through_date, generated_at, three specialists (sport, verdict, assessment, next_week_focus, evidence_ids, uncertainty) and head_coach (headline, verdict, tradeoff, next_week_change, success_check, uncertainty). Stored in existing app_settings under team_analysis:{week_start}. Inputs are hashed; changed inputs reject saves and mark reads stale. No numerical confidence; no plan changes.

Visuals derive from existing specialist duration totals and dated evidence. Missing durations are not filled with inferred values; allocation and session marks never encode a physiological score.
