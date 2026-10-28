#!/bin/zsh
# Re-sign and reinstall TrainLog on the iPhone before the free 7-day profile expires.
# Run by the launchd agent in scripts/com.ronek22.trainlog.redeploy.plist (see README).
# Does nothing unless the profile expires within RENEW_DAYS (or FORCE=1) and the phone is reachable.
# INSTALL=1 (`just ios`) builds and installs now, keeping the current profile, and opens the app.
set -euo pipefail

DEVICE_ID="${DEVICE_ID:-EA4E024D-F96E-51F5-841B-04DDF2CC2B49}"
APP_ID="${APP_ID:-7LNZV748SW.com.ronek22.trainlog}"
BUNDLE_ID="${APP_ID#*.}"
RENEW_DAYS="${RENEW_DAYS:-2}"
FORCE="${FORCE:-0}"
INSTALL="${INSTALL:-0}"

IOS_DIR="${0:A:h:h}"
PROFILES="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
APP="$IOS_DIR/build/device/Build/Products/Debug-iphoneos/TrainLog.app"

log() { print -r -- "$(date '+%F %T') $*"; }
notify() { osascript -e "display notification \"$1\" with title \"TrainLog redeploy\"" >/dev/null 2>&1 || true; }

# Newest cached profile for this app id, and its expiry as epoch seconds.
profile=""; expires=0
for f in "$PROFILES"/*.mobileprovision(N); do
  plist=$(security cms -D -i "$f" 2>/dev/null) || continue
  [[ $(plutil -extract Entitlements.application-identifier raw - <<<"$plist" 2>/dev/null) == "$APP_ID" ]] || continue
  exp=$(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$(plutil -extract ExpirationDate raw - <<<"$plist")" +%s)
  if (( exp > expires )); then profile="$f"; expires=$exp; fi
done

days_left=$(( (expires - $(date +%s)) / 86400 ))
if [[ "$FORCE" != 1 && "$INSTALL" != 1 ]] && (( expires > 0 && days_left >= RENEW_DAYS )); then
  log "profile valid for $days_left more day(s), nothing to do"
  exit 0
fi

if ! xcrun devicectl list devices 2>/dev/null | grep "$DEVICE_ID" | grep -q "available"; then
  if [[ "$INSTALL" == 1 ]]; then
    log "the iPhone is not reachable: unlock it and keep it on the same Wi-Fi (or plug it in)"; exit 1
  fi
  log "profile expires in $days_left day(s) but the iPhone is not reachable; will retry"
  exit 0
fi

# Xcode reuses a cached profile until it expires; moving it aside makes it issue a fresh 7-day one.
# A plain install keeps it unless it's about to run out anyway.
if [[ -n "$profile" ]] && { [[ "$INSTALL" != 1 ]] || (( days_left < RENEW_DAYS )); }; then
  mv "$profile" "$HOME/.Trash/" && log "moved old profile $(basename "$profile") to Trash"
fi

log "building $(git -C "$IOS_DIR" rev-parse --abbrev-ref HEAD)@$(git -C "$IOS_DIR" rev-parse --short HEAD)"
if ! xcodebuild -project "$IOS_DIR/TrainLog.xcodeproj" -scheme TrainLog -configuration Debug \
    -destination "platform=iOS,id=$DEVICE_ID" -derivedDataPath "$IOS_DIR/build/device" \
    -allowProvisioningUpdates build -quiet; then
  log "build failed"; notify "Build failed — see ~/Library/Logs/TrainLog-redeploy.log"; exit 1
fi

if ! xcrun devicectl device install app --device "$DEVICE_ID" "$APP" >/dev/null; then
  log "install failed"; notify "Install failed — is the iPhone unlocked and on Wi-Fi?"; exit 1
fi

new_exp=$(security cms -D -i "$APP/embedded.mobileprovision" | plutil -extract ExpirationDate raw -)
log "installed $BUNDLE_ID, profile now expires $new_exp"
notify "Reinstalled on iPhone, valid until ${new_exp%T*}"
if [[ "$INSTALL" == 1 ]]; then
  xcrun devicectl device process launch --device "$DEVICE_ID" --terminate-existing "$BUNDLE_ID" >/dev/null \
    && log "opened TrainLog" || log "installed; open TrainLog on the phone"
fi
