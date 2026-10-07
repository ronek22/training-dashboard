#!/bin/bash
# Run the Codex helper as a launchd user agent so it starts at login and comes back if it dies.
# Usage: codex_helper_service.sh install | uninstall
set -euo pipefail

LABEL="com.trainingdashboard.codex-helper"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="gui/$(id -u)"

case "${1:-}" in
  install)
    python="$(command -v python3)"
    # A helper started by hand holds the port; launchd takes over from here.
    "$python" "$ROOT/scripts/codex_planning_helper.py" stop >/dev/null || true
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    mkdir -p "$(dirname "$PLIST")"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python</string>
    <string>$ROOT/scripts/codex_planning_helper.py</string>
    <string>serve</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$(dirname "$python"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <!-- Restart after crashes or kills; a clean stop (just codex-helper-stop) stays stopped. -->
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$ROOT/.codex-planning-helper.log</string>
  <key>StandardErrorPath</key><string>$ROOT/.codex-planning-helper.log</string>
</dict>
</plist>
EOF
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Installed $LABEL ($PLIST)."
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL."
    ;;
  *)
    echo "Usage: $0 install | uninstall" >&2
    exit 2
    ;;
esac
