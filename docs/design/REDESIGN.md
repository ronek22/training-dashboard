# TrainLog redesign — "Energetic multi-sport"

Branch: `redesign-multisport`. Goal: every page looks like its artboard. The user checks on a
MacBook Pro M4 in full screen (**1512 × 945 viewport**) and on phone.

## Where the design lives

| Page | Screenshot (look here first) | Source (exact values) |
|---|---|---|
| Today (Dashboard) | `screens/today.png` | `artboards/Main.dc.html` |
| Plan | `screens/plan.png` | `artboards/Plan.dc.html` |
| Calendar | `screens/calendar.png` | `artboards/Calendar.dc.html` |
| Strength | `screens/strength.png` | `artboards/Strength.dc.html` |
| Activities | `screens/activities.png` | `artboards/Activities.dc.html` |
| Records | `screens/records.png` | `artboards/Records.dc.html` |
| Season in review | `screens/season.png` | `artboards/Season.dc.html` |
| All years | `screens/years.png` | `artboards/Years.dc.html` |
| Mountains | `screens/mountains.png` | `artboards/Mountains.dc.html` |
| System (colors, type, components) | `screens/system.png` | `artboards/System.dc.html` |

- Screenshots are 1440 px wide, rendered from the artboards. Read the PNG to see the target;
  grep the `.dc.html` only for exact sizes/colors (styles are inline; data is in the
  `<script type="text/x-dc">` block at the bottom). Don't read whole artboard files.
- To view an artboard live: open the `.dc.html` in a browser (it uses `support.js` next to it).
- Pages without an artboard (Recovery, Food, Goals, Trends, Athlete, Coach
  Notes, Sync, Usage…): apply the system below and borrow patterns from the closest artboard.

## Status

- Done: **Today**, **Plan**, **Calendar** (month + week view).
- Next, in order: **Strength** → **Activities** → the rest.
- Known leftovers: Calendar day popup; Plan editor / planned-session modal / coaching approval
  flow; ~50 hardcoded old-blue colors; strength session count mismatch (dashboard API 21 vs
  Strength page 17).

## Design system

Tokens live in `frontend/src/style.css` (`:root`, light override under `[data-theme='light']`).
Always use tokens, never raw hex.

- **Base:** near-black. `--bg #0a0c11`, cards `--surface #12151c`, insets `rgb(var(--deep-rgb))`,
  raised `--surface2` / `--surface3`, hairlines `--border` / `--border-strong`.
- **One color per sport:** ride `--ride` (blue #3b8cff), run `--run` (orange #ff8a2a),
  strength `--strength` (magenta #ff4d9a), walk/mobility/recovery `--z2` (teal #2ed3b0),
  travel/hikes/other `--tone-recovery` (violet). Tinted text variants: `--tone-ride` etc.
- **Volt `--volt` (#d4ff3a) is for the ONE primary action per view and for wins**
  (streaks, plan followed, today ring). Don't overuse it: secondary actions are **outline
  buttons** (transparent, `1px solid var(--border-strong)`, pill radius).
- **Status:** `--warning` / `--warning-text` (amber), `--danger` / `--danger-text`, `--success-text`.
- **Type:** body `--font-body` (Archivo). Numbers and titles `--font-display`
  (Barlow Condensed), page titles and hero numbers **italic 800 uppercase**.
  Kickers/labels: 11px, 600–700, `letter-spacing: .14em`, uppercase, `--muted`.
- **Shape:** cards `--radius-card` (24px) with `1px solid var(--border)`; tiles 20px; inner cells
  12–14px; pills 999px.
- **Patterns to reuse:**
  - Page header: kicker ("Train · Calendar") + big display title, controls right-aligned.
  - Stat tile: label first, big display value below.
  - Sport chip: 4×14px rounded color bar + label + time (see `CalendarDayCell.vue`).
  - Planned = dashed border in the sport color, no fill. Missed = red tint. Sick = amber tint.
    Today = 2px volt ring.
  - Tags/intents: quiet pills; only one tinted pill per card.
  - Charts: read colors via `themeColor()` (`utils/theme.js`), sport colors for series.

## How to implement a page

1. Look at the screenshot. Read only the page's `.vue` template + the parts of its style you touch.
2. Change the template where the structure differs from the artboard (python/sed edits are fine).
3. Restyle by appending a **"Multi-sport redesign layer"** block at the end of the component's
   `<style scoped>`. If an older rule wins, raise specificity with the page root class
   (e.g. `.plan-page …`) instead of `!important`.
4. Verify in the browser at 1512 × 945 **and** mobile (375 px): compare against the screenshot,
   and check `document.documentElement.scrollWidth - innerWidth <= 0` (no horizontal overflow).
   The morning check-in modal opens on load — close it with `[aria-label="Close check-in"]`,
   never submit it.
5. Commit on `redesign-multisport`, one commit per page or fix.

Dev notes: Vite HMR picks up `frontend/src` changes (Docker mounts only `src`, so `index.html`
changes need a rebuild — fonts are loaded via `@import` in `style.css` for that reason).
