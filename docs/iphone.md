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
