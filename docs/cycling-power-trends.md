# Cycling power trends

Open **Trends → Cycling power** (`/metrics?view=cycling-power`).

## Saved power profile and coaching advice

Power calculations are saved in the local database and reused across page visits and backend restarts. Changes to cycling activities or their cached power streams invalidate the saved result, so the next visit or **Refresh** recalculates it. This includes a newly synced indoor ride and streams fetched later through backfill. Refreshing unchanged data reuses the cache.

The **What to focus on** panel offers an on-demand Codex review with practical priorities, the evidence behind them, and a way to check progress. Click **Generate advice** with the local Codex helper running. The result is saved; opening the page, navigating away and back, or refreshing never starts AI generation. Unchanged advice is reused, including repeated requests to the helper. When the cycling profile changes, the previous advice stays visible with **Update advice**. Updating is an explicit choice, so each synced ride does not automatically consume tokens.

Advice treats all-time bests, recent efforts, benchmark limitations and missing recordings as context. It does not automatically change your plan. A review based on an outdated snapshot is rejected if the data changes before it can be saved.

The first version shows best sustained power for 5, 15 and 30 seconds, and 1, 2, 5, 10, 20 and 30 minutes, plus monthly bests and per-ride effort comparisons. Select a duration, then choose a reference ride and filter to efforts within ±5% of its power. Heart rate comes from the same interval as the winning power effort; it is not the whole-ride average.

## Data coverage

Ride activities require cached Strava details with `device_watts: true`. VirtualRide activities imported through the explicit `streams_backfill` path also qualify when they contain a cached watts stream; this covers Zwift/KICKR rides whose backfill stored streams without the full detail payload. Indoor classification alone is not proof of measured power. Estimated and unconfirmed outdoor power is excluded.

The page reports analyzed rides and coverage gaps. Use **Data & Sync → Fetch all cycling power** to backfill missing Zwift/indoor cycling streams in batches, then refresh the power tab. Stream backfill considers the full activity history and stops safely at Strava rate limits. Results describe analyzed history, not necessarily every ride in the Strava account until that backfill completes.

Zero watts counts. Missing or invalid power and recording gaps longer than two seconds break continuous efforts. Short recordings cannot yield longer-duration records. Months with no qualifying effort have no chart point. Heart rate is absent when the winning window lacks complete valid HR data.

Heart rate is context, not an automatic fitness verdict: cooling, fatigue, and HR lag affect comparisons. Short sprint HR is particularly limited. Running, activity-detail power records and calendar badges are outside this first version.
