from pathlib import Path
from typing import Any, Dict, List, Tuple

import sqlite3

DB_PATH = Path("Data/DB/spacex.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rockets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spacex_id TEXT UNIQUE,
            name TEXT,
            type TEXT,
            active INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS launchpads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spacex_id TEXT UNIQUE,
            name TEXT,
            region TEXT,
            latitude REAL,
            longitude REAL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS launches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spacex_id TEXT UNIQUE,
            name TEXT,
            date_utc TEXT,
            success INTEGER,
            rocket_id INTEGER,
            launchpad_id INTEGER,
            details TEXT,
            FOREIGN KEY (rocket_id) REFERENCES rockets(id),
            FOREIGN KEY (launchpad_id) REFERENCES launchpads(id)
        )
        """
    )

    conn.commit()


def load_dimension_tables(
    conn: sqlite3.Connection,
    rockets_map: Dict[str, Dict[str, Any]],
    launchpads_map: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, int]]:
    cur = conn.cursor()

    for spacex_id, r in rockets_map.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO rockets (spacex_id, name, type, active)
            VALUES (?, ?, ?, ?)
            """,
            (
                spacex_id,
                r.get("name"),
                r.get("type"),
                1 if r.get("active") else 0,
            ),
        )

    for spacex_id, p in launchpads_map.items():
        latitude = p.get("latitude")
        longitude = p.get("longitude")

        cur.execute(
            """
            INSERT OR IGNORE INTO launchpads (spacex_id, name, region, latitude, longitude)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                spacex_id,
                p.get("name"),
                p.get("region"),
                latitude,
                longitude,
            ),
        )

    conn.commit()

    cur.execute("SELECT id, spacex_id FROM rockets")
    rocket_id_map = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("SELECT id, spacex_id FROM launchpads")
    launchpad_id_map = {row[1]: row[0] for row in cur.fetchall()}

    return rocket_id_map, launchpad_id_map


def load_launches(
    conn: sqlite3.Connection,
    launches: List[Dict[str, Any]],
    rocket_id_map: Dict[str, int],
    launchpad_id_map: Dict[str, int],
) -> None:
    cur = conn.cursor()

    for launch in launches:
        spacex_id = launch.get("id")
        rocket_spacex = launch.get("rocket")
        launchpad_spacex = launch.get("launchpad")

        rocket_id = rocket_id_map.get(rocket_spacex)
        launchpad_id = launchpad_id_map.get(launchpad_spacex)

        success_val = launch.get("success")
        if success_val is None:
            success_int = None
        else:
            success_int = 1 if success_val else 0

        cur.execute(
            """
            INSERT OR IGNORE INTO launches
            (spacex_id, name, date_utc, success, rocket_id, launchpad_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                spacex_id,
                launch.get("name"),
                launch.get("date_utc"),
                success_int,
                rocket_id,
                launchpad_id,
                launch.get("details"),
            ),
        )

    conn.commit()


