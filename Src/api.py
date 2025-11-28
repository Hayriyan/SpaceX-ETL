from typing import Any, Dict, List, Set

import requests

BASE_URL = "https://api.spacexdata.com/v4"


def get_json(endpoint: str) -> Any:
    """GET helper with basic error handling."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise SystemExit(f"Error fetching {url}: {exc}") from exc


def extract_all_launches() -> List[Dict[str, Any]]:
    launches = get_json("launches")
    if not isinstance(launches, list):
        raise ValueError("Unexpected launches payload")
    return launches


def extract_unique_ids(launches: List[Dict[str, Any]]) -> tuple[Set[str], Set[str]]:
    rocket_ids: Set[str] = set()
    launchpad_ids: Set[str] = set()
    for launch in launches:
        rid = launch.get("rocket")
        pid = launch.get("launchpad")
        if rid:
            rocket_ids.add(rid)
        if pid:
            launchpad_ids.add(pid)
    return rocket_ids, launchpad_ids


def fetch_rockets(unique_rocket_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    rockets: Dict[str, Dict[str, Any]] = {}
    for rid in unique_rocket_ids:
        rockets[rid] = get_json(f"rockets/{rid}")
    return rockets


def fetch_launchpads(unique_launchpad_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    launchpads: Dict[str, Dict[str, Any]] = {}
    for pid in unique_launchpad_ids:
        launchpads[pid] = get_json(f"launchpads/{pid}")
    return launchpads


