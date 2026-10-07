import json
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS trail_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    osm_key TEXT NOT NULL,
    park TEXT NOT NULL,
    parks_json TEXT NOT NULL DEFAULT '[]',
    around INTEGER NOT NULL DEFAULT 0,
    ascent_m REAL,
    descent_m REAL,
    ele_min REAL,
    ele_max REAL,
    colours_json TEXT NOT NULL,
    names_json TEXT NOT NULL,
    coords_json TEXT NOT NULL,
    length_m REAL NOT NULL,
    coverage REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'todo',
    walked_by_json TEXT NOT NULL DEFAULT '[]',
    first_walked_on TEXT,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trail_sections_region ON trail_sections(region);

CREATE TABLE IF NOT EXISTS mountain_tracks (
    activity_id TEXT PRIMARY KEY,
    region TEXT NOT NULL,
    name TEXT,
    date TEXT NOT NULL,
    sport_type TEXT,
    distance_km REAL,
    elevation_m REAL,
    latlng_json TEXT NOT NULL,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mountain_tracks_region ON mountain_tracks(region);

CREATE TABLE IF NOT EXISTS trail_pois (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    osm_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    ele INTEGER,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    park TEXT NOT NULL,
    parks_json TEXT NOT NULL DEFAULT '[]',
    around INTEGER NOT NULL DEFAULT 0,
    trail_m INTEGER,
    visited_by_json TEXT NOT NULL DEFAULT '[]',
    first_visited_on TEXT
);
CREATE INDEX IF NOT EXISTS idx_trail_pois_region ON trail_pois(region);

CREATE TABLE IF NOT EXISTS map_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    axis_json TEXT NOT NULL,
    length_m INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_map_labels_region ON map_labels(region);

CREATE TABLE IF NOT EXISTS trailheads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    node_lat REAL NOT NULL,
    node_lon REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trailheads_region ON trailheads(region);

CREATE TABLE IF NOT EXISTS elevation_cache (
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    ele REAL NOT NULL,
    PRIMARY KEY (lat, lon)
);
"""


def migrate(conn: sqlite3.Connection) -> None:
    """Columns added after the tables first shipped."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(trail_sections)")}
    if "parks_json" not in columns:
        conn.execute("ALTER TABLE trail_sections ADD COLUMN parks_json TEXT NOT NULL DEFAULT '[]'")
    if "around" not in columns:
        conn.execute("ALTER TABLE trail_sections ADD COLUMN around INTEGER NOT NULL DEFAULT 0")
    for column in ("ascent_m", "descent_m", "ele_min", "ele_max"):
        if column not in columns:
            conn.execute(f"ALTER TABLE trail_sections ADD COLUMN {column} REAL")
    poi_columns = {row[1] for row in conn.execute("PRAGMA table_info(trail_pois)")}
    if "around" not in poi_columns:
        conn.execute("ALTER TABLE trail_pois ADD COLUMN around INTEGER NOT NULL DEFAULT 0")


def _section(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "park": row["park"],
        "parks": json.loads(row["parks_json"] or "[]") or [row["park"]],
        "around": bool(row["around"]),
        "ascent_m": row["ascent_m"],
        "descent_m": row["descent_m"],
        "ele_min": row["ele_min"],
        "ele_max": row["ele_max"],
        "colours": json.loads(row["colours_json"]),
        "names": json.loads(row["names_json"]),
        "coords": json.loads(row["coords_json"]),
        "length_m": row["length_m"],
        "coverage": row["coverage"],
        "status": row["status"],
        "walked_by": json.loads(row["walked_by_json"] or "[]"),
        "first_walked_on": row["first_walked_on"],
    }


def list_sections(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trail_sections WHERE region = ? ORDER BY id", (region,)).fetchall()
    return [_section(row) for row in rows]


def replace_sections(conn: sqlite3.Connection, region: str, sections: list[dict]) -> None:
    imported_at = datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM trail_sections WHERE region = ?", (region,))
    conn.executemany(
        """
        INSERT INTO trail_sections (region, osm_key, park, parks_json, around, ascent_m, descent_m, ele_min, ele_max,
                                    colours_json, names_json, coords_json, length_m, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                region,
                s["osm_key"],
                s["park"],
                json.dumps(s.get("parks") or [s["park"]]),
                int(bool(s.get("around"))),
                s.get("ascent_m"),
                s.get("descent_m"),
                s.get("ele_min"),
                s.get("ele_max"),
                json.dumps(s["colours"]),
                json.dumps(s["names"], ensure_ascii=False),
                json.dumps(s["coords"], separators=(",", ":")),
                s["length_m"],
                imported_at,
            )
            for s in sections
        ],
    )


def save_coverage(conn: sqlite3.Connection, results: list[tuple[int, dict]]) -> None:
    conn.executemany(
        "UPDATE trail_sections SET coverage = ?, status = ?, walked_by_json = ?, first_walked_on = ? WHERE id = ?",
        [(r["coverage"], r["status"], json.dumps(r["walked_by"]), r["first_walked_on"], section_id) for section_id, r in results],
    )


def imported_at(conn: sqlite3.Connection, region: str):
    row = conn.execute("SELECT MAX(imported_at) AS imported_at FROM trail_sections WHERE region = ?", (region,)).fetchone()
    return row["imported_at"] if row else None


def region_summary(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT region,
               SUM(length_m) AS total_m,
               SUM(CASE WHEN status = 'done' THEN length_m ELSE 0 END) AS done_m,
               MAX(imported_at) AS imported_at
        FROM trail_sections WHERE around = 0 GROUP BY region
        """
    ).fetchall()
    return {row["region"]: dict(row) for row in rows}


def track_ids(conn: sqlite3.Connection) -> set:
    return {row["activity_id"] for row in conn.execute("SELECT activity_id FROM mountain_tracks")}


def track_counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT region, COUNT(*) AS n FROM mountain_tracks GROUP BY region").fetchall()
    return {row["region"]: row["n"] for row in rows}


def list_tracks(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM mountain_tracks WHERE region = ? ORDER BY date, activity_id", (region,)).fetchall()
    return [
        {
            "activity_id": row["activity_id"],
            "name": row["name"],
            "date": row["date"],
            "sport_type": row["sport_type"],
            "distance_km": row["distance_km"],
            "elevation_m": row["elevation_m"],
            "latlng": json.loads(row["latlng_json"]),
        }
        for row in rows
    ]


def upsert_track(conn: sqlite3.Connection, track: dict) -> None:
    conn.execute(
        """
        INSERT INTO mountain_tracks (activity_id, region, name, date, sport_type, distance_km, elevation_m, latlng_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            region = excluded.region, name = excluded.name, date = excluded.date, sport_type = excluded.sport_type,
            distance_km = excluded.distance_km, elevation_m = excluded.elevation_m,
            latlng_json = excluded.latlng_json, fetched_at = excluded.fetched_at
        """,
        (
            track["activity_id"],
            track["region"],
            track["name"],
            track["date"],
            track["sport_type"],
            track["distance_km"],
            track["elevation_m"],
            json.dumps(track["latlng"], separators=(",", ":")),
        ),
    )


def replace_pois(conn: sqlite3.Connection, region: str, pois: list[dict]) -> None:
    conn.execute("DELETE FROM trail_pois WHERE region = ?", (region,))
    conn.executemany(
        """
        INSERT INTO trail_pois (region, osm_id, kind, name, ele, lat, lon, park, parks_json, around, trail_m)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (region, p["osm_id"], p["kind"], p["name"], p["ele"], p["lat"], p["lon"], p["park"], json.dumps(p["parks"]), int(bool(p.get("around"))), p["trail_m"])
            for p in pois
        ],
    )


def list_pois(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trail_pois WHERE region = ? ORDER BY id", (region,)).fetchall()
    return [
        {
            "id": row["id"],
            "kind": row["kind"],
            "name": row["name"],
            "ele": row["ele"],
            "lat": row["lat"],
            "lon": row["lon"],
            "park": row["park"],
            "parks": json.loads(row["parks_json"] or "[]") or [row["park"]],
            "around": bool(row["around"]),
            "trail_m": row["trail_m"],
            "visited_by": json.loads(row["visited_by_json"] or "[]"),
            "first_visited_on": row["first_visited_on"],
        }
        for row in rows
    ]


def save_poi_visits(conn: sqlite3.Connection, results: list[tuple[int, dict]]) -> None:
    conn.executemany(
        "UPDATE trail_pois SET visited_by_json = ?, first_visited_on = ? WHERE id = ?",
        [(json.dumps(r["visited_by"]), r["first_visited_on"], poi_id) for poi_id, r in results],
    )


def tracks_without_altitude(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Tracks stored as [lat, lon] points, i.e. before altitude was kept (one comma in the first point)."""
    rows = conn.execute(
        """
        SELECT activity_id, region,
               substr(latlng_json, 1, instr(latlng_json, ']')) AS first_point
        FROM mountain_tracks ORDER BY date, activity_id
        """
    ).fetchall()
    return [(row["activity_id"], row["region"]) for row in rows if row["first_point"].count(",") == 1]


def update_track_points(conn: sqlite3.Connection, activity_id: str, latlng: list) -> None:
    conn.execute(
        "UPDATE mountain_tracks SET latlng_json = ?, fetched_at = CURRENT_TIMESTAMP WHERE activity_id = ?",
        (json.dumps(latlng, separators=(",", ":")), activity_id),
    )


def replace_labels(conn: sqlite3.Connection, region: str, labels: list[dict]) -> None:
    conn.execute("DELETE FROM map_labels WHERE region = ?", (region,))
    conn.executemany(
        "INSERT INTO map_labels (region, kind, name, lat, lon, axis_json, length_m) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(region, l["kind"], l["name"], l["lat"], l["lon"], json.dumps([l["a"], l["b"]]), l["length_m"]) for l in labels],
    )


def list_labels(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM map_labels WHERE region = ? ORDER BY length_m DESC", (region,)).fetchall()
    return [
        {"kind": row["kind"], "name": row["name"], "lat": row["lat"], "lon": row["lon"],
         "a": json.loads(row["axis_json"])[0], "b": json.loads(row["axis_json"])[1], "length_m": row["length_m"]}
        for row in rows
    ]


def cached_elevations(conn: sqlite3.Connection, keys: list[tuple[float, float]]) -> dict:
    found = {}
    for start in range(0, len(keys), 400):
        chunk = keys[start:start + 400]
        clause = " OR ".join(["(lat = ? AND lon = ?)"] * len(chunk))
        params = [value for key in chunk for value in key]
        for row in conn.execute(f"SELECT lat, lon, ele FROM elevation_cache WHERE {clause}", params):
            found[(row["lat"], row["lon"])] = row["ele"]
    return found


def cache_elevations(conn: sqlite3.Connection, heights: dict) -> None:
    conn.executemany("INSERT OR REPLACE INTO elevation_cache (lat, lon, ele) VALUES (?, ?, ?)", [(lat, lon, ele) for (lat, lon), ele in heights.items()])


def replace_trailheads(conn: sqlite3.Connection, region: str, trailheads: list[dict]) -> None:
    conn.execute("DELETE FROM trailheads WHERE region = ?", (region,))
    conn.executemany(
        "INSERT INTO trailheads (region, name, kind, lat, lon, node_lat, node_lon) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(region, t["name"], t["kind"], t["lat"], t["lon"], t["node"][0], t["node"][1]) for t in trailheads],
    )


def list_trailheads(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trailheads WHERE region = ? ORDER BY id", (region,)).fetchall()
    return [{"id": row["id"], "name": row["name"], "kind": row["kind"], "lat": row["lat"], "lon": row["lon"],
             "node": (row["node_lat"], row["node_lon"])} for row in rows]
