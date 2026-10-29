# iOS app roadmap (TrainLog Pocket)

The native iPhone app in `ios/`. The Roadmap page shows this file as the iOS track.

Working rule: when an iOS change ships a feature, add one line at the top of "Shipped" and
remove it from Now/Next/Later. Fixes and polish don't need a line. Format:
`- YYYY-MM-DD — **Title** — One sentence on what you can do now.`

## Now

- **Background widget refresh** — Widgets and the Lock Screen update without opening the app.
- **Busy day toggle** — Mark a hectic day from the check-in so the plan eases off (`life_load`).
- **Merge into main** — The `ios-app` branch carries backend changes the web app also runs.

## Next

- **Session brief** — Today's lifts, targets and what changed, shown before a workout.
- **Sunday weekly recap** — A celebratory look back at the week on the phone.
- **Shopping list** — Built from the dinner plan, with barcode scanning for products.
- **Coach chat** — The in-app coach on the phone, tied to what you're looking at.

## Later

- **Apple Watch strength app** — Log sets on the Watch without starting a separate workout.
- **Backend off the Mac** — Move the server to a small EU VPS on Tailscale so the app works when the Mac is off.

## Shipped

- 2026-10-29 — **Smart reminders** — Check-in, rehab and dinner nudges fire only when that thing is still undone today.
- 2026-10-29 — **Readiness vitals** — Each vital is judged against your own typical range, with a week of dots.
- 2026-10-29 — **Guided rehab** — Run the rehab checklist on the phone with animated exercise demos.
- 2026-10-29 — **Today card for every day** — The Today card offers something to do on rest, training and rehab days.
- 2026-10-28 — **Strength rest chime** — The phone chimes and buzzes when rest ends, and logging a set is quicker.
- 2026-10-28 — **Apple Watch workouts** — Watch workouts reach the Mac as soon as they finish; Strava enriches them later.
- 2026-10-28 — **Liquid Glass tab bar** — The system tab bar, with the check-in moved onto Today.
- 2026-10-28 — **Edit meals** — Change or remove a logged meal from the phone.
- 2026-10-28 — **Tailscale** — Reach the Mac from anywhere, not only on home Wi-Fi.
- 2026-10-28 — **Widgets and Live Activity** — Home and Lock Screen widgets, plus a rest timer on the Lock Screen.
- 2026-10-28 — **Body screen** — Sleep stages, steps, heart rate and training load in one place.
- 2026-10-28 — **Apple Health sync** — The app sends Health data itself, replacing Health Data Export.
- 2026-10-28 — **Trends** — Year-so-far charts and recovery metrics on the phone.
- 2026-10-28 — **Activity detail v2** — Gauges, a route map, zones and lifts for each activity.
- 2026-10-28 — **Offline cache** — Screens show the last data at once and fail fast when the Mac is out of reach.
- 2026-10-27 — **Settings** — Server address, a Bonjour finder for the Mac and reminders.
- 2026-10-27 — **On the iPhone** — App icon, device builds and automatic redeploys before the profile expires.
- 2026-10-27 — **Plan** — Week list, day detail and a sheet to move a session.
- 2026-10-27 — **Activities** — The activity list with a detail screen.
- 2026-10-27 — **Check-in** — A quick sheet for sleep, energy, stress, pain, sore areas and weight.
- 2026-10-27 — **Food** — Log meals and estimate one from a photo with Snap meal.
- 2026-10-27 — **Strength session** — Run a workout from a template and log sets, with a Resume banner on Today.
- 2026-10-27 — **Today** — Readiness, today's session and the week at a glance.
- 2026-10-27 — **Design and project** — The iOS artboards, agent rules and the Xcode project.
