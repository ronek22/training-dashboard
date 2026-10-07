"""Manual route planner: the user clicks points on the map, the route between them follows the
marked trails (shortest walking time on the trail graph, like the route ideas), and the answer
carries the geometry with heights, distance, Naismith time and how much of it is new trail.

Clicks snap to the nearest trail within SNAP_M; a click further out stays where it is and is
joined with a straight, off-trail line (an approach road, a car park). Heights come from the
elevation cache only, sampled exactly as at import, so planning never calls the elevation API.
"""
import heapq
import math
from bisect import bisect_right
from collections import defaultdict
from typing import Optional

from ..repositories import trails as repo
from .route_ideas import TrailGraph, _places_on_route, clean_stop_name, walking_hours
from .trail_coverage import REGIONS, Projection, sample_polyline
from .trail_elevation import PROFILE_SPACING_M, _key

SNAP_M = 200          # a click this close to a trail lands on it (the map sends more when zoomed out)
MAX_SNAP_M = 1000
PLACE_NAME_M = 150    # a waypoint this close to a summit, pass or hut takes its name
TRAILHEAD_NAME_M = 300
MAX_POINTS = 60


class Network:
    """The trail graph of one range plus what planning needs per section: projected geometry,
    distance along it, and the cached height profile."""

    def __init__(self, conn, region_key: str, sections: list[dict]):
        bbox = REGIONS[region_key]["bbox"]
        self.projection = Projection((bbox[0] + bbox[2]) / 2)  # the projection the heights were cached with
        self.sections = sections
        self.graph = TrailGraph(sections)
        self.xy, self.along, self.bounds, samples = [], [], [], []
        for section in sections:
            points = [self.projection.xy(lat, lon) for lat, lon in section["coords"]]
            along = [0.0]
            for a, b in zip(points, points[1:]):
                along.append(along[-1] + math.dist(a, b))
            self.xy.append(points)
            self.along.append(along)
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            self.bounds.append((min(xs), min(ys), max(xs), max(ys)))
            samples.append(sample_polyline(points, PROFILE_SPACING_M))
        known = repo.cached_elevations(conn, sorted({_key(*self.projection.latlon(x, y)) for s in samples for x, y in s}))
        # Heights at evenly spaced offsets along each section (None where never fetched).
        self.heights = [[known.get(_key(*self.projection.latlon(x, y))) for x, y in s] for s in samples]
        self.pois = repo.list_pois(conn, region_key)
        self.trailheads = repo.list_trailheads(conn, region_key)

    # ---------- geometry ----------

    def length(self, i: int) -> float:
        return self.along[i][-1]

    def point_at(self, i: int, offset: float) -> tuple[float, float]:
        along, points = self.along[i], self.xy[i]
        k = min(max(bisect_right(along, offset) - 1, 0), len(points) - 2)
        span = along[k + 1] - along[k]
        share = 0.0 if not span else min(1.0, max(0.0, (offset - along[k]) / span))
        (x1, y1), (x2, y2) = points[k], points[k + 1]
        return x1 + share * (x2 - x1), y1 + share * (y2 - y1)

    def height_at(self, i: int, offset: float) -> Optional[float]:
        heights, total = self.heights[i], self.length(i)
        if not total or len(heights) < 2:
            return heights[0] if heights else None
        position = min(max(offset / total, 0.0), 1.0) * (len(heights) - 1)
        k = min(int(position), len(heights) - 2)
        a, b = heights[k], heights[k + 1]
        if a is None or b is None:
            return a if b is None else b
        return a + (position - k) * (b - a)

    def snap(self, lat: float, lon: float, radius: float = SNAP_M) -> Optional[tuple[int, float, float]]:
        """(section index, offset along it, distance) of the nearest trail point within `radius`."""
        x, y = self.projection.xy(lat, lon)
        best = None
        for i, (x0, y0, x1, y1) in enumerate(self.bounds):
            if x < x0 - radius or x > x1 + radius or y < y0 - radius or y > y1 + radius:
                continue
            points, along = self.xy[i], self.along[i]
            for k in range(len(points) - 1):
                (ax, ay), (bx, by) = points[k], points[k + 1]
                dx, dy = bx - ax, by - ay
                span = dx * dx + dy * dy
                t = 0.0 if not span else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / span))
                d = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
                if d <= radius and (best is None or d < best[2]):
                    best = (i, along[k] + t * (along[k + 1] - along[k]), d)
        return best

    # ---------- pieces of trail ----------

    def piece(self, i: int, start: float, end: float) -> dict:
        """Walking section i from offset `start` to offset `end` (either direction)."""
        forward = end >= start
        lo, hi = min(start, end), max(start, end)
        along = self.along[i]
        offsets = [lo] + [a for a in along if lo < a < hi] + [hi]
        if not forward:
            offsets.reverse()
        coords = []
        for offset in offsets:
            lat, lon = self.projection.latlon(*self.point_at(i, offset))
            coords.append([lat, lon, self.height_at(i, offset)])
        # Climb from the cached 100 m samples inside the piece plus its two ends.
        heights, total = self.heights[i], self.length(i)
        step = total / (len(heights) - 1) if len(heights) > 1 else total
        inside = [(k * step, h) for k, h in enumerate(heights) if lo < k * step < hi]
        profile = [self.height_at(i, lo)] + [h for _, h in inside] + [self.height_at(i, hi)]
        if not forward:
            profile.reverse()
        up = down = None
        if all(h is not None for h in profile):
            rises = [b - a for a, b in zip(profile, profile[1:])]
            up, down = sum(r for r in rises if r > 0), -sum(r for r in rises if r < 0)
        length = hi - lo
        return {"section": i, "coords": coords, "length_m": length, "ascent_m": up, "descent_m": down,
                "hours": walking_hours(length, up, down), "on_trail": True,
                "new": self.sections[i]["status"] != "done"}

    def off_trail(self, a: list, b: list) -> dict:
        length = math.dist(self.projection.xy(a[0], a[1]), self.projection.xy(b[0], b[1]))
        return {"section": None, "coords": [[a[0], a[1], None], [b[0], b[1], None]], "length_m": length, "ascent_m": None, "descent_m": None,
                "hours": walking_hours(length, None, None), "on_trail": False, "new": False}

    # ---------- routing ----------

    def leg(self, a: dict, b: dict) -> list[dict]:
        """Pieces from waypoint a to waypoint b: along the trails when both are on one."""
        if a["snap"] is None or b["snap"] is None:
            return [self.off_trail(a["point"], b["point"])]
        (i, off_a, _), (j, off_b, _) = a["snap"], b["snap"]
        if i == j:
            return [self.piece(i, off_a, off_b)]
        coords_i, coords_j = self.sections[i]["coords"], self.sections[j]["coords"]
        # Leave section i by either end, enter section j by either end.
        starts = {tuple(coords_i[0]): self.piece(i, off_a, 0), tuple(coords_i[-1]): self.piece(i, off_a, self.length(i))}
        ends = {tuple(coords_j[0]): self.piece(j, 0, off_b), tuple(coords_j[-1]): self.piece(j, self.length(j), off_b)}
        dist, prev, origin = {}, {}, {}
        queue = []
        for node, first in starts.items():
            if node not in dist or first["hours"] < dist[node]:
                dist[node], origin[node] = first["hours"], node
                heapq.heappush(queue, (first["hours"], node))
        best, best_node = math.inf, None
        while queue:
            d, node = heapq.heappop(queue)
            if d > dist.get(node, math.inf) or d >= best:
                continue
            if node in ends and d + ends[node]["hours"] < best:
                best, best_node = d + ends[node]["hours"], node
            for other, hours, index, forward in self.graph.adj[node]:
                nd = d + hours
                if nd < dist.get(other, math.inf):
                    dist[other], prev[other] = nd, (node, index, forward)
                    heapq.heappush(queue, (nd, other))
        if best_node is None:
            return [self.off_trail(a["point"], b["point"])]  # trails not connected
        steps, node = [], best_node
        while node in prev:
            node, index, forward = prev[node]
            steps.append((index, forward))
        start_node = node
        middle = [self.piece(index, 0, self.length(index)) if forward else self.piece(index, self.length(index), 0) for index, forward in reversed(steps)]
        return [p for p in [starts[start_node], *middle, ends[best_node]] if p["length_m"] > 0.5]

    def waypoint(self, lat: float, lon: float, radius: float = SNAP_M) -> dict:
        snap = self.snap(lat, lon, max(SNAP_M, min(radius, MAX_SNAP_M)))
        if snap:
            lat, lon = self.projection.latlon(*self.point_at(snap[0], snap[1]))
        return {"point": [lat, lon], "snap": snap, "name": self._name_near(lat, lon)}

    def _name_near(self, lat: float, lon: float) -> Optional[str]:
        here = self.projection.xy(lat, lon)
        def distance(p):
            return math.dist(here, self.projection.xy(p["lat"], p["lon"]))
        places = [(distance(p), p) for p in self.pois if p["kind"] in ("peak", "pass", "hut")]
        near = min((dp for dp in places if dp[0] <= PLACE_NAME_M), key=lambda dp: dp[0], default=None)
        if near:
            return near[1]["name"]
        heads = [(distance(t), t) for t in self.trailheads]
        head = min((dt for dt in heads if dt[0] <= TRAILHEAD_NAME_M), key=lambda dt: dt[0], default=None)
        return clean_stop_name(head[1]["name"]) if head else None


_networks: dict[tuple, Network] = {}


def _network(conn, region_key: str) -> Network:
    sections = repo.list_sections(conn, region_key)
    signature = (region_key, repo.imported_at(conn, region_key), hash(tuple((s["id"], s["status"]) for s in sections)))
    if signature not in _networks:
        _networks.clear()  # one range at a time keeps memory flat
        _networks[signature] = Network(conn, region_key, sections)
    return _networks[signature]


def _simplify(network: Network, waypoints: list[dict]) -> list[dict]:
    """Drops points the route passes through anyway (same distance without them), so a route
    opened from an idea keeps only the points that shape it."""
    kept = [waypoints[0]]
    for i in range(1, len(waypoints) - 1):
        a, here, b = kept[-1], waypoints[i], waypoints[i + 1]
        if here["snap"] is None:
            kept.append(here)
            continue
        through = sum(p["length_m"] for p in network.leg(a, here) + network.leg(here, b))
        direct = network.leg(a, b)
        if any(not p["on_trail"] for p in direct) or abs(sum(p["length_m"] for p in direct) - through) > 1:
            kept.append(here)
    return kept + waypoints[-1:] if len(waypoints) > 1 else kept


def plan_route(conn, region_key: str, points: list, simplify: bool = False) -> dict:
    if region_key not in REGIONS:
        raise ValueError(f"Unknown region: {region_key}")
    if len(points) > MAX_POINTS:
        raise ValueError(f"A route can have at most {MAX_POINTS} points")
    network = _network(conn, region_key)
    if not network.sections:
        raise ValueError("Trails for this range aren't loaded yet")
    # A point is [lat, lon] or [lat, lon, snap radius in metres].
    waypoints = [network.waypoint(float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else SNAP_M) for p in points]
    for waypoint, point in zip(waypoints, points):
        waypoint["input"] = list(point)
    if simplify:
        waypoints = _simplify(network, waypoints)
    pieces = [piece for a, b in zip(waypoints, waypoints[1:]) for piece in network.leg(a, b)]

    track: list[list] = []
    segments: list[dict] = []
    for piece in pieces:
        coords = [[round(lat, 6), round(lon, 6), round(ele, 1) if ele is not None else None] for lat, lon, ele in piece["coords"]]
        track.extend(coords[1:] if track else coords)
        last = segments[-1] if segments else None
        if last and last["new"] == piece["new"] and last["on_trail"] == piece["on_trail"]:
            last["coords"].extend([c[:2] for c in coords[1:]])
        else:
            segments.append({"new": piece["new"], "on_trail": piece["on_trail"], "coords": [c[:2] for c in coords]})
    if not track and waypoints:
        lat, lon = waypoints[0]["point"]
        track = [[round(lat, 6), round(lon, 6), None]]

    have_heights = pieces and all(p["ascent_m"] is not None for p in pieces if p["on_trail"])
    on_route = _places_on_route(network.pois, [tuple(c[:2]) for c in track], "") if len(track) > 1 else []
    heights = [c[2] for c in track if c[2] is not None]
    return {
        "waypoints": [{"lat": round(w["point"][0], 6), "lon": round(w["point"][1], 6), "on_trail": w["snap"] is not None, "name": w["name"]} for w in waypoints],
        "points": [w["input"] for w in waypoints],  # the clicks behind the waypoints (fewer after simplify)
        "segments": segments,
        "track": track,
        "distance_m": round(sum(p["length_m"] for p in pieces)),
        "hours": round(sum(p["hours"] for p in pieces), 2),
        "ascent_m": round(sum(p["ascent_m"] or 0 for p in pieces)) if have_heights else None,
        "descent_m": round(sum(p["descent_m"] or 0 for p in pieces)) if have_heights else None,
        "max_ele": round(max(heights)) if heights else None,
        "new_m": round(sum(p["length_m"] for p in pieces if p["new"])),
        "off_trail_m": round(sum(p["length_m"] for p in pieces if not p["on_trail"])),
        "places": [{"name": p["name"], "kind": p["kind"], "ele": p.get("ele"), "lat": p["lat"], "lon": p["lon"], "reached": bool(p["visited_by"])} for p in on_route],
    }


# ---------- saved routes ----------

MAX_NAME = 120


def _clean(name: Optional[str], collection: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    name = " ".join(name.split())[:MAX_NAME] if name is not None else None
    collection = " ".join(collection.split())[:MAX_NAME] if collection is not None else None
    if name is not None and not name:
        raise ValueError("A saved route needs a name")
    return name, collection


def _existing_collection(conn, region_key: str, collection: Optional[str]) -> Optional[str]:
    """An existing collection's spelling when only the case differs ("winter" joins "Winter")."""
    if not collection:
        return collection
    for route in repo.list_saved_routes(conn, region_key):
        if route["collection"].lower() == collection.lower():
            return route["collection"]
    return collection


def _summary(planned: dict) -> dict:
    return {key: planned[key] for key in ("distance_m", "hours", "ascent_m", "descent_m", "max_ele", "new_m")}


def list_saved_routes(conn, region_key: str) -> dict:
    """Saved routes of a range, each re-planned so new trail reflects the hikes since saving."""
    if region_key not in REGIONS:
        raise ValueError(f"Unknown region: {region_key}")
    routes = repo.list_saved_routes(conn, region_key)
    for route in routes:
        try:
            route.update(_summary(plan_route(conn, region_key, route["points"])))
        except ValueError:
            route["new_m"] = None  # trails not loaded: keep the stats from when it was saved
    collections = sorted({r["collection"] for r in routes if r["collection"]}, key=str.lower)
    return {"routes": routes, "collections": collections}


def save_route(conn, region_key: str, name: str, collection: str, points: list) -> dict:
    name, collection = _clean(name, collection or "")
    collection = _existing_collection(conn, region_key, collection)
    if len(points) < 2:
        raise ValueError("A route needs at least two points")
    planned = plan_route(conn, region_key, points)
    route_id = repo.insert_saved_route(conn, region_key, name, collection, points, planned)
    conn.commit()
    return repo.get_saved_route(conn, route_id)


def update_route(conn, route_id: int, name: Optional[str] = None, collection: Optional[str] = None, points: Optional[list] = None) -> dict:
    current = repo.get_saved_route(conn, route_id)
    if not current:
        raise LookupError("Saved route not found")
    name, collection = _clean(name, collection)
    collection = _existing_collection(conn, current["region"], collection)
    fields = {key: value for key, value in (("name", name), ("collection", collection)) if value is not None}
    if points is not None:
        if len(points) < 2:
            raise ValueError("A route needs at least two points")
        fields["points"] = points
        fields.update(plan_route(conn, current["region"], points))
    repo.update_saved_route(conn, route_id, fields)
    conn.commit()
    return repo.get_saved_route(conn, route_id)


def delete_route(conn, route_id: int) -> None:
    if not repo.delete_saved_route(conn, route_id):
        raise LookupError("Saved route not found")
    conn.commit()
