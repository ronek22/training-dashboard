"""Photos uploaded to Strava for mountain hikes, kept for the trip recap map.

Strava's activity photos endpoint lists each photo with where (phone GPS) and when it was taken,
and a CDN URL per requested size. The URLs are not guaranteed to last, so both sizes are
downloaded once into `photos/` next to the database (not into it, so the backups stay small): a
small thumbnail for the map pins and the filmstrip, and a large one for the lightbox. Metadata
lives in `activity_photos`. Photos are fetched by the Mountains track sync and
the regular Strava import, for the same foot activities in a mapped range that get a GPS track.

Photos are often added a day or two after the hike, so a hike is checked again whenever a Strava
listing shows a different photo count than the one stored, and on every Mountains sync for
RECHECK_DAYS after the hike.
"""
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from .. import db

THUMB_SIZE = 256
IMAGE_SIZE = 1600
RECHECK_DAYS = 10
PHOTO_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")  # Strava's unique_id is a UUID; it names the files.


def photo_path(unique_id: str, thumb: bool = False) -> Optional[Path]:
    if not PHOTO_ID.match(unique_id or ""):
        return None
    return Path(db.DB_PATH).parent / "photos" / f"{unique_id}{'-thumb' if thumb else ''}.jpg"


def _save(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    partial.write_bytes(content)
    partial.replace(path)


def _listing(client: httpx.Client, activity_id: str, size: int) -> tuple[Optional[list], bool]:
    """(photos, rate_limited). None when the activity can't be read (deleted, private to another app)."""
    response = client.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}/photos",
        params={"size": size, "photo_sources": "true"},
    )
    if response.status_code == 429:
        return None, True
    if response.status_code >= 400:
        return None, False
    body = response.json()
    return (body if isinstance(body, list) else []), False


def _url(photo: dict, size: int) -> Optional[str]:
    urls = photo.get("urls") or {}
    url = urls.get(str(size)) or next(iter(urls.values()), None)
    # Strava answers with a placeholder while an upload is still being processed.
    if not url or photo.get("placeholder_image") or "placeholder" in url:
        return None
    return url


def _download(client: httpx.Client, url: str) -> Optional[bytes]:
    """The image from Strava's CDN, without sending the athlete's Strava token along."""
    request = client.build_request("GET", url)
    request.headers.pop("Authorization", None)
    try:
        response = client.send(request)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400 or not response.headers.get("content-type", "image/jpeg").startswith("image/"):
        return None
    return response.content


def stored_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {row[0]: row[1] for row in conn.execute("SELECT activity_id, photo_count FROM activity_photo_syncs")}


def sync_activity_photos(conn: sqlite3.Connection, client: httpx.Client, activity_id: str) -> tuple[int, bool]:
    """Bring one activity's stored photos in line with Strava. (photos added, finished without rate limit)."""
    activity_id = str(activity_id)
    photos, limited = _listing(client, activity_id, IMAGE_SIZE)
    if limited:
        return 0, False
    photos = [p for p in photos or [] if photo_path(p.get("unique_id")) and _url(p, IMAGE_SIZE)]
    known = {
        row[0] for row in conn.execute("SELECT unique_id FROM activity_photos WHERE activity_id = ?", (activity_id,))
        if photo_path(row[0]).exists()
    }
    thumbs: dict[str, str] = {}
    if any(p["unique_id"] not in known for p in photos):
        small, limited = _listing(client, activity_id, THUMB_SIZE)
        if limited:
            return 0, False
        thumbs = {p["unique_id"]: _url(p, THUMB_SIZE) for p in small or [] if p.get("unique_id")}

    now = datetime.now().isoformat(timespec="seconds")
    added = 0
    for position, photo in enumerate(photos):
        uid = photo["unique_id"]
        location = photo.get("location") or []
        lat, lon = (location[0], location[1]) if len(location) == 2 else (None, None)
        width, height = (photo.get("sizes") or {}).get(str(IMAGE_SIZE)) or (None, None)
        meta = (activity_id, position, photo.get("created_at"), photo.get("created_at_local"), lat, lon,
                (photo.get("caption") or "").strip() or None, width, height)
        if uid in known:
            conn.execute(
                "UPDATE activity_photos SET activity_id = ?, position = ?, taken_at = ?, taken_at_local = ?, lat = ?, lon = ?, "
                "caption = ?, width = ?, height = ? WHERE unique_id = ?",
                (*meta, uid),
            )
            continue
        image = _download(client, _url(photo, IMAGE_SIZE))
        if not image:
            continue
        thumb = _download(client, thumbs[uid]) if thumbs.get(uid) else None
        _save(photo_path(uid), image)
        _save(photo_path(uid, thumb=True), thumb or image)
        conn.execute(
            "INSERT OR REPLACE INTO activity_photos (unique_id, activity_id, position, taken_at, taken_at_local, lat, lon, "
            "caption, width, height, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, *meta, now),
        )
        added += 1

    listed = {p["unique_id"] for p in photos}
    for (uid,) in conn.execute("SELECT unique_id FROM activity_photos WHERE activity_id = ?", (activity_id,)).fetchall():
        if uid not in listed:  # Deleted on Strava.
            conn.execute("DELETE FROM activity_photos WHERE unique_id = ?", (uid,))
            for thumb in (False, True):
                photo_path(uid, thumb).unlink(missing_ok=True)
    conn.execute(
        "INSERT INTO activity_photo_syncs (activity_id, photo_count, synced_at) VALUES (?, ?, ?) "
        "ON CONFLICT(activity_id) DO UPDATE SET photo_count = excluded.photo_count, synced_at = excluded.synced_at",
        (activity_id, len(photos), now),
    )
    conn.commit()
    return added, True


def sync_listed_photos(conn: sqlite3.Connection, client: httpx.Client, activities: list) -> tuple[int, int]:
    """Strava summary activities whose photo count differs from what is stored. (added, left for later)."""
    counts = stored_counts(conn)
    due = [
        str(a["id"]) for a in activities
        if (a.get("total_photo_count") or 0) != counts.get(str(a["id"]), 0)
    ]
    return _sync_many(conn, client, due)


def sync_track_photos(conn: sqlite3.Connection, client: httpx.Client, today: Optional[date] = None) -> tuple[int, int]:
    """Stored mountain tracks never checked for photos, and recent ones checked again. (added, left for later)."""
    since = ((today or datetime.now().date()) - timedelta(days=RECHECK_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT m.activity_id FROM mountain_tracks m LEFT JOIN activity_photo_syncs s ON s.activity_id = m.activity_id "
        "WHERE s.activity_id IS NULL OR m.date >= ? ORDER BY m.date DESC, m.activity_id",
        (since,),
    ).fetchall()
    return _sync_many(conn, client, [row[0] for row in rows])


def _sync_many(conn: sqlite3.Connection, client: httpx.Client, activity_ids: list[str]) -> tuple[int, int]:
    added = 0
    for index, activity_id in enumerate(activity_ids):
        count, complete = sync_activity_photos(conn, client, activity_id)
        added += count
        if not complete:
            return added, len(activity_ids) - index
    return added, 0


def photos_for(conn: sqlite3.Connection, activity_ids: list[str]) -> dict[str, list[dict]]:
    """Stored photos per activity, in Strava's order (images at GET /trails/photos/{id})."""
    if not activity_ids:
        return {}
    marks = ",".join("?" for _ in activity_ids)
    try:
        rows = conn.execute(
            f"SELECT unique_id, activity_id, taken_at, taken_at_local, lat, lon, caption, width, height FROM activity_photos "
            f"WHERE activity_id IN ({marks}) ORDER BY activity_id, position",
            [str(a) for a in activity_ids],
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row["activity_id"], []).append({
            "id": row["unique_id"],
            "taken_at": row["taken_at"],
            "taken_at_local": row["taken_at_local"],
            "lat": row["lat"],
            "lon": row["lon"],
            "caption": row["caption"],
            "width": row["width"],
            "height": row["height"],
        })
    return out


def stored_photo(unique_id: str, thumb: bool) -> Optional[Path]:
    path = photo_path(unique_id, thumb)
    return path if path and path.is_file() else None
