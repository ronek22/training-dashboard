# TrainLog Pocket (iOS)

Native SwiftUI client for the TrainLog backend. Design: `../docs/design/screens/ios/overview.png`.
Rules for agents: `AGENTS.md`.

## Setup

1. Xcode 26+ with the iOS Simulator platform installed.
2. Start the backend on the Mac from the repo root: `docker compose up`. The API listens on
   port 8000.
3. Find the Mac's Wi-Fi address: `ipconfig getifaddr en0`.
4. Open `TrainLog.xcodeproj`, run on a simulator or your iPhone, and enter
   `http://<that-ip>:8000` in Settings (or use "Find on this Wi-Fi").

The Simulator reaches the Mac at `http://localhost:8000` directly.

## On your iPhone

- Free Apple ID signing works, but the app expires after 7 days. `scripts/redeploy-device.sh`
  re-signs and reinstalls it when the profile has under 2 days left and the phone is reachable
  (`FORCE=1` to do it now). To push your latest code to the phone right away, run `just ios`
  from the repo root (`just ios-renew` also renews the profile). A launchd agent runs it every 4 hours:

  ```bash
  cp scripts/com.ronek22.trainlog.redeploy.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ronek22.trainlog.redeploy.plist
  ```

  Log: `~/Library/Logs/TrainLog-redeploy.log`. It builds whatever is checked out in `ios/`.
  A paid developer account ($99/yr) removes the 7-day limit and enables TestFlight.
- The phone and the Mac must be on the same Wi-Fi. Allow the "Local Network" prompt on first
  launch.
- Away from home the app shows cached data and queues new logs. Tailscale is the planned
  upgrade for remote access.
