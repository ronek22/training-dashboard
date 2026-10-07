import unittest

from backend.app.services.route_ideas import build_trailheads, plan_routes, walking_hours

LAT, LON = 49.2, 20.0
# A square of trail A-B-C-D (each side ~1.1 km north-south / ~0.73 km east-west) plus a spur D-E.
A, B, C, D, E = (LAT, LON), (LAT, LON + 0.01), (LAT + 0.01, LON + 0.01), (LAT + 0.01, LON), (LAT + 0.02, LON)


def section(sid, a, b, length, status="todo", coverage=0.0, parks=("TPN",), around=False, ascent=0, descent=0, name=None):
    return {"id": sid, "coords": [list(a), list(b)], "length_m": length, "status": status, "coverage": coverage,
            "parks": list(parks), "around": around, "ascent_m": ascent, "descent_m": descent, "ele_max": 1500,
            "names": [name or f"S{sid}"], "colours": ["red"]}


def head(name, node, kind="bus"):
    return {"name": name, "kind": kind, "lat": node[0], "lon": node[1], "node": node}


class WalkingTimeTests(unittest.TestCase):
    def test_flat_and_climbing_times(self):
        self.assertAlmostEqual(walking_hours(10000, 0, 0), 2.0)
        self.assertAlmostEqual(walking_hours(5400, 500, 0), 1.08 + 500 / 600)  # Kuźnice – Murowaniec, signposted 1 h 45
        self.assertAlmostEqual(walking_hours(5000, None, None), 1.0)            # no heights: distance only

    def test_signposted_tatras_day_matches(self):
        # Kuźnice – Świnica and back: ~20 km, 1300 m up and down, signposted about 7 h 30.
        self.assertAlmostEqual(walking_hours(20000, 1300, 1300), 7.47, places=2)


class PlanRoutesTests(unittest.TestCase):
    def setUp(self):
        self.sections = [
            section(1, A, B, 1000, status="done"),
            section(2, B, C, 1000),
            section(3, C, D, 1000),
            section(4, D, A, 1000, status="partial", coverage=0.5),
            section(5, D, E, 1000, around=True),
        ]

    def test_loop_from_a_trailhead_picks_up_the_missing_trail(self):
        routes = plan_routes(self.sections, [head("Kuźnice", A)], [], "TPN", hours=1.2)
        loop = next(r for r in routes if r["mode"] == "loop")
        self.assertEqual(loop["start"]["name"], "Kuźnice")
        self.assertEqual(loop["end"]["name"], "Kuźnice")
        self.assertEqual(sorted(loop["new_sections"]), [1, 2, 3])          # list indexes of sections 2-4
        self.assertEqual(loop["new_m"], 2500)                               # partial section counts half
        self.assertLessEqual(loop["hours"], 1.2)
        walked = [s["section"] for s in loop["steps"]]
        self.assertNotIn(5, walked)                                         # around spur is not a target by default

    def test_around_trails_are_targets_only_when_included(self):
        routes = plan_routes(self.sections, [head("Kuźnice", A)], [], "TPN", hours=1.6, include_around=True)
        self.assertIn(4, max(routes, key=lambda r: r["new_m"])["new_sections"])

    def test_time_budget_is_respected(self):
        routes = plan_routes(self.sections, [head("Kuźnice", A)], [], "TPN", hours=0.9)
        self.assertTrue(routes)
        self.assertTrue(all(0.36 <= r["hours"] <= 0.9 for r in routes))   # at least 40% of the budget

    def test_one_way_ends_at_another_trailhead(self):
        sections = self.sections[:3]  # A-B done, B-C and C-D missing; no way back except the same way
        routes = plan_routes(sections, [head("Start", A, kind="parking"), head("Finish", D)], [], "TPN", hours=0.7)  # the 0.8 h out-and-back from Finish does not fit
        one_way = next(r for r in routes if r["mode"] == "one-way" and r["start"]["name"] == "Start")
        self.assertEqual((one_way["end"]["name"], one_way["end"]["kind"]), ("Finish", "bus"))
        self.assertEqual(sorted(one_way["new_sections"]), [1, 2])

    def test_one_way_only_finishes_at_a_bus_stop(self):
        sections = self.sections[:3]
        routes = plan_routes(sections, [head("Start", A), head("Car park", D, kind="parking")], [], "TPN", hours=1.3)
        self.assertTrue(routes)
        self.assertTrue(all(r["mode"] == "loop" for r in routes))

    def test_loops_rank_above_one_way_routes_of_similar_value(self):
        # Full square from A as a loop, or A-B-C-D one way to a bus at D: the loop wins.
        routes = plan_routes(self.sections[:4], [head("Start", A), head("Bus", D)], [], "TPN", hours=1.2)
        self.assertEqual(routes[0]["mode"], "loop")

    def test_climbing_makes_routes_longer_in_time(self):
        steep = [dict(s, ascent_m=600, descent_m=600) for s in self.sections]
        flat = plan_routes(self.sections, [head("Kuźnice", A)], [], "TPN", hours=1.2)
        hilly = plan_routes(steep, [head("Kuźnice", A)], [], "TPN", hours=8)
        self.assertGreater(max(r["hours"] for r in hilly), max(r["hours"] for r in flat))

    def test_places_on_the_route_are_listed(self):
        summit = {"name": "Kopa", "kind": "peak", "ele": 2000, "lat": C[0], "lon": C[1], "visited_by": [], "parks": ["TPN"]}
        loop = next(r for r in plan_routes(self.sections, [head("Kuźnice", A)], [summit], "TPN", hours=1.2) if r["mode"] == "loop")
        self.assertEqual(loop["places"], [{"name": "Kopa", "kind": "peak", "ele": 2000, "reached": False}])
        self.assertEqual(loop["title"], "Kuźnice – Kopa – Kuźnice")

    def test_nothing_missing_means_no_routes(self):
        done = [dict(s, status="done") for s in self.sections]
        self.assertEqual(plan_routes(done, [head("Kuźnice", A)], [], "TPN", hours=7), [])


def bus_stop(sid, lat, lon, name=""):
    return {"type": "node", "id": sid, "lat": lat, "lon": lon, "tags": {"highway": "bus_stop", **({"name": name} if name else {})}}


def parking(sid, lat, lon, name="", access=None):
    tags = {"amenity": "parking", **({"name": name} if name else {}), **({"access": access} if access else {})}
    return {"type": "way", "id": sid, "center": {"lat": lat, "lon": lon}, "tags": tags}


class SummitAndNamingTests(unittest.TestCase):
    def test_unreached_summit_tips_the_choice(self):
        # Two equal spurs from the trailhead; only one leads past a summit not reached yet.
        north, east = (LAT + 0.009, LON), (LAT, LON + 0.0125)
        sections = [section(1, A, north, 1000), section(2, A, east, 1000)]
        summit = {"name": "Kopa", "kind": "peak", "ele": 1900, "lat": east[0], "lon": east[1], "visited_by": [], "parks": ["TPN"]}
        best = plan_routes(sections, [head("Kuźnice", A)], [summit], "TPN", hours=0.5)[0]
        self.assertEqual(best["new_sections"], [1])
        self.assertEqual(best["places"][0]["name"], "Kopa")

    def test_one_way_that_returns_to_its_start_is_a_loop(self):
        sections = [section(1, A, B, 1000), section(2, B, C, 1000), section(3, C, D, 1000), section(4, D, A, 1000)]
        routes = plan_routes(sections, [head("Kuźnice", A)], [], "TPN", hours=1.2)
        self.assertTrue(routes)
        self.assertTrue(all(r["mode"] == "loop" for r in routes))

    def test_bus_stop_codes_are_dropped_from_names(self):
        heads = build_trailheads([bus_stop(1, LAT + 0.0005, LON, "Szklarska Poręba Średnia (84)"),
                                  bus_stop(2, LAT + 0.0005, LON + 0.01, "Dom Gerharta Hauptmanna 04")],
                                 [section(1, A, B, 1000)], "tatras")
        self.assertEqual(sorted(h["name"] for h in heads), ["Dom Gerharta Hauptmanna", "Szklarska Poręba Średnia"])


class TrailheadTests(unittest.TestCase):
    def setUp(self):
        self.sections = [section(1, A, B, 1000), section(2, B, C, 1000)]

    def test_bus_stops_and_car_parks_near_junctions(self):
        heads = build_trailheads([
            bus_stop(1, LAT + 0.0005, LON, "Kuźnice"),               # ~55 m from A
            parking(2, LAT + 0.01, LON + 0.0105),                     # unnamed, near C
            bus_stop(3, LAT + 0.0102, LON + 0.012, "Polana"),         # named stop ~150 m from C, same place
            parking(4, LAT + 0.05, LON + 0.05, "Far away"),
            parking(5, LAT, LON + 0.0101, "Hotel", access="customers"),
        ], self.sections, "tatras")
        self.assertEqual(sorted((h["name"], h["kind"], tuple(h["node"])) for h in heads),
                         [("Kuźnice", "bus", A), ("Polana", "bus", C)])

    def test_unnamed_car_park_borrows_the_nearest_stop_name(self):
        heads = build_trailheads([parking(2, LAT + 0.01, LON + 0.0105), bus_stop(3, LAT + 0.02, LON + 0.01, "Polana")], self.sections, "tatras")
        self.assertEqual([(h["name"], h["kind"]) for h in heads], [("Polana", "parking")])



class ElevationTests(unittest.TestCase):
    def setUp(self):
        import sqlite3
        from backend.app.repositories import trails as repo
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(repo.SCHEMA)

    def apply(self, sections, lookup):
        from backend.app.services.trail_coverage import Projection, sample_polyline
        from backend.app.services.trail_elevation import apply_section_elevation
        return apply_section_elevation(self.conn, sections, Projection(LAT), sample_polyline, lookup)

    def test_ascent_and_descent_from_the_profile_and_cached_for_next_time(self):
        calls = []
        def lookup(points):
            calls.append(len(points))
            return [1000 + (lat - LAT) * 10000 for lat, _ in points]   # +100 m per 0.01° north
        climb = section(1, A, D, 1100)                                  # A→D runs north
        self.assertTrue(self.apply([climb], lookup))
        self.assertEqual((climb["ascent_m"], climb["descent_m"], climb["ele_min"], climb["ele_max"]), (100, 0, 1000, 1100))
        again = section(1, A, D, 1100)
        self.assertTrue(self.apply([again], lambda points: self.fail("should use the cache")))
        self.assertEqual(again["ascent_m"], 100)

    def test_unavailable_service_leaves_sections_without_heights(self):
        import httpx
        def broken(points):
            raise httpx.ConnectError("offline")
        flat = section(1, A, B, 730)
        flat.pop("ascent_m"), flat.pop("descent_m")
        self.assertFalse(self.apply([flat], broken))
        self.assertNotIn("ascent_m", flat)

if __name__ == "__main__":
    unittest.main()
