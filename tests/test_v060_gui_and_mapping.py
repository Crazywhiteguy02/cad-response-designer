from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from event_config import (
    load_event_plan_map,
    operational_conditions,
    event_types_for_condition,
    resolve_response_plan,
    response_plan_changes_by_condition,
)


def test_three_operational_conditions_exist():
    df = load_event_plan_map()
    conditions = operational_conditions(df)
    assert [x["operational_condition"] for x in conditions] == ["1", "2", "3"]
    assert [x["condition_name"] for x in conditions] == [
        "Normal Operations",
        "High Call Volume",
        ">50% Unit Utilization",
    ]


def test_alpha_event_description():
    df = load_event_plan_map()
    events = event_types_for_condition("1", df)
    alpha = next(x for x in events if x["event_type"] == "ALPHA")
    assert alpha["description"] == "EMS LEVEL 1"


def test_alpha_maps_to_same_plan_in_all_conditions():
    df = load_event_plan_map()
    for condition in ["1", "2", "3"]:
        mapping = resolve_response_plan("ALPHA", condition, df)
        assert mapping["response_plan_id"] == "ALPHA"
    assert response_plan_changes_by_condition("ALPHA", df) is False


def test_gui_uses_event_type_before_response_plan():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Operational Condition"' in app
    assert '"Event Type"' in app
    assert "resolve_response_plan" in app
    assert "resolve_response_plan" in app


def test_gui_manual_mode_is_named_test_time_not_distance():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Manual Test Time"' in app
    assert '["OpenStreetMap / OSRM", "Manual Test Distance"]' not in app


def test_gui_preserves_dispatch_order_language():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Initial response plus any additional alarm or Ad Hoc plans" in app
    assert "assignments_in_dispatch_order" in app
