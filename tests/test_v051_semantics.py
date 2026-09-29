from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import (
    ScenarioUnit,
    SimulationState,
    Assignment,
    choose_for_requirement,
    assignments_in_dispatch_order,
)


def _unit(uid, minutes, miles=20.0):
    return ScenarioUnit(
        unit_id=uid,
        unit_type="M",
        beat="421",
        station_id="421",
        attributes=set(),
        equipment={},
        m_skill_count=1,
        test_time_minutes=99.0,
        routing_mode="osm",
        route_distance_miles=miles,
        route_time_seconds=minutes * 60.0,
    )


def test_max_10_uses_minutes_not_miles():
    # 20 road miles is permitted because the modeled travel time is under 10 minutes.
    fast_far = _unit("M421", minutes=9.5, miles=20.0)
    unit, _ = choose_for_requirement(
        "M", [fast_far], SimulationState(), max_time_minutes=10.0
    )
    assert unit is not None
    assert unit.unit_id == "M421"


def test_over_10_minutes_fails_even_if_under_10_miles():
    slow_close = _unit("M421", minutes=10.5, miles=5.0)
    unit, _ = choose_for_requirement(
        "M", [slow_close], SimulationState(), max_time_minutes=10.0
    )
    assert unit is None


def test_display_order_not_eta_order():
    state = SimulationState(assignments=[
        Assignment(step=1, requirement="M", unit_id="M421", sequence=1, display_order=None),
        Assignment(step=7, requirement="E", unit_id="E426", sequence=2, display_order=1),
        Assignment(step=9, requirement="EMS", unit_id="EMS401", sequence=3, display_order=None),
    ])
    ordered = assignments_in_dispatch_order(state)
    assert [a.unit_id for a in ordered] == ["E426", "M421", "EMS401"]
