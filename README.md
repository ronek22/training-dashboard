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

Or use the Makefile:

```bash
make up
```

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

That endpoint is for remote MCP clients such as ChatGPT once you expose it through HTTPS.

Practical setup:

1. Run the app locally with Docker.
2. Expose `http://localhost:8000` through a tunnel such as ngrok or Cloudflare Tunnel.
3. In ChatGPT developer mode, connect the public `https://.../mcp` URL.

Example with ngrok:

```bash
make chatgpt
```

That one command:

1. starts Docker Compose in the background
2. starts an ngrok tunnel to `localhost:8000`
3. lets you copy the HTTPS tunnel URL for ChatGPT

Then take the HTTPS forwarding URL from ngrok, for example:

```text
https://abc123.ngrok-free.app
```

and use this MCP endpoint in ChatGPT:

```text
https://abc123.ngrok-free.app/mcp
```

### Use a static ngrok URL

ngrok supports a fixed dev-domain URL. As of the ngrok blog update on January 8, 2026, every ngrok account gets one automatically assigned free dev domain on `ngrok-free.dev`, and you can use it with the CLI by passing `--url`.

Find your dev domain in the ngrok dashboard under `Gateway > Domains`, then start the tunnel like this:

```bash
NGROK_URL=https://your-domain.ngrok-free.dev make chatgpt
```

or:

```bash
NGROK_URL=https://your-domain.ngrok-free.dev make tunnel
```

Then use:

```text
https://your-domain.ngrok-free.dev/mcp
```

Notes:

- On free accounts, the dev domain is assigned automatically; you cannot choose the hostname.
- If `NGROK_URL` is not set, the Makefile keeps the old behavior and starts a random public URL.
- If you want a chosen `*.ngrok.app` hostname or your own custom domain, that requires a paid ngrok plan.
- The `Makefile` now loads root `.env`, so you can store `NGROK_URL=https://your-domain.ngrok-free.dev` there and just run `make chatgpt`.

Other useful commands:

```bash
make up-detached
make tunnel
make logs
make down
make test-backend
```

## Backend Testing

The backend now has a lightweight smoke test pass that exercises the modularized app assembly and core routes.

Run it with:

```bash
make test-backend
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

Imported activities are upserted by Strava activity ID, so rerunning the same range will refresh existing records instead of duplicating them.

## Dashboard Pages

| Page | Description |
|------|-------------|
| **Dashboard** | 14-day overview, recent runs/rides, Z2 pace trend, coach notes |
| **Plan** | Weekly workout plans prepared by Claude, shown day by day |
| **Calendar** | Weekly calendar view with daily activities, hours, distance, and elevation |
| **Activities** | Full activity log with filters by type |
| **Metrics** | Personal metrics trends (weight, Z2 pace, FTP, heel pain, streak) |
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

> "Update my streak metric to 170 days"

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

## Streak Logic

The sidebar streak is computed automatically from consecutive calendar days with at least one logged activity.

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
