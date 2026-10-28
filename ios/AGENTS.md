# iOS app instructions (TrainLog Pocket)

These rules override the root `AGENTS.md` for anything under `ios/`. The root file's web rules
(Vue, `redesign-multisport`, Vite, frontend tests) do not apply here.

## What this app is

A native SwiftUI client for the existing FastAPI backend in `../backend`. The phone does what
happens away from the desk; planning and deep analysis stay on the web app (MacBook).

MVP scope is the screens in `../docs/design/artboards/iOS.dc.html`
(picture: `../docs/design/screens/ios/overview.png`):

1. Today · 2. Strength session · 3. Food · 4. Quick log sheet · 5. Activities ·
6. Activity detail · 7. Lock screen Live Activity + widgets (phase 2) · 8. Settings ·
9. Plan week · 10. Plan day · 11. Move day sheet

Do not port web-only pages (Trends, Records, Mountains, Season, Goals, Calendar, Plan editor…).
If a feature isn't in the artboard, ask before building it.

## Keep context small

- Work inside `ios/`. Read the backend only to learn an endpoint: grep the route in
  `../backend/app/routers/`, then read that handler and the service function it calls. Never
  read `../frontend/` unless asked to match a web behaviour, and then only the one component.
- Searches: scope them to `ios/` (or a specific `../backend/app/routers/<file>.py`), never the
  whole repo.
- To see a screen's design: read `overview.png` once, then grep `iOS.dc.html` for the frame's
  comment (`<!-- ============ 3. FOOD`) and read only that block for exact values.

## Stack and structure

- Swift 6, SwiftUI, iOS 18+, `@Observable` models, `async/await` + `URLSession`. No third-party
  dependencies unless asked (Swift Charts, MapKit, HealthKit, ActivityKit, WidgetKit are fine).
- Layout (create as the app grows):
  - `TrainLog/App/`: app entry, tab bar, routing
  - `TrainLog/API/`: `APIClient` (one place for base URL, decoding, errors) + `Codable` DTOs
  - `TrainLog/Features/<Screen>/`: one folder per screen (view + view model)
  - `TrainLog/Design/`: tokens (colors, fonts, spacing) and shared components
  - `TrainLogTests/`: unit tests for decoding and view-model logic
  - `TrainLogWidgets/`: widget extension (Home/Lock Screen widgets, strength Live Activity)
  - `Shared/`: code compiled into both the app and the extension (widget snapshot in the
    `group.com.ronek22.trainlog` App Group, Live Activity attributes)
- DTOs mirror backend JSON with `snake_case` keys (use `.convertFromSnakeCase`). Decode only
  fields the app uses; make anything optional that the backend may omit.

## Backend

- Runs on the Mac via Docker (`docker compose up`), API on port **8000**, binds `0.0.0.0`,
  CORS open. No auth: the app is LAN-only for now (home Wi-Fi). Tailscale comes later and only
  changes the base URL.
- Base URL lives in Settings (UserDefaults), default `http://<mac-ip>:8000`. Needs
  `NSAllowsLocalNetworking` (ATS) and `NSLocalNetworkUsageDescription` in Info.plist.
- Endpoints the MVP uses (verify in the router before relying on fields):
  - Today: `GET /dashboard` (large; prefer `GET /widget/today` where it's enough),
    `GET /checkins/today`, `GET /plans/weekly`
  - Strength session: `/strength/workouts/sessions` (`GET /sessions/active`, `POST /sessions`,
    `GET /sessions/{id}`) and `/strength/workouts/templates`
  - Food: `GET /nutrition/food`, `POST /nutrition/food/entries`, `GET /nutrition/dinners`
  - Quick log: `POST /checkins`, `POST /sick-mode`, `POST /activities`
  - Activities: `GET /activities`, `GET /activities/{id}`,
    `GET|POST /activities/{id}/feedback`
  - Plan: `GET /plans/weekly?limit=4`, `POST /plans/weekly/swap`,
    `PUT /recovery/issues/{id}/ticks` (rehab checklist)
  - Apple Health: `POST /integrations/health-data/push` (Shortcut payload format, see
    `../docs/apple-health-shortcut.md`), sent by `Health/HealthSync.swift`
- When the phone needs a lighter or new endpoint, add it to the backend in the same branch,
  with a backend test (`PYTHONPATH="$PWD" backend/.venv/bin/python -m unittest -q
  backend.tests.test_<area>` from the repo root). Don't change existing response shapes the web
  app uses; add fields or a new route instead.
- Offline: cache the last good response per screen; queue writes (check-ins, sets, food) and
  retry when the server is reachable. Show "last synced" rather than an error wall.

## Design

Same system as the web (`../docs/design/REDESIGN.md`, tokens in `../frontend/src/style.css`):

- Dark only. `bg #0A0C11`, card `#12151C`, border `#1C212B`, inset `#0E1117`.
- Sport colors: ride `#3B8CFF`, run `#FF8A2A`, strength `#FF4D9A`, walk/mobility/rehab `#2ED3B0`,
  hike/other `#8B7BFF`.
- Volt `#D4FF3A` is for the ONE primary action per screen and for wins. Secondary actions are
  outline pills. Flat design: no decorative gradients.
- Fonts: Barlow Condensed (numbers, titles; titles italic 800 uppercase), Archivo (body).
  Bundle both. Kickers: 11pt, semibold, tracking .14em, uppercase, muted `#8A93A6`.
- iOS patterns: large titles, bottom tab bar (Today · Plan · + · Food · Activities), sheets for
  quick input, swipe actions on rows, 44pt minimum tap targets, haptics on set logged.

## Build and verify

- Build and run in the iOS Simulator (iPhone 17 Pro, iOS 26; same 393 × 852 pt as the artboard). After a UI change, screenshot the
  simulator and compare with the screen's frame in `overview.png`.
- Run unit tests with `xcodebuild test` (scheme `TrainLog`, simulator destination); pipe
  through `tail`.
- Commit on an `ios-*` branch, one commit per screen or fix. Don't commit `DerivedData`,
  `xcuserdata` or signing files.
