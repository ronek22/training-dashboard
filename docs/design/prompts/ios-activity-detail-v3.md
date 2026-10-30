# Prompt: iOS activity detail v3 (artboards first, then build)

Paste everything below the line into a new Claude Code session started in `ios/`.

---

The iOS Activity detail screen looks unfinished next to the web one. The web
`ActivityDetail` page looks mature and good; the phone version (v2, shipped 10-28 from
`docs/design/artboards/iOSActivityDetail.dc.html`) doesn't. I want a v3 redesign that brings
the phone up to the web's level, adapted to a 393 pt screen, not shrunk down from the desktop.

Work in two phases. **Do not write any Swift until I approve the artboards.**

## Phase 1: artboards (stop at the end)

### 1. Look at both versions before designing

- **Web (the reference).** Run the frontend against the local backend and screenshot
  `/activities/<id>` at ~1512 px wide for one real activity of each kind: outdoor ride,
  indoor ride with power, run, hike, strength, and an "other/physio" one (pick ids with
  `GET /activities`). Then read only the components that drive what you see:
  `frontend/src/views/ActivityDetail.vue` and `frontend/src/components/activity-detail/*`
  (start with `ActivityHeader`, `ActivityKit`, `SessionWinCard`, `SessionReadPanel`,
  `EnduranceAnalysis`; open `StrengthAnalysis` / `HikeAnalysis` for those sports). Note the
  type sizes, spacing, card treatments, chart styling, and how the page builds hierarchy.
- **iOS (what we have).** Build and run in the simulator (iPhone 17 Pro) and screenshot the
  same activities, scrolled through the whole screen. Code is in
  `TrainLog/Features/Activities/ActivityDetail*.swift`.
- Also read the v2 artboard's module map (`<!-- ============ MODULE MAP`) so you keep the
  data coverage. v3 is a visual redesign, not a feature change.

### 2. Write the diagnosis

Before drawing anything, write a short, specific critique: **why does the web look better
and the phone worse?** Name concrete causes with screenshot evidence, e.g. too many
equal-weight boxed cards, no single hero, cramped or inconsistent spacing, numbers too small
or too big, labels everywhere, weak chart styling, colours used without meaning, uneven
section rhythm. Then list the 5–8 design principles v3 will follow to fix them. Put this at
the top of the artboard as a notes frame.

### 3. Build the artboard

Create `docs/design/artboards/iOSActivityDetailV3.dc.html`. Keep v2 in place so we can
compare. Copy the file conventions from `iOSActivityDetail.dc.html` (`support.js`,
`<x-dc>`, fonts, `.phone` frame 393 × 852 with a fold line, `.frame-cap` captions).

Frames to include:

1. **Notes**: diagnosis plus principles (from step 2).
2. **Before / after**: a v2 screenshot (or a faithful redraw) next to the v3 ride, so the
   change is obvious at a glance.
3. **One full-length phone per sport**: Ride (outdoor, power), Run, Hike, Strength,
   Other/Physio. Draw the whole scroll, not only above the fold. Use realistic numbers from
   the real activities you screenshotted.
4. **Component sheet**: the reusable parts at 1:1 (hero/header, stat row, stream chart with
   scrub state, zones bar, best-efforts row, lift-vs-last row, feel meters, coach take,
   win strip, pain alert), each with its exact sizes, spacing and colours written beside it,
   so phase 2 can implement them without guessing.
5. **States**: loading, no streams (manual entry), no feedback yet (the "log how it felt"
   prompt), offline/last synced.

Design rules (from `ios/AGENTS.md` and `docs/design/REDESIGN.md`; follow them exactly):

- Dark only: bg `#0A0C11`, card `#12151C`, border `#1C212B`, inset `#0E1117`. Sport colours:
  ride `#3B8CFF`, run `#FF8A2A`, strength `#FF4D9A`, walk/mobility/rehab `#2ED3B0`,
  hike/other `#8B7BFF`. Volt `#D4FF3A` only for the one primary action and for wins.
- Flat: no decorative gradients. Barlow Condensed for numbers and titles (titles italic
  800 uppercase), Archivo for body. Kickers 11 pt semibold, tracking .14em, muted `#8A93A6`.
- iOS patterns: large title / nav bar, 44 pt tap targets, sheets for input, native-feeling
  scroll. Pick one spacing scale (e.g. 4/8/12/16/24/32) and use only that.
- Each sport gets one clear hero moment at the top. Section order follows the v2 module map
  unless the diagnosis gives a reason to change it; call out any change in a caption.
- Charts should look like the web's (line weight, fills, axes, gridlines, labels), sized
  for the phone.

### 4. Check and hand over

- Open the artboard in the browser pane, screenshot each frame, and fix anything that
  overflows 393 pt, misaligns or breaks the rules above.
- Commit the artboard on a new `ios-activity-detail-v3` branch (one commit).
- Then **stop** and send me: the artboard link/path, the diagnosis in 5 bullets, and a list of
  anything that needs a backend change (there should be none, or very little). Wait for my
  approval or change requests. Revise the artboard until I say "approved".

## Phase 2: implementation (only after I say "approved")

- Stay on `ios-activity-detail-v3`. Rebuild `ActivityDetailView` / `ActivityDetailCards`
  to match the approved artboard. Put new shared pieces (stat row, chart styling, zones bar)
  in `TrainLog/Design/` if other screens can reuse them. Remove v2 code that becomes dead.
  Don't change `ActivityDetailFormat` logic unless a format has to change.
- Keep every data point v2 shows; no new endpoints unless phase 1 listed them and I agreed.
  If one is needed, add it to the backend in the same branch with a test, and don't change
  existing response shapes.
- Keep the existing Today-style motion (cards lift in, numbers count up) where it fits;
  respect Reduce Motion.
- After each sport looks right, screenshot the simulator next to that sport's artboard frame
  and fix differences before moving on. Check all five sports plus the empty/loading states.
- Run `xcodebuild test` (scheme `TrainLog`, iPhone 17 Pro simulator) piped through `tail`;
  update or add tests for any view-model logic you touched.
- One commit per logical step (e.g. shared components, then each sport). Add one line at the
  top of "Shipped" in `docs/roadmaps/ios.md`: `**Activity detail v3**`.
- Finish with side-by-side screenshots (artboard vs simulator) for each sport and a list of
  anything you deliberately did differently from the artboard.
