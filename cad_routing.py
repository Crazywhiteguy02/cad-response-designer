from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import time
import threading
from typing import Iterable

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent / "data"
STATION_FILE = DATA_DIR / "station_crosswalk.csv"
GEOCODE_SEED_FILE = DATA_DIR / "geocode_seeds.csv"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"

USER_AGENT = "CADence/0.9.1 (public-safety response-planning simulator)"

_METERS_PER_MILE = 1609.344
_last_nominatim_request = 0.0
_nominatim_lock = threading.Lock()


class RoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float
    label: str = ""


@dataclass(frozen=True)
class RouteMetric:
    distance_miles: float
    duration_seconds: float


def load_station_crosswalk() -> pd.DataFrame:
    df = pd.read_csv(STATION_FILE, dtype=str).fillna("")
    df["cad_station_id"] = df["cad_station_id"].astype(str)
    df["active"] = df["active"].str.upper().eq("TRUE")
    for col in ("latitude", "longitude"):
        if col not in df.columns:
            df[col] = ""
    return df



def apply_station_active_overrides(
    stations: pd.DataFrame,
    overrides: dict[str, bool] | None = None,
) -> pd.DataFrame:
    """Return station data with session/scenario active overrides applied."""
    effective = stations.copy()
    for sid, enabled in (overrides or {}).items():
        mask = effective["cad_station_id"].astype(str) == str(sid)
        effective.loc[mask, "active"] = bool(enabled)
    return effective

def station_record(station_id: str, stations: pd.DataFrame | None = None) -> dict | None:
    stations = load_station_crosswalk() if stations is None else stations
    match = stations[stations["cad_station_id"] == str(station_id)]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def _normalize_geocode_query(query: str) -> str:
    text = (query or "").strip().lower()
    text = text.replace(".", " ").replace(",", " ")
    replacements = {
        " parkway": " pkwy",
        " road": " rd",
        " street": " st",
        " avenue": " ave",
        " boulevard": " blvd",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _load_geocode_seeds() -> dict[str, GeoPoint]:
    if not GEOCODE_SEED_FILE.exists():
        return {}
    frame = pd.read_csv(GEOCODE_SEED_FILE, dtype=str).fillna("")
    seeds: dict[str, GeoPoint] = {}
    for _, row in frame.iterrows():
        try:
            key = _normalize_geocode_query(str(row.get("query", "")))
            if not key:
                continue
            seeds[key] = GeoPoint(
                lat=float(row["latitude"]),
                lon=float(row["longitude"]),
                label=str(row.get("label", "") or row.get("query", "")),
            )
        except (TypeError, ValueError, KeyError):
            continue
    return seeds


def station_point_from_record(record: dict | None) -> GeoPoint | None:
    """Return a stored station coordinate without calling an external geocoder."""
    if not record:
        return None
    lat = str(record.get("latitude", "") or "").strip()
    lon = str(record.get("longitude", "") or "").strip()
    if not lat or not lon:
        return None
    try:
        return GeoPoint(
            lat=float(lat),
            lon=float(lon),
            label=str(
                record.get("station_name")
                or record.get("address")
                or record.get("cad_station_id")
                or ""
            ),
        )
    except (TypeError, ValueError):
        return None


def parse_lat_lon(lat, lon) -> GeoPoint:
    lat = float(lat)
    lon = float(lon)
    if not (-90 <= lat <= 90):
        raise ValueError("Latitude must be between -90 and 90.")
    if not (-180 <= lon <= 180):
        raise ValueError("Longitude must be between -180 and 180.")
    return GeoPoint(lat=lat, lon=lon, label=f"{lat:.6f}, {lon:.6f}")


def _throttle_nominatim() -> None:
    global _last_nominatim_request
    with _nominatim_lock:
        elapsed = time.monotonic() - _last_nominatim_request
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        _last_nominatim_request = time.monotonic()


def _geocode_census(query: str, timeout: float) -> GeoPoint | None:
    """Use the U.S. Census geocoder first for U.S. street addresses."""
    try:
        response = requests.get(
            CENSUS_GEOCODER_URL,
            params={
                "address": query,
                "benchmark": "Public_AR_Current",
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
        matches = (
            payload.get("result", {})
            .get("addressMatches", [])
        )
        if not matches:
            return None
        item = matches[0]
        coords = item.get("coordinates") or {}
        lat = coords.get("y")
        lon = coords.get("x")
        if lat is None or lon is None:
            return None
        return GeoPoint(
            lat=float(lat),
            lon=float(lon),
            label=str(item.get("matchedAddress") or query),
        )
    except Exception:
        # Census is a preferred first lookup, not a single point of failure.
        return None


def _retry_after_seconds(response, attempt: int) -> float:
    header = None
    try:
        header = response.headers.get("Retry-After")
    except Exception:
        header = None

    if header:
        try:
            return max(1.1, min(float(header), 12.0))
        except (TypeError, ValueError):
            pass

    # Gentle exponential backoff while keeping the UI responsive.
    return min(1.5 * (2 ** attempt), 8.0)


def _geocode_nominatim(query: str, timeout: float) -> GeoPoint | None:
    """Nominatim fallback with required throttling and explicit 429 handling."""
    for attempt in range(3):
        _throttle_nominatim()
        try:
            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "us",
                },
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.8",
                },
                timeout=timeout,
            )
        except requests.RequestException:
            if attempt < 2:
                time.sleep(_retry_after_seconds(None, attempt))
                continue
            return None

        if response.status_code == 429:
            if attempt < 2:
                time.sleep(_retry_after_seconds(response, attempt))
                continue
            return None

        if response.status_code != 200:
            return None

        try:
            payload = response.json()
        except Exception:
            return None

        if not payload:
            return None

        item = payload[0]
        try:
            return GeoPoint(
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                label=str(item.get("display_name") or query),
            )
        except (KeyError, TypeError, ValueError):
            return None

    return None


def geocode_address(query: str, timeout: float = 15.0) -> GeoPoint:
    query = (query or "").strip()
    if not query:
        raise RoutingError("No address was supplied for geocoding.")

    # Static seeds avoid external calls for known frequently used locations.
    seeded = _load_geocode_seeds().get(_normalize_geocode_query(query))
    if seeded is not None:
        return seeded

    point = _geocode_census(query, timeout)
    if point is not None:
        return point

    point = _geocode_nominatim(query, timeout)
    if point is not None:
        return point

    raise RoutingError(
        "Address lookup is temporarily unavailable or the address could not be found. "
        "Try the full street address, try again shortly, or use Coordinates."
    )


def _coord_string(points: Iterable[GeoPoint]) -> str:
    return ";".join(f"{p.lon:.7f},{p.lat:.7f}" for p in points)


def _parse_table_response(payload: dict, source_count: int) -> list[RouteMetric | None]:
    if payload.get("code") != "Ok":
        raise RoutingError(f"OSRM table error: {payload.get('code', 'unknown')}")
    durations = payload.get("durations")
    distances = payload.get("distances")
    if not durations or not distances:
        raise RoutingError("OSRM table did not return both durations and distances.")

    results: list[RouteMetric | None] = []
    for i in range(source_count):
        duration = durations[i][0]
        distance = distances[i][0]
        if duration is None or distance is None:
            results.append(None)
        else:
            results.append(
                RouteMetric(
                    distance_miles=float(distance) / _METERS_PER_MILE,
                    duration_seconds=float(duration),
                )
            )
    return results


def route_table(
    origins: list[GeoPoint],
    destination: GeoPoint,
    timeout: float = 25.0,
) -> list[RouteMetric | None]:
    if not origins:
        return []

    points = origins + [destination]
    destination_index = len(points) - 1
    sources = ";".join(str(i) for i in range(len(origins)))

    response = requests.get(
        f"{OSRM_TABLE_URL}/{_coord_string(points)}",
        params={
            "sources": sources,
            "destinations": str(destination_index),
            "annotations": "duration,distance",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )

    # Some OSRM deployments do not expose distance matrices. If so, fall back
    # to individual route requests so the prototype still gets both metrics.
    try:
        response.raise_for_status()
        return _parse_table_response(response.json(), len(origins))
    except Exception:
        return [route_pair(origin, destination, timeout=timeout) for origin in origins]


def route_pair(
    origin: GeoPoint,
    destination: GeoPoint,
    timeout: float = 25.0,
) -> RouteMetric | None:
    response = requests.get(
        f"{OSRM_ROUTE_URL}/{_coord_string([origin, destination])}",
        params={"overview": "false", "steps": "false"},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return None
    route = payload["routes"][0]
    return RouteMetric(
        distance_miles=float(route["distance"]) / _METERS_PER_MILE,
        duration_seconds=float(route["duration"]),
    )



def _parse_route_geometry_response(payload: dict) -> dict | None:
    """Parse one OSRM route with GeoJSON geometry."""
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return None

    route = payload["routes"][0]
    geometry = route.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        return None

    return {
        "path": [[float(lon), float(lat)] for lon, lat in coordinates],
        "distance_miles": float(route["distance"]) / _METERS_PER_MILE,
        "duration_seconds": float(route["duration"]),
    }


def route_geometry(
    origin: GeoPoint,
    destination: GeoPoint,
    timeout: float = 25.0,
) -> dict | None:
    """Return the actual OSRM route polyline as GeoJSON coordinates."""
    response = requests.get(
        f"{OSRM_ROUTE_URL}/{_coord_string([origin, destination])}",
        params={
            "overview": "full",
            "steps": "false",
            "geometries": "geojson",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return _parse_route_geometry_response(response.json())


def filter_route_rows_for_map(
    route_rows: list[dict],
    dispatched_unit_ids: list[str] | set[str] | tuple[str, ...],
    *,
    show_all: bool = False,
    additional_unit_ids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """Filter station-route rows for map display.

    Default behavior shows only stations containing dispatched units.
    Additional in-service units may be overlaid, or show_all may be used
    deliberately for full-system troubleshooting.

    If multiple in-service units share a station, the route is drawn once and
    the label contains only the units currently visible under the filter.
    """
    dispatched = {str(x) for x in dispatched_unit_ids}
    additional = {str(x) for x in (additional_unit_ids or [])}
    visible = dispatched | additional

    filtered: list[dict] = []
    for original in route_rows:
        row = dict(original)
        unit_ids = row.get("unit_ids", [])

        if isinstance(unit_ids, str):
            unit_ids = [x.strip() for x in unit_ids.split(",") if x.strip()]
        else:
            unit_ids = [str(x) for x in unit_ids]

        if show_all:
            visible_here = unit_ids
        else:
            visible_here = [uid for uid in unit_ids if uid in visible]

        if not visible_here:
            continue

        row["visible_unit_ids"] = visible_here
        row["units"] = ", ".join(visible_here)
        row["label"] = f"Station {row.get('station', '')} | {', '.join(visible_here)}"
        filtered.append(row)

    return filtered

def format_duration(seconds: float | None) -> str:
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return ""
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
