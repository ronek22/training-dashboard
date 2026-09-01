# Training Dashboard

Personal training dashboard with FastAPI backend, Vue 3 frontend, and MCP server for Claude integration.

See [docs/README.md](docs/README.md) for planning and decision documents, including the [roadmap](docs/roadmap.md).

## Stack

- **Backend**: FastAPI + SQLite (Python)
- **Frontend**: Vue 3 + Vite
- **MCP Server**: Python script that lets Claude push data directly
- **Docker Compose**: One command to run everything

## Quick Start

### 1. Clone / copy this folder to your machine

### 2. Start the dashboard

```bash
docker compose up --build
```

Or use `just` to start it in the background:

```bash
just
```

Use `just up` when you want Docker Compose to remain in the foreground.

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 3. Set up the MCP Server (connect Claude to your dashboard)

Install the MCP dependency:
```bash
cd mcp
pip install -r requirements.txt
```

Add to your Claude Desktop config file:

**Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "training-dashboard": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/training-dashboard/mcp/server.py"]
    }
  }
}
```

Replace `/ABSOLUTE/PATH/TO/` with the actual path. Then restart Claude Desktop.

## ChatGPT Connection

The backend now also exposes the same MCP tools over HTTP at:

```text
http://localhost:8000/mcp
```

Other useful commands:

```bash
just up
just restart
just logs
just down
just test-backend
```

## Backend Testing

The backend now has a lightweight smoke test pass that exercises the modularized app assembly and core routes.

Run it with:

```bash
just test-backend
```

Notes:

- The test command uses a workspace-local dependency directory at `.tmp_test_deps/`.
- The test app uses `TRAINING_DB_PATH` to point SQLite at a temporary test database instead of `/data/training.db`.
- In normal app usage, `TRAINING_DB_PATH` is optional and defaults to `/data/training.db`.

Quick verification before connecting ChatGPT:

```bash
curl http://localhost:8000/mcp
```

Expected shape:

```json
{
  "name": "training-dashboard",
  "version": "1.1.0",
  "endpoint": "/mcp",
  "transport": "jsonrpc-http"
}
```

You can also verify `initialize` manually:

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Notes:

- The existing `mcp/server.py` is still the local `stdio` bridge for Claude Desktop.
- ChatGPT will need the remote HTTPS endpoint, not the local `stdio` script.
- Read tools and write tools are both exposed; ChatGPT can write into the app through MCP once connected.
- The app itself still runs locally on your machine; only the tunnel URL is public.
- With the current setup there is no auth layer on `/mcp`, so use a temporary tunnel only while you need it.

## Moving Claude Chat History

There is no app-level, one-click import from Claude chat history into ChatGPT in this project.

The practical approach is:

1. Export or copy the important Claude thread.
2. Start a new ChatGPT conversation.
3. Paste a project summary or upload the exported text/file as context.
4. Ask ChatGPT to continue from that history.

For this dashboard, the better long-term source of truth is the app itself:

- activities
- metrics
- coach notes
- weekly plans

Once ChatGPT is connected to `/mcp`, it can read those directly instead of relying on old chat history.

## Strava Direct Import

You can import activities straight from Strava through the backend, without using MCP tokens.

### 1. Create a Strava API app

In the Strava API settings, get:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

The backend uses the refresh token to obtain access tokens automatically.

### 2. Provide credentials to Docker

Create a root `.env` file from the example:

```bash
cp .env.example .env
```

Then fill in:

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

Docker Compose reads `.env` automatically. You can still export them in your shell instead if you prefer:

```bash
export STRAVA_CLIENT_ID=your_client_id
export STRAVA_CLIENT_SECRET=your_client_secret
export STRAVA_REFRESH_TOKEN=your_refresh_token
docker compose up --build
```

### 3. Import activities

Date range is optional.

- If you leave dates empty, the backend syncs from the latest stored activity date through today.
- The start date is inclusive, so if you already have one workout on that day and later add another, the next sync still picks it up.
- For the very first import, set a custom start date if you want a historical backfill.

Use the Activities page import form, or call the backend directly:

```bash
curl -X POST http://localhost:8000/integrations/strava/import \
  -H "Content-Type: application/json" \
  -d '{"start_date":"2026-06-01","end_date":"2026-06-22"}'
```

You can also let the backend choose the range automatically:

```bash
curl -X POST http://localhost:8000/integrations/strava/import \
  -H "Content-Type: application/json" \
  -d '{}'
```

Check integration status:

```bash
curl http://localhost:8000/integrations/strava/status
```

Imported activities retain a Strava source reference. Rerunning the same range refreshes the canonical activity, including one first created from HealthFit, instead of duplicating it.

## HealthFit Directory Import

HealthFit can be used as the always-available workout source when Strava API access is unavailable. The backend scans HealthFit's `.fit` backups from a read-only directory mount.

Set the host directory in `.env`:

```env
HEALTHFIT_EXPORT_DIR="/Users/your-name/Library/Mobile Documents/iCloud~com~altifondo~HealthFit/Documents"
```

Then rebuild/restart the services and open **Sync → HealthFit Directory**. Always run the preview before applying an import.

Duplicate protection is deliberately conservative:

- during the first initialization only, files strictly before the latest stored activity date are baselined by filename without opening or importing them;
- cutoff-day files are decoded and linked only when one compatible same-day activity exists;
- only unmatched files newer than the cutoff create activities;
- ambiguous matches are skipped for review;
- every processed file receives a durable HealthFit source reference;
- after initialization, every previously unseen file is parsed regardless of workout date, so late iCloud uploads are not hidden by the cutoff;
- a later Strava import attaches its Strava ID to a uniquely compatible HealthFit activity instead of inserting another activity.

The iCloud directory is mounted read-only at `/healthfit`. If macOS has evicted a recent FIT file from local storage, download it in Finder before scanning again.

## Dashboard Pages

| Page | Description |
|------|-------------|
| **Dashboard** | 14-day overview, recent runs/rides, Z2 pace trend, coach notes |
| **Plan** | Weekly workout plans prepared by Claude, shown day by day |
| **Calendar** | Weekly calendar view with daily activities, hours, distance, and elevation |
| **Activities** | Full activity log with filters by type |
| **Trends** | Overview plus focused Load, Recovery, Daily activity, Weight, and FTP views with personal-baseline charts |
| **Coach Notes** | All coaching observations categorized by topic |

## What Claude Can Push via MCP

Once the MCP server is connected, Claude can:

- **Log activities** — runs, rides, strength sessions from Strava analysis
- **Read dashboard activity history** — activities, stats, notes, plans, and calendar summaries directly from your app
- **Read compact coaching context** — one bundled MCP tool for recent load, latest activities, notes, metrics, streak, weekly mix, and active plan
- **Add coach notes** — observations about HR, pacing, fatigue, heel pain
- **Log metrics** — Z2 pace benchmarks, FTP, weight, resting HR, streak count, heel pain level
- **Update weekly summaries** — total km, elevation, sessions per week
- **Save weekly plans** — structured day-by-day workout weeks directly into the dashboard
- **Adjust weekly plans** — patch only the remaining days of the current week while preserving past or already completed sessions

### Example — ask Claude in this chat:

> "Log today's run to my dashboard and add a note about Zone 2 progress"

> "Log my latest FTP test and use it as my cycling threshold"

> "Add a coach note about the heel recovery progress"

> "Look at my completed workouts so far this week and adjust the rest of my weekly plan"

## HR Zone Reference (stored in dashboard)

| Zone | Running HR | Cycling HR |
|------|-----------|------------|
| Z1 recovery | <150 | <140 |
| **Z2 aerobic** | **150–162** | **140–152** |
| Z3 tempo | 163–172 | 153–162 |
| Z4 threshold | 173–182 | 163–172 |
| Z5 max | 183+ | 173+ |

## Data Storage

SQLite database stored in `./data/training.db` — persists across container restarts.

## Consistency And Legacy Streak Logic

The primary Trends experience uses planned sessions fulfilled, adapted, or missed across recent weeks. This respects intentional rest days and is more useful than rewarding consecutive training days.

### Apple Health Data Export

The backend can read raw JSON files produced by the iOS Health Data Export app from an iCloud Drive directory mounted read-only into the container. Set `HEALTH_DATA_EXPORT_DIR` in `.env`; the backend checks for new files on startup and every 15 minutes by default. **Data & Sync** also provides preview and immediate-import controls. The importer streams large files instead of loading them into memory and safely skips both already-processed files and overlapping samples in later daily exports. Set `HEALTH_DATA_AUTO_IMPORT=false` to disable the background check or adjust `HEALTH_DATA_IMPORT_INTERVAL_SECONDS` when needed.

The selective import covers sleep stages, resting heart rate, HRV, body weight, steps, walking/running distance, and flights climbed. Apple sleep category codes are normalized into core, deep, REM, awake, and unspecified sleep, and overlapping sleep providers are resolved to one nightly source. Raw all-day heart-rate samples and HealthKit workout records remain in the source export; HealthFit and cached run/ride streams stay authoritative for workouts and training-zone distribution.

The backend can still compute the legacy consecutive-day streak for compatibility and compact context:

- Any activity type counts toward the streak.
- If your latest activity was `today` or `yesterday`, the streak is considered active.
- If the latest activity is older than yesterday, the current streak shows `0 days`.

## Development

Backend hot-reloads automatically. For frontend changes:
```bash
docker compose up
```
Changes to `frontend/src/` reflect immediately.

To reset all data:
```bash
rm -rf data/
docker compose up
```
