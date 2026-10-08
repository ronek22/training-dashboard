# TrainLog on iPhone (same Wi-Fi)

TrainLog can run as a Home Screen web app. The existing Mac database remains the
source of truth. This setup needs no Apple developer account, app signing, public
hosting, or tunnel.

## Start it

1. Start Docker Desktop or OrbStack on the Mac.
2. Find the Mac's Wi-Fi IP in **System Settings → Wi-Fi → Details → TCP/IP**.
   For example, `192.168.1.42`. Reserve that address for the Mac in your router's
   DHCP settings if you want the Home Screen icon to keep working after reconnects.
3. From the project directory, run (substitute your actual address):

   ```sh
   just phone 192.168.1.42
   ```

   Without `just`:

   ```sh
   TRAINLOG_LAN_IP=192.168.1.42 docker compose -f docker-compose.yml -f docker-compose.phone.yml up -d --build backend phone
   ```

4. Connect the iPhone to the same Wi-Fi and open `http://192.168.1.42:3080` in Safari.
5. Tap **Share → Add to Home Screen → Add**. Enable **Open as Web App** if shown.

The phone service serves a production build and proxies `/api` to the backend.
Run the same command after code changes to rebuild it. The existing development
frontend on port 3000 is independent. Phone navigation appears at widths up to
640px; wider screens retain the desktop navigation.

## Everyday use

- **Today** opens the dashboard, including today's session and training summaries.
- **Plan** shows the weekly plan and session details.
- **Trends** opens the existing trends views.
- **More** provides access to the other pages and installation instructions.
- The coach drawer, dashboard coach refresh, and automatic weekly planning are
  available through `localhost` on the Mac. Other advanced pages may also rely
  on Mac-only helpers; the phone experience focuses on Today, Plan, and Trends.

Keep the Mac awake, Docker running, and both devices on the same network. A guest
Wi-Fi network may block communication between devices. If Safari cannot connect,
check the IP, Docker, and macOS firewall access for your container runtime.

The phone server binds to the Wi-Fi IP you supply. Do not add router port
forwarding or a public tunnel. Devices able to reach that address can access the
app; the app does not currently have a login. This is local-network access, not
an identity check or a check of the Wi-Fi network name. Existing backend and dev
frontend port bindings are controlled by the base Compose file.

## Home Screen widget

A large Home Screen widget shows today's session, the readiness level with its
top reasons, a morning check-in nudge, the week's progress, and tomorrow's session.
It works away from home Wi-Fi: the backend writes a small file to iCloud Drive
and the free **Scriptable** app draws the widget from it.

```
backend (every 15 min, after the Health import)
  → iCloud Drive/TrainLog/trainlog-today.json
  → Scriptable widget on the iPhone
```

### On the Mac

1. In `.env`, point the widget folder at iCloud Drive (quotes are needed because
   of the space):

   ```sh
   TRAINLOG_WIDGET_DIR="/Users/<you>/Library/Mobile Documents/com~apple~CloudDocs/TrainLog"
   ```

2. Recreate the backend so it picks up the folder (it is created if missing):

   ```sh
   docker compose up -d backend
   ```

3. Within a minute `iCloud Drive/TrainLog/trainlog-today.json` appears. The same
   data is at `http://localhost:8000/widget/today` for checking.

### On the iPhone

1. Install **Scriptable** from the App Store.
2. In Scriptable, tap **+**, name the script **TrainLog Today**, and paste in
   [`iphone-widget.js`](iphone-widget.js) (AirDrop it, or open the file from the
   repository in iCloud/Files and copy it).
3. Scriptable → **Settings → File Bookmarks → +** → pick the `TrainLog` folder in
   iCloud Drive → name it exactly `TrainLog`.
4. Run the script once in Scriptable: it previews the large widget.
5. Long-press the Home Screen → **Edit → Add Widget → Scriptable** → the **large**
   size → **Add Widget**. Long-press it → **Edit Widget**:
   - **Script**: TrainLog Today
   - **When Interacting**: Open URL
   - **Parameter**: the phone app address, e.g. `http://192.168.1.42:3080`
     (optional; tapping then opens TrainLog when you are on home Wi-Fi)

Medium and small sizes also work and show less.

### What it shows and when it updates

- The file is rewritten every `HEALTH_DATA_IMPORT_INTERVAL_SECONDS` (15 minutes by
  default), right after the Health import, so this morning's sleep, HRV and
  resting HR count once the Health Shortcut has run. Plan changes, logged sessions
  and check-ins appear on the next cycle.
- iOS decides when widgets redraw (roughly every 15–60 minutes). Opening
  Scriptable or the widget's script forces a refresh.
- The footer shows the update time. Data older than 3 hours turns it amber with
  "Mac offline?": the Mac was asleep, Docker stopped, or iCloud had not synced yet.
- Week dots: green filled = done, blue ring = today, red ring = missed or
  skipped, grey dash = rest, grey = upcoming.
- The date follows the backend's UTC clock, like the dashboard, so it keeps
  showing the previous day until 02:00 (01:00 in winter).

## Offline behavior and HTTPS

This first version has no service worker and does not save a separate offline
copy of your training data. An already open page can retain its current display;
new loads require the Mac. With the Mac unreachable, Safari may display its own
connection error. There is no custom cold-start offline screen.

Local HTTP supports the basic Home Screen experience. Secure-context features,
including service-worker caching, require trusted HTTPS. That can be added later
using a local certificate authority trusted on the iPhone. No public domain is
required for that setup.

## Stop

```sh
just phone-stop 192.168.1.42
```

This stops only the phone frontend. To stop the entire stack, including the phone:

```sh
TRAINLOG_LAN_IP=192.168.1.42 docker compose -f docker-compose.yml -f docker-compose.phone.yml down
```
