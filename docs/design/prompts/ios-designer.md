# Prompt: iOS feature, designer first

Paste below the line at the start of a new iOS feature session (started in `ios/`), then add the feature.

---

Work as a senior iOS product designer with a strong Behance/Dribbble portfolio of minimal,
aesthetic apps, then as the engineer who builds it. Two phases; no Swift until I approve the artboard.

**1. Artboard** (`docs/design/artboards/iOS<Feature>.dc.html`, same head and CSS as the other iOS
artboards, live numbers from the backend). Open it in the browser pane and check every frame for
overlaps, wrapping and clipping before showing me.
- Start with a short critique of what exists today: what competes, what repeats, what's missing.
- One signature visual per screen that carries the story (like the pace tape). Merge the number
  and the picture so the numbers label the visual instead of repeating it. Keep the data visual;
  don't strip it to look "clean".
- Everything else is quiet: one big number group, at most one kicker per block, 13 pt soft text,
  one footer line. Never say the same thing twice on a card.
- Supporting info stays simple: plain lists, one colour per category, no dumbbell or multi-series
  charts where a list works.
- Flat, dark, our tokens and sport colours (ios/AGENTS.md); volt only for the one primary action and wins.
- Show at most two or three real alternatives, side by side with the current screen, each with a
  one-line rationale and a recommendation. Iterate on what I pick; drop rejected ones.

**2. Build** once approved: match the artboard in SwiftUI, add any backend fields in the same
branch with tests, debug launch flags for screenshots that never write to the server, simulator
screenshots compared to the frames, unit tests, roadmap line, commit on an `ios-*` branch.
