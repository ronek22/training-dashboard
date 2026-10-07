import json
import sqlite3
import unittest

import httpx

from backend.app.repositories import trails as repo
from backend.app.repositories.settings import get_setting_value
from backend.app.services.trail_coverage import (
    SYNCED_UNTIL_KEY,
    build_sections,
    build_pois,
    build_valley_labels,
    compute_coverage,
    compute_poi_visits,
    parse_elevation,
    import_region,
    list_regions,
    region_map,
    sync_tracks,
)

LAT, LON = 49.2, 20.0
TPN, TANAP = 2226518, 6757027


def node(n, lat, lon):
    return n, {"lat": lat, "lon": lon}


# Nodes along a west-east line at LAT plus a branch north from node 2.
NODES = dict([
    node(1, LAT, LON), node(2, LAT, LON + 0.01), node(3, LAT, LON + 0.02), node(4, LAT, LON + 0.03),
    node(5, LAT + 0.01, LON + 0.01),
    node(9, LAT, LON + 0.3), node(10, LAT, LON + 0.31),  # ~15 km outside both parks
    node(20, LAT + 0.02, LON + 0.025), node(21, LAT + 0.03, LON + 0.025),  # along the TPN/TANAP border
    node(30, LAT + 0.07, LON), node(31, LAT + 0.07, LON + 0.01),           # ~2 km north of the parks
])


def way(way_id, nodes):
    return {"type": "way", "id": way_id, "nodes": nodes, "geometry": [NODES[n] for n in nodes]}


def relation(rel_id, colour, ways, name):
    return {
        "type": "relation", "id": rel_id,
        "tags": {"route": "hiking", "osmc:symbol": f"{colour}:white:{colour}_bar", "name": name},
        "members": [{"type": "way", "ref": w, "role": ""} for w in ways],
    }


TRAILS = [
    way(101, [1, 2, 3]), way(102, [3, 4]), way(103, [2, 5]), way(104, [9, 10]), way(105, [20, 21]), way(106, [30, 31]),
    relation(1, "red", [101, 102, 104], "Red ridge"),
    relation(2, "blue", [102], "Blue valley"),
    relation(3, "green", [103], "Green branch"),
    relation(5, "yellow", [105], "Border ridge"),
    relation(6, "blue", [106], "Town walk"),
    {"type": "relation", "id": 4, "tags": {"route": "hiking", "osmc:symbol": "green:white:green_backslash"}, "members": [{"type": "way", "ref": 102, "role": ""}]},
]


def square(way_id, south, west, north, east):
    ring = [(south, west), (south, east), (north, east), (north, west), (south, west)]
    return {"type": "way", "id": way_id, "nodes": list(range(len(ring))), "geometry": [{"lat": a, "lon": b} for a, b in ring]}


PARKS = [
    square(201, LAT - 0.05, LON - 0.05, LAT + 0.05, LON + 0.025),
    square(202, LAT - 0.05, LON + 0.025, LAT + 0.05, LON + 0.1),
    {"type": "relation", "id": TPN, "members": [{"type": "way", "ref": 201, "role": "outer"}]},
    {"type": "relation", "id": TANAP, "members": [{"type": "way", "ref": 202, "role": "outer"}]},
]


def poi(poi_id, lat, lon, **tags):
    return {"type": "node", "id": poi_id, "lat": lat, "lon": lon, "tags": tags}


POIS = [
    poi(301, LAT + 0.0003, LON + 0.005, natural="peak", name="Trail Peak", ele="2301 m"),     # ~33 m off the red trail
    poi(302, LAT + 0.004, LON + 0.005, natural="peak", name="Wild Peak", ele="2400"),         # ~440 m off any trail
    poi(303, LAT, LON + 0.03, natural="saddle", name="East Pass"),
    poi(304, LAT + 0.0002, LON + 0.025, natural="cave_entrance", name="Bat Cave"),           # ~22 m off the trail
    poi(308, LAT + 0.0005, LON + 0.012, natural="cave_entrance", name="Closed Cave"),        # ~55 m up the slope
    poi(309, LAT + 0.0006, LON + 0.0205, natural="peak", name="Border Peak"),                # ~66 m, where TPN meets TANAP
    poi(310, LAT + 0.0004, LON + 0.0255, natural="peak", name="Ridge Peak"),                 # on a TANAP trail, 36 m from the border
    poi(311, LAT, LON + 0.0101, natural="cave_entrance", name="Jaskinia Mroźna wejście"),
    poi(312, LAT + 0.0001, LON + 0.0103, natural="cave_entrance", name="Jaskinia Mroźna – wyjście"),
    poi(305, LAT, LON + 0.012, natural="peak", ele="2000"),                                  # unnamed
    {"type": "way", "id": 306, "center": {"lat": LAT + 0.009, "lon": LON + 0.01}, "tags": {"tourism": "alpine_hut", "name": "Hut"}},
    poi(307, LAT + 0.0091, LON + 0.0101, tourism="alpine_hut", name="Hut"),                  # same hut as a node
]


def fake_heights(points):
    """Terrain rising 1 m for every 10 m north of LAT, starting at 1000 m."""
    return [1000.0 + (lat - LAT) * 11054 for lat, _ in points]


def line(lat_offset, lon_from, lon_to, steps=60):
    return [[LAT + lat_offset, lon_from + (lon_to - lon_from) * i / steps] for i in range(steps + 1)]


def by_names(sections):
    return {tuple(s["names"]): s for s in sections}


class BuildSectionsTests(unittest.TestCase):
    def test_splits_at_junctions_and_colour_changes_inside_parks(self):
        sections = build_sections(TRAILS, PARKS, "tatras")
        named = by_names(sections)
        self.assertEqual(len(sections), 6)
        self.assertEqual(named[("Red ridge",)]["colours"], ["red"])
        self.assertEqual(named[("Blue valley", "Red ridge")]["colours"], ["red", "blue"])
        self.assertEqual(named[("Blue valley", "Red ridge")]["park"], "TANAP")
        self.assertEqual(named[("Green branch",)]["park"], "TPN")
        lengths = sorted(round(s["length_m"]) for s in sections if s["names"] == ["Red ridge"])
        self.assertEqual(lengths, [727, 727])  # 1-2 and 2-3, split by the green junction

    def test_trails_along_the_state_border_belong_to_both_parks(self):
        named = by_names(build_sections(TRAILS, PARKS, "tatras"))
        self.assertEqual(named[("Border ridge",)]["parks"], ["TANAP", "TPN"])
        self.assertEqual(named[("Green branch",)]["parks"], ["TPN"])
        self.assertEqual(named[("Blue valley", "Red ridge")]["parks"], ["TANAP"])  # crosses the border only at one end

    def test_trails_just_outside_the_parks_count_for_the_nearest_park(self):
        named = by_names(build_sections(TRAILS, PARKS, "tatras"))
        town = named[("Town walk",)]
        self.assertEqual((town["park"], town["parks"], town["around"]), ("TPN", ["TPN"], True))
        self.assertFalse(named[("Green branch",)]["around"])

    def test_places_outside_the_parks_are_marked_around(self):
        sections = build_sections(TRAILS, PARKS, "tatras")
        town_peak = poi(320, LAT + 0.0702, LON + 0.005, natural="peak", name="Town Hill")
        places = {p["name"]: p for p in build_pois(TRAILS + PARKS + POIS + [town_peak], sections, "tatras")}
        self.assertEqual((places["Town Hill"]["park"], places["Town Hill"]["around"]), ("TPN", True))
        self.assertFalse(places["Trail Peak"]["around"])

    def test_ignores_trails_outside_parks_and_non_standard_symbols(self):
        sections = build_sections(TRAILS, PARKS, "tatras")
        self.assertTrue(all(lon < LON + 0.1 for s in sections for _, lon in s["coords"]))
        self.assertTrue(all("green" not in s["colours"] or s["names"] == ["Green branch"] for s in sections))



def bike_relation(rel_id, ways, name):
    return {"type": "relation", "id": rel_id, "tags": {"route": "bicycle", "name": name},
            "members": [{"type": "way", "ref": w, "role": ""} for w in ways]}


class BikeRouteTests(unittest.TestCase):
    def setUp(self):
        NODES.update(dict([node(32, LAT + 0.07, LON + 0.02), node(40, LAT - 0.07, LON + 0.06), node(41, LAT - 0.07, LON + 0.07)]))
        self.addCleanup(lambda: [NODES.pop(n) for n in (32, 40, 41)])

    def build(self, bike_parks):
        # The town walk (way 106, nodes 30-31) is also part of a bike route: there the hiking mark wins.
        bikes = [way(108, [31, 32]), way(109, [40, 41]),
                 bike_relation(7, [106, 108], "Town loop"), bike_relation(8, [109], "Far side loop")]
        return build_sections(TRAILS + bikes, PARKS, "tatras", bike_parks=bike_parks)

    def test_cycle_routes_count_only_in_the_chosen_park(self):
        sections = self.build(("TPN",))
        bike = [s for s in sections if s["colours"] == ["bike"]]
        self.assertEqual([s["names"] for s in bike], [["Town loop"]])     # far side loop is near TANAP
        self.assertEqual(bike[0]["park"], "TPN")
        town = next(s for s in sections if "Town walk" in s["names"])
        self.assertEqual((town["colours"], town["names"]), (["blue"], ["Town walk"]))

    def test_cycle_routes_are_ignored_elsewhere(self):
        self.assertFalse(any("bike" in s["colours"] for s in self.build(())))

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.sections = build_sections(TRAILS, PARKS, "tatras")
        self.first = next(s for s in self.sections if s["coords"][0][1] == LON or s["coords"][-1][1] == LON)

    def track(self, activity_id, latlng, date="2024-09-08"):
        return {"activity_id": activity_id, "date": date, "latlng": latlng}

    def test_walked_section_is_done_and_credited_to_earliest_activity(self):
        tracks = [self.track("b", line(0.0001, LON, LON + 0.01), "2024-09-08"), self.track("a", line(-0.0001, LON, LON + 0.01), "2019-09-13")]
        result = compute_coverage([self.first], tracks, LAT)[0]
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["walked_by"], ["a", "b"])
        self.assertEqual(result["first_walked_on"], "2019-09-13")

    def test_parallel_track_beyond_drift_distance_does_not_count(self):
        result = compute_coverage([self.first], [self.track("x", line(0.0018, LON, LON + 0.01))], LAT)[0]  # ~200 m north
        self.assertEqual(result["status"], "todo")
        self.assertEqual(result["walked_by"], [])

    def test_half_walked_section_is_partial(self):
        result = compute_coverage([self.first], [self.track("x", line(0, LON, LON + 0.005))], LAT)[0]
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["first_walked_on"])

    def test_long_gaps_in_a_track_do_not_cover_trails(self):
        jump = [[LAT, LON - 0.001], [LAT, LON + 0.011]]  # one ~870 m straight jump (lift / lost signal)
        result = compute_coverage([self.first], [self.track("x", jump)], LAT)[0]
        self.assertEqual(result["status"], "todo")



class DriftingGpsTests(unittest.TestCase):
    """GPS that runs 50–150 m off a trail it clearly follows still counts."""

    def setUp(self):
        NODES.update(dict([node(50, LAT + 0.0018, LON), node(51, LAT + 0.0018, LON + 0.01)]))
        self.addCleanup(lambda: [NODES.pop(n) for n in (50, 51)])
        self.red = lambda sections: next(s for s in sections if s["names"] == ["Red ridge"] and s["coords"][0][1] in (LON, LON + 0.01) and min(c[1] for c in s["coords"]) == LON)

    def statuses(self, extra, track_line):
        sections = build_sections(TRAILS + extra, PARKS, "tatras")
        results = compute_coverage(sections, [{"activity_id": "t", "date": "2020-06-15", "latlng": track_line}], LAT)
        return {tuple(s["names"]): r for s, r in zip(sections, results) if min(c[1] for c in s["coords"]) == LON and max(c[1] for c in s["coords"]) <= LON + 0.0101}

    def test_track_running_100_m_off_its_only_trail_counts(self):
        result = self.statuses([], line(0.0009, LON, LON + 0.01))[("Red ridge",)]
        self.assertEqual((result["status"], result["walked_by"]), ("done", ["t"]))

    def test_track_that_stops_short_does_not_count(self):
        result = self.statuses([], line(0.0009, LON, LON + 0.006))[("Red ridge",)]
        self.assertNotEqual(result["status"], "done")

    def test_credit_goes_to_the_nearer_parallel_trail(self):
        parallel = [way(110, [50, 51]), relation(9, "black", [110], "Parallel")]
        results = self.statuses(parallel, line(0.0012, LON, LON + 0.01))  # 133 m from red, 66 m from the parallel trail
        self.assertEqual(results[("Parallel",)]["status"], "done")
        self.assertNotEqual(results[("Red ridge",)]["status"], "done")

def strava_transport(activities, streams):
    def handler(request):
        if request.url.path.endswith("/athlete/activities"):
            page = int(request.url.params["page"])
            after = int(request.url.params["after"])
            return httpx.Response(200, json=[a for a in activities if a["epoch"] > after][(page - 1) * 200:page * 200])
        activity_id = request.url.path.split("/")[-2]
        handler.stream_calls.append(activity_id)
        return httpx.Response(200, json={"latlng": {"data": streams.get(activity_id, [])}})
    handler.stream_calls = []
    return handler


def activity(activity_id, sport, start, epoch, date="2024-09-08T08:00:00Z"):
    return {"id": activity_id, "name": f"Hike {activity_id}", "sport_type": sport, "type": sport, "start_latlng": start,
            "end_latlng": start, "start_date": date, "start_date_local": date, "distance": 12000, "total_elevation_gain": 900, "epoch": epoch}


class PlacesTests(unittest.TestCase):
    def setUp(self):
        self.sections = build_sections(TRAILS, PARKS, "tatras")
        self.pois = {p["name"]: p for p in build_pois(TRAILS + PARKS + POIS, self.sections, "tatras")}

    def test_keeps_named_places_near_marked_trails_once(self):
        self.assertEqual(sorted(self.pois), ["Bat Cave", "Border Peak", "East Pass", "Hut", "Jaskinia Mroźna", "Ridge Peak", "Trail Peak"])
        self.assertEqual(self.pois["Trail Peak"]["kind"], "peak")
        self.assertEqual(self.pois["Trail Peak"]["ele"], 2301)
        self.assertEqual(self.pois["Trail Peak"]["park"], "TPN")
        self.assertEqual(self.pois["East Pass"]["park"], "TANAP")
        self.assertEqual(self.pois["Hut"]["osm_id"], "w306")

    def test_border_summits_belong_to_every_park_whose_trail_reaches_them(self):
        self.assertEqual(self.pois["Border Peak"]["parks"], ["TANAP", "TPN"])
        self.assertEqual(self.pois["Trail Peak"]["parks"], ["TPN"])
        self.assertEqual(self.pois["Ridge Peak"]["parks"], ["TANAP", "TPN"])
        self.assertEqual(self.pois["East Pass"]["parks"], ["TANAP"])

    def test_summit_off_the_trail_line_is_reached_by_walking_the_trail_past_it(self):
        border = self.pois["Border Peak"]
        on_trail = {"activity_id": "x", "date": "2024-06-08", "latlng": line(0, LON + 0.015, LON + 0.03)}
        self.assertEqual(compute_poi_visits([border], [on_trail], LAT)[0]["visited_by"], ["x"])
        elsewhere = {"activity_id": "y", "date": "2024-06-08", "latlng": line(-0.002, LON + 0.015, LON + 0.03)}
        self.assertEqual(compute_poi_visits([border], [elsewhere], LAT)[0]["visited_by"], [])

    def test_parse_elevation(self):
        self.assertEqual([parse_elevation(v) for v in ("2499", "1987,5 m", "~", None)], [2499, 1988, None, None])

    def test_place_is_reached_when_a_track_passes_close(self):
        pois = [self.pois["Trail Peak"], self.pois["Bat Cave"]]
        tracks = [
            {"activity_id": "late", "date": "2024-06-08", "latlng": line(0.0002, LON, LON + 0.01)},
            {"activity_id": "early", "date": "2019-09-13", "latlng": line(0.0003, LON + 0.004, LON + 0.006)},
        ]
        peak, cave = compute_poi_visits(pois, tracks, LAT)
        self.assertEqual(peak, {"visited_by": ["early", "late"], "first_visited_on": "2019-09-13"})
        self.assertEqual(cave, {"visited_by": [], "first_visited_on": None})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(repo.SCHEMA + "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);")
        import_region(self.conn, "tatras", fetch=lambda query: TRAILS + PARKS + POIS, elevations=fake_heights)

    def tearDown(self):
        self.conn.close()

    def test_import_stores_sections_and_region_summary(self):
        regions = {r["key"]: r for r in list_regions(self.conn)["regions"]}
        self.assertEqual(regions["tatras"]["done_pct"], 0)
        self.assertGreater(regions["tatras"]["total_km"], 2.5)
        self.assertIsNone(regions["karkonosze"]["imported_at"])
        parks = region_map(self.conn, "tatras")["parks"]
        self.assertEqual([p["key"] for p in parks], ["TPN", "TANAP"])
        payload = region_map(self.conn, "tatras")
        around_km = sum(s["length_m"] for s in payload["sections"] if s["around"]) / 1000
        all_km = sum(s["length_m"] for s in payload["sections"]) / 1000
        self.assertGreater(around_km, 0.5)
        self.assertAlmostEqual(regions["tatras"]["total_km"], round(all_km - around_km, 1), places=1)  # range tabs: parks only

    def test_sync_fetches_mountain_hikes_once_and_updates_coverage(self):
        acts = [
            activity(11, "Hike", [LAT, LON], 1725782400),
            activity(12, "Ride", [LAT, LON], 1725782500),        # not on foot
            activity(13, "Hike", [52.2, 21.0], 1725782600),      # Warsaw, outside regions
        ]
        handler = strava_transport(acts, {"11": line(0, LON, LON + 0.03, steps=300)})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = sync_tracks(self.conn, client)
        self.assertEqual((result["added"], result["regions"], result["complete"]), (1, ["tatras"], True))
        self.assertEqual(handler.stream_calls, ["11"])
        self.assertEqual(get_setting_value(self.conn, SYNCED_UNTIL_KEY), "1725782400")

        payload = region_map(self.conn, "tatras")
        done = [s for s in payload["sections"] if s["status"] == "done"]
        self.assertEqual(len(done), 3)  # whole west-east line, not the green branch
        self.assertTrue(all(s["walked_by"] == ["11"] for s in done))
        self.assertEqual(payload["tracks"][0]["id"], "11")
        self.assertLess(len(payload["tracks"][0]["latlng"]), 301)
        places = {p["name"]: p for p in payload["pois"]}
        self.assertEqual(places["East Pass"]["visited_by"], ["11"])
        self.assertEqual(places["Hut"]["visited_by"], [])

        from backend.app.services.hike_detail import hike_context
        hike = hike_context(self.conn, "11")
        self.assertEqual(hike["region"]["key"], "tatras")
        self.assertEqual(sorted(p["key"] for p in hike["parks"]), ["TANAP", "TPN"])
        self.assertEqual(hike["totals"]["trail_km"], hike["totals"]["new_trail_km"])  # first walk of every section
        self.assertGreater(hike["totals"]["trail_km"], 2)
        reached = {p["name"] for p in hike["places"] if p["reached_here"]}
        self.assertTrue({"East Pass", "Trail Peak"} <= reached)
        self.assertNotIn("Hut", reached)  # the hut is up the green branch, off this walk
        self.assertTrue(all(len(point) == 3 for point in hike["track"]))
        self.assertIsNone(hike_context(self.conn, "not-a-hike"))

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            again = sync_tracks(self.conn, client)
        self.assertEqual(again["added"], 0)
        self.assertEqual(handler.stream_calls, ["11"])

    def test_rate_limit_keeps_sync_cursor_so_missing_tracks_are_retried(self):
        def limited(request):
            if request.url.path.endswith("/athlete/activities"):
                return httpx.Response(200, json=[activity(11, "Hike", [LAT, LON], 1725782400)] if request.url.params["page"] == "1" else [])
            return httpx.Response(429, json={})
        with httpx.Client(transport=httpx.MockTransport(limited)) as client:
            result = sync_tracks(self.conn, client)
        self.assertEqual((result["added"], result["pending"], result["complete"]), (0, 1, False))
        self.assertIsNone(get_setting_value(self.conn, SYNCED_UNTIL_KEY))



def with_alt(points, alt):
    return [[lat, lon, alt] for lat, lon in points]


class SummitHeightTests(unittest.TestCase):
    """Turning back below a summit must not count; walking over its marker always does."""

    def setUp(self):
        sections = build_sections(TRAILS, PARKS, "tatras")
        self.peak = {p["name"]: p for p in build_pois(TRAILS + PARKS + POIS, sections, "tatras")}["Trail Peak"]  # 2301 m, ~33 m off the trail
        self.beside = line(0, LON + 0.004, LON + 0.006)          # on the trail, ~33 m from the marker
        self.over = line(0.0003, LON + 0.004, LON + 0.006)       # straight over the marker

    def visits(self, *tracks):
        return compute_poi_visits([self.peak], list(tracks), LAT)[0]["visited_by"]

    def test_near_miss_far_below_the_summit_does_not_reach_it(self):
        self.assertEqual(self.visits({"activity_id": "low", "date": "2024-06-08", "latlng": with_alt(self.beside, 2215.0)}), [])

    def test_near_miss_within_height_tolerance_reaches_it(self):
        self.assertEqual(self.visits({"activity_id": "top", "date": "2024-06-08", "latlng": with_alt(self.beside, 2275.0)}), ["top"])

    def test_walking_over_the_marker_counts_whatever_the_altitude(self):
        self.assertEqual(self.visits({"activity_id": "over", "date": "2019-09-11", "latlng": with_alt(self.over, 2240.0)}), ["over"])

    def test_track_without_altitude_needs_a_close_pass(self):
        close = {"activity_id": "close", "date": "2019-01-01", "latlng": with_alt(self.beside, None)}
        farther = {"activity_id": "far", "date": "2019-01-01", "latlng": with_alt(line(-0.0002, LON + 0.004, LON + 0.006), None)}  # ~55 m
        self.assertEqual(self.visits(close, farther), ["close"])

    def test_places_without_height_ignore_altitude(self):
        hut = dict(self.peak, kind="hut", ele=None)
        track = {"activity_id": "x", "date": "2024-06-08", "latlng": with_alt(self.beside, 1500.0)}
        self.assertEqual(compute_poi_visits([hut], [track], LAT)[0]["visited_by"], ["x"])

    def test_thin_track_keeps_altitude(self):
        from backend.app.services.trail_coverage import Projection, thin_track
        thinned = thin_track([[LAT, LON], [LAT, LON + 0.00001], [LAT, LON + 0.001]], 5, Projection(LAT), [1000.04, 1001.0, 1010.0])
        self.assertEqual(thinned, [[LAT, LON, 1000.0], [LAT, LON + 0.001, 1010.0]])
        self.assertEqual(thin_track([[LAT, LON], [LAT, LON + 0.001]], 5, Projection(LAT)), [[LAT, LON], [LAT, LON + 0.001]])


class AltitudeBackfillTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(repo.SCHEMA + "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);")
        import_region(self.conn, "tatras", fetch=lambda query: TRAILS + PARKS + POIS, elevations=fake_heights)
        repo.upsert_track(self.conn, {"activity_id": "old", "region": "tatras", "name": "Old hike", "date": "2019-09-13",
                                      "sport_type": "Hike", "distance_km": 10, "elevation_m": 900, "latlng": line(0, LON, LON + 0.01)})

    def tearDown(self):
        self.conn.close()

    def test_sync_adds_altitude_to_tracks_stored_without_it(self):
        def handler(request):
            if request.url.path.endswith("/athlete/activities"):
                return httpx.Response(200, json=[])
            handler.calls.append((request.url.path.split("/")[-2], request.url.params["keys"]))
            return httpx.Response(200, json={"latlng": {"data": line(0, LON, LON + 0.01)}, "altitude": {"data": [2000.0] * 61}})
        handler.calls = []
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = sync_tracks(self.conn, client)
        self.assertEqual(handler.calls, [("old", "latlng,altitude")])
        self.assertEqual((result["altitude_added"], result["altitude_pending"]), (1, 0))
        self.assertEqual(repo.list_tracks(self.conn, "tatras")[0]["latlng"][0][2], 2000.0)
        self.assertEqual(repo.tracks_without_altitude(self.conn), [])

    def test_rate_limit_leaves_the_rest_for_the_next_sync(self):
        def limited(request):
            if request.url.path.endswith("/athlete/activities"):
                return httpx.Response(200, json=[])
            return httpx.Response(429, json={})
        with httpx.Client(transport=httpx.MockTransport(limited)) as client:
            result = sync_tracks(self.conn, client)
        self.assertEqual((result["altitude_added"], result["altitude_pending"]), (0, 1))
        self.assertEqual(repo.tracks_without_altitude(self.conn), [("old", "tatras")])


def valley(way_id, name, points):
    return {"type": "way", "id": way_id, "nodes": list(range(len(points))), "tags": {"natural": "valley", "name": name},
            "geometry": [{"lat": a, "lon": b} for a, b in points]}


class ValleyLabelTests(unittest.TestCase):
    def test_valleys_become_labels_along_their_axis_longest_first(self):
        labels = build_valley_labels([
            valley(401, "Dolina Kościeliska", [(LAT, LON), (LAT + 0.03, LON)]),
            valley(402, "Dolina Kościeliska", [(LAT, LON), (LAT + 0.002, LON)]),   # shorter duplicate piece
            valley(403, "Żleb", [(LAT, LON + 0.01), (LAT, LON + 0.012)]),
            valley(404, "Tiny", [(LAT, LON), (LAT + 0.0002, LON)]),                # under 100 m
            poi(405, LAT, LON, natural="valley", name="Node valley"),
        ], "tatras")
        self.assertEqual([l["name"] for l in labels], ["Dolina Kościeliska", "Żleb"])
        kosc = labels[0]
        self.assertAlmostEqual(kosc["lat"], LAT + 0.015, places=5)
        self.assertLess(kosc["a"][0], kosc["b"][0])  # axis runs south to north like the valley
        self.assertGreater(kosc["length_m"], 3000)

    def test_import_stores_valley_labels(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(repo.SCHEMA + "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);")
        import_region(conn, "tatras", fetch=lambda q: TRAILS + PARKS + POIS + [valley(401, "Dolina", [(LAT, LON), (LAT + 0.03, LON)])], elevations=fake_heights)
        self.assertEqual([l["name"] for l in region_map(conn, "tatras")["labels"]], ["Dolina"])
        conn.close()


class HistoryBackfillTests(unittest.TestCase):
    """Old mountain hikes and walks join the activity history so they get a detail page; runs don't."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from backend.app import db
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, "DB_PATH", str(Path(self.temp.name) / "test.db"))
        self.patch.start()
        db.init_db()
        self.conn = db.get_db()
        for activity_id, sport in (("101", "Hike"), ("102", "Walk"), ("103", "Run")):
            repo.upsert_track(self.conn, {"activity_id": activity_id, "region": "tatras", "name": f"{sport} {activity_id}", "date": "2018-09-21",
                                          "sport_type": sport, "distance_km": 20, "elevation_m": 1500, "latlng": [[LAT, LON, 1000.0], [LAT, LON + 0.01, 1100.0]]})
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.patch.stop()
        self.temp.cleanup()

    def test_sync_adds_missing_hikes_and_walks_but_not_runs(self):
        def handler(request):
            if request.url.path.endswith("/athlete/activities"):
                return httpx.Response(200, json=[])
            activity_id = request.url.path.rsplit("/", 1)[-1]
            handler.calls.append(activity_id)
            sport = {"101": "Hike", "102": "Walk"}[activity_id]
            return httpx.Response(200, json={"id": int(activity_id), "name": f"Old {sport}", "type": sport, "sport_type": sport,
                                             "start_date_local": "2018-09-21T08:00:00Z", "distance": 25200, "moving_time": 30000,
                                             "total_elevation_gain": 1600, "average_heartrate": 118, "max_heartrate": 165})
        handler.calls = []
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = sync_tracks(self.conn, client)
        self.assertEqual((result["history_added"], result["history_pending"]), (2, 0))
        self.assertEqual(handler.calls, ["101", "102"])
        rows = {r["id"]: dict(r) for r in self.conn.execute("SELECT id, type, date, distance_km, duration_min, avg_hr FROM activities")}
        self.assertEqual(sorted(rows), ["101", "102"])
        self.assertEqual((rows["101"]["type"], rows["101"]["date"], rows["101"]["distance_km"], rows["101"]["duration_min"]), ("Hike", "2018-09-21", 25.2, 500.0))

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            again = sync_tracks(self.conn, client)
        self.assertEqual(again["history_added"], 0)
        self.assertEqual(handler.calls, ["101", "102"])

if __name__ == "__main__":
    unittest.main()
