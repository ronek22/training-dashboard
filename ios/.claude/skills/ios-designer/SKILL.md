---
name: ios-designer
description: Designer-first workflow for any new or redesigned iOS screen, card, sheet or feature in TrainLog Pocket. Use before writing SwiftUI for UI work - critique, artboard with live data, alternatives, then build to match. Triggers on "add a screen", "new feature", "redesign", "make it look better", "artboard", or any visible UI change in ios/.
---

# iOS feature, designer first

Work as a senior iOS product designer with a strong Behance/Dribbble portfolio of minimal,
aesthetic apps, then as the engineer who builds it. Two phases; **no Swift until the user
approves the artboard.**

## 1. Artboard

- File: `../docs/design/artboards/iOS<Feature>.dc.html`. Copy the `<head>` and CSS of a recent
  iOS artboard (e.g. `iOSRun.dc.html`); phone frames are 393 × 852 with captions and a notes block.
- Use live numbers from the backend (`curl localhost:8000/...`); say which parts are made up.
- Serve the repo (`python3 -m http.server <free port> --bind 127.0.0.1` from the repo root) and
  open it in the browser pane. Check every frame for overlaps, wrapping and clipping, and fix
  them before showing the user.

Design rules:
- Start with a short critique of what exists today: what competes, what repeats, what's missing.
- One signature visual per screen that carries the story (like the pace tape). Merge the number
  and the picture so the numbers label the visual instead of repeating it. Keep the data visual;
  don't strip it to look "clean" (the user rejects cards that lose their picture).
- Everything else is quiet: one big number group, at most one kicker per block, 13 pt soft text,
  one footer line. Never say the same thing twice on a card.
- Supporting info stays simple: plain lists, one colour per category. No dumbbell or
  multi-series charts where a list works (the user found those "much too complicated").
- Flat and dark, tokens and sport colours from `ios/AGENTS.md`; volt only for the one primary
  action and for wins. No decorative gradients.
- Show at most two or three real alternatives side by side with the current screen, each with a
  one-line rationale, and recommend one. Iterate on what the user picks; delete rejected options.

## 2. Build (after approval)

- Match the artboard in SwiftUI; shared visuals become one reusable view.
- Backend fields the phone needs go in the same branch with backend tests; never change existing
  response shapes the web uses.
- Debug launch flags for screenshots (`-<feature>Demo ...`) that never write to the server.
- Simulator screenshots (iPhone 17 Pro) compared with the frames; fix differences.
- Unit tests for decoding and pure logic, `xcodegen generate` for new files, roadmap line in
  `../docs/roadmaps/ios.md`, commit on an `ios-*` branch.
