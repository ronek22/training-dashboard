# Apple Health sync with an iOS Shortcut

A free replacement for the Health Data Export automation. A personal Shortcuts
automation writes the last 7 days of recovery data to iCloud Drive; the backend's
existing Health Data Export watcher picks it up (every 15 minutes, or **Data & Sync →
Import now**).

Why it is reliable:

- It runs on an event that happens while the phone is **unlocked** (Health data is
  unreadable while locked, which is why time-of-day automations silently fail).
- Every run re-sends a **rolling 7-day window**, so a missed day is filled in by the
  next run.
- Imports are idempotent: repeated samples are skipped, and daily step/distance totals
  replace the previous total for that day.

## File contract

- Location: the folder in `HEALTH_DATA_EXPORT_DIR` (`iCloud Drive/Health Data Export`).
- Name: must start with `Shortcut` (e.g. `Shortcut_Health.json`); overwrite it each run.
- Content:

```json
{
  "exported_at": "2026-09-28T09:15:00+02:00",
  "resting_hr": [{"start": "…ISO 8601…", "end": "…", "value": "52", "source": "Apple Watch (Jakub)"}],
  "hrv":        [ …same shape… ],
  "weight":     [ …same shape, optional "unit" (kg or lb)… ],
  "sleep":      [ …same shape; value is the stage text, e.g. "Core", "Deep", "REM", "Awake" … ],
  "steps":      [{"start": "2026-09-27T00:00:00+02:00", "value": "11250"}],
  "walking_running_distance": [ …daily, optional "unit" (km or m)… ],
  "flights_climbed": [ …daily… ]
}
```

Every key is optional. Numbers may be strings with a comma decimal separator.
Steps, distance and flights must be **daily totals** (Group By: Day); each day's
total supersedes Health Data Export's 15-minute buckets for that date.

## Building the Shortcut (≈10 minutes)

Create a new shortcut named **Dashboard Health Sync**.

### 1. One block per sample metric

Repeat these four actions for **Resting Heart Rate**, **Heart Rate Variability**,
**Weight** (Body Mass) and **Sleep Analysis**:

1. **Find Health Samples** where *Type* is `<metric>` and *Start Date* is in the last
   `7` days. Sort by Start Date, no limit.
2. **Repeat with Each** item in *Health Samples*. Inside the loop, add a **Text**
   action with exactly:

   ```
   {"start":"[Start Date]","end":"[End Date]","value":"[Value]","unit":"[Unit]","source":"[Source]"}
   ```

   Each `[…]` is the *Repeat Item* variable: tap it and pick the property. For both
   dates set **Date Format → ISO 8601** and turn **Include ISO 8601 Time** on.
3. After **End Repeat**: **Combine Text** *Repeat Results* with *Custom* separator `,`.
4. **Set Variable** `RHR` / `HRV` / `Weight` / `Sleep` to *Combined Text*.

### 2. Steps (daily totals)

Same as above, but in **Find Health Samples** for *Steps* set **Group By → Day**.
The Text inside the loop only needs `{"start":"[Start Date]","value":"[Value]"}`.
Store it in the `Steps` variable. (Optional: repeat for *Walking + Running Distance*
and *Flights Climbed*.)

### 3. Write the file

1. **Text**:

   ```
   {"exported_at":"[Current Date]","resting_hr":[[RHR]],"hrv":[[HRV]],"weight":[[Weight]],"sleep":[[Sleep]],"steps":[[Steps]]}
   ```

   (`[Current Date]` in ISO 8601 with time; the outer `[`…`]` are literal JSON
   brackets around each variable.)
2. **Save File**: Text → turn **Ask Where to Save** off → tap the folder and choose
   `iCloud Drive/Health Data Export` → *Subpath* `Shortcut_Health.json` →
   **Overwrite If File Exists** on.

Run it once by hand and allow Health access for every data type it asks about.

### 4. Automation

Shortcuts → **Automation** → **+** → **App** → pick an app you open every day
(Strava, Messages…) → *Is Opened* → **Run Immediately** → **Dashboard Health Sync**.
Optionally add a second automation on **Charger → Is Disconnected**.

## First run and checks

- To backfill a gap, temporarily change `7` days to cover it (e.g. `14`), run once,
  then set it back.
- After an import, **Data & Sync** lists the file with format `shortcut`. If sleep
  stages are missing, the phone is printing stage names the importer does not know
  yet: the import's `metadata_json.target_counts.unrecognized_sleep_labels` lists
  them so the mapping in `SHORTCUT_SLEEP_LABELS`
  (`backend/app/services/health_data.py`) can be extended.
