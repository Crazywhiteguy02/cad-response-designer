from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from event_config import load_event_plan_map, resolve_response_plan
from requirements import REQUIREMENTS
from response_plans import (
    load_response_plan_items,
    load_response_plan_meta,
    load_alarm_levels,
    get_response_plan,
    ad_hoc_plan_names,
    next_alarm_for_event,
)
from engine import ScenarioUnit, simulate_response_plan


def make_unit(uid, typ, attrs=(), equipment=(), m=0, distance=5, beat="421", station="421"):
    return ScenarioUnit(
        unit_id=uid,
        unit_type=typ,
        beat=beat,
        station_id=station,
        attributes=set(attrs),
        equipment={x: 1 for x in equipment},
        m_skill_count=m,
        test_time_minutes=float(distance),
    )


def test_raw_cad_import_counts():
    items = load_response_plan_items()
    meta = load_response_plan_meta()
    assert len(items) == 36784
    assert meta["resp_plan_name"].nunique() == 5394
    assert int(meta["is_ad_hoc"].sum()) == 111
    assert len(REQUIREMENTS) == 1014


def test_alpha_is_imported_graph_not_only_hardcoded():
    plan = get_response_plan("ALPHA")
    assert plan.is_ad_hoc is False
    assert plan.items[1].item_type == 1
    assert plan.items[1].alternatives[0].requirement == "M"
    assert plan.items[1].alternatives[0].max_route == 10
    assert plan.items[3].item_type == 2
    assert plan.items[3].alternatives[0].requirement == "M"
    assert plan.items[7].alternatives[0].recommend_mode == "Use Default"


def test_recommend_mode_mapping_from_gui_validation():
    items = load_response_plan_items()
    blood = items[(items["resp_plan_name"] == "BLOODF") & (items["req_name"] == "ALS CHASE CAR")]
    assert not blood.empty
    assert blood.iloc[0]["recommend_mode"] == "1"
    plan = get_response_plan("BLOODF")
    alt = next(a for item in plan.items.values() for a in item.alternatives if a.requirement == "ALS CHASE CAR")
    assert alt.recommend_mode == "Street Network"


def test_event_type_mapping_comes_from_fire_export():
    df = load_event_plan_map()
    assert df["event_type"].nunique() == 110
    for condition in ("1", "2", "3"):
        assert resolve_response_plan("ALPHA", condition, df)["response_plan_id"] == "ALPHA"
    assert resolve_response_plan("EXPLOF", "1", df)["response_plan_id"] == "EXPLOF COND_1"


def test_alarm_table_and_ad_hoc_library():
    alarms = load_alarm_levels()
    assert len(alarms) == 93
    fh = next_alarm_for_event("FHOU", 1, alarms)
    assert fh["alarm_level"] == 2
    assert fh["response_plan"] == "2ND_ALARM_FHOU"
    exp = next_alarm_for_event("EXPLOF", 4, alarms)
    assert exp is None
    assert "FD-APP_1M" in ad_hoc_plan_names()


def test_data_driven_alpha_matches_validated_baseline():
    units = [
        make_unit("M421", "M", attrs=["TRANSPORT", "MEDIC"], m=1, distance=5),
        make_unit("E426", "E", attrs=["ENGINE", "HEAVY"], distance=2),
        make_unit("ALS401", "ALS", attrs=["COUNTY", "CHASE CAR"], m=1, distance=3, beat="431", station="431"),
        make_unit("EMS401", "EMS", attrs=["COUNTY", "BALLISTIC", "CHASE CAR"], distance=6, beat="442", station="442"),
    ]
    state = simulate_response_plan("ALPHA", units)
    assert [(a.requirement, a.unit_id) for a in state.assignments] == [
        ("M", "M421"),
        ("E", "E426"),
        ("ALS CHASE CAR", "ALS401"),
    ]
    assert state.applied_plans[0] == ("Initial", "ALPHA")


def test_app_has_post_dispatch_controls():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Post-dispatch actions" in app
    assert "Add Alarm Level" in app
    assert "Apply Ad Hoc Plan" in app
    assert "simulate_response_plan" in app


def test_ad_hoc_plan_builds_on_existing_incident_state():
    units = [
        make_unit("M421", "M", attrs=["TRANSPORT", "MEDIC"], m=1, distance=2),
        make_unit("M422", "M", attrs=["TRANSPORT", "MEDIC"], m=1, distance=4, beat="422", station="422"),
        make_unit("E426", "E", attrs=["ENGINE", "HEAVY"], distance=3),
        make_unit("ALS401", "ALS", attrs=["COUNTY", "CHASE CAR"], m=1, distance=5, beat="431", station="431"),
    ]
    state = simulate_response_plan("ALPHA", units)
    state = simulate_response_plan("FD-APP_1M", units, state=state, source_kind="Ad Hoc")
    assert state.assignments[-1].unit_id == "M422"
    assert state.assignments[-1].source_kind == "Ad Hoc"
    assert state.assignments[-1].batch_id > state.assignments[0].batch_id
