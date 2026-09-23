from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog import load_catalog
from requirements import REQUIREMENTS
from engine import (
    ScenarioUnit,
    qualifies,
    simulate_alpha,
    scenario_units_from_frame,
    pair_conflicts,
)


def make_unit(uid, typ, attrs=(), equipment=(), m=0, distance=5, beat="421", station="421"):
    return ScenarioUnit(
        unit_id=uid,
        unit_type=typ,
        beat=beat,
        station_id=station,
        attributes=set(attrs),
        equipment={x: 1 for x in equipment},
        m_skill_count=m,
        test_distance=float(distance),
    )


def test_catalog_import_and_current_units():
    df = load_catalog()
    assert len(df) == 5757
    lookup = df.set_index("unit_id")
    assert lookup.loc["E421", "unit_type"] == "E"
    assert lookup.loc["E421M", "beat"] == "421"
    assert lookup.loc["ALS401", "unit_type"] == "ALS"
    assert lookup.loc["ALS401", "beat"] == "431"
    assert lookup.loc["HM401", "unit_type"] == "HM"
    assert lookup.loc["HM401", "beat"] == "440"
    assert lookup.loc["HM401M", "station_id"] == "440"


def test_m_suffix_attribute_model():
    df = load_catalog().set_index("unit_id")
    assert "ALS FIRST RESP" not in df.loc["E421", "default_attributes"]
    assert "ALS FIRST RESP" in df.loc["E421M", "default_attributes"]
    assert "ALS FIRST RESP" in df.loc["TT425M", "default_attributes"]
    assert "ALS FIRST RESP" in df.loc["RE433M", "default_attributes"]
    assert "ALS FIRST RESP" not in df.loc["HM401", "default_attributes"]
    assert "ALS FIRST RESP" in df.loc["HM401M", "default_attributes"]
    assert df.loc["E421", "pair_unit_id"] == "E421M"
    assert df.loc["E421M", "pair_unit_id"] == "E421"


def test_current_chase_car_requirements():
    als = make_unit("ALS401", "ALS", attrs=["COUNTY", "CHASE CAR"])
    ems = make_unit("EMS401", "EMS", attrs=["COUNTY", "BALLISTIC", "CHASE CAR"])
    medic = make_unit("M421", "M", attrs=["TRANSPORT", "MEDIC"], m=1)

    assert qualifies(als, REQUIREMENTS["CHASE CAR"])[0]
    assert qualifies(ems, REQUIREMENTS["CHASE CAR"])[0]
    assert not qualifies(medic, REQUIREMENTS["CHASE CAR"])[0]

    assert qualifies(als, REQUIREMENTS["ALS CHASE CAR"])[0]
    assert not qualifies(ems, REQUIREMENTS["ALS CHASE CAR"])[0]

    assert qualifies(ems, REQUIREMENTS["EMS COUNTY"])[0]
    assert not qualifies(als, REQUIREMENTS["EMS COUNTY"])[0]


def test_hm401_requirements_are_exact_unit_ids():
    hm = make_unit("HM401", "HM", attrs=["RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"])
    hmm = make_unit("HM401M", "HM", attrs=["RESCUE", "HAZMAT", "HEAVY", "EXTRICATION", "ALS FIRST RESP"], m=1)
    other = make_unit("HM440", "HM", attrs=["HEAVY"])
    assert qualifies(hm, REQUIREMENTS["HM401"])[0]
    assert not qualifies(hmm, REQUIREMENTS["HM401"])[0]
    assert qualifies(hmm, REQUIREMENTS["HM401M"])[0]
    assert not qualifies(other, REQUIREMENTS["HM401"])[0]


def test_alpha_current_logic_with_als_chase_car_branch():
    # M421 is within 10; no chase car is initially selected. E426 is nearest
    # resource in the CHASE CAR=NO group. ALS401 then supplies the second M skill.
    units = [
        make_unit("M421", "M", attrs=["TRANSPORT", "MEDIC"], m=1, distance=5),
        make_unit("E426", "E", attrs=["ENGINE", "HEAVY"], m=0, distance=2),
        make_unit("ALS401", "ALS", attrs=["COUNTY", "CHASE CAR"], m=1, distance=3, beat="431", station="431"),
        make_unit("EMS401", "EMS", attrs=["COUNTY", "BALLISTIC", "CHASE CAR"], m=0, distance=6, beat="442", station="442"),
    ]
    state = simulate_alpha(units)
    got = [(a.requirement, a.unit_id) for a in state.assignments]
    assert got == [("M", "M421"), ("E", "E426"), ("ALS CHASE CAR", "ALS401")]
    trace = "\n".join(state.trace)
    assert "CONDITION M: YES" in trace
    assert "CONDITION CHASE CAR: NO" in trace
    assert "CONDITION ALS_SKILL: NO" in trace
    assert "CONDITION SUPPRESSION UNIT: YES" in trace


def test_alpha_initial_max_distance_fallback():
    # M is outside max distance, so step 1 fails. ALS401 wins fallback by distance.
    # M Recommended? remains NO; the M/A group then selects the closer A421.
    units = [
        make_unit("M421", "M", attrs=["TRANSPORT", "MEDIC"], m=1, distance=15),
        make_unit("ALS401", "ALS", attrs=["COUNTY", "CHASE CAR"], m=1, distance=4, beat="431", station="431"),
        make_unit("A421", "A", attrs=["COUNTY", "TRANSPORT", "AMBULANCE"], distance=8),
        make_unit("E426", "E", attrs=["ENGINE", "HEAVY"], distance=3),
    ]
    state = simulate_alpha(units)
    got = [(a.requirement, a.unit_id) for a in state.assignments]
    assert got[0] == ("ALS CHASE CAR", "ALS401")
    assert got[1] == ("A", "A421")
    trace = "\n".join(state.trace)
    assert "M: no eligible unconsumed unit within max distance 10" in trace
    assert "CONDITION M: NO" in trace
    assert "CONDITION CHASE CAR: YES" in trace


def test_pair_conflict_warning_logic():
    frame = pd.DataFrame([
        {"Unit ID": "E421", "Pair Unit": "E421M"},
        {"Unit ID": "E421M", "Pair Unit": "E421"},
        {"Unit ID": "M421", "Pair Unit": ""},
    ])
    assert pair_conflicts(frame) == [("E421", "E421M")]
