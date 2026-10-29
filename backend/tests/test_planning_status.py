import unittest

from backend.app.services.planning_status import _parse_ios_track, _parse_shipped, get_planning_status

CURRENT_STATE = """# Current State

## Recently Completed

- 2026-10-15 — Monthly letter (`shipped/2026-10.md`)

### Legacy entry

2026-09-02: Implements the `legacy` idea. A legacy entry still written here keeps showing up.

## Recommended Next Step

Nothing.
"""

OCTOBER = """# Shipped in October 2026

### Monthly letter

2026-10-15: Implements the `monthly-coach-letter` idea. A short monthly letter arrives from the coach.

- Details that the Roadmap page does not show.
"""

EARLIER = """# Shipped: earlier sprint and phase records

### Sprint 3 feedback loop

Undated sprint record that the Roadmap page skips.
"""


class PlanningStatusShippedTests(unittest.TestCase):
    def test_entries_come_from_monthly_files_and_legacy_section(self):
        shipped = _parse_shipped(CURRENT_STATE, [OCTOBER, EARLIER])

        self.assertEqual([item["title"] for item in shipped], ["Monthly letter", "Legacy entry"])
        self.assertEqual(shipped[0]["date"], "2026-10-15")
        self.assertEqual(shipped[0]["summary"], "A short monthly letter arrives from the coach.")

    def test_index_lines_alone_are_not_entries(self):
        self.assertEqual(_parse_shipped(CURRENT_STATE.replace("### Legacy entry", "Legacy entry")), [])

    def test_repository_docs_list_shipped_features_newest_first(self):
        shipped = get_planning_status()["shipped"]

        self.assertGreater(len(shipped), 40)
        dates = [item["date"] for item in shipped]
        self.assertEqual(dates, sorted(dates, reverse=True))


IOS = """# iOS app roadmap

Format: `- YYYY-MM-DD — **Title** — One sentence.`

## Now

- **Widget refresh** — Widgets update without opening the `app`.

## Next

## Later

- **Watch app** — Log sets on the Watch.

## Shipped

- 2026-10-27 — **Today** — Readiness at a glance.
- 2026-10-29 — **Guided rehab** — Rehab with demos.
"""


class PlanningStatusIosTrackTests(unittest.TestCase):
    def test_buckets_and_shipped_lines_are_parsed(self):
        track = _parse_ios_track(IOS)

        self.assertEqual([bucket["name"] for bucket in track["buckets"]], ["Now", "Next", "Later"])
        self.assertEqual(track["buckets"][0]["items"], [{"title": "Widget refresh", "detail": "Widgets update without opening the app."}])
        self.assertEqual(track["buckets"][1]["items"], [])
        self.assertEqual([entry["title"] for entry in track["shipped"]], ["Guided rehab", "Today"])

    def test_repository_docs_include_the_ios_track(self):
        ios = get_planning_status()["ios"]

        self.assertEqual(ios["path"], "docs/roadmaps/ios.md")
        self.assertTrue(ios["buckets"][0]["items"])
        self.assertGreater(len(ios["shipped"]), 10)


if __name__ == "__main__":
    unittest.main()
