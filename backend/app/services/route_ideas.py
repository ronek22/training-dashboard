"""Route ideas: day hikes from a bus stop or car park that pick up as much not-yet-walked trail as
fits in the time available.

The trail network is a graph of sections between junctions. Walking time per section is
Naismith's rule with a descent term (5 km/h, plus 1 h per 600 m up and 1 h per 1000 m down),
which matches TPN signpost times within ~10 minutes (Kuźnice–Murowaniec 1 h 45, Kuźnice–Świnica
and back ~7 h 30). From every trailhead the planner greedily inserts missing
stretches of trail into the route where they add the most new kilometres per extra hour
(a cheapest-insertion heuristic for the orienteering problem), returning to the same trailhead
(loop), or, when it is clearly better, ending at a different trailhead with a bus stop to get back. The best, most different routes win.
"""
import heapq
import math
import re
from collections import defaultdict
from typing import Optional

from .trail_coverage import REGIONS, Projection, sample_polyline

WALK_KMH = 5.0
ASCENT_M_PER_H = 600
DESCENT_M_PER_H = 1000

ACCESS_SNAP_M = 300       # a bus stop or car park this close to a trail junction makes it a trailhead
TRAILHEAD_MERGE_M = 400   # trailheads closer than this are the same place
NAME_SEARCH_M = 1500      # unnamed car parks borrow the nearest bus stop's name
POI_ON_ROUTE_M = 80
MIN_NEW_M = 1000
MIN_NEW_SHARE = 0.2
MAX_ROUTES = 8
ONE_WAY_FACTOR = 0.75      # a one-way route has to be clearly better than the loops to rank above them
MIN_SHARE_OF_BUDGET = 0.4  # a "day" idea shouldn't be a 20-minute stroll
SUMMIT_BONUS_M = 1000      # an unreached summit or pass on a missing section is worth this much new trail
STOP_CODE = re.compile(r"\s*\(\d+\)$|\s+0\d$")
OVERLAP_LIMIT = 0.5       # skip a route whose new trail is mostly covered by a better one


def walking_hours(length_m: float, ascent_m: Optional[float], descent_m: Optional[float]) -> float:
    flat = length_m / 1000 / WALK_KMH
    if ascent_m is None or descent_m is None:
        return flat
    return flat + ascent_m / ASCENT_M_PER_H + descent_m / DESCENT_M_PER_H


# ---------- trailheads ----------

def clean_stop_name(name: str) -> str:
    """Drop stop codes: "Szklarska Poręba Średnia (84)", "Karkonoska 54 03"."""
    return STOP_CODE.sub("", name).strip() or name

def _access_kind(tags: dict) -> Optional[str]:
    if tags.get("highway") == "bus_stop" or tags.get("public_transport") == "platform" and tags.get("bus") == "yes":
        return "bus"
    if tags.get("amenity") == "parking" and tags.get("access") not in ("private", "no", "customers"):
        return "parking"
    return None


def build_trailheads(elements: list[dict], sections: list[dict], region_key: str) -> list[dict]:
    """Trail junctions within reach of a bus stop or public car park."""
    bbox = REGIONS[region_key]["bbox"]
    projection = Projection((bbox[0] + bbox[2]) / 2)
    cell = ACCESS_SNAP_M
    junctions: dict[tuple, list] = defaultdict(list)
    for section in sections:
        for end in (section["coords"][0], section["coords"][-1]):
            x, y = projection.xy(*end)
            junctions[(int(x // cell), int(y // cell))].append((x, y, tuple(end)))

    access, named_stops = [], []
    for element in elements:
        tags = element.get("tags", {})
        kind = _access_kind(tags)
        centre = element if "lat" in element else element.get("center")
        if not kind or not centre:
            continue
        x, y = projection.xy(centre["lat"], centre["lon"])
        name = (tags.get("name") or "").strip()
        if kind == "bus" and name:
            named_stops.append((x, y, name))
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for jx, jy, node in junctions.get((int(x // cell) + dx, int(y // cell) + dy), ()):
                    d = math.dist((x, y), (jx, jy))
                    if d <= ACCESS_SNAP_M and (best is None or d < best[0]):
                        best = (d, node, jx, jy)
        if best:
            access.append({"kind": kind, "name": name, "lat": centre["lat"], "lon": centre["lon"], "node": best[1], "xy": (best[2], best[3])})

    # Named bus stops first, then named car parks, then the rest; one trailhead per place.
    rank = lambda a: (0 if a["kind"] == "bus" and a["name"] else 1 if a["name"] else 2)
    kept: list[dict] = []
    for item in sorted(access, key=rank):
        if any(math.dist(item["xy"], other["xy"]) < TRAILHEAD_MERGE_M for other in kept):
            continue
        if not item["name"]:
            nearby = [(math.dist(item["xy"], (x, y)), name) for x, y, name in named_stops]
            nearby = [n for n in nearby if n[0] <= NAME_SEARCH_M]
            item["name"] = min(nearby)[1] if nearby else ("Bus stop" if item["kind"] == "bus" else "Car park")
        kept.append(item)
    return [{"name": clean_stop_name(t["name"]), "kind": t["kind"], "lat": round(t["lat"], 6), "lon": round(t["lon"], 6), "node": t["node"]} for t in kept]


# ---------- graph ----------

class TrailGraph:
    def __init__(self, sections: list[dict]):
        self.sections = sections
        self.adj: dict[tuple, list] = defaultdict(list)
        self.hours: dict[tuple[int, bool], float] = {}
        for index, section in enumerate(sections):
            a, b = tuple(section["coords"][0]), tuple(section["coords"][-1])
            if a == b:
                continue
            up, down = section.get("ascent_m"), section.get("descent_m")
            forward = walking_hours(section["length_m"], up, down)
            backward = walking_hours(section["length_m"], down, up)
            self.hours[(index, True)], self.hours[(index, False)] = forward, backward
            self.adj[a].append((b, forward, index, True))
            self.adj[b].append((a, backward, index, False))

    def ends(self, index: int, forward: bool) -> tuple[tuple, tuple]:
        coords = self.sections[index]["coords"]
        a, b = tuple(coords[0]), tuple(coords[-1])
        return (a, b) if forward else (b, a)

    def shortest(self, source: tuple, limit: float) -> tuple[dict, dict]:
        dist, prev = {source: 0.0}, {}
        queue = [(0.0, source)]
        while queue:
            d, node = heapq.heappop(queue)
            if d > dist.get(node, math.inf) or d > limit:
                continue
            for other, hours, index, forward in self.adj[node]:
                nd = d + hours
                if nd < dist.get(other, math.inf) and nd <= limit:
                    dist[other], prev[other] = nd, (node, index, forward)
                    heapq.heappush(queue, (nd, other))
        return dist, prev


def path(prev: dict, source: tuple, target: tuple) -> list[tuple[int, bool]]:
    steps, node = [], target
    while node != source:
        node, index, forward = prev[node][0], prev[node][1], prev[node][2]
        steps.append((index, forward))
    return steps[::-1]


def target_chains(graph: TrailGraph, targets: dict[int, float], stops: frozenset = frozenset()) -> list[dict]:
    """Missing sections merged into chains through junctions where nothing else branches off,
    so the planner adds whole missing stretches instead of 50 m pieces. Chains also end at
    trailheads (`stops`), where a route can start."""
    degree = {node: len(edges) for node, edges in graph.adj.items()}
    used, chains = set(), []
    for start in targets:
        if start in used or (start, True) not in graph.hours:
            continue
        used.add(start)
        steps = [(start, True)]
        for direction in (True, False):  # grow forwards from the end, then backwards from the start
            node = graph.ends(start, True)[1 if direction else 0]
            while degree.get(node, 0) == 2 and node not in stops:
                nxt = next(((i, f) for _, _, i, f in graph.adj[node] if i not in used and i in targets), None)
                if nxt is None:
                    break
                used.add(nxt[0])
                if direction:
                    steps.append(nxt)
                    node = graph.ends(*nxt)[1]
                else:
                    steps.insert(0, (nxt[0], not nxt[1]))
                    node = graph.ends(nxt[0], not nxt[1])[0]
        chains.append({
            "steps": steps,
            "gain": sum(targets[i] for i, _ in steps),
            "forward": (graph.ends(*steps[0])[0], graph.ends(*steps[-1])[1], sum(graph.hours[s] for s in steps)),
            "backward": (graph.ends(*steps[-1])[1], graph.ends(*steps[0])[0], sum(graph.hours[(i, not f)] for i, f in steps)),
        })
    return chains


# ---------- planning ----------

def plan_routes(
    sections: list[dict],
    trailheads: list[dict],
    pois: list[dict],
    park: str,
    hours: float,
    include_around: bool = False,
) -> list[dict]:
    graph = TrailGraph(sections)
    in_area = lambda s: park in s["parks"]
    targets = {
        i: s["length_m"] * (1 - (s["coverage"] if s["status"] == "partial" else 0))
        for i, s in enumerate(sections)
        if s["status"] != "done" and in_area(s) and (include_around or not s["around"]) and (i, True) in graph.hours
    }
    if not targets:
        return []
    area_nodes = {tuple(s["coords"][e]) for s in sections if in_area(s) for e in (0, -1)}
    heads = [dict(t, name=clean_stop_name(t["name"])) for t in trailheads if tuple(t["node"]) in area_nodes]
    bonus = _summit_bonus(sections, targets, pois, park, include_around)
    chains = target_chains(graph, targets, frozenset(tuple(t["node"]) for t in heads))
    for chain in chains:
        chain["gain"] += sum(bonus.get(i, 0) for i, _ in chain["steps"])

    sources = {tuple(t["node"]) for t in heads}
    for chain in chains:
        sources.update({chain["forward"][0], chain["forward"][1]})
    tables = {node: graph.shortest(node, hours) for node in sources}
    dist = lambda a, b: tables[a][0].get(b, math.inf) if a in tables else math.inf
    # One-way routes must finish at a bus stop, so there is a way back to the start.
    bus_nodes = [tuple(t["node"]) for t in heads if t["kind"] == "bus"]
    to_any_head = {node: min((dist(node, h), h) for h in bus_nodes) for node in sources} if bus_nodes else {}

    candidates = []
    for head in heads:
        for mode in ("loop", "one-way") if to_any_head else ("loop",):
            route = _insert_chains(head, mode, chains, dist, to_any_head, hours)
            if route:
                candidates.append(_describe(route, head, mode, graph, tables, to_any_head, targets, heads, pois, park, chains))

    def score(r: dict) -> float:
        value = r["new_m"] + SUMMIT_BONUS_M * sum(1 for p in r["places"] if not p["reached"] and p["kind"] in ("peak", "pass"))
        return value * (ONE_WAY_FACTOR if r["mode"] == "one-way" else 1)
    chosen, covered = [], []
    for route in sorted((c for c in candidates if c), key=lambda r: (-score(r), r["hours"])):
        if route["new_m"] < MIN_NEW_M or route["new_m"] < MIN_NEW_SHARE * route["distance_m"]:
            continue
        if route["hours"] < MIN_SHARE_OF_BUDGET * hours:
            continue
        new = set(route["new_sections"])
        if any(len(new & other) > OVERLAP_LIMIT * len(new) for other in covered):
            continue
        chosen.append(route)
        covered.append(new)
        if len(chosen) == MAX_ROUTES:
            break
    return chosen


def _insert_chains(head: dict, mode: str, chains: list[dict], dist, to_any_head, limit: float) -> list[tuple]:
    start = tuple(head["node"])
    end_cost = (lambda node: dist(node, start)) if mode == "loop" else (lambda node: to_any_head.get(node, (math.inf,))[0])
    items: list[tuple] = []  # (chain index, (u, v, hours))
    total, used = end_cost(start), set()  # one way from a car park: at least the walk to a bus stop
    pool = [
        (c, way) for c, chain in enumerate(chains) for way in (chain["forward"], chain["backward"])
        if dist(start, way[0]) + way[2] + end_cost(way[1]) <= limit
    ]
    while True:
        best = None
        for c, (u, v, hours) in pool:
            if c in used:
                continue
            gain = chains[c]["gain"]
            for i in range(len(items) + 1):
                before = start if i == 0 else items[i - 1][1][1]
                if i == len(items):
                    delta = dist(before, u) + hours + end_cost(v) - end_cost(before)
                else:
                    after = items[i][1][0]
                    delta = dist(before, u) + hours + dist(v, after) - dist(before, after)
                if not math.isfinite(delta) or total + delta > limit:
                    continue
                ratio = gain / max(delta, 0.05)
                if best is None or ratio > best[0]:
                    best = (ratio, delta, i, c, (u, v, hours))
        if best is None:
            return items
        _, delta, i, c, way = best
        items.insert(i, (c, way))
        used.add(c)
        total += delta


def _describe(items, head, mode, graph, tables, to_any_head, targets, heads, pois, park, chains) -> Optional[dict]:
    start = tuple(head["node"])
    steps: list[tuple[int, bool]] = []
    node = start
    for c, (u, v, _) in items:
        if u != node and u not in tables.get(node, ({}, {}))[0]:
            return None
        steps += path(tables[node][1], node, u) if node != u else []
        steps += _chain_walk(chains[c], u)
        node = v
    end = start if mode == "loop" else to_any_head[node][1] if node in to_any_head else start
    if end == start:
        mode = "loop"  # a "one way" that ends where it began is a loop
    if node != end:
        if node not in tables or end not in tables[node][0]:
            return None
        steps += path(tables[node][1], node, end)
    if not steps:
        return None

    sections = graph.sections
    distance = sum(sections[i]["length_m"] for i, _ in steps)
    hours = sum(graph.hours[s] for s in steps)
    have_heights = all(sections[i].get("ascent_m") is not None for i, _ in steps)
    ascent = sum(sections[i]["ascent_m"] if f else sections[i]["descent_m"] for i, f in steps) if have_heights else None
    descent = sum(sections[i]["descent_m"] if f else sections[i]["ascent_m"] for i, f in steps) if have_heights else None
    new_sections = sorted({i for i, _ in steps if i in targets})
    new_m = sum(targets[i] for i in new_sections)
    end_head = next((t for t in heads if tuple(t["node"]) == end), head)

    route_points = [tuple(p) for i, _ in steps for p in sections[i]["coords"]]
    on_route = _places_on_route(pois, route_points, park)
    highlight = max((p for p in on_route if p["kind"] in ("peak", "hut")), key=lambda p: (p["kind"] == "peak", p.get("ele") or 0), default=None)
    name_parts = [head["name"]] + ([_short(highlight["name"])] if highlight else []) + [end_head["name"]]
    return {
        "key": f"{mode}:{head['name']}:{','.join(map(str, new_sections[:6]))}",
        "title": " – ".join(name_parts),
        "mode": mode,
        "start": {"name": head["name"], "kind": head["kind"], "lat": head["lat"], "lon": head["lon"]},
        "end": {"name": end_head["name"], "kind": end_head["kind"], "lat": end_head["lat"], "lon": end_head["lon"]},
        "distance_m": round(distance),
        "hours": round(hours, 2),
        "ascent_m": round(ascent) if ascent is not None else None,
        "descent_m": round(descent) if descent is not None else None,
        "max_ele": max((sections[i].get("ele_max") or 0) for i, _ in steps) or None,
        "new_m": round(new_m),
        "new_sections": new_sections,
        "steps": [{"section": sections[i]["id"], "forward": f, "new": i in targets} for i, f in steps],
        "places": [{"name": p["name"], "kind": p["kind"], "ele": p.get("ele"), "reached": bool(p["visited_by"])} for p in on_route],
    }


def _chain_walk(chain: dict, u: tuple) -> list[tuple[int, bool]]:
    if chain["forward"][0] == u:
        return chain["steps"]
    return [(i, not f) for i, f in reversed(chain["steps"])]


def _summit_bonus(sections, targets, pois, park, include_around) -> dict[int, float]:
    """Missing sections that lead over a summit or pass not reached yet get a bonus, so routes
    lean towards tops rather than only the cheapest forest kilometres."""
    bonus: dict[int, float] = defaultdict(float)
    wanted = [p for p in pois if p["kind"] in ("peak", "pass") and not p["visited_by"] and park in (p.get("parks") or [p.get("park")])
              and (include_around or not p.get("around"))]
    if not wanted:
        return bonus
    projection = Projection(wanted[0]["lat"])
    cell = POI_ON_ROUTE_M
    grid: dict[tuple, list] = defaultdict(list)
    for i in targets:
        for lat, lon in sections[i]["coords"]:
            x, y = projection.xy(lat, lon)
            grid[(int(x // cell), int(y // cell))].append((x, y, i))
    for poi in wanted:
        x, y = projection.xy(poi["lat"], poi["lon"])
        near = {i for dx in (-1, 0, 1) for dy in (-1, 0, 1) for qx, qy, i in grid.get((int(x // cell) + dx, int(y // cell) + dy), ())
                if math.dist((x, y), (qx, qy)) <= POI_ON_ROUTE_M}
        if near:
            bonus[min(near)] += SUMMIT_BONUS_M
    return bonus


def _short(name: str) -> str:
    parts = [p.strip() for p in name.split(" / ")]
    polish = next((p for p in parts if any(ch in p for ch in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")), parts[-1])
    return polish


def _places_on_route(pois: list[dict], route_points: list[tuple], park: str) -> list[dict]:
    if not route_points:
        return []
    lat0 = route_points[0][0]
    projection = Projection(lat0)
    cell = POI_ON_ROUTE_M
    grid: dict[tuple, list] = defaultdict(list)
    for lat, lon in route_points:
        x, y = projection.xy(lat, lon)
        grid[(int(x // cell), int(y // cell))].append((x, y))
    found, seen = [], set()
    for poi in pois:
        if poi["kind"] not in ("peak", "pass", "hut", "cave") or (poi["kind"], poi["name"]) in seen:
            continue
        x, y = projection.xy(poi["lat"], poi["lon"])
        cx, cy = int(x // cell), int(y // cell)
        near = any(math.dist((x, y), q) <= POI_ON_ROUTE_M for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid.get((cx + dx, cy + dy), ()))
        if near:
            found.append(poi)
            seen.add((poi["kind"], poi["name"]))  # some summits are mapped twice
    return sorted(found, key=lambda p: -(p.get("ele") or 0))


# ---------- read model ----------

HOUR_PRESETS = {"half": 4.0, "day": 7.0, "long": 10.0}
_cache: dict[tuple, dict] = {}


def route_ideas(conn, region_key: str, park: str, hours: float, include_around: bool = False) -> dict:
    from ..repositories import trails as repo

    if region_key not in REGIONS:
        raise ValueError(f"Unknown region: {region_key}")
    parks = [p["key"] for p in REGIONS[region_key]["parks"].values()]
    if park not in parks:
        raise ValueError(f"Unknown park for {region_key}: {park}")
    sections = repo.list_sections(conn, region_key)
    # Recompute only when the trails or what's been walked changed.
    signature = (region_key, park, hours, include_around, repo.imported_at(conn, region_key),
                 hash(tuple((s["id"], s["status"], s["coverage"]) for s in sections)))
    if signature not in _cache:
        trailheads = repo.list_trailheads(conn, region_key)
        pois = repo.list_pois(conn, region_key)
        _cache.clear()  # one entry is plenty; keeps memory flat
        _cache[signature] = {
            "routes": plan_routes(sections, trailheads, pois, park, hours, include_around),
            "trailheads": len(trailheads),
            "has_heights": any(s.get("ascent_m") is not None for s in sections),
            "hours": hours,
        }
    return _cache[signature]
