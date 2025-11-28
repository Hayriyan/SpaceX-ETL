## SpaceX ETL & Analytics Pipeline

This project builds a full **ETL pipeline** on top of the public SpaceX v4 API and a **pandas-based analytics notebook**.

Data flows like this:

- **SpaceX Cloud API** → **Python ETL (`Src/`)** → **SQLite warehouse (`Data/DB/spacex.db`)** → **pandas analysis (`notebook/spacex_analysis.ipynb`)** → **CSV + plots (`Data/Procesed/`)**

The design is intentionally close to a production data-engineering setup: raw snapshots, a normalized warehouse, and a separate analytics layer.

---

## 1. Project Structure

- **`.env`**
  - Reserved for environment variables (e.g., API keys, configuration). Not currently required by the SpaceX public API, but ready if you extend the project.

- **`Src/`**
  - **`api.py`** – handles all HTTP calls to the SpaceX API and extraction of unique IDs.
  - **`db.py`** – owns the SQLite schema and *all* DB write logic (DWH layer).
  - **`etl.py`** – orchestrates the Extract–Transform–Load workflow and writes raw JSON snapshots.
  - **`__init__.py`** – marks `Src` as a package so it can be imported from the entry script.

- **`etl_pipeline.py`**
  - Small command-line entry point that simply calls `Src.etl.run_etl()`. This is how you trigger the whole ETL.

- **`Data/`**
  - **`Row/`** – raw API snapshots:
    - `launches.json`, `rockets.json`, `launchpads.json`
  - **`DB/`** – normalized SQLite warehouse:
    - `spacex.db`
  - **`Procesed/`** – analytics outputs:
    - `mission_report.csv`, `failed_missions.csv`, `launches_per_year.png`

- **`notebook/`**
  - **`spacex_analysis.ipynb`** – all pandas + matplotlib analysis and reporting logic.

- **`requirments.txt`**
  - Python dependencies: `requests`, `pandas`, `matplotlib`, `jupyter`, `python-dotenv`.

---

## 2. Database Schema (3NF Warehouse)

The normalized warehouse lives in `Data/DB/spacex.db`. Schema creation is implemented in `Src/db.py` inside `create_schema`.

### 2.1 `rockets` table

Defined in `create_schema`:

- **`id INTEGER PRIMARY KEY AUTOINCREMENT`**
  - Internal surrogate key used as an FK in `launches.rocket_id`.
- **`spacex_id TEXT UNIQUE`**
  - The original SpaceX rocket ID string (e.g. `"5e9d0d95eda69955f709d1eb"`).
- **`name TEXT`**
  - Human-readable rocket name (e.g. `"Falcon 9"`).
- **`type TEXT`**
  - Rocket type/category as given by the API.
- **`active INTEGER`**
  - 1 = active, 0 = retired. Converted from the Boolean API field.

Why this is 3NF:

- Each rocket appears exactly once; attributes depend only on the rocket key.
- Launch-specific attributes (success, date, etc.) are not stored here.

### 2.2 `launchpads` table

Columns:

- **`id INTEGER PRIMARY KEY AUTOINCREMENT`**
  - Internal surrogate key used as an FK in `launches.launchpad_id`.
- **`spacex_id TEXT UNIQUE`**
  - Native SpaceX launchpad ID.
- **`name TEXT`**
  - Pad/site name (e.g., `"CCSFS SLC 40"`).
- **`region TEXT`**
  - Geographic region (e.g., `"Florida"`).
- **`latitude REAL`, `longitude REAL`**
  - Geo coordinates of the pad.

Again, launchpads are stored once and referenced from `launches` by integer ID.

### 2.3 `launches` table

Columns:

- **`id INTEGER PRIMARY KEY AUTOINCREMENT`**
  - Internal surrogate key for the launch.
- **`spacex_id TEXT UNIQUE`**
  - Native SpaceX launch ID string.
- **`name TEXT`**
  - Mission name (e.g., `"Starlink 4-1"`).
- **`date_utc TEXT`**
  - Launch time in ISO UTC string form.
- **`success INTEGER`**
  - 1 = success, 0 = failure, `NULL` = unknown / not yet determined.
- **`rocket_id INTEGER` FK → `rockets.id`**
  - Internal integer referencing the rocket row.
- **`launchpad_id INTEGER` FK → `launchpads.id`**
  - Internal integer referencing the launchpad row.
- **`details TEXT`**
  - Free-text mission description or failure notes.

This table forms the **fact table** in the warehouse: each row is a launch event referencing dimension tables `rockets` and `launchpads` by integer IDs (not by long string IDs from the API).

---

## 3. ETL Flow (Python Code, Step by Step)

### 3.1 API Layer – `Src/api.py`

This module isolates all HTTP calls and ID extraction.

- **`BASE_URL = "https://api.spacexdata.com/v4"`**
  - Base prefix used for every API call.

- **`get_json(endpoint: str) -> Any`**
  - Builds a full URL with `BASE_URL` + `endpoint`.
  - Sends `GET` via `requests.get(..., timeout=20)`.
  - `resp.raise_for_status()` will raise an HTTP error for non-2xx responses.
  - Returns the JSON-decoded Python object.
  - On any `RequestException`, calls `SystemExit` with a clear error message.

- **`extract_all_launches() -> list[dict]`**
  - Calls `get_json("launches")`.
  - Asserts the response is a list (the expected payload shape).
  - Returns a list of launch dictionaries.

- **`extract_unique_ids(launches: list[dict]) -> tuple[set[str], set[str]]`**
  - Iterates over the list of launch dictionaries.
  - For each launch:
    - Reads `launch["rocket"]` (SpaceX rocket ID) and `launch["launchpad"]` (launchpad ID).
    - Adds them to **two sets**: `rocket_ids` and `launchpad_ids`.
  - Using sets ensures **deduplication**: no rocket/launchpad is fetched twice.
  - Returns `(rocket_ids, launchpad_ids)`.

- **`fetch_rockets(unique_rocket_ids: set[str]) -> dict[str, dict]`**
  - For each rocket ID in the set, fetches `rockets/{id}` via `get_json`.
  - Returns a mapping: `{spacex_rocket_id: rocket_payload_dict}`.
  - This acts as a **mini dimension cache** in memory.

- **`fetch_launchpads(unique_launchpad_ids: set[str]) -> dict[str, dict]`**
  - For each launchpad ID in the set, fetches `launchpads/{id}`.
  - Returns `{spacex_launchpad_id: launchpad_payload_dict}`.

These functions together implement:

1. Full launch manifest fetch.
2. Extraction and dedup of rocket/launchpad IDs.
3. **One-time fetch** per rocket and launchpad.

### 3.2 Database Layer – `Src/db.py`

This module owns the warehouse and all writes.

- **`DB_PATH = Path("Data/DB/spacex.db")`**
  - Path to the SQLite file inside the `Data/DB` directory.

- **`get_connection() -> sqlite3.Connection`**
  - Ensures `Data/DB` exists (`mkdir(parents=True, exist_ok=True)`).
  - Returns an open SQLite connection to `spacex.db`.

- **`create_schema(conn) -> None`**
  - Creates three tables (`rockets`, `launchpads`, `launches`) if they don’t already exist.
  - Uses `CREATE TABLE IF NOT EXISTS ...` SQL.
  - Commits at the end.
  - Encodes the 3NF warehouse design described in section 2.

- **`load_dimension_tables(conn, rockets_map, launchpads_map) -> (rocket_id_map, launchpad_id_map)`**
  - **Input**:
    - `rockets_map`: `{spacex_rocket_id: rocket_dict}` from `api.fetch_rockets`.
    - `launchpads_map`: `{spacex_launchpad_id: launchpad_dict}` from `api.fetch_launchpads`.
  - **Process (rockets)**:
    - Iterates `rockets_map.items()`.
    - For each entry, executes:
      ```sql
      INSERT OR IGNORE INTO rockets (spacex_id, name, type, active)
      VALUES (?, ?, ?, ?)
      ```
    - Converts the `active` Boolean from the API to `1` or `0`.
    - Uses `INSERT OR IGNORE` so re-running ETL is **idempotent** (no crashing on duplicates).
  - **Process (launchpads)**:
    - Iterates `launchpads_map.items()`.
    - Pulls `latitude` and `longitude` directly.
    - Executes:
      ```sql
      INSERT OR IGNORE INTO launchpads (spacex_id, name, region, latitude, longitude)
      VALUES (?, ?, ?, ?, ?)
      ```
  - **Mapping back to internal IDs**:
    - After inserts, it queries:
      - `SELECT id, spacex_id FROM rockets`
      - `SELECT id, spacex_id FROM launchpads`
    - Builds two dictionaries:
      - `rocket_id_map = {spacex_id: internal_id}`
      - `launchpad_id_map = {spacex_id: internal_id}`
    - These dictionaries are **critical** for later mapping launches to integer foreign keys.

- **`load_launches(conn, launches, rocket_id_map, launchpad_id_map) -> None`**
  - **Inputs**:
    - `launches`: list of launch dicts from `extract_all_launches`.
    - `rocket_id_map`: maps SpaceX rocket `id` → `rockets.id`.
    - `launchpad_id_map`: maps spaceX launchpad `id` → `launchpads.id`.
  - **Process**:
    - Iterates each launch dictionary.
    - Reads:
      - `spacex_id`: `launch["id"]`
      - `rocket_spacex`: `launch["rocket"]`
      - `launchpad_spacex`: `launch["launchpad"]`
    - Looks up:
      - `rocket_id = rocket_id_map.get(rocket_spacex)`
      - `launchpad_id = launchpad_id_map.get(launchpad_spacex)`
    - Safely converts `success`:
      - If `success` is `None` → store `NULL`.
      - `True` → `1`, `False` → `0`.
    - Inserts each launch row with:
      ```sql
      INSERT OR IGNORE INTO launches
      (spacex_id, name, date_utc, success, rocket_id, launchpad_id, details)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ```
    - `INSERT OR IGNORE` makes it safe to re-run ETL without duplicating rows.
  - Commits at the end.

### 3.3 ETL Orchestrator – `Src/etl.py`

This module wires the API and DB layers and saves raw data.

- **`RAW_DIR = Path("Data/Row")`**
  - Location where raw API snapshots are stored as JSON.

- **`save_raw_json(name: str, data: Any) -> None`**
  - Ensures `Data/Row` exists.
  - Writes `data` to `Data/Row/{name}.json` using `json.dump`.
  - Used to persist:
    - `launches.json`
    - `rockets.json`
    - `launchpads.json`
  - This is the **raw data lake** layer, used for debugging or replay.

- **`run_etl() -> None`**
  - **Extract:**
    - `launches = api.extract_all_launches()`
    - `rocket_ids, launchpad_ids = api.extract_unique_ids(launches)`
    - `rockets_map = api.fetch_rockets(rocket_ids)`
    - `launchpads_map = api.fetch_launchpads(launchpad_ids)`
  - **Raw persistence:**
    - `save_raw_json("launches", launches)`
    - `save_raw_json("rockets", rockets_map)`
    - `save_raw_json("launchpads", launchpads_map)`
  - **Load:**
    - Opens a DB connection: `conn = db.get_connection()`
    - `db.create_schema(conn)` to ensure tables exist.
    - `rocket_id_map, launchpad_id_map = db.load_dimension_tables(...)`.
    - `db.load_launches(conn, launches, rocket_id_map, launchpad_id_map)`.
    - Closes the connection in a `finally` block.

In other words, `run_etl()` is a single function that:

1. Hits the SpaceX API efficiently.
2. Saves raw JSON.
3. Populates a fully normalized SQLite warehouse.

### 3.4 Entry Script – `etl_pipeline.py`

The script at the project root:

- Imports `run_etl`:
  - `from Src.etl import run_etl`
- Defines:
  - `main()` → simply calls `run_etl()`.
- Guard:
  - `if __name__ == "__main__": main()`

Usage from the terminal (after activating the virtual env):

```bash
python etl_pipeline.py
```

This will:

- Hit SpaceX API.
- Write raw JSON into `Data/Row`.
- Create/update `Data/DB/spacex.db` with rockets, launchpads, launches.

---

## 4. Analytics Layer – `notebook/spacex_analysis.ipynb`

All pandas + plotting code lives in the notebook so the ETL stays focused on data movement and structure.

### 4.1 Setup (Cells 0–1)

- **Imports**:
  - `sqlite3`, `Path` from `pathlib`.
  - `pandas as pd`.
  - `matplotlib.pyplot as plt`.

- **Paths**:
  - `DB_PATH = Path("../Data/DB/spacex.db")`
  - `PROCESSED_DIR = Path("../Data/Procesed")`; creates the directory if needed.

- **Loading tables from SQLite**:
  - Opens a connection: `conn = sqlite3.connect(DB_PATH)`.
  - Reads tables:
    - `df_launches = pd.read_sql_query("SELECT * FROM launches", conn)`
    - `df_rockets = pd.read_sql_query("SELECT * FROM rockets", conn)`
    - `df_launchpads = pd.read_sql_query("SELECT * FROM launchpads", conn)`
  - Closes `conn`.

### 4.2 Building the Master Dataset (Cell 2)

- **Join launches ↔ rockets**:
  - `master = df_launches.merge(df_rockets, how="left", left_on="rocket_id", right_on="id", suffixes=("_launch", "_rocket"))`
  - This attaches rocket attributes (name, type, active) to each launch row.

- **Join with launchpads**:
  - `master = master.merge(df_launchpads, how="left", left_on="launchpad_id", right_on="id", suffixes=("", "_launchpad"))`
  - Adds launchpad attributes (name, region, coordinates).

- **Export**:
  - `master.to_csv(PROCESSED_DIR / "mission_report.csv", index=False)`
  - This CSV is the **master fact table** used by downstream analysis / BI.

### 4.3 Mission Debrief Analysis (Cells 3–4)

All questions from the assignment are answered here.

#### 4.3.1 Workhorse Rocket

- Code:
  - `workhorse = master.groupby("name_rocket")["spacex_id_launch"].count().sort_values(ascending=False)`
  - Prints the top 10 rockets by mission count.
- Insight:
  - Shows which rocket configuration has flown the most missions (Falcon 9).

#### 4.3.2 Reliability (Success Rate, Rockets with ≥ 5 Launches)

- Code:
  - Drops launches with unknown `success`: `master.dropna(subset=["success"])`.
  - Groups by `name_rocket`, then:
    - `launches = count(spacex_id_launch)`
    - `success_rate = mean(success)`
  - Filters to `launches >= 5`.
  - Sorts by `success_rate` descending.
- Insight:
  - Provides empirical reliability for frequently flown rockets; avoids skew from rockets with only 1–2 launches.

#### 4.3.3 Launch Cadence per Year

- Code:
  - Converts string timestamp:
    - `master["date_utc"] = pd.to_datetime(master["date_utc"], errors="coerce")`
  - Extracts `year`: `master["year"] = master["date_utc"].dt.year`
  - Counts launches per year:
    - `launches_per_year = master.groupby("year")["spacex_id_launch"].count()`
  - Prints the counts.
  - Plots a bar chart:
    - `launches_per_year.plot(kind="bar")`
    - Saves to `PROCESSED_DIR / "launches_per_year.png"`.
- Insight:
  - Visualizes growth in launch frequency over time; shows how cadence accelerates in recent years.

#### 4.3.4 Geography – Region with Most Launches

- Code:
  - `by_region = master.groupby("region")["spacex_id_launch"].count().sort_values(ascending=False)`
  - Prints top regions.
- Insight:
  - Identifies which physical regions host the majority of SpaceX launches (e.g., Florida vs. California vs. Marshall Islands).

#### 4.3.5 Failure Analysis

- Code:
  - Filters `master[master["success"] == 0]`.
  - Selects columns:
    - `["name_launch", "date_utc", "details", "name_rocket", "region"]`
  - Sorts by `date_utc`.
  - Prints first 20 failed missions.
  - Saves full failure list:
    - `failed.to_csv(PROCESSED_DIR / "failed_missions.csv", index=False)`.
- Insight:
  - Enables qualitative review of failure patterns: early Falcon 1 development flights, later rare Falcon 9 anomalies, launchpad-specific issues, etc.

---

## 5. How to Run Everything

### 5.1 Install Dependencies

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirments.txt
```

### 5.2 Run the ETL

```bash
source .venv/bin/activate
python etl_pipeline.py
```

This will:

- Fetch the latest launches, rockets, and launchpads from the SpaceX API.
- Save raw JSON under `Data/Row/`.
- Create or update `Data/DB/spacex.db` with fully normalized tables.

### 5.3 Run the Analysis Notebook

```bash
source .venv/bin/activate
jupyter notebook notebook/spacex_analysis.ipynb
```

Then, in the UI:

1. Run cells from top to bottom.
2. Check `Data/Procesed/` for the generated:
   - `mission_report.csv`
   - `failed_missions.csv`
   - `launches_per_year.png`

---

## 6. Extending the Project

A few ideas for further exploration:

- **Geospatial maps** – use `folium` to plot launchpads on a real map using their latitude/longitude.
- **Core-level reliability** – extend the schema with booster cores and compute time between flights for each booster.
- **Robustness** – add exponential backoff + retries around `get_json`, and isolate network-layer errors from downstream logic.
- **Incremental loads** – store last loaded launch date and only ingest new launches, rather than reloading the full history each time.

This repo should give you a strong, end-to-end example of how to go from a public REST API to a queryable warehouse and analytical insights using pandas.


