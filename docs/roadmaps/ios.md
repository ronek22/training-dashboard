# iOS app roadmap (TrainLog Pocket)

The native iPhone app in `ios/`. The Roadmap page shows this file as the iOS track.

Working rule: when an iOS change ships a feature, add one line at the top of "Shipped" and
remove it from Now/Next/Later. Fixes and polish don't need a line. Format:
`- YYYY-MM-DD — **Title** — One sentence on what you can do now.`

## Now


## Next

- **Lift history mid-session** — Tap a lift during a workout to see its last few sessions.

## Later

- **Shopping list** — Built from the dinner plan, with barcode scanning for products. Parked for now.
- **Backend off the Mac** — Move the server to a small EU VPS on Tailscale so the app works when the Mac is off.

## Shipped

- 2026-11-03 — **Morning brief and wins** — When your sleep syncs, one push says today's session and why (the short version on a red day). Today shows check-in and protein as a quiet row, and finished parts of the session card turn volt with a small burst, up to a clean day.
- 2026-11-03 — **Run comeback** — On a run day Today shows your easy pace from current VDOT on a pace tape (with your 2015 pace off the edge), or the return-to-run step as jog/walk blocks; a Pace guide explains the way back and every pace; after a run syncs, one tap says how it felt, and two hard runs in a row ease the band by 10 s/km.
- 2026-11-02 — **Strength after-session summary** — Finishing a lift (on the phone, Watch or web) ends on a recap: volume against last time with time, sets and reps counting up, new bests per lift, and where each target goes next (up, a rep more, or hold, with the reason) so the cautious progression is plain to see.
- 2026-11-02 — **Body v3** — Body opens on Day or Body. Day is a 24-hour dial (last night's sleep stages, steps per hour, a wind-down before lights out) with a lights-out target that pays back sleep debt, and vitals that call out the best day of the week. Body is a muscle map coloured by readiness from every sport, with active injuries pinned and a week of sessions per body area.
- 2026-11-02 — **Trends v2** — Trends leads with the last 12 weeks stacked by sport against your typical week (tap a week for its split). The year totals shrink to one card with a vs-last-year comparison and a page per sport. HRV and resting HR show a 7-day average line.
- 2026-11-01 — **Watch widgets** — Today, Rehab, Week and Food in the Watch Smart Stack and on watch faces (rectangular, circular, corner, inline), in the phone widgets' look; the most useful one rises to the top: the session in the morning, unfinished rehab and food to go in the evening, tomorrow once done.
- 2026-11-01 — **Watch workouts on Strava** — Strength and rehab sessions recorded on the Watch go up to Strava with their heart rate and Strava's own exercise list (exercises, reps, weights, holds), since Strava never imports them from Apple Health. Needs Strava reconnected once for upload access.
- 2026-10-31 — **Apple Watch app** — Start today's lift, bodyweight day or rehab on the Watch: one set at a time with the Crown, effort taps, a rest ring with haptics, holds that count themselves, live heart rate on wrist and phone, start on either device and steer from both (opening a lift or rehab on the iPhone readies the Watch, one Start begins both), and an Apple Health workout at the end that lands in the calendar.
- 2026-10-31 — **Sync status** — Today shows how many logs are waiting for the Mac (or were refused), and Settings lists them with Send now and a log of what went out after waiting.
- 2026-10-31 — **Bodyweight lifts** — A bodyweight or travel-kit day starts from Today or Plan as a one-time session that follows the coach's steps; reps-only sets with optional added weight, and planks as timed holds you start yourself.
- 2026-10-30 — **Food v2** — Food opens on a week strip with target dots, a calorie ring that shows kcal to go and the planned dinner, macro columns and a meal timeline; scanned and logged meals show a macro donut, a ½–2× portion picker and a grams stepper per item.
- 2026-10-30 — **Widgets v2** — The wide Today widget shows the next session with its focus in sport colour, week hours over a sport bar and kcal to go side by side; small Week and Food widgets match the app's D2 look, with no ring.
- 2026-10-30 — **Coach chat** — Ask the coach from an activity, a plan day or week, or Today, and pick up the same chats as the web; replies land even if you close the chat.
- 2026-10-30 — **Activity detail v3** — Every activity opens with a visual (glowing pace, speed or elevation route, an animated power or heart-rate trace, or a muscle map), a coloured grid that explains itself, calm sections with splits and running form, and Show more sheets.
- 2026-10-29 — **Coaching rehab demos** — The phone's rehab figures move like the web's: a solid body with the working muscle lighting up, the target pose as a ghost, an arrow along the move and a countdown with a tempo bar.
- 2026-10-29 — **Workout builder** — Build and edit workouts in Workout Studio from your own lift history, with a body map of what they work and a nudge when core is missing.
- 2026-10-29 — **Workout Studio** — Start any workout built on the Mac from Today, planned or not; the one that's waited longest comes first.
- 2026-10-29 — **Sunday weekly recap** — On Sunday and Monday Today offers the week in review: time moving, sports, days, wins, goals, recovery and next week's focus, with an optional Sunday evening nudge.
- 2026-10-29 — **Session brief** — Before a planned workout starts, see each lift's target, whether it goes up or holds and why, and what you did last time.
- 2026-10-29 — **Busy day** — Tag a hectic day (deadline, travel, family, poor sleep, late night) from the check-in so hard sessions get flagged with a calmer day to swap to.
- 2026-10-29 — **Zwift rides in Apple Health** — Indoor rides from Strava are saved to Health as cycling workouts, so they count in Fitness without HealthFit.
- 2026-10-29 — **Background widget refresh** — Widgets and the Lock Screen update hourly and after sleep or a Watch workout syncs, at home or over Tailscale.
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
