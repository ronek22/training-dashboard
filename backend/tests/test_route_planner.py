import sqlite3
import unittest

from backend.app.repositories import trails as repo
from backend.app.services.route_planner import Network, _simplify
from backend.app.services.trail_coverage import Projection, sample_polyline
from backend.app.services.trail_elevation import apply_section_elevation

LAT, LON = 49.2, 20.0
# A square of trail A-B-C-D: A-B and C-D run east-west (~727 m), B-C and D-A north-south (~1105 m).
A, B, C, D = (LAT, LON), (LAT, LON + 0.01), (LAT + 0.01, LON + 0.01), (LAT + 0.01, LON)


def section(sid, a, b, length, status="todo"):
    return {"id": sid, "coords": [list(a), list(b)], "length_m": length, "status": status, "coverage": 0.0,
            "parks": ["TPN"], "around": False, "names": [f"S{sid}"], "colours": ["red"]}


def between(a, b, share):
    return (a[0] + share * (b[0] - a[0]), a[1] + share * (b[1] - a[1]))


class RoutePlannerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(repo.SCHEMA)
        self.sections = [section(1, A, B, 727, status="done"), section(2, B, C, 1105), section(3, C, D, 727), section(4, D, A, 1105)]
        # Heights rise 100 m per 0.01° north, so B→C climbs 100 m.
        for s in self.sections:
            s["ascent_m"] = s["descent_m"] = None
        apply_section_elevation(self.conn, self.sections, Projection((49.06 + 49.35) / 2), sample_polyline,
                                lambda points: [1000 + (lat - LAT) * 10000 for lat, _ in points])
        self.network = Network(self.conn, "tatras", self.sections)

    def plan(self, *points):
        waypoints = [self.network.waypoint(lat, lon) for lat, lon in points]
        return waypoints, [p for a, b in zip(waypoints, waypoints[1:]) for p in self.network.leg(a, b)]

    def test_route_runs_along_the_trails_through_the_junction(self):
        waypoints, pieces = self.plan(between(A, B, 0.8), between(B, C, 0.5))
        self.assertTrue(all(w["snap"] for w in waypoints))
        self.assertEqual([p["section"] for p in pieces], [0, 1])          # along A-B to B, then up B-C
        self.assertAlmostEqual(sum(p["length_m"] for p in pieces), 0.2 * 727 + 0.5 * 1105, delta=15)
        self.assertAlmostEqual(pieces[1]["ascent_m"], 50, delta=2)
        self.assertEqual([p["new"] for p in pieces], [False, True])       # A-B was walked already

    def test_two_points_on_one_trail_go_straight_along_it(self):
        _, pieces = self.plan(between(B, C, 0.9), between(B, C, 0.1))
        self.assertEqual(len(pieces), 1)
        self.assertAlmostEqual(pieces[0]["length_m"], 0.8 * 1105, delta=10)
        self.assertAlmostEqual(pieces[0]["descent_m"], 80, delta=2)
        self.assertEqual(pieces[0]["coords"][0][2] > pieces[0]["coords"][-1][2], True)  # heights follow the walk

    def test_click_away_from_trails_is_joined_off_trail(self):
        far = (LAT + 0.005, LON + 0.005)                                   # middle of the square, ~360 m from any side
        waypoints, pieces = self.plan(between(A, B, 0.5), far)
        self.assertIsNone(waypoints[1]["snap"])
        self.assertEqual([p["on_trail"] for p in pieces], [False])
        snapped = self.network.waypoint(*far, radius=500)                  # zoomed out, the map snaps further
        self.assertIsNotNone(snapped["snap"])

    def test_simplify_keeps_only_points_that_shape_the_route(self):
        points = [between(A, B, 0.5), B, between(B, C, 0.5), C, between(C, D, 0.5)]
        waypoints = [self.network.waypoint(lat, lon) for lat, lon in points]
        kept = _simplify(self.network, waypoints)
        self.assertEqual(len(kept), 2)  # the route between the ends already passes B and C
        self.assertEqual(kept[0], waypoints[0])
        self.assertEqual(kept[-1], waypoints[-1])


class SavedRouteTests(unittest.TestCase):
    """Saving, listing, changing and deleting planned routes (planning itself is stubbed)."""

    def setUp(self):
        from unittest import mock
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(repo.SCHEMA)
        self.new_m = 1500
        def fake_plan(conn, region, points, simplify=False):
            return {"distance_m": 1000 * len(points), "hours": 1.5, "ascent_m": 300, "descent_m": 280, "max_ele": 1900, "new_m": self.new_m}
        patcher = mock.patch("backend.app.services.route_planner.plan_route", side_effect=fake_plan)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_list_and_update(self):
        from backend.app.services.route_planner import list_saved_routes, save_route, update_route
        saved = save_route(self.conn, "tatras", "  Orla   Perć ", "Summer", [[49.2, 20.0], [49.21, 20.01]])
        self.assertEqual((saved["name"], saved["collection"], saved["distance_m"]), ("Orla Perć", "Summer", 2000))
        save_route(self.conn, "tatras", "Kasprowy", "", [[49.2, 20.0], [49.21, 20.01], [49.22, 20.0]])
        self.new_m = 0   # walked since: the list re-plans
        listed = list_saved_routes(self.conn, "tatras")
        self.assertEqual(listed["collections"], ["Summer"])
        self.assertEqual({r["name"]: r["new_m"] for r in listed["routes"]}, {"Orla Perć": 0, "Kasprowy": 0})
        moved = update_route(self.conn, saved["id"], collection="summer", points=[[49.2, 20.0], [49.21, 20.01], [49.23, 20.02]])
        self.assertEqual((moved["collection"], moved["distance_m"], len(moved["points"])), ("Summer", 3000, 3))  # joins the existing spelling
        self.assertEqual(list_saved_routes(self.conn, "karkonosze")["routes"], [])

    def test_validation_and_delete(self):
        from backend.app.services.route_planner import delete_route, save_route, update_route
        with self.assertRaises(ValueError):
            save_route(self.conn, "tatras", "   ", "", [[49.2, 20.0], [49.21, 20.01]])
        with self.assertRaises(ValueError):
            save_route(self.conn, "tatras", "One point", "", [[49.2, 20.0]])
        saved = save_route(self.conn, "tatras", "Gone", "", [[49.2, 20.0], [49.21, 20.01]])
        delete_route(self.conn, saved["id"])
        with self.assertRaises(LookupError):
            delete_route(self.conn, saved["id"])
        with self.assertRaises(LookupError):
            update_route(self.conn, saved["id"], name="x")


if __name__ == "__main__":
    unittest.main()
