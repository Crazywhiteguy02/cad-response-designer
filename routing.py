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

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"

USER_AGENT = "CADResponseDesignerPrototype/0.5 (OpenStreetMap routing validation)"

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
    return df


def station_record(station_id: str, stations: pd.DataFrame | None = None) -> dict | None:
    stations = load_station_crosswalk() if stations is None else stations
    match = stations[stations["cad_station_id"] == str(station_id)]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


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


def geocode_address(query: str, timeout: float = 15.0) -> GeoPoint:
    query = (query or "").strip()
    if not query:
        raise RoutingError("No address was supplied for geocoding.")

    _throttle_nominatim()
    response = requests.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise RoutingError(f"OpenStreetMap could not geocode: {query}")

    item = payload[0]
    return GeoPoint(
        lat=float(item["lat"]),
        lon=float(item["lon"]),
        label=str(item.get("display_name") or query),
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


def format_duration(seconds: float | None) -> str:
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return ""
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
