"""Mountain trail coverage: which marked trails the athlete has walked.

Trails come from OpenStreetMap hiking relations (PTTK/KST/KČT colour marks), split
into junction-to-junction sections and clipped to the national parks of a region.
Coverage compares 10 m samples along each section with the athlete's GPS tracks.
"""
import math
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from ..repositories import trails as repo
from ..repositories.settings import get_setting_value, set_setting_value

REGIONS = {
    "tatras": {
        "name": "Tatras",
        "bbox": (49.05, 19.50, 49.35, 20.40),
        "parks": {
            2226518: {"key": "TPN", "country": "PL", "name": "Tatrzański Park Narodowy"},
            6757027: {"key": "TANAP", "country": "SK", "name": "Tatranský národný park"},
        },
    },
    "karkonosze": {
        "name": "Karkonosze",
        "bbox": (50.60, 15.35, 50.88, 16.05),
        "parks": {
            1329832: {"key": "KPN", "country": "PL", "name": "Karkonoski Park Narodowy"},
            2327566: {"key": "KRNAP", "country": "CZ", "name": "Krkonošský národní park"},
        },
        # Cycle routes around Szklarska Poręba double as winter walking routes; only on the Polish side.
        "bike_parks": ("KPN",),
    },
}

TRAIL_COLOURS = ("red", "blue", "green", "yellow", "black", "bike")
BIKE_ROUTES = {"bicycle", "mtb"}
# Standard marked trail: coloured stripe between two white ones, e.g. "red:white:red_bar".
TRAIL_SYMBOL = re.compile(r"^(red|blue|green|yellow|black):white:\1_bar$")

SAMPLE_M = 10            # spacing of coverage samples along a section
MATCH_M = 30             # a sample is walked when a track passes this close
DONE_SHARE = 0.8         # share of samples needed for a section to count as done
PARTIAL_SHARE = 0.25
CREDIT_SHARE = 0.6       # share of samples one activity needs to be credited with a section
MAX_TRACK_GAP_M = 200    # longer jumps are lifts or GPS gaps, never walked
DRIFT_MATCH_M = 150      # second pass for drifting GPS: how far off a track may run ...
DRIFT_DONE_SHARE = 0.85  # ... along how much of the section, while it stays the nearest trail
DRIFT_NEAREST_SLACK_M = 15
DRIFT_SAMPLE_M = 20
DRIFT_END_M = 150        # ... and the track reaches both ends of the section this closely (Piechowice: 145 m drift; Zadni Granat turned back 208 m short)
TRACK_STORE_SPACING_M = 5
CELL_M = 50

FOOT_SPORTS = {"Hike", "Walk", "Run", "TrailRun", "BackcountrySki", "Snowshoe"}
# Mountain tracks of these sports are also added to the activity history (so they get a detail
# page); runs are left out because old runs would land on the personal best wall.
HISTORY_SPORTS = ("Hike", "Walk")
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
# Named places along the trails. A place is listed only when a marked trail comes within
# NEAR_TRAIL metres: summits the trail reaches (Świnica's tourist top is ~70 m from the main
# summit), passes and caves the trail goes through, huts beside it. It counts as reached when
# a GPS track gets as close as the trail allows plus some GPS slack.
POI_KINDS = ("peak", "pass", "cave", "hut")
POI_NEAR_TRAIL_M = {"peak": 80, "pass": 40, "cave": 30, "hut": 150}
POI_VISIT_M = {"peak": 50, "pass": 50, "cave": 60, "hut": 80}
POI_VISIT_SLACK_M = 30
# Summits and passes: walking within DIRECT metres of the marker always counts, whatever the
# altitude says (Mały Kościelec's marker sits on the trail below the true top). A near miss beyond
# that counts only when the hike also got within HEIGHT_TOLERANCE of the summit height, so turning
# back below a top doesn't (Świnica: 61 m away but 75 m below). Strava altitude, barometric or
# terrain-corrected, matched known pass and hut heights within ±25 m on hikes from 2016 to 2026;
# summits really reached read 20–29 m low, tops only skirted −37 m or lower.
POI_HEIGHT_KINDS = {"peak", "pass"}
POI_DIRECT_M = 25
POI_HEIGHT_TOLERANCE_M = 35
POI_CELL_M = 100

USER_AGENT = "training-dashboard/1.0 (personal trail coverage)"
SYNCED_UNTIL_KEY = "trail_tracks_synced_until"


# ---------- geometry ----------

class Projection:
    """Local equirectangular projection in metres; accurate enough within one range."""

    def __init__(self, lat0: float):
        self.kx = 111320 * math.cos(math.radians(lat0))
        self.ky = 110540

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        return lon * self.kx, lat * self.ky

    def latlon(self, x: float, y: float) -> tuple[float, float]:
        return y / self.ky, x / self.kx


def polyline_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def sample_polyline(points: list[tuple[float, float]], spacing: float) -> list[tuple[float, float]]:
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    count = max(2, int(total // spacing) + 1)
    samples, travelled, index = [], 0.0, 0
    for step in range(count):
        target = total * step / (count - 1)
        while index < len(lengths) - 1 and travelled + lengths[index] < target:
            travelled += lengths[index]
            index += 1
        share = 0.0 if lengths[index] == 0 else min(1.0, max(0.0, (target - travelled) / lengths[index]))
        (x1, y1), (x2, y2) = points[index], points[index + 1]
        samples.append((x1 + share * (x2 - x1), y1 + share * (y2 - y1)))
    return samples


def point_along(points: list[tuple[float, float]], distance: float) -> tuple[float, float]:
    for a, b in zip(points, points[1:]):
        step = math.dist(a, b)
        if step and distance <= step:
            share = distance / step
            return a[0] + share * (b[0] - a[0]), a[1] + share * (b[1] - a[1])
        distance -= step
    return points[-1]


def point_in_edges(edges: list[tuple[tuple[float, float], tuple[float, float]]], lon: float, lat: float) -> bool:
    """Ray casting over an unordered set of boundary edges (outer and inner rings alike)."""
    inside = False
    for (x1, y1), (x2, y2) in edges:
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def thin_track(latlng: list, spacing: float, projection: Projection, altitude: Optional[list] = None) -> list[list]:
    """Keep a point every `spacing` metres. Points are [lat, lon] or, once altitude is known,
    [lat, lon, alt] (alt may be None when Strava has no altitude for the activity)."""
    def entry(i: int) -> list:
        point = latlng[i]
        lat, lon = round(point[0], 6), round(point[1], 6)
        if altitude is None and len(point) < 3:
            return [lat, lon]
        alt = (altitude[i] if i < len(altitude) else None) if altitude is not None else point[2]
        return [lat, lon, None if alt is None else round(alt, 1)]

    kept, last = [], None
    for i, point in enumerate(latlng):
        xy = projection.xy(point[0], point[1])
        if last is None or math.dist(xy, last) >= spacing:
            kept.append(entry(i))
            last = xy
    if latlng and kept[-1][:2] != [round(latlng[-1][0], 6), round(latlng[-1][1], 6)]:
        kept.append(entry(len(latlng) - 1))
    return kept


# ---------- trail sections from OSM ----------

def _edge(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def build_sections(trail_elements: list[dict], park_elements: list[dict], region_key: str, bike_parks: Optional[tuple] = None) -> list[dict]:
    """Split marked trails into junction-to-junction sections inside the region's parks.
    In `bike_parks` cycle routes count too, as the "bike" colour, where no hiking trail runs."""
    region = REGIONS[region_key]
    bike_parks = set(region.get("bike_parks", ()) if bike_parks is None else bike_parks)
    ways = {e["id"]: e for e in trail_elements if e["type"] == "way"}
    node_ll: dict[int, tuple[float, float]] = {}
    edge_colours: dict[tuple[int, int], set] = defaultdict(set)
    edge_names: dict[tuple[int, int], set] = defaultdict(set)
    hiking_names: set = set()
    for relation in (e for e in trail_elements if e["type"] == "relation"):
        tags = relation.get("tags", {})
        match = TRAIL_SYMBOL.match(tags.get("osmc:symbol", "")) if tags.get("route") == "hiking" else None
        if match:
            colour = match.group(1)
        elif bike_parks and tags.get("route") in BIKE_ROUTES:
            colour = "bike"
        else:
            continue
        name = tags.get("name") or tags.get("description") or tags.get("ref")
        if match and name:
            hiking_names.add(name)
        for member in relation.get("members", []):
            way = ways.get(member["ref"]) if member["type"] == "way" else None
            if not way:
                continue
            for node, point in zip(way["nodes"], way.get("geometry") or []):
                if point:
                    node_ll[node] = (point["lat"], point["lon"])
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                if a != b and a in node_ll and b in node_ll:
                    edge_colours[_edge(a, b)].add(colour)
                    if name:
                        edge_names[_edge(a, b)].add(name)

    # Where a cycle route runs on a marked hiking trail, the hiking marks win.
    for key, colours in edge_colours.items():
        if "bike" in colours and len(colours) > 1:
            colours.discard("bike")
            edge_names[key] = {n for n in edge_names[key] if n in hiking_names}

    neighbours: dict[int, set] = defaultdict(set)
    for a, b in edge_colours:
        neighbours[a].add(b)
        neighbours[b].add(a)

    def is_break(node: int) -> bool:
        if len(neighbours[node]) != 2:
            return True
        a, b = neighbours[node]
        return edge_colours[_edge(node, a)] != edge_colours[_edge(node, b)]

    visited: set = set()

    def walk(start: int, nxt: int) -> list[int]:
        path = [start, nxt]
        visited.add(_edge(start, nxt))
        while not is_break(path[-1]):
            options = [n for n in neighbours[path[-1]] if _edge(path[-1], n) not in visited]
            if not options:
                break
            visited.add(_edge(path[-1], options[0]))
            path.append(options[0])
        return path

    chains = []
    for node in list(neighbours):
        if is_break(node):
            for nxt in sorted(neighbours[node]):
                if _edge(node, nxt) not in visited:
                    chains.append(walk(node, nxt))
    for edge in sorted(edge_colours):  # closed loops without a junction
        if edge not in visited:
            chains.append(walk(*edge))

    park_edges = _park_edges(park_elements, region)
    projection = Projection((region["bbox"][0] + region["bbox"][2]) / 2)
    boundary_grids = {key: _edge_grid(edges, projection) for key, edges in park_edges.items()}
    around_grids = {key: _edge_grid(edges, projection, AROUND_PARKS_M, AROUND_CELL_M) for key, edges in park_edges.items()}
    sections = []
    for path in chains:
        coords = [node_ll[n] for n in path]
        points = [projection.xy(*p) for p in coords]
        length = polyline_length(points)
        if length < 1:
            continue
        mid_lat, mid_lon = projection.latlon(*point_along(points, length / 2))
        park = next((key for key, edges in park_edges.items() if point_in_edges(edges, mid_lon, mid_lat)), None)
        around = not park
        if park:
            # A trail along the state border (e.g. Kasprowy – Kopa Kondracka) belongs to both parks.
            samples = sample_polyline(points, 25)
            parks = {park} | {
                key for key, grid in boundary_grids.items()
                if sum(_near_edges(grid, x, y, SHARED_BORDER_M) for x, y in samples) >= SHARED_BORDER_SHARE * len(samples)
            }
        else:
            # Trails just outside the parks (Szklarska Poręba, Piechowice, Karpacz, Zakopane) count
            # for the nearest park, so its area covers the whole trail network around it.
            mid = projection.xy(mid_lat, mid_lon)
            distances = {key: _edge_distance(grid, *mid, AROUND_CELL_M) for key, grid in around_grids.items()}
            park = min(distances, key=distances.get) if distances else None
            if park is None or distances[park] > AROUND_PARKS_M:
                continue
            parks = {park}
        colours = [c for c in TRAIL_COLOURS if c in edge_colours[_edge(path[0], path[1])]]
        if colours == ["bike"] and park not in bike_parks:
            continue
        pairs = list(zip(path, path[1:]))
        names = sorted(set().union(*(edge_names[_edge(a, b)] for a, b in pairs)))
        sections.append({
            "osm_key": f"{min(path[0], path[-1])}-{max(path[0], path[-1])}-{len(path)}",
            "park": park,
            "parks": sorted(parks),
            "around": around,
            "colours": colours,
            "names": names[:4],
            "coords": [[round(lat, 6), round(lon, 6)] for lat, lon in coords],
            "length_m": round(length, 1),
        })
    return sections


SHARED_BORDER_M = 40       # a section sample this close to a park's boundary is "on" that border
SHARED_BORDER_SHARE = 0.5  # share of a section that must run along a park's boundary to count for that park
BOUNDARY_CELL_M = 100
AROUND_PARKS_M = 8000     # trails outside the parks but this close to one count for the nearest park
AROUND_CELL_M = 2000


def _edge_grid(edges: list, projection: Projection, reach: float = SHARED_BORDER_M, cell: float = BOUNDARY_CELL_M) -> dict[tuple[int, int], list]:
    """Boundary edges (lon/lat pairs) projected to metres and bucketed by cell."""
    grid: dict[tuple[int, int], list] = defaultdict(list)
    for (lon1, lat1), (lon2, lat2) in edges:
        (x1, y1), (x2, y2) = projection.xy(lat1, lon1), projection.xy(lat2, lon2)
        for cx in range(int((min(x1, x2) - reach) // cell), int((max(x1, x2) + reach) // cell) + 1):
            for cy in range(int((min(y1, y2) - reach) // cell), int((max(y1, y2) + reach) // cell) + 1):
                grid[(cx, cy)].append((x1, y1, x2, y2))
    return grid


def _edge_distance(grid: dict, px: float, py: float, cell: float) -> float:
    best = math.inf
    for x1, y1, x2, y2 in grid.get(_cell(px, py, cell), ()):
        dx, dy = x2 - x1, y2 - y1
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
        best = min(best, math.hypot(px - x1 - t * dx, py - y1 - t * dy))
    return best


def _near_edges(grid: dict, px: float, py: float, limit: float, cell: float = BOUNDARY_CELL_M) -> bool:
    for x1, y1, x2, y2 in grid.get(_cell(px, py, cell), ()):
        dx, dy = x2 - x1, y2 - y1
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
        if math.hypot(px - x1 - t * dx, py - y1 - t * dy) <= limit:
            return True
    return False


def _park_edges(park_elements: list[dict], region: dict) -> dict[str, list]:
    ways = {e["id"]: e for e in park_elements if e["type"] == "way"}
    result = {}
    for relation in (e for e in park_elements if e["type"] == "relation"):
        park = region["parks"].get(relation["id"])
        if not park:
            continue
        edges = []
        for member in relation.get("members", []):
            way = ways.get(member["ref"]) if member["type"] == "way" else None
            if way:
                line = [(p["lon"], p["lat"]) for p in way.get("geometry") or [] if p]
                edges.extend(zip(line, line[1:]))
        result[park["key"]] = edges
    return result


# ---------- places (summits, passes, caves, huts) ----------

def poi_kind(tags: dict) -> Optional[str]:
    if tags.get("natural") == "cave_entrance":
        return "cave"
    if tags.get("tourism") == "alpine_hut":
        return "hut"
    if tags.get("natural") == "saddle" or tags.get("mountain_pass") == "yes":
        return "pass"
    if tags.get("natural") == "peak":
        return "peak"
    return None


def parse_elevation(value: Optional[str]) -> Optional[int]:
    match = re.match(r"\s*(\d+(?:[.,]\d+)?)", value or "")
    return round(float(match.group(1).replace(",", "."))) if match else None


# "Jaskinia Mroźna wejście" / "... wyjście" are two openings of one cave.
CAVE_OPENING = re.compile(r"\s*[-–,(]?\s*(wej[sś]cie|wyj[sś]cie|otw[oó]r)\b.*$", re.IGNORECASE)
BORDER_REACH_M = 60


def place_name(kind: str, name: str) -> str:
    return CAVE_OPENING.sub("", name).strip() or name if kind == "cave" else name


def _cell(x: float, y: float, size: float) -> tuple[int, int]:
    return int(x // size), int(y // size)


def build_valley_labels(elements: list[dict], region_key: str) -> list[dict]:
    """Named valleys, gullies and cirques as map labels: a midpoint plus two points around it
    that give the valley's direction there, so the name can be drawn along the valley."""
    bbox = REGIONS[region_key]["bbox"]
    projection = Projection((bbox[0] + bbox[2]) / 2)
    longest: dict[str, dict] = {}
    for element in elements:
        tags = element.get("tags", {})
        name = (tags.get("name") or "").strip()
        if element["type"] != "way" or tags.get("natural") != "valley" or not name:
            continue
        points = [projection.xy(p["lat"], p["lon"]) for p in element.get("geometry") or [] if p]
        if len(points) < 2:
            continue
        length = polyline_length(points)
        if length < 100 or (name in longest and longest[name]["length_m"] >= length):
            continue  # the same valley is sometimes split into several ways; keep the longest

        def at(share: float) -> list[float]:
            lat, lon = projection.latlon(*point_along(points, length * share))
            return [round(lat, 6), round(lon, 6)]

        mid = at(0.5)
        longest[name] = {"kind": "valley", "name": name, "lat": mid[0], "lon": mid[1], "a": at(0.3), "b": at(0.7), "length_m": round(length)}
    return sorted(longest.values(), key=lambda label: -label["length_m"])


def build_pois(elements: list[dict], sections: list[dict], region_key: str) -> list[dict]:
    """Named places close to a marked trail, in every park whose trail reaches them (border summits)."""
    region = REGIONS[region_key]
    bbox = region["bbox"]
    projection = Projection((bbox[0] + bbox[2]) / 2)
    park_edges = _park_edges(elements, region)
    trail_points: dict[tuple[int, int], list] = defaultdict(list)
    for section in sections:
        for x, y in sample_polyline([projection.xy(lat, lon) for lat, lon in section["coords"]], 20):
            trail_points[_cell(x, y, POI_CELL_M)].append((x, y, section["park"]))

    pois: list[dict] = []
    for element in elements:
        tags = element.get("tags", {})
        kind = poi_kind(tags)
        name = place_name(kind, (tags.get("name") or "").strip())
        centre = element if "lat" in element else element.get("center")
        if not kind or not name or not centre:
            continue
        lat, lon = centre["lat"], centre["lon"]
        px, py = projection.xy(lat, lon)
        cx, cy = _cell(px, py, POI_CELL_M)
        limit = POI_NEAR_TRAIL_M[kind]
        nearest, park, parks = math.inf, None, set()
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                for x, y, section_park in trail_points.get((cx + dx, cy + dy), ()):
                    distance = math.dist((px, py), (x, y))
                    if distance <= limit:
                        parks.add(section_park)
                    if distance < nearest:
                        nearest, park = distance, section_park
        if nearest > limit:
            continue
        # Summits on the state border belong to both parks, even when the ridge trail was filed under one.
        inside_park = False
        for park_key, edges in park_edges.items():
            probes = [(px, py)] + [(px + dx, py + dy) for dx, dy in ((BORDER_REACH_M, 0), (-BORDER_REACH_M, 0), (0, BORDER_REACH_M), (0, -BORDER_REACH_M))]
            if any(point_in_edges(edges, *reversed(projection.latlon(x, y))) for x, y in probes):
                parks.add(park_key)
                inside_park = True
        # The same hut is often mapped as both a node and a building outline.
        if any(p["kind"] == kind and p["name"] == name and math.dist((px, py), projection.xy(p["lat"], p["lon"])) < 500 for p in pois):
            continue
        pois.append({
            "osm_id": f"{element['type'][0]}{element['id']}",
            "kind": kind,
            "name": name,
            "ele": parse_elevation(tags.get("ele")),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "park": park,
            "parks": sorted(parks),
            "around": not inside_park,
            "trail_m": round(nearest),
        })
    return pois


def compute_poi_visits(pois: list[dict], tracks: list[dict], lat0: float) -> list[dict]:
    projection = Projection(lat0)
    grid: dict[tuple[int, int], list] = defaultdict(list)
    for index, track in enumerate(tracks):
        for point in track["latlng"]:
            x, y = projection.xy(point[0], point[1])
            grid[_cell(x, y, POI_CELL_M)].append((x, y, index, point[2] if len(point) > 2 else None))
    with_altitude = [any(len(point) > 2 and point[2] is not None for point in track["latlng"]) for track in tracks]
    results = []
    for poi in pois:
        px, py = projection.xy(poi["lat"], poi["lon"])
        cx, cy = _cell(px, py, POI_CELL_M)
        radius = max(POI_VISIT_M[poi["kind"]], (poi.get("trail_m") or 0) + POI_VISIT_SLACK_M)
        hits: dict[int, list] = defaultdict(list)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                for x, y, index, alt in grid.get((cx + dx, cy + dy), ()):
                    distance = math.dist((px, py), (x, y))
                    if distance <= radius:
                        hits[index].append((distance, alt))
        height = poi.get("ele") if poi["kind"] in POI_HEIGHT_KINDS else None
        visitors = set()
        for index, near in hits.items():
            if not height or any(distance <= POI_DIRECT_M for distance, _ in near):
                visitors.add(index)
            elif with_altitude[index]:
                if any(alt is not None and alt >= height - POI_HEIGHT_TOLERANCE_M for _, alt in near):
                    visitors.add(index)
            elif any(distance <= POI_VISIT_M[poi["kind"]] for distance, _ in near):
                visitors.add(index)  # no altitude recorded at all: a close pass is the best evidence
        credited = sorted((tracks[i] for i in visitors), key=lambda t: (t["date"], str(t["activity_id"])))
        results.append({
            "visited_by": [t["activity_id"] for t in credited],
            "first_visited_on": credited[0]["date"] if credited else None,
        })
    return results


# ---------- coverage ----------

def compute_coverage(sections: list[dict], tracks: list[dict], lat0: float) -> list[dict]:
    """For each section: share of samples near any track, and which tracks walked it."""
    projection = Projection(lat0)
    reach = MATCH_M + 5
    grid: dict[tuple[int, int], list] = defaultdict(list)
    for index, track in enumerate(tracks):
        points = [projection.xy(point[0], point[1]) for point in track["latlng"]]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if math.dist((x1, y1), (x2, y2)) > MAX_TRACK_GAP_M:
                continue
            for cx in range(int((min(x1, x2) - reach) // CELL_M), int((max(x1, x2) + reach) // CELL_M) + 1):
                for cy in range(int((min(y1, y2) - reach) // CELL_M), int((max(y1, y2) + reach) // CELL_M) + 1):
                    grid[(cx, cy)].append((x1, y1, x2, y2, index))

    results = []
    for section in sections:
        samples = sample_polyline([projection.xy(lat, lon) for lat, lon in section["coords"]], SAMPLE_M)
        walked = 0
        credit: dict[int, int] = defaultdict(int)
        for px, py in samples:
            near = set()
            for x1, y1, x2, y2, index in grid.get((int(px // CELL_M), int(py // CELL_M)), ()):
                if index in near:
                    continue
                dx, dy = x2 - x1, y2 - y1
                span = dx * dx + dy * dy
                t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
                if math.hypot(px - x1 - t * dx, py - y1 - t * dy) <= MATCH_M:
                    near.add(index)
            walked += bool(near)
            for index in near:
                credit[index] += 1
        share = walked / len(samples)
        credited = sorted(
            (tracks[i] for i, hits in credit.items() if hits / len(samples) >= CREDIT_SHARE),
            key=lambda t: (t["date"], str(t["activity_id"])),
        )
        results.append({
            "coverage": round(share, 3),
            "status": section_status(share),
            "walked_by": [t["activity_id"] for t in credited],
            "first_walked_on": credited[0]["date"] if credited and share >= DONE_SHARE else None,
        })
    _drifted_tracks_pass(sections, tracks, results, projection)
    return results


def _closest_on_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy), cx, cy


def _drifted_tracks_pass(sections: list[dict], tracks: list[dict], results: list[dict], projection: Projection) -> None:
    """Second chance for sections not done: GPS in forests and valleys can drift 50–150 m off a
    trail for long stretches. A sample counts when a track passes within DRIFT_MATCH_M and, where
    the track is, this section is the nearest marked trail (so a parallel trail doesn't get the
    credit). The section is done when that holds for DRIFT_DONE_SHARE of it and the track gets within
    DRIFT_END_M of both ends, so turning back partway up a steep trail doesn't count."""
    pending = [i for i, r in enumerate(results) if r["status"] != "done"]
    if not pending or not tracks:
        return
    cell = DRIFT_MATCH_M
    track_grid: dict[tuple[int, int], list] = defaultdict(list)
    for index, track in enumerate(tracks):
        points = [projection.xy(point[0], point[1]) for point in track["latlng"]]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if math.dist((x1, y1), (x2, y2)) > MAX_TRACK_GAP_M:
                continue
            for cx in range(int((min(x1, x2) - cell) // cell), int((max(x1, x2) + cell) // cell) + 1):
                for cy in range(int((min(y1, y2) - cell) // cell), int((max(y1, y2) + cell) // cell) + 1):
                    track_grid[(cx, cy)].append((x1, y1, x2, y2, index))
    section_points: dict[tuple[int, int], list] = defaultdict(list)
    section_samples = []
    for i, section in enumerate(sections):
        samples = sample_polyline([projection.xy(lat, lon) for lat, lon in section["coords"]], DRIFT_SAMPLE_M)
        section_samples.append(samples)
        for x, y in samples:
            section_points[_cell(x, y, cell)].append((x, y, i))

    def nearest_sections(x: float, y: float) -> dict[int, float]:
        cx, cy = _cell(x, y, cell)
        best: dict[int, float] = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for sx, sy, i in section_points.get((cx + dx, cy + dy), ()):
                    d = math.dist((x, y), (sx, sy))
                    if d < best.get(i, math.inf):
                        best[i] = d
        return best

    for i in pending:
        samples = section_samples[i]
        hits, credit = 0, defaultdict(int)
        for px, py in samples:
            closest: dict[int, tuple] = {}
            for x1, y1, x2, y2, index in track_grid.get(_cell(px, py, cell), ()):
                d, cx, cy = _closest_on_segment(px, py, x1, y1, x2, y2)
                if d <= DRIFT_MATCH_M and d < closest.get(index, (math.inf,))[0]:
                    closest[index] = (d, cx, cy)
            counted = False
            for index, (_, cx, cy) in closest.items():
                distances = nearest_sections(cx, cy)
                if i in distances and distances[i] <= min(distances.values()) + DRIFT_NEAREST_SLACK_M:
                    counted = True
                    credit[index] += 1
            hits += counted
        share = hits / len(samples)
        if share < DRIFT_DONE_SHARE:
            continue

        def reaches(index: int, point: tuple) -> bool:
            return any(
                track == index and _closest_on_segment(*point, x1, y1, x2, y2)[0] <= DRIFT_END_M
                for x1, y1, x2, y2, track in track_grid.get(_cell(*point, cell), ())
            )

        ends = (samples[0], samples[-1])
        walkers = [t for t, n in credit.items() if n / len(samples) >= CREDIT_SHARE and all(reaches(t, end) for end in ends)]
        if not walkers:
            continue
        credited = sorted((tracks[t] for t in walkers), key=lambda t: (t["date"], str(t["activity_id"])))
        results[i] = {
            "coverage": round(share, 3),
            "status": "done",
            "walked_by": [t["activity_id"] for t in credited],
            "first_walked_on": credited[0]["date"] if credited else None,
        }


def section_status(share: float) -> str:
    if share >= DONE_SHARE:
        return "done"
    return "partial" if share >= PARTIAL_SHARE else "todo"


def recompute_region(conn: sqlite3.Connection, region_key: str) -> int:
    sections = repo.list_sections(conn, region_key)
    if not sections:
        return 0
    tracks = repo.list_tracks(conn, region_key)
    bbox = REGIONS[region_key]["bbox"]
    lat0 = (bbox[0] + bbox[2]) / 2
    results = compute_coverage(sections, tracks, lat0)
    repo.save_coverage(conn, [(s["id"], r) for s, r in zip(sections, results)])
    pois = repo.list_pois(conn, region_key)
    repo.save_poi_visits(conn, [(p["id"], r) for p, r in zip(pois, compute_poi_visits(pois, tracks, lat0))])
    conn.commit()
    return len(sections)


# ---------- OSM import ----------

def overpass(query: str, client: Optional[httpx.Client] = None) -> list[dict]:
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(120, connect=10), headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    errors = []
    try:
        for attempt in range(2):
            for url in OVERPASS_URLS:
                try:
                    response = client.post(url, data={"data": query})
                    if response.status_code == 200 and response.text.lstrip().startswith("{"):
                        return response.json()["elements"]
                    errors.append(f"{url}: HTTP {response.status_code}")
                    if response.status_code == 429:  # per-IP slot still busy; give it a moment
                        time.sleep(10)
                except httpx.HTTPError as error:
                    errors.append(f"{url}: {error.__class__.__name__}")
            time.sleep(5 * (attempt + 1))
    finally:
        if owned:
            client.close()
    raise RuntimeError("OpenStreetMap (Overpass) is unavailable right now: " + "; ".join(errors[-3:]))


def region_query(region_key: str) -> str:
    """One Overpass request for a range: hiking relations, park boundaries and named places."""
    region = REGIONS[region_key]
    south, west, north, east = region["bbox"]
    box = f"({south},{west},{north},{east})"
    park_ids = ",".join(str(i) for i in region["parks"])
    return (
        "[out:json][timeout:180];"
        f'relation["route"="hiking"]{box}->.trails;.trails out body;way(r.trails);out geom;'
        + (f'relation["route"~"^(bicycle|mtb)$"]{box}->.bikes;.bikes out body;way(r.bikes);out geom;' if region.get("bike_parks") else "")
        + f"relation(id:{park_ids})->.parks;.parks out body;way(r.parks);out geom;"
        "("
        f'node["natural"="peak"]["name"]{box};'
        f'node["natural"="saddle"]["name"]{box};'
        f'node["mountain_pass"="yes"]["name"]{box};'
        f'node["natural"="cave_entrance"]["name"]{box};'
        f'nwr["tourism"="alpine_hut"]["name"]{box};'
        f'node["highway"="bus_stop"]{box};'
        f'nwr["amenity"="parking"]{box};'
        ");out center tags;"
        f'way["natural"="valley"]["name"]{box};out geom;'
    )


def import_region(
    conn: sqlite3.Connection,
    region_key: str,
    fetch: Callable[[str], list[dict]] = overpass,
    elevations: Optional[Callable] = None,
) -> dict:
    from .route_ideas import build_trailheads
    from .trail_elevation import apply_section_elevation, opentopodata_elevations

    if region_key not in REGIONS:
        raise ValueError(f"Unknown region: {region_key}")
    elements = fetch(region_query(region_key))
    sections = build_sections(elements, elements, region_key)
    if not sections:
        raise RuntimeError("OpenStreetMap returned no marked trails for this region.")
    pois = build_pois(elements, sections, region_key)
    bbox = REGIONS[region_key]["bbox"]
    has_heights = apply_section_elevation(conn, sections, Projection((bbox[0] + bbox[2]) / 2), sample_polyline, elevations or opentopodata_elevations)
    trailheads = build_trailheads(elements, sections, region_key)
    repo.replace_sections(conn, region_key, sections)
    repo.replace_pois(conn, region_key, pois)
    repo.replace_labels(conn, region_key, build_valley_labels(elements, region_key))
    repo.replace_trailheads(conn, region_key, trailheads)
    conn.commit()
    recompute_region(conn, region_key)
    return {
        "region": region_key,
        "sections": len(sections),
        "km": round(sum(s["length_m"] for s in sections) / 1000, 1),
        "places": len(pois),
        "trailheads": len(trailheads),
        "elevation": has_heights,
    }


# ---------- Strava tracks ----------

def region_for_activity(activity: dict) -> Optional[str]:
    for point in (activity.get("start_latlng"), activity.get("end_latlng")):
        if not point or len(point) != 2:
            continue
        for key, region in REGIONS.items():
            south, west, north, east = region["bbox"]
            if south <= point[0] <= north and west <= point[1] <= east:
                return key
    return None


def is_foot_activity(activity: dict) -> bool:
    return activity.get("sport_type") in FOOT_SPORTS or activity.get("type") in FOOT_SPORTS


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def fetch_track_streams(client: httpx.Client, activity_id: str) -> tuple[Optional[list], Optional[list], bool]:
    """(latlng, altitude, rate_limited) for one Strava activity."""
    response = client.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
        params={"keys": "latlng,altitude", "key_by_type": "true"},
    )
    if response.status_code == 429:
        return None, None, True
    if response.status_code >= 400:
        return None, None, False
    body = response.json()
    return (body.get("latlng") or {}).get("data") or [], (body.get("altitude") or {}).get("data") or [], False


def sync_tracks(conn: sqlite3.Connection, client: httpx.Client) -> dict:
    """Fetch GPS for mountain foot activities from Strava that are not stored yet, then add
    altitude to tracks stored before altitude was kept."""
    after = int(get_setting_value(conn, SYNCED_UNTIL_KEY) or 0)
    known = repo.track_ids(conn)
    listed, page, newest = [], 1, after
    while True:
        response = client.get("https://www.strava.com/api/v3/athlete/activities", params={"per_page": 200, "page": page, "after": after})
        if response.status_code == 429:
            raise RuntimeError("Strava rate limit reached. Try again in 15 minutes.")
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        listed.extend(batch)
        page += 1
    candidates = [a for a in listed if is_foot_activity(a) and region_for_activity(a) and str(a["id"]) not in known]

    added, regions, complete = 0, set(), True
    for activity in candidates:
        latlng, altitude, limited = fetch_track_streams(client, activity["id"])
        if limited:
            complete = False
            break
        region_key = region_for_activity(activity)
        if not latlng or len(latlng) < 2:
            continue
        bbox = REGIONS[region_key]["bbox"]
        repo.upsert_track(conn, {
            "activity_id": str(activity["id"]),
            "region": region_key,
            "name": (activity.get("name") or "").strip(),
            "date": (activity.get("start_date_local") or activity.get("start_date") or "")[:10],
            "sport_type": activity.get("sport_type") or activity.get("type"),
            "distance_km": round((activity.get("distance") or 0) / 1000, 2),
            "elevation_m": round(activity.get("total_elevation_gain") or 0),
            "latlng": thin_track(latlng, TRACK_STORE_SPACING_M, Projection((bbox[0] + bbox[2]) / 2), altitude),
        })
        added += 1
        regions.add(region_key)

    altitude_added, altitude_pending = 0, 0
    if complete:
        missing = repo.tracks_without_altitude(conn)
        for index, (activity_id, region_key) in enumerate(missing):
            latlng, altitude, limited = fetch_track_streams(client, activity_id)
            if limited:
                altitude_pending = len(missing) - index
                break
            if not latlng or len(latlng) < 2:
                continue
            bbox = REGIONS[region_key]["bbox"]
            repo.update_track_points(conn, activity_id, thin_track(latlng, TRACK_STORE_SPACING_M, Projection((bbox[0] + bbox[2]) / 2), altitude))
            altitude_added += 1
            regions.add(region_key)
    history_added, history_pending = 0, 0
    if complete and altitude_pending == 0:
        history_added, history_pending = _add_missing_to_history(conn, client)

    for activity in listed:
        if activity.get("start_date"):
            newest = max(newest, _epoch(activity["start_date"]))
    if complete:
        set_setting_value(conn, SYNCED_UNTIL_KEY, str(newest))
    conn.commit()
    for region_key in sorted(regions):
        recompute_region(conn, region_key)
    return {
        "checked": len(listed),
        "added": added,
        "pending": len(candidates) - added if not complete else 0,
        "regions": sorted(regions),
        "complete": complete,
        "altitude_added": altitude_added,
        "altitude_pending": altitude_pending,
        "history_added": history_added,
        "history_pending": history_pending,
    }


def _add_missing_to_history(conn: sqlite3.Connection, client: httpx.Client) -> tuple[int, int]:
    """Mountain hikes and walks older than the activity history (it starts in 2026) are added
    with the regular Strava import code, one request per activity."""
    from .activities import upsert_activity
    from .strava import build_activity_from_strava

    missing = repo.tracks_missing_from_history(conn, HISTORY_SPORTS)
    added = 0
    for index, activity_id in enumerate(missing):
        response = client.get(f"https://www.strava.com/api/v3/activities/{activity_id}")
        if response.status_code == 429:
            conn.commit()
            return added, len(missing) - index
        if response.status_code >= 400:
            continue
        upsert_activity(conn, build_activity_from_strava(response.json()), preserve_annotations=True)
        added += 1
    conn.commit()
    return added, 0


# ---------- read models ----------

def list_regions(conn: sqlite3.Connection) -> dict:
    summary = repo.region_summary(conn)
    tracks = repo.track_counts(conn)
    regions = []
    for key, region in REGIONS.items():
        row = summary.get(key, {})
        total, done = row.get("total_m", 0), row.get("done_m", 0)
        regions.append({
            "key": key,
            "name": region["name"],
            "imported_at": row.get("imported_at"),
            "total_km": round(total / 1000, 1),
            "done_km": round(done / 1000, 1),
            "done_pct": round(done / total * 100) if total else 0,
            "tracks": tracks.get(key, 0),
        })
    return {"regions": regions, "synced_until": get_setting_value(conn, SYNCED_UNTIL_KEY)}


def region_map(conn: sqlite3.Connection, region_key: str, mapy_api_key: Optional[str] = None) -> dict:
    if region_key not in REGIONS:
        raise ValueError(f"Unknown region: {region_key}")
    region = REGIONS[region_key]
    bbox = region["bbox"]
    projection = Projection((bbox[0] + bbox[2]) / 2)
    sections = repo.list_sections(conn, region_key)
    tracks = repo.list_tracks(conn, region_key)
    return {
        "region": {"key": region_key, "name": region["name"], "bbox": bbox},
        "parks": [{"key": p["key"], "label": p["key"], "country": p["country"], "name": p["name"]} for p in region["parks"].values()],
        "sections": [
            {
                "id": s["id"],
                "park": s["park"],
                "parks": s["parks"],
                "colours": s["colours"],
                "names": s["names"],
                "length_m": s["length_m"],
                "coords": s["coords"],
                "coverage": s["coverage"],
                "status": s["status"],
                "around": s["around"],
                "walked_by": s["walked_by"],
                "first_walked_on": s["first_walked_on"],
            }
            for s in sections
        ],
        "pois": repo.list_pois(conn, region_key),
        "labels": repo.list_labels(conn, region_key),
        "tracks": [
            {
                "id": t["activity_id"],
                "name": t["name"],
                "date": t["date"],
                "sport_type": t["sport_type"],
                "distance_km": t["distance_km"],
                "elevation_m": t["elevation_m"],
                "latlng": [[round(p[0], 5), round(p[1], 5)] for p in thin_track(t["latlng"], 20, projection)],
            }
            for t in sorted(tracks, key=lambda t: t["date"], reverse=True)
        ],
        "imported_at": repo.imported_at(conn, region_key),
        "mapy_api_key": mapy_api_key or None,
        "thresholds": {"match_m": MATCH_M, "done_share": DONE_SHARE},
    }


def strava_client(access_token: str) -> httpx.Client:
    return httpx.Client(timeout=30, headers={"Authorization": f"Bearer {access_token}"})
