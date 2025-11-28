from pathlib import Path
from typing import Any, Dict, List

import json

from . import api
from . import db

RAW_DIR = Path("Data/Row")


def save_raw_json(name: str, data: Any) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


def run_etl() -> None:
    # Extract
    launches: List[Dict[str, Any]] = api.extract_all_launches()
    rocket_ids, launchpad_ids = api.extract_unique_ids(launches)

    rockets_map = api.fetch_rockets(rocket_ids)
    launchpads_map = api.fetch_launchpads(launchpad_ids)

    # Optionally persist raw snapshots
    save_raw_json("launches", launches)
    save_raw_json("rockets", rockets_map)
    save_raw_json("launchpads", launchpads_map)

    # Load into SQLite
    conn = db.get_connection()
    try:
        db.create_schema(conn)
        rocket_id_map, launchpad_id_map = db.load_dimension_tables(
            conn, rockets_map, launchpads_map
        )
        db.load_launches(conn, launches, rocket_id_map, launchpad_id_map)
    finally:
        conn.close()


