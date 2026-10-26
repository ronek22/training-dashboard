"""Kit wear: shoes, bikes, chains, tyres and trainers with replacement thresholds.

Each item has a sport (the activity type it is used for), a start date and a
distance and/or time threshold. Activities get one item per kind ("slot"):
a run fills the shoes slot, a ride can fill the bike, chain and tyres slots.

Bike parts (chain, tyres, cassette, brake pads) can belong to a bike: they then
count exactly the rides on that bike since they were fitted, and are never a
sport default themselves. Parts keep a service log (wax, lube, clean, sealant)
and an optional "service every N km" that drives its own nearly-due cue.
Replacing a part retires it and starts a fresh copy, so the chain history of a
bike is its retired chains.

Assignments are stored, not derived, so history stays put when defaults change:

* an item linked to a Strava gear id claims that gear's activities;
* otherwise the sport's default item for that kind claims the activity;
* a part follows whichever bike the activity is on;
* a manual choice (including "none") is never overwritten.

The sweep runs whenever kit is read, so every import path (Strava, HealthFit,
manual) is covered. Usage is summed over live activities, so a deleted
activity drops out on its own and a reassignment moves its distance.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

KINDS = {
    "shoes": {"label": "Shoes", "sport": "Run", "unit": "km"},
    "bike": {"label": "Bike", "sport": "Ride", "unit": "km"},
    # A direct-drive trainer still turns the bike's chain, but not its wheels, cassette or brakes.
    "chain": {"label": "Chain", "sport": "Ride", "unit": "km", "part": True, "indoor": True},
    "tyres": {"label": "Tyres", "sport": "Ride", "unit": "km", "part": True},
    "cassette": {"label": "Cassette", "sport": "Ride", "unit": "km", "part": True},
    "brake_pads": {"label": "Brake pads", "sport": "Ride", "unit": "km", "part": True},
    "trainer": {"label": "Trainer", "sport": "VirtualRide", "unit": "h"},
}
SPORTS = ("Run", "Ride", "VirtualRide", "Hike", "Walk")
PART_KINDS = tuple(key for key, meta in KINDS.items() if meta.get("part"))
NEARLY_DUE = 0.9
SERVICE_ACTIONS = {
    "wax": {"label": "Wax", "due": "Re-wax"},
    "lube": {"label": "Lube", "due": "Lube"},
    "clean": {"label": "Clean", "due": "Clean"},
    "sealant": {"label": "Sealant", "due": "Sealant top-up"},
    "other": {"label": "Service", "due": "Service"},
}

EDITABLE = (
    "name", "sport", "started_on", "threshold_km", "threshold_hours", "start_km", "start_hours", "is_default",
    "retired_on", "strava_gear_id", "notes", "parent_id", "service_action", "service_every_km", "count_indoor",
)
INDOOR = "VirtualRide"
# Added after the first release; existing databases get them on first use.
_LATER_COLUMNS = {
    "parent_id": "INTEGER",
    "service_action": "TEXT",
    "service_every_km": "REAL",
    "replaces_id": "INTEGER",
    "count_indoor": "INTEGER",
}


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS kit_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            sport TEXT NOT NULL,
            started_on TEXT NOT NULL,
            threshold_km REAL,
            threshold_hours REAL,
            start_km REAL NOT NULL DEFAULT 0,
            start_hours REAL NOT NULL DEFAULT 0,
            is_default INTEGER NOT NULL DEFAULT 0,
            retired_on TEXT,
            strava_gear_id TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_kit (
            activity_id TEXT NOT NULL,
            slot TEXT NOT NULL,
            kit_id INTEGER,
            source TEXT NOT NULL DEFAULT 'auto',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (activity_id, slot)
        );

        CREATE INDEX IF NOT EXISTS idx_activity_kit_item ON activity_kit(kit_id);

        CREATE TABLE IF NOT EXISTS kit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kit_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            done_on TEXT NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(kit_items)")}
    for column, kind in _LATER_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE kit_items ADD COLUMN {column} {kind}")
            if column == "count_indoor":
                indoor = ", ".join(f"'{key}'" for key, meta in KINDS.items() if meta.get("indoor"))
                conn.execute(f"UPDATE kit_items SET count_indoor = kind IN ({indoor})")


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


# ---------------------------------------------------------------------------
# Assignment sweep
# ---------------------------------------------------------------------------

_IN_WINDOW = "a.type = k.sport AND a.date >= k.started_on AND (k.retired_on IS NULL OR a.date <= k.retired_on)"


def sync_assignments(conn: sqlite3.Connection) -> None:
    ensure_tables(conn)
    if _has_table(conn, "activity_source_refs"):
        # Strava gear wins over the sport default, never over a manual choice.
        conn.execute(
            f"""
            INSERT INTO activity_kit (activity_id, slot, kit_id, source)
            SELECT a.id, k.kind, k.id, 'strava'
            FROM kit_items k
            JOIN activity_source_refs sr ON sr.source = 'strava'
                AND json_extract(sr.metadata_json, '$.gear_id') = k.strava_gear_id
            JOIN activities a ON a.id = sr.activity_id
            WHERE k.strava_gear_id IS NOT NULL AND {_IN_WINDOW}
            ON CONFLICT(activity_id, slot) DO UPDATE SET
                kit_id = excluded.kit_id, source = 'strava', updated_at = CURRENT_TIMESTAMP
            WHERE activity_kit.source = 'auto'
            """
        )
    parts = ", ".join(f"'{kind}'" for kind in PART_KINDS)
    _claim_defaults(conn, f"k.kind NOT IN ({parts})")
    # Parts follow the activity's bike. A part row left over from another bike
    # (the bike was changed by hand or by Strava gear), or an indoor ride on a
    # part that only wears outdoors, is dropped first.
    conn.execute(
        f"""
        DELETE FROM activity_kit
        WHERE source = 'auto'
            AND kit_id IN (SELECT id FROM kit_items WHERE parent_id IS NOT NULL AND NOT COALESCE(count_indoor, 0))
            AND activity_id IN (SELECT id FROM activities WHERE type = '{INDOOR}')
        """
    )
    conn.execute(
        """
        DELETE FROM activity_kit
        WHERE source = 'auto'
            AND kit_id IN (SELECT id FROM kit_items WHERE parent_id IS NOT NULL)
            AND EXISTS (
                SELECT 1 FROM activity_kit b JOIN kit_items part ON part.id = activity_kit.kit_id
                WHERE b.activity_id = activity_kit.activity_id AND b.slot = 'bike' AND b.kit_id IS NOT part.parent_id
            )
        """
    )
    if _has_table(conn, "activity_source_refs"):
        # Rides from before the bike was tracked still carry its Strava gear id.
        conn.execute(
            f"""
            INSERT OR IGNORE INTO activity_kit (activity_id, slot, kit_id, source)
            SELECT a.id, k.kind, k.id, 'auto'
            FROM kit_items k
            JOIN kit_items bike ON bike.id = k.parent_id AND bike.strava_gear_id IS NOT NULL
            JOIN activity_source_refs sr ON sr.source = 'strava'
                AND json_extract(sr.metadata_json, '$.gear_id') = bike.strava_gear_id
            JOIN activities a ON a.id = sr.activity_id
            LEFT JOIN activity_kit b ON b.activity_id = a.id AND b.slot = 'bike'
            WHERE a.date >= k.started_on AND (k.retired_on IS NULL OR a.date <= k.retired_on)
                AND (b.kit_id IS NULL OR b.kit_id = bike.id) AND COALESCE(b.source, '') != 'manual'
                AND (a.type != '{INDOOR}' OR COALESCE(k.count_indoor, 0))
            """
        )
    conn.execute(
        f"""
        INSERT OR IGNORE INTO activity_kit (activity_id, slot, kit_id, source)
        SELECT a.id, k.kind, k.id, 'auto'
        FROM kit_items k
        JOIN activity_kit b ON b.kit_id = k.parent_id AND b.slot = 'bike'
        JOIN activities a ON a.id = b.activity_id
        WHERE k.parent_id IS NOT NULL AND a.date >= k.started_on AND (k.retired_on IS NULL OR a.date <= k.retired_on)
            AND (a.type != '{INDOOR}' OR COALESCE(k.count_indoor, 0))
        """
    )
    # Loose parts (not fitted to a bike) can still be a sport default.
    _claim_defaults(conn, f"k.kind IN ({parts}) AND k.parent_id IS NULL")
    conn.execute("DELETE FROM activity_kit WHERE activity_id NOT IN (SELECT id FROM activities)")
    conn.commit()


def _claim_defaults(conn: sqlite3.Connection, where: str) -> None:
    conn.execute(
        f"""
        INSERT OR IGNORE INTO activity_kit (activity_id, slot, kit_id, source)
        SELECT a.id, k.kind, k.id, 'auto'
        FROM kit_items k
        JOIN activities a ON {_IN_WINDOW}
        WHERE k.is_default = 1 AND k.retired_on IS NULL AND {where}
        """
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _share_status(share: Optional[float]) -> str:
    if share is None:
        return "no_threshold"
    if share >= 1:
        return "due"
    if share >= NEARLY_DUE:
        return "nearly_due"
    return "ok"


def _events(conn: sqlite3.Connection, kit_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, action, done_on, note FROM kit_events WHERE kit_id = ? ORDER BY done_on DESC, id DESC", (kit_id,)
    ).fetchall()
    return [{**dict(row), "label": SERVICE_ACTIONS.get(row["action"], SERVICE_ACTIONS["other"])["label"]} for row in rows]


def _service(conn: sqlite3.Connection, item: dict[str, Any], events: list[dict[str, Any]], used_km: float) -> Optional[dict[str, Any]]:
    """Distance since the last logged service of the item's service action."""
    action = item.get("service_action")
    if not action or item.get("retired_on"):
        return None
    last = next((event for event in events if event["action"] == action), None)
    if last:
        # Rides from the day after the service count toward the next one.
        since_km = conn.execute(
            """
            SELECT COALESCE(SUM(a.distance_km), 0) FROM activity_kit ak JOIN activities a ON a.id = ak.activity_id
            WHERE ak.kit_id = ? AND a.date > ?
            """,
            (item["id"], last["done_on"]),
        ).fetchone()[0]
    else:
        # Without a logged service the distance since is unknown, so no cue yet.
        since_km = None
    every = item.get("service_every_km")
    share = since_km / every if every and since_km is not None else None
    meta = SERVICE_ACTIONS.get(action, SERVICE_ACTIONS["other"])
    return {
        "action": action,
        "label": meta["label"],
        "due_label": meta["due"],
        "every_km": every,
        "last_on": last["done_on"] if last else None,
        "since_km": round(since_km, 1) if since_km is not None else None,
        "share": round(share, 3) if share is not None else None,
        "status": "unlogged" if last is None else _share_status(share),
    }


def _serialize(row: sqlite3.Row, today: date, conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    item = dict(row)
    item["is_default"] = bool(item["is_default"])
    item["count_indoor"] = bool(item.get("count_indoor"))
    used_km = round((item.pop("activity_km") or 0) + (item["start_km"] or 0), 1)
    used_hours = round((item.pop("activity_min") or 0) / 60 + (item["start_hours"] or 0), 1)
    shares = [
        used / threshold
        for used, threshold in ((used_km, item["threshold_km"]), (used_hours, item["threshold_hours"]))
        if threshold
    ]
    share = max(shares) if shares else None
    status = "retired" if item["retired_on"] else _share_status(share)
    remaining_km = round(item["threshold_km"] - used_km, 1) if item["threshold_km"] else None
    events = _events(conn, item["id"]) if conn is not None else []
    service = _service(conn, item, events, used_km) if conn is not None else None
    return {
        **item,
        "events": events,
        "service": service,
        "kind_label": KINDS.get(item["kind"], {}).get("label", item["kind"].title()),
        "used_km": used_km,
        "used_hours": used_hours,
        "used_share": round(share, 3) if share is not None else None,
        "remaining_km": remaining_km,
        "status": status,
        "age_days": (today - date.fromisoformat(item["started_on"])).days,
    }


def _rows(conn: sqlite3.Connection, where: str = "1 = 1", params: tuple = ()) -> list[sqlite3.Row]:
    return conn.execute(
        f"""
        SELECT k.*,
            COUNT(a.id) AS activity_count,
            SUM(a.distance_km) AS activity_km,
            SUM(a.duration_min) AS activity_min,
            MAX(a.date) AS last_used_on
        FROM kit_items k
        LEFT JOIN activity_kit ak ON ak.kit_id = k.id
        LEFT JOIN activities a ON a.id = ak.activity_id
        WHERE {where}
        GROUP BY k.id
        ORDER BY k.retired_on IS NOT NULL, k.retired_on DESC, k.kind, k.is_default DESC, k.started_on DESC
        """,
        params,
    ).fetchall()


def list_kit(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    sync_assignments(conn)
    items = [_serialize(row, today, conn) for row in _rows(conn)]
    names = {item["id"]: item["name"] for item in items}
    for item in items:
        item["parent_name"] = names.get(item["parent_id"])
        item["due_reason"] = _due_reason(item)
    return {
        "items": items,
        "due": [item for item in items if item["due_reason"]],
        "kinds": [{"key": key, **meta} for key, meta in KINDS.items()],
        "service_actions": [{"key": key, **meta} for key, meta in SERVICE_ACTIONS.items()],
        "sports": list(SPORTS),
        "strava_gear": _strava_gear(conn),
    }


def get_item(conn: sqlite3.Connection, kit_id: int, today: Optional[date] = None) -> dict[str, Any]:
    rows = _rows(conn, "k.id = ?", (kit_id,))
    if not rows:
        raise LookupError("Kit item not found.")
    return _serialize(rows[0], today or date.today(), conn)


def _due_reason(item: dict[str, Any]) -> Optional[str]:
    if item["status"] in ("nearly_due", "due"):
        return "wear"
    if item["service"] and item["service"]["status"] in ("nearly_due", "due"):
        return "service"
    return None


def kit_due(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    """Active items at 90%+ of a wear threshold or service interval, for the Today cue."""
    return list_kit(conn, today)["due"]


def kit_due_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    return [
        {
            **{key: item[key] for key in ("name", "kind", "parent_name", "due_reason", "status", "used_km", "threshold_km", "used_hours", "threshold_hours")},
            "service": item["service"] if item["due_reason"] == "service" else None,
        }
        for item in kit_due(conn, today)
    ]


def default_item(conn: sqlite3.Connection, sport: str, kind: str, today: Optional[date] = None) -> Optional[dict[str, Any]]:
    sync_assignments(conn)
    rows = _rows(conn, "k.sport = ? AND k.kind = ? AND k.is_default = 1 AND k.retired_on IS NULL", (sport, kind))
    return _serialize(rows[0], today or date.today(), conn) if rows else None


def _strava_gear(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Gear ids seen on imported Strava activities, to link items to."""
    if not _has_table(conn, "activity_source_refs"):
        return []
    rows = conn.execute(
        """
        SELECT json_extract(sr.metadata_json, '$.gear_id') AS gear_id, a.type AS sport,
            COUNT(*) AS activity_count, ROUND(SUM(a.distance_km), 1) AS distance_km, MAX(a.date) AS last_used_on
        FROM activity_source_refs sr
        JOIN activities a ON a.id = sr.activity_id
        WHERE sr.source = 'strava' AND json_extract(sr.metadata_json, '$.gear_id') IS NOT NULL
        GROUP BY gear_id, a.type
        ORDER BY last_used_on DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _validate(conn: sqlite3.Connection, fields: dict[str, Any], kind: str, kit_id: Optional[int] = None) -> None:
    if "sport" in fields and fields["sport"] not in SPORTS:
        raise ValueError(f"Sport must be one of {', '.join(SPORTS)}.")
    for key in ("threshold_km", "threshold_hours", "start_km", "start_hours", "service_every_km"):
        if fields.get(key) is not None and fields[key] < 0:
            raise ValueError(f"{key} cannot be negative.")
    if fields.get("service_action") and fields["service_action"] not in SERVICE_ACTIONS:
        raise ValueError(f"Service must be one of {', '.join(SERVICE_ACTIONS)}.")
    if fields.get("parent_id") is not None:
        if kind not in PART_KINDS:
            raise ValueError("Only bike parts can be fitted to a bike.")
        parent = conn.execute("SELECT kind, sport FROM kit_items WHERE id = ?", (fields["parent_id"],)).fetchone()
        if parent is None or parent["kind"] != "bike" or fields["parent_id"] == kit_id:
            raise ValueError("Parts can only be fitted to a bike.")
        # A fitted part rides wherever its bike rides and is never a default itself.
        fields["sport"] = parent["sport"]
        fields["is_default"] = 0


def _claim_default(conn: sqlite3.Connection, kit_id: int) -> None:
    """One default per sport and kind: the newest choice wins."""
    conn.execute(
        """
        UPDATE kit_items SET is_default = 0
        WHERE id != ? AND (kind, sport) = (SELECT kind, sport FROM kit_items WHERE id = ?)
        """,
        (kit_id, kit_id),
    )


def create_item(conn: sqlite3.Connection, payload: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    ensure_tables(conn)
    today = today or date.today()
    kind = payload.get("kind")
    if kind not in KINDS:
        raise ValueError(f"Kind must be one of {', '.join(KINDS)}.")
    fields = {
        "name": payload.get("name") or KINDS[kind]["label"],
        "kind": kind,
        "sport": payload.get("sport") or KINDS[kind]["sport"],
        "started_on": payload.get("started_on") or today.isoformat(),
        "threshold_km": payload.get("threshold_km"),
        "threshold_hours": payload.get("threshold_hours"),
        "start_km": payload.get("start_km") or 0,
        "start_hours": payload.get("start_hours") or 0,
        "is_default": 1 if payload.get("is_default", True) else 0,
        "strava_gear_id": payload.get("strava_gear_id") or None,
        "notes": payload.get("notes"),
        "parent_id": payload.get("parent_id"),
        "service_action": payload.get("service_action") or None,
        "service_every_km": payload.get("service_every_km"),
        "replaces_id": payload.get("replaces_id"),
        "count_indoor": 1 if payload.get("count_indoor", KINDS[kind].get("indoor", False)) else 0,
    }
    _validate(conn, fields, kind)
    cursor = conn.execute(
        f"INSERT INTO kit_items ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
        tuple(fields.values()),
    )
    kit_id = cursor.lastrowid
    if fields["is_default"]:
        _claim_default(conn, kit_id)
    sync_assignments(conn)
    return get_item(conn, kit_id, today)


def update_item(conn: sqlite3.Connection, kit_id: int, payload: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    ensure_tables(conn)
    current = conn.execute("SELECT * FROM kit_items WHERE id = ?", (kit_id,)).fetchone()
    if current is None:
        raise LookupError("Kit item not found.")
    fields = {key: payload[key] for key in EDITABLE if key in payload}
    _validate(conn, fields, current["kind"], kit_id)
    if "is_default" in fields:
        fields["is_default"] = 1 if fields["is_default"] else 0
    if fields.get("retired_on"):
        fields["is_default"] = 0  # a retired item stops claiming new activities
    if "strava_gear_id" in fields:
        fields["strava_gear_id"] = fields["strava_gear_id"] or None
    if "service_action" in fields:
        fields["service_action"] = fields["service_action"] or None
    if "count_indoor" in fields:
        fields["count_indoor"] = 1 if fields["count_indoor"] else 0
    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(f"UPDATE kit_items SET {assignments} WHERE id = ?", (*fields.values(), kit_id))
    if fields.get("is_default"):
        _claim_default(conn, kit_id)
    sync_assignments(conn)
    return get_item(conn, kit_id, today)


def replace_item(conn: sqlite3.Connection, kit_id: int, payload: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    """Retire an item and start a fresh copy (same bike, thresholds and service plan)."""
    ensure_tables(conn)
    today = today or date.today()
    current = conn.execute("SELECT * FROM kit_items WHERE id = ?", (kit_id,)).fetchone()
    if current is None:
        raise LookupError("Kit item not found.")
    if current["retired_on"]:
        raise ValueError("That item is already retired.")
    on = date.fromisoformat(payload.get("on") or today.isoformat())
    started = date.fromisoformat(current["started_on"])
    if on < started:
        raise ValueError("The replacement date is before this item was fitted.")
    # The old item keeps everything up to the day before; the new one starts on the day.
    retired_on = max(started, on - timedelta(days=1))
    was_default = bool(current["is_default"])
    update_item(conn, kit_id, {"retired_on": retired_on.isoformat()}, today)
    # Rows from the replacement day on belong to the new item.
    conn.execute(
        "DELETE FROM activity_kit WHERE kit_id = ? AND source != 'manual' AND activity_id IN (SELECT id FROM activities WHERE date > ?)",
        (kit_id, retired_on.isoformat()),
    )
    fresh = create_item(
        conn,
        {
            "kind": current["kind"],
            "name": payload.get("name") or current["name"],
            "sport": current["sport"],
            "started_on": on.isoformat(),
            "threshold_km": current["threshold_km"],
            "threshold_hours": current["threshold_hours"],
            "is_default": was_default,
            "strava_gear_id": current["strava_gear_id"],
            "parent_id": current["parent_id"],
            "service_action": current["service_action"],
            "service_every_km": current["service_every_km"],
            "count_indoor": bool(current["count_indoor"]),
            "replaces_id": kit_id,
        },
        today,
    )
    if payload.get("service_action"):
        # e.g. a new chain that was waxed before fitting
        log_event(conn, fresh["id"], {"action": payload["service_action"], "done_on": on.isoformat()}, today)
    return get_item(conn, fresh["id"], today)


def log_event(conn: sqlite3.Connection, kit_id: int, payload: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    ensure_tables(conn)
    today = today or date.today()
    if conn.execute("SELECT 1 FROM kit_items WHERE id = ?", (kit_id,)).fetchone() is None:
        raise LookupError("Kit item not found.")
    action = payload.get("action")
    if action not in SERVICE_ACTIONS:
        raise ValueError(f"Action must be one of {', '.join(SERVICE_ACTIONS)}.")
    conn.execute(
        "INSERT INTO kit_events (kit_id, action, done_on, note) VALUES (?, ?, ?, ?)",
        (kit_id, action, payload.get("done_on") or today.isoformat(), payload.get("note")),
    )
    conn.commit()
    return get_item(conn, kit_id, today)


def delete_event(conn: sqlite3.Connection, event_id: int, today: Optional[date] = None) -> dict[str, Any]:
    ensure_tables(conn)
    row = conn.execute("SELECT kit_id FROM kit_events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise LookupError("Log entry not found.")
    conn.execute("DELETE FROM kit_events WHERE id = ?", (event_id,))
    conn.commit()
    return get_item(conn, row["kit_id"], today)


# ---------------------------------------------------------------------------
# Per-activity assignment
# ---------------------------------------------------------------------------


def activity_kit(conn: sqlite3.Connection, activity_id: str) -> dict[str, Any]:
    sync_assignments(conn)
    activity = conn.execute("SELECT id, date, type FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if activity is None:
        raise LookupError("Activity not found.")
    chosen = {
        row["slot"]: dict(row)
        for row in conn.execute("SELECT slot, kit_id, source FROM activity_kit WHERE activity_id = ?", (activity_id,))
    }
    candidates = conn.execute(
        "SELECT id, name, kind, retired_on FROM kit_items WHERE sport = ? AND started_on <= ? ORDER BY retired_on IS NOT NULL, name",
        (activity["type"], activity["date"]),
    ).fetchall()
    kinds = [kind for kind in KINDS if any(row["kind"] == kind for row in candidates) or kind in chosen]
    slots = []
    for kind in kinds:
        assigned = chosen.get(kind)
        slots.append(
            {
                "slot": kind,
                "label": KINDS[kind]["label"],
                "kit_id": assigned["kit_id"] if assigned else None,
                "source": assigned["source"] if assigned else None,
                "options": [
                    {"id": row["id"], "name": row["name"], "retired": bool(row["retired_on"])}
                    for row in candidates
                    if row["kind"] == kind
                ],
            }
        )
    return {"activity_id": activity_id, "slots": slots}


def assign_activity_kit(conn: sqlite3.Connection, activity_id: str, slot: str, kit_id: Optional[int]) -> dict[str, Any]:
    ensure_tables(conn)
    if slot not in KINDS:
        raise ValueError(f"Slot must be one of {', '.join(KINDS)}.")
    if conn.execute("SELECT 1 FROM activities WHERE id = ?", (activity_id,)).fetchone() is None:
        raise LookupError("Activity not found.")
    if kit_id is not None:
        item = conn.execute("SELECT kind FROM kit_items WHERE id = ?", (kit_id,)).fetchone()
        if item is None:
            raise LookupError("Kit item not found.")
        if item["kind"] != slot:
            raise ValueError("That item is not the right kind for this slot.")
    if slot == "bike":
        # Parts follow the new bike on the next sweep.
        conn.execute(
            "DELETE FROM activity_kit WHERE activity_id = ? AND source = 'auto' AND kit_id IN (SELECT id FROM kit_items WHERE parent_id IS NOT NULL)",
            (activity_id,),
        )
    conn.execute(
        """
        INSERT INTO activity_kit (activity_id, slot, kit_id, source) VALUES (?, ?, ?, 'manual')
        ON CONFLICT(activity_id, slot) DO UPDATE SET
            kit_id = excluded.kit_id, source = 'manual', updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, slot, kit_id),
    )
    conn.commit()
    return activity_kit(conn, activity_id)


# ---------------------------------------------------------------------------
# Strava gear import
# ---------------------------------------------------------------------------

GEAR_SPORT = {"shoes": "Run", "bike": "Ride"}
GEAR_THRESHOLD_KM = {"shoes": 700}


def annotate_strava_gear(conn: sqlite3.Connection, gear: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark which Strava gear is already linked to a kit item."""
    ensure_tables(conn)
    linked = {
        row["strava_gear_id"]: row["id"]
        for row in conn.execute("SELECT id, strava_gear_id FROM kit_items WHERE strava_gear_id IS NOT NULL")
    }
    return [{**item, "kit_id": linked.get(item["gear_id"])} for item in gear]


def import_strava_gear(
    conn: sqlite3.Connection, gear: list[dict[str, Any]], gear_ids: list[str], today: Optional[date] = None
) -> dict[str, Any]:
    """Create linked kit items that start at Strava's lifetime distance.

    Each item starts today, so only new activities on that gear add to it and
    nothing already counted by Strava is counted twice.
    """
    today = today or date.today()
    created = []
    for item in annotate_strava_gear(conn, gear):
        if item["gear_id"] not in gear_ids or item["kit_id"]:
            continue
        kit = create_item(
            conn,
            {
                "kind": item["kind"],
                "name": item["name"],
                "sport": GEAR_SPORT[item["kind"]],
                "started_on": today.isoformat(),
                "threshold_km": GEAR_THRESHOLD_KM.get(item["kind"]),
                "is_default": item["primary"] and not item["retired"],
                "strava_gear_id": item["gear_id"],
            },
            today,
        )
        # Activities from today already linked to the gear are inside Strava's total.
        start_km = max(0.0, item["distance_km"] - (kit["used_km"] or 0))
        kit = update_item(conn, kit["id"], {"start_km": round(start_km, 1), **({"retired_on": today.isoformat()} if item["retired"] else {})}, today)
        created.append(kit)
    return {"created": created, "gear": annotate_strava_gear(conn, gear)}


GEAR_IDS_FROM = "kit_gear_ids_from"


def gear_backfill_range(conn: sqlite3.Connection, kit_id: int) -> Optional[tuple[str, str]]:
    """Dates whose Strava gear ids are still unknown for a part fitted before its bike was tracked.

    Gear ids are saved on import from the kit release on, and backfilled
    once per date range; the setting remembers how far back they are known.
    """
    from ..repositories.settings import get_setting_value

    row = conn.execute(
        """
        SELECT k.started_on, bike.started_on AS bike_started_on
        FROM kit_items k JOIN kit_items bike ON bike.id = k.parent_id
        WHERE k.id = ? AND bike.strava_gear_id IS NOT NULL
        """,
        (kit_id,),
    ).fetchone()
    if row is None:
        return None
    known_from = get_setting_value(conn, GEAR_IDS_FROM) or row["bike_started_on"]
    if row["started_on"] >= known_from:
        return None
    return row["started_on"], known_from


def mark_gear_ids_known(conn: sqlite3.Connection, start_date: str) -> None:
    from ..repositories.settings import get_setting_value, set_setting_value

    current = get_setting_value(conn, GEAR_IDS_FROM)
    if not current or start_date < current:
        set_setting_value(conn, GEAR_IDS_FROM, start_date)

