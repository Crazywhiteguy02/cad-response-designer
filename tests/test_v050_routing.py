from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routing import (
    load_station_crosswalk,
    parse_lat_lon,
    _parse_table_response,
    format_duration,
)
from engine import ScenarioUnit, SimulationState, choose_for_requirement


def _unit(uid, unit_type="M", distance=None, seconds=None, test_time_minutes=99):
    return ScenarioUnit(
        unit_id=uid,
        unit_type=unit_type,
        beat="421",
        station_id="421",
        attributes=set(),
        equipment={},
        m_skill_count=1,
        test_time_minutes=test_time_minutes,
        routing_mode="osm" if distance is not None else "manual",
        route_distance_miles=distance,
        route_time_seconds=seconds,
    )


def test_station_prefix_examples():
    stations = load_station_crosswalk().set_index("cad_station_id")
    assert stations.loc["401", "jurisdiction"] == "Fairfax County, VA"
    assert stations.loc["101", "jurisdiction"] == "Arlington County, VA"
    assert stations.loc["201", "jurisdiction"] == "Alexandria City, VA"
    assert stations.loc["301", "jurisdiction"] == "Metropolitan Washington Airports Authority"
    assert stations.loc["501", "jurisdiction"] if "501" in stations.index else True
    assert stations.loc["601", "jurisdiction"] == "Loudoun County, VA"
    assert stations.loc["701", "jurisdiction"] == "Montgomery County, MD"
    assert stations.loc["801", "jurisdiction"] == "Prince George's County, MD"


def test_city_fairfax_crosswalk():
    stations = load_station_crosswalk().set_index("cad_station_id")
    assert stations.loc["403", "jurisdiction"] == "Fairfax City, VA"
    assert stations.loc["433", "jurisdiction"] == "Fairfax City, VA"


def test_arlington_station_107_is_inactive():
    stations = load_station_crosswalk().set_index("cad_station_id")
    assert bool(stations.loc["107", "active"]) is False


def test_parse_lat_lon():
    p = parse_lat_lon(38.85, -77.30)
    assert p.lat == 38.85
    assert p.lon == -77.30


def test_osrm_table_parser():
    payload = {
        "code": "Ok",
        "durations": [[300.0], [240.0]],
        "distances": [[8046.72], [4023.36]],
    }
    metrics = _parse_table_response(payload, 2)
    assert round(metrics[0].distance_miles, 2) == 5.00
    assert metrics[1].duration_seconds == 240.0


def test_format_duration():
    assert format_duration(428) == "7:08"


def test_requirement_ordering_uses_travel_time_not_distance():
    # Both qualify for M. Unit B is farther by mileage but faster by modeled travel time.
    a = _unit("M421", distance=3.0, seconds=420.0)
    b = _unit("M426", distance=4.0, seconds=300.0)
    unit, _ = choose_for_requirement("M", [a, b], SimulationState())
    assert unit.unit_id == "M426"


def test_max_time_uses_route_time():
    under_10 = _unit("M421", distance=20.0, seconds=570.0)
    over_10 = _unit("M426", distance=5.0, seconds=630.0)
    unit, _ = choose_for_requirement(
        "M", [under_10, over_10], SimulationState(), max_time_minutes=10.0
    )
    assert unit.unit_id == "M421"


def test_unrouted_osm_unit_is_not_candidate():
    unresolved = ScenarioUnit(
        unit_id="M421",
        unit_type="M",
        beat="421",
        station_id="421",
        attributes=set(),
        equipment={},
        m_skill_count=1,
        test_time_minutes=1.0,
        routing_mode="osm",
        route_distance_miles=None,
        route_time_seconds=None,
    )
    unit, _ = choose_for_requirement("M", [unresolved], SimulationState())
    assert unit is None
