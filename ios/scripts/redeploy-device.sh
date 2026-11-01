#!/bin/zsh
# Re-sign and reinstall TrainLog on the iPhone and the Apple Watch before the free 7-day profiles
# expire. Run by the launchd agent in scripts/com.ronek22.trainlog.redeploy.plist (see README).
# Does nothing unless a profile expires within RENEW_DAYS (or FORCE=1) and that device is reachable.
# INSTALL=1 (`just ios`) builds and installs now, keeping the current profile, and opens the app.
# The Watch app goes on straight from the Mac, after the phone (a phone install can remove it);
# WATCH=0 skips it.
set -euo pipefail

DEVICE_ID="${DEVICE_ID:-00008140-001E70110A52801C}"
WATCH_ID="${WATCH_ID:-00008310-000F51DE026A601E}"
WATCH="${WATCH:-1}"
APP_ID="${APP_ID:-7LNZV748SW.com.ronek22.trainlog}"
BUNDLE_ID="${APP_ID#*.}"
RENEW_DAYS="${RENEW_DAYS:-2}"
FORCE="${FORCE:-0}"
INSTALL="${INSTALL:-0}"

IOS_DIR="${0:A:h:h}"
PROFILES="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
APP="$IOS_DIR/build/device/Build/Products/Debug-iphoneos/TrainLog.app"
WATCH_APP="$IOS_DIR/build/watch-device/Build/Products/Debug-watchos/TrainLogWatch.app"

log() { print -r -- "$(date '+%F %T') $*"; }
notify() { osascript -e "display notification \"$1\" with title \"TrainLog redeploy\"" >/dev/null 2>&1 || true; }
reachable() { xcrun devicectl list devices 2>/dev/null | grep "$1" | grep -qE "available|connected"; }
epoch() { TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$1" +%s; }
phone_installed=0

# The Watch app, built on its own and installed straight onto the Watch (the iPhone's Watch app
# can't install the embedded copy under free signing). Due when the installed build's profile runs
# out within RENEW_DAYS, the app is missing from the Watch, or the phone was just reinstalled.
renew_watch() {
  [[ "$WATCH" == 1 ]] || return 0
  if ! reachable "$WATCH_ID"; then
    log "Watch: not reachable (it has to be unlocked: on the wrist, near the Mac); will retry"
    return 0
  fi
  local watch_expires=0 watch_bundle="$BUNDLE_ID.watchkitapp" reason=""
  [[ -f "$WATCH_APP/embedded.mobileprovision" ]] && watch_expires=$(epoch \
    "$(security cms -D -i "$WATCH_APP/embedded.mobileprovision" | plutil -extract ExpirationDate raw -)")
  local watch_days=$(( (watch_expires - $(date +%s)) / 86400 ))
  if [[ "$FORCE" == 1 || "$INSTALL" == 1 ]]; then reason="asked"
  elif (( phone_installed )); then reason="the phone was reinstalled"
  elif (( watch_expires == 0 )); then reason="no Watch build here yet"
  elif (( watch_days < RENEW_DAYS )); then reason="profile expires in $watch_days day(s)"
  elif ! xcrun devicectl device info apps --device "$WATCH_ID" 2>/dev/null | grep -q "$watch_bundle"; then
    reason="app missing from the Watch"
  else
    log "Watch: profile valid for $watch_days more day(s), nothing to do"
    return 0
  fi

  # A cached Watch profile close to running out would be reused: move it aside for a fresh one.
  local f plist
  for f in "$PROFILES"/*.mobileprovision(N); do
    plist=$(security cms -D -i "$f" 2>/dev/null) || continue
    [[ "$(plutil -extract Entitlements.application-identifier raw - <<<"$plist" 2>/dev/null)" == "$APP_ID.watchkitapp" ]] || continue
    if (( ($(epoch "$(plutil -extract ExpirationDate raw - <<<"$plist")") - $(date +%s)) / 86400 < RENEW_DAYS )); then
      mv "$f" "$HOME/.Trash/" && log "Watch: moved old profile $(basename "$f") to Trash"
    fi
  done

  # Built for any Watch: the Watch is already in the profile, and building for it by id would need it unlocked.
  log "Watch: building ($reason)"
  if ! xcodebuild -project "$IOS_DIR/TrainLog.xcodeproj" -scheme TrainLogWatch -configuration Debug \
      -destination "generic/platform=watchOS" -derivedDataPath "$IOS_DIR/build/watch-device" \
      -allowProvisioningUpdates -allowProvisioningDeviceRegistration build -quiet; then
    log "Watch: build failed"; notify "Watch build failed — see ~/Library/Logs/TrainLog-redeploy.log"; return 1
  fi
  if ! xcrun devicectl device install app --device "$WATCH_ID" "$WATCH_APP" >/dev/null; then
    # Locked (off the wrist) refuses the install: retried every run, and only flagged on the last day.
    log "Watch: install failed (it has to be unlocked: on the wrist, near the Mac); will retry"
    (( watch_expires > 0 && watch_days < 1 )) && notify "Wear your Watch near the Mac: TrainLog on it expires today"
    return 1
  fi
  local new_exp
  new_exp=$(security cms -D -i "$WATCH_APP/embedded.mobileprovision" | plutil -extract ExpirationDate raw -)
  log "Watch: installed $watch_bundle, profile now expires $new_exp"
  notify "Reinstalled on Apple Watch, valid until ${new_exp%T*}"
}

# Newest cached profile for this app id, and its expiry as epoch seconds. The widget extension
# (APP_ID.widgets) has its own profile issued alongside; it's renewed together with the app's.
profile=""; expires=0; extension_profiles=()
for f in "$PROFILES"/*.mobileprovision(N); do
  plist=$(security cms -D -i "$f" 2>/dev/null) || continue
  app_id=$(plutil -extract Entitlements.application-identifier raw - <<<"$plist" 2>/dev/null)
  # The Watch app's profile is renewed with the Watch (renew_watch).
  [[ "$app_id" == "$APP_ID.watchkitapp" ]] && continue
  if [[ "$app_id" == "$APP_ID".* ]]; then extension_profiles+=("$f"); continue; fi
  [[ "$app_id" == "$APP_ID" ]] || continue
  exp=$(epoch "$(plutil -extract ExpirationDate raw - <<<"$plist")")
  if (( exp > expires )); then profile="$f"; expires=$exp; fi
done

days_left=$(( (expires - $(date +%s)) / 86400 ))
if [[ "$FORCE" != 1 && "$INSTALL" != 1 ]] && (( expires > 0 && days_left >= RENEW_DAYS )); then
  log "profile valid for $days_left more day(s), nothing to do"
  renew_watch
  exit 0
fi

if ! reachable "$DEVICE_ID"; then
  if [[ "$INSTALL" == 1 ]]; then
    log "the iPhone is not reachable: unlock it and keep it on the same Wi-Fi (or plug it in)"; exit 1
  fi
  log "profile expires in $days_left day(s) but the iPhone is not reachable; will retry"
  renew_watch
  exit 0
fi

# Xcode reuses a cached profile until it expires; moving it aside makes it issue a fresh 7-day one.
# A plain install keeps it unless it's about to run out anyway.
if [[ -n "$profile" ]] && { [[ "$INSTALL" != 1 ]] || (( days_left < RENEW_DAYS )); }; then
  for f in "$profile" "${extension_profiles[@]}"; do
    mv "$f" "$HOME/.Trash/" && log "moved old profile $(basename "$f") to Trash"
  done
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
phone_installed=1
renew_watch || true
if [[ "$INSTALL" == 1 ]]; then
  xcrun devicectl device process launch --device "$DEVICE_ID" --terminate-existing "$BUNDLE_ID" >/dev/null \
    && log "opened TrainLog" || log "installed; open TrainLog on the phone"
fi
