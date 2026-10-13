import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from fastapi import HTTPException

from backend.app import db
from backend.app.repositories import trails as trail_repo
from backend.app.services import season_review

DECEMBER = date(2030, 12, 5)


class SeasonReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def add(self, activity_id, day, kind="Ride", minutes=60, distance=None):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, duration_min, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, f"{kind} {activity_id}", minutes, distance),
        )
        self.conn.commit()

    def review(self, year=2030, today=DECEMBER):
        return season_review.build_season_review(self.conn, year, today=today)

    def test_running_year_is_open_all_year_and_past_years_need_data(self):
        self.add("old", "2028-06-01", "Hike", 300, 12.0)
        self.add("now", "2030-03-01")

        spring = season_review.season_review_status(self.conn, today=date(2030, 4, 1))
        self.assertEqual(spring["years"], [2030, 2028])
        self.assertEqual(spring["coach_opens_on"], "2030-12-01")
        self.assertIsNone(season_review.season_review_status(self.conn, today=date(2030, 12, 1))["coach_opens_on"])
        running = self.review(today=date(2030, 4, 1))
        self.assertFalse(running["complete"])
        self.assertEqual(running["as_of"], "2030-04-01")
        self.assertEqual(running["coach_opens_on"], "2030-12-01")
        self.assertIsNone(self.review(2028, today=date(2030, 4, 1))["coach_opens_on"])
        with self.assertRaisesRegex(ValueError, "No activities recorded in 2029"):
            self.review(2029)

    def test_running_year_coach_paragraph_waits_for_december(self):
        self.add("now", "2030-03-01")

        with self.assertRaises(season_review.CoachNotOpen):
            season_review.write_coach_paragraph(self.conn, 2030, today=date(2030, 10, 13))
        self.assertIsNone(season_review.saved_coach_paragraph(self.conn, 2030))
        _, created = season_review.write_coach_paragraph(self.conn, 2030, today=date(2030, 12, 1))
        self.assertTrue(created)

    def test_totals_compare_with_last_year_only_when_it_has_data(self):
        self.add("r1", "2030-02-01", "Ride", 120, 50.0)
        self.add("r2", "2030-03-01", "VirtualRide", 60, 30.0)
        self.add("l1", "2030-03-02", "WeightTraining", 45)

        alone = self.review()["totals"]
        self.assertIsNone(alone["previous_year"])
        ride = next(item for item in alone["sports"] if item["key"] == "ride")
        self.assertEqual((ride["sessions"], ride["hours"], ride["km"]), (2, 3.0, 80.0))
        self.assertNotIn("previous", ride)
        self.assertNotIn("previous", alone["total"])
        strength = next(item for item in alone["sports"] if item["key"] == "strength")
        self.assertIsNone(strength["km"])
        # Sports with nothing logged are left out, not shown as zeros.
        self.assertEqual({item["key"] for item in alone["sports"]}, {"ride", "strength"})

        self.add("r0", "2029-05-01", "Ride", 90, 40.0)
        compared = self.review()["totals"]
        self.assertEqual(compared["previous_year"], 2029)
        ride = next(item for item in compared["sports"] if item["key"] == "ride")
        self.assertEqual(ride["previous"]["km"], 40.0)
        self.assertEqual(ride["change"]["km"], 100)
        strength = next(item for item in compared["sports"] if item["key"] == "strength")
        self.assertIsNone(strength["previous"])
        self.assertTrue(compared["to_date"])

    def test_totals_match_the_dashboard_year_chart(self):
        from backend.app.services.dashboard import build_yearly_distance_series

        year = date.today().year  # The year charts always show the running year.
        self.add("r1", f"{year}-01-10", "Ride", 75, 33.3)
        self.add("r2", f"{year}-01-20", "VirtualRide", 50, 20.1)
        chart = build_yearly_distance_series(self.conn, ("Ride", "VirtualRide"))[-1]
        totals = season_review.build_season_review(self.conn, year, today=date(year, 12, 31))["totals"]
        ride = next(item for item in totals["sports"] if item["key"] == "ride")

        self.assertEqual(ride["km"], chart["cumulative_km"])
        self.assertEqual(ride["hours"], chart["cumulative_hours"])
        self.assertEqual(ride["sessions"], chart["cumulative_sessions"])

    def test_empty_sections_are_hidden(self):
        self.add("one", "2030-04-01", "Walk", 30, 2.0)

        result = self.review()

        self.assertIsNone(result["streak"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["lifts"], [])
        self.assertEqual(result["mountains"], [])
        self.assertIsNone(result["best_month"])
        self.assertIsNone(result["goals"])
        self.assertIsNone(result["coach"])

    def test_streak_and_best_month_stay_inside_the_year(self):
        for offset in range(6):  # 28 Dec 2029 to 2 Jan 2030: only two days fall in 2030.
            self.add(f"x{offset}", (date(2029, 12, 28) + timedelta(days=offset)).isoformat(), "Run", 30, 5.0)
        for offset in range(4):
            self.add(f"m{offset}", (date(2030, 5, 10) + timedelta(days=offset)).isoformat(), "Ride", 90, 30.0)

        result = self.review()

        self.assertEqual(result["streak"]["days"], 4)
        self.assertEqual(result["streak"]["start"], "2030-05-10")
        self.assertEqual(result["best_month"]["month"], "2030-05")
        self.assertEqual(result["best_month"]["hours"], 6.0)
        may = result["months"][4]
        self.assertEqual((may["hours"], may["sports"]["ride"]["km"]), (6.0, 120.0))
        self.assertEqual(len(result["months"]), 12)
        self.assertEqual(result["days"][0], {"date": "2030-01-01", "minutes": 30, "sport": "run"})

    def test_records_need_a_beaten_best_and_cite_where_they_started(self):
        self.add("a", "2029-08-10", "Ride", 120, 60.0)
        self.add("b", "2030-07-14", "Ride", 150, 82.5)
        self.add("first-run", "2030-07-15", "Run", 30, 5.0)  # A first ever attempt beats nothing.

        records = self.review()["records"]

        longest = next(item for item in records if item["label"] == "Longest ride")
        self.assertEqual((longest["from"], longest["display"], longest["activity_id"]), ("60.0 km", "82.5 km", "b"))
        self.assertFalse(longest["new_this_year"])
        self.assertFalse(any(item["category"] == "Run" for item in records))

    def test_mountains_count_trail_and_summits_first_reached_in_the_year(self):
        self.conn.executescript(trail_repo.SCHEMA)
        trail_repo.migrate(self.conn)
        sections = [
            ("tatras", "TPN", 2000.0, "done", "2030-08-01", 0),
            ("tatras", "TPN", 3000.0, "done", "2029-08-01", 0),
            ("tatras", "TPN", 5000.0, "todo", None, 0),
            ("tatras", "TPN", 9000.0, "done", "2030-08-01", 1),  # Outside the park: not counted.
        ]
        for region, park, length, status, first, around in sections:
            self.conn.execute(
                "INSERT INTO trail_sections (region, osm_key, park, colours_json, names_json, coords_json, length_m, status, first_walked_on, around, imported_at) "
                "VALUES (?, 'w', ?, '[]', '[]', '[]', ?, ?, ?, ?, '2030-01-01')",
                (region, park, length, status, first, around),
            )
        self.conn.execute(
            "INSERT INTO trail_pois (region, osm_id, kind, name, ele, lat, lon, park, first_visited_on, visited_by_json) "
            "VALUES ('tatras', 'n1', 'peak', 'Kasprowy Wierch', 1987, 49.23, 19.98, 'TPN', '2030-08-01', '[\"h\"]')"
        )
        self.conn.commit()
        self.add("h", "2030-08-01", "Hike", 400, 18.0)

        [tatras] = self.review()["mountains"]

        self.assertEqual(tatras["gained_km"], 2.0)
        self.assertEqual(tatras["gained_pct"], 20.0)
        self.assertEqual(tatras["done_pct_end"], 50)
        self.assertEqual([item["name"] for item in tatras["summits"]], ["Kasprowy Wierch"])
        self.assertEqual(tatras["links"][0]["to"], "/mountains/tatras")

    def test_goals_list_completions_and_weekly_goals_from_their_start(self):
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, status_changed_at, commitment) "
            "VALUES ('Ride 1000 km in 2030', 'year', 'ride_km', 1000, '2030-01-01', '2030-12-31', 0, 'completed', '2030-09-28 10:00:00', 'flexible')"
        )
        self.conn.execute(
            "INSERT INTO goals (title, period_type, metric_type, target_value, start_date, end_date, is_active, lifecycle_status, commitment) "
            "VALUES ('Lift three times per week', 'week', 'strength_sessions', 3, '2030-11-04', '2030-11-10', 1, 'active', 'anchor')"
        )
        self.conn.commit()
        for day in ("2030-11-04", "2030-11-06", "2030-11-08", "2030-11-12"):
            self.add(f"lift-{day}", day, "WeightTraining", 50)

        goals = self.review()["goals"]

        self.assertEqual([item["title"] for item in goals["completed"]], ["Ride 1000 km in 2030"])
        [weekly] = goals["weekly"]
        # Weeks before the goal started are not counted as missed; the running week is left out.
        self.assertEqual((weekly["kept"], weekly["weeks"]), (1, 4))
        self.assertTrue(weekly["anchor"])

    def test_coach_paragraph_is_written_on_request_and_never_rewritten(self):
        self.add("r1", "2030-02-01", "Ride", 120, 50.0)
        self.add("r2", "2030-03-01", "Ride", 60, 30.0)
        self.conn.execute(
            "INSERT INTO monthly_letters (month, letter_json) VALUES ('2030-03', ?)",
            ('{"label": "March 2030", "wins": [{"kind": "streak"}], "focus": {"source": "sleep", "headline": "Bank sleep before the hard days"}}',),
        )
        self.conn.commit()
        self.assertIsNone(self.review()["coach"])

        coach, created = season_review.write_coach_paragraph(self.conn, 2030, today=DECEMBER)
        self.assertTrue(created)
        self.assertIn("2030 came to 2 sessions and 3 hours", coach["text"])
        self.assertIn("Bank sleep before the hard days", coach["text"])
        self.assertEqual(coach["letters_used"], ["2030-03"])

        self.add("r3", "2030-04-01", "Ride", 600, 200.0)
        again, created = season_review.write_coach_paragraph(self.conn, 2030, today=DECEMBER)
        self.assertFalse(created)
        self.assertEqual(again["text"], coach["text"])
        self.assertEqual(self.review()["coach"]["text"], coach["text"])

    def test_career_strip_covers_every_year_including_gaps(self):
        self.add("a", "2027-03-01", "Run", 60, 10.0)
        self.add("b", "2029-03-01", "Ride", 120, 50.0)
        self.add("c", "2030-03-01", "Ride", 30, 10.0)

        career = self.review(2029, today=date(2030, 6, 1))["career"]["years"]

        self.assertEqual([item["year"] for item in career], [2027, 2028, 2029, 2030])
        self.assertEqual([item["available"] for item in career], [True, False, True, True])  # The gap year has no review.
        self.assertEqual(career[1]["hours"], 0)
        self.assertEqual(career[2]["sports"], {"ride": 2.0})

    def test_badges_name_records_records_at_the_time_and_best_since(self):
        hours = {2021: 150, 2022: 300, 2023: 100, 2024: 80, 2025: 90, 2026: 200, 2027: 400}
        for year, minutes_total in hours.items():
            for index in range(4):
                self.add(f"{year}-{index}", f"{year}-0{index + 1}-10", "Run", minutes_total * 15, 5.0)

        def headlines(year):
            return [badge["headline"] for badge in self.review(year, today=date(2028, 1, 10))["career"]["badges"]]

        self.assertIn("Most hours of any year", headlines(2027))
        self.assertIn("Most hours up to then", headlines(2022))
        self.assertIn("Most hours since 2022", headlines(2026))
        # 2025 beat 2024 but not 2023, which is too close to call "since".
        self.assertFalse([item for item in headlines(2025) if item.startswith("Most hours")])
        record = next(badge for badge in self.review(2027, today=date(2028, 1, 10))["career"]["badges"] if badge["metric"] == "hours")
        self.assertEqual(record["detail"], "400 h · previous best 300 h in 2022")

    def test_best_since_needs_a_real_share_of_the_best_year(self):
        for index in range(40):
            self.add(f"old-{index}", f"2024-02-{(index % 28) + 1:02d}", "WeightTraining", 45)
        self.add("mid", "2025-02-01", "WeightTraining", 45)
        self.add("mid2", "2025-02-02", "WeightTraining", 45)
        self.add("now", "2029-02-01", "WeightTraining", 45)
        self.add("now2", "2029-02-02", "WeightTraining", 45)
        self.add("now3", "2029-02-03", "WeightTraining", 45)

        badges = self.review(2029, today=date(2030, 1, 10))["career"]["badges"]

        self.assertFalse([badge for badge in badges if badge["metric"] == "strength"])

    def test_milestones_name_the_activity_that_crossed_them(self):
        self.add("first", "2029-05-01", "Run", 600, 990.0)
        self.add("crossing", "2030-02-03", "Run", 60, 12.0)
        self.add("after", "2030-03-03", "Run", 60, 12.0)

        milestones = self.review()["career"]["milestones"]

        running = [item for item in milestones if item["kind"] == "run_km"]
        self.assertEqual(running, [{"kind": "run_km", "value": 1000, "unit": "km of running", "date": "2030-02-03",
                                    "activity_id": "crossing", "activity_name": "Run crossing"}])
        self.assertEqual(self.review(2029)["career"]["milestones"], [])  # 990 km, 10 h and 1 activity cross nothing.

    def test_running_year_is_compared_on_the_same_dates_with_pace_against_the_best_year(self):
        self.add("best-early", "2027-03-01", "Ride", 600, 100.0)
        self.add("best-late", "2027-11-01", "Ride", 1200, 200.0)
        self.add("last-early", "2029-02-01", "Ride", 120, 40.0)
        self.add("last-late", "2029-11-20", "Ride", 600, 150.0)
        self.add("now", "2030-04-01", "Ride", 900, 120.0)

        totals = self.review(today=date(2030, 6, 15))["totals"]

        self.assertEqual(totals["compared_until"], "06-15")
        self.assertEqual(totals["total"]["previous"]["hours"], 2.0)  # Only last year's February ride by 15 June.
        ride = next(item for item in totals["sports"] if item["key"] == "ride")
        self.assertEqual(ride["previous"]["km"], 40.0)
        self.assertEqual(totals["pace"], {"year": 2027, "hours": 10.0, "full_hours": 30.0, "delta": 5.0})
        finished = self.review(2029, today=date(2030, 6, 15))["totals"]
        self.assertIsNone(finished["pace"])
        self.assertIsNone(finished["compared_until"])

    def test_season_bests_frame_the_year_against_other_seasons(self):
        for activity_id, day, km in (("a", "2026-05-01", 60.0), ("b", "2027-05-01", 40.0), ("c", "2028-05-01", 50.0), ("d", "2030-05-01", 55.0)):
            self.add(activity_id, day, "Ride", 180, km)

        def longest(year):
            return next((item for item in self.review(year, today=date(2031, 1, 10))["season_bests"] if item["label"] == "Longest ride"), None)

        self.assertEqual(longest(2030)["headline"], "Best since 2026")
        self.assertEqual(longest(2030)["activity_id"], "d")
        self.assertEqual(longest(2028)["headline"], "Best since 2026")  # It beat 2027; only 2026, two years back, was better.
        self.assertEqual(longest(2026)["headline"], "Best of any season")  # The first season: nothing beaten, so not in records.
        self.add("e", "2031-05-01", "Ride", 240, 75.0)
        review_2031 = self.review(2031, today=date(2032, 1, 10))
        self.assertIn("Longest ride", [item["label"] for item in review_2031["records"]])
        self.assertNotIn("Longest ride", [item["label"] for item in review_2031["season_bests"]])  # Not listed twice.
        self.assertEqual(self.review(2027, today=date(2031, 1, 10))["season_bests"], [])  # Last of four, a year after the best.

    def test_season_bests_need_three_seasons_to_frame_against(self):
        def ranked(years):
            return {"yearly": {str(year): {"value": value, "display": f"{value} s", "date": f"{year}-05-01", "activity_id": str(year)}
                               for year, value in years.items()}, "higher_is_better": False}

        def sections(effort):
            return {"cycling_power": {"records": []}, "cycling_distance": {"outdoor": {"records": [{"label": "40K", **effort}]}, "indoor": {"records": []}},
                    "running": {"records": []}, "lifts": {"records": []}}

        two = season_review._season_bests(sections(ranked({2013: 5000, 2026: 5800})), 2026, set())
        three = season_review._season_bests(sections(ranked({2013: 5000, 2020: 6000, 2026: 5800})), 2026, set())

        self.assertEqual(two, [])
        self.assertEqual([(item["label"], item["headline"]) for item in three], [("40K", "Best since 2013")])

    def test_records_api_does_not_carry_the_per_year_bests(self):
        from backend.app.services.personal_records import build_personal_records

        self.add("a", "2029-05-01", "Ride", 180, 60.0)
        self.add("b", "2030-05-01", "Ride", 180, 70.0)
        self.assertNotIn('"yearly"', json.dumps(build_personal_records(self.conn, today=date(2030, 6, 1))))
        full = build_personal_records(self.conn, today=date(2030, 6, 1), include_yearly=True)
        self.assertEqual(set(full["cycling_distance"]["outdoor"]["longest"]["yearly"]), {"2029", "2030"})

    def test_coach_paragraph_tells_a_comeback_and_can_be_rewritten_on_request(self):
        for index in range(30):
            self.add(f"peak-{index}", f"2023-0{index % 9 + 1}-{index % 27 + 1:02d}", "Run", 60, 10.0)
        self.add("low", "2026-05-01", "Run", 30, 5.0)
        for index in range(20):
            self.add(f"now-{index}", f"2030-0{index % 9 + 1}-{index % 27 + 1:02d}", "Run", 60, 10.0)

        first, created = season_review.write_coach_paragraph(self.conn, 2030, today=DECEMBER)
        self.assertTrue(created)
        self.assertIn("A full comeback from nothing logged in 2029.", first["text"])

        again, created = season_review.write_coach_paragraph(self.conn, 2030, today=DECEMBER)
        self.assertFalse(created)
        self.assertNotIn("previous", again)
        self.add("late", "2030-12-03", "Run", 600, 40.0)
        rewritten, created = season_review.write_coach_paragraph(self.conn, 2030, today=DECEMBER, rewrite=True)
        self.assertTrue(created)
        self.assertEqual(rewritten["previous"]["text"], first["text"])
        self.assertNotEqual(rewritten["text"], first["text"])

    def test_routes_return_404_for_a_closed_year_and_keep_the_saved_paragraph(self):
        from backend.app.routers import records

        self.add("r1", "2029-02-01", "Ride", 120, 50.0)
        june = date(2030, 6, 1)
        self.assertEqual(records.season_review_years(day=june)["years"], [2029])
        self.assertEqual(records.season_review(2029, day=june)["year"], 2029)
        with self.assertRaises(HTTPException) as closed:
            records.season_review(2030, day=june)
        self.assertEqual(closed.exception.status_code, 404)
        self.assertTrue(records.season_review_coach(2029, day=june)["created"])
        self.assertFalse(records.season_review_coach(2029, day=june)["created"])
        self.add("r2", "2030-02-01", "Ride", 60, 20.0)
        self.assertEqual(records.season_review(2030, day=june)["coach_opens_on"], "2030-12-01")
        with self.assertRaises(HTTPException) as early:
            records.season_review_coach(2030, day=june)
        self.assertEqual(early.exception.status_code, 409)

if __name__ == "__main__":
    unittest.main()
