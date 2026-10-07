"""Mountain context for one hike: the trails it walked (and which were new), summits and places it
reached, and the surrounding trails, places and valley names for the map. Kept small: only what
lies around the hike, not the whole range."""
import sqlite3
from typing import Optional

from ..repositories import trails as repo
from .trail_coverage import REGIONS, Projection, thin_track

AROUND_DEG = 0.012  # backdrop margin around the hike (~1.3 km north-south)


def _bbox(points: list) -> tuple[float, float, float, float]:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return min(lats) - AROUND_DEG, min(lons) - AROUND_DEG * 1.5, max(lats) + AROUND_DEG, max(lons) + AROUND_DEG * 1.5


def _inside(bbox, lat: float, lon: float) -> bool:
    return bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]


def mountain_region(conn: sqlite3.Connection, activity_id: str) -> Optional[str]:
    """The mapped range an activity's GPS track belongs to, if it was synced as a mountain track."""
    try:
        row = conn.execute("SELECT region FROM mountain_tracks WHERE activity_id = ?", (str(activity_id),)).fetchone()
    except sqlite3.OperationalError:  # trails tables not created (older databases in tests)
        return None
    return row["region"] if row else None


def hike_context(conn: sqlite3.Connection, activity_id: str) -> Optional[dict]:
    row = conn.execute("SELECT region FROM mountain_tracks WHERE activity_id = ?", (str(activity_id),)).fetchone()
    if not row:
        return None
    region_key = row["region"]
    track = next(t for t in repo.list_tracks(conn, region_key) if t["activity_id"] == str(activity_id))
    region = REGIONS[region_key]
    projection = Projection((region["bbox"][0] + region["bbox"][2]) / 2)
    bbox = _bbox(track["latlng"])

    sections, walked = [], []
    for s in repo.list_sections(conn, region_key):
        if not any(_inside(bbox, lat, lon) for lat, lon in s["coords"]):
            continue
        on_hike = str(activity_id) in s["walked_by"]
        first = on_hike and s["status"] == "done" and s["walked_by"][0] == str(activity_id)
        sections.append({
            "id": s["id"], "colours": s["colours"], "names": s["names"], "length_m": s["length_m"],
            "coords": s["coords"], "status": s["status"], "parks": s["parks"], "around": s["around"],
            "on_hike": on_hike, "first_time": first,
        })
        if on_hike:
            walked.append(sections[-1])

    places = []
    for p in repo.list_pois(conn, region_key):
        if not _inside(bbox, p["lat"], p["lon"]):
            continue
        reached_here = str(activity_id) in p["visited_by"]
        places.append({
            "id": p["id"], "kind": p["kind"], "name": p["name"], "ele": p["ele"], "lat": p["lat"], "lon": p["lon"],
            "parks": p["parks"], "around": p["around"], "visited_by": p["visited_by"],
            "reached_here": reached_here, "first_time": reached_here and p["visited_by"][0] == str(activity_id),
        })

    labels = [l for l in repo.list_labels(conn, region_key) if _inside(bbox, l["lat"], l["lon"])]
    parks = sorted({park for s in walked for park in s["parks"]}) or sorted({p["park"] for p in places if p["reached_here"]})
    park_names = {p["key"]: p["name"] for p in region["parks"].values()}
    reached = [p for p in places if p["reached_here"]]
    return {
        "region": {"key": region_key, "name": region["name"]},
        "parks": [{"key": key, "name": park_names.get(key, key)} for key in parks],
        "track": [[round(p[0], 6), round(p[1], 6), p[2] if len(p) > 2 else None] for p in thin_track(track["latlng"], 10, projection)],
        "sections": sections,
        "places": places,
        "labels": labels,
        "totals": {
            "trail_km": round(sum(s["length_m"] for s in walked) / 1000, 1),
            "new_trail_km": round(sum(s["length_m"] for s in walked if s["first_time"]) / 1000, 1),
            "summits": sum(1 for p in reached if p["kind"] == "peak"),
            "new_summits": sum(1 for p in reached if p["kind"] == "peak" and p["first_time"]),
            "places": len(reached),
        },
    }
