from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scenario_units_from_frame, simulate_alpha


def test_afr_equipment_dropdown_is_loaded_into_unit_equipment():
    frame = pd.DataFrame([{
        "Unit ID": "TT425M",
        "Unit Type": "TT",
        "Beat": "425",
        "Station": "425",
        "Attributes": "TRUCK; HEAVY; BALLISTIC; EXTRICATION; ALS FIRST RESP",
        "AFR Equipment": "AFR2",
        "Other Equipment": "",
        "M Skills": 1,
        "Test Distance": 3.0,
        "Pair Unit": "TT425",
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])
    unit = scenario_units_from_frame(frame)[0]
    assert unit.equipment == {"AFR2": 1}


def test_other_equipment_combines_with_afr_equipment():
    frame = pd.DataFrame([{
        "Unit ID": "TT425M",
        "Unit Type": "TT",
        "Beat": "425",
        "Station": "425",
        "Attributes": "TRUCK; HEAVY; BALLISTIC; EXTRICATION; ALS FIRST RESP",
        "AFR Equipment": "AFR2",
        "Other Equipment": "VENT, WINCH",
        "M Skills": 1,
        "Test Distance": 3.0,
        "Pair Unit": "TT425",
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])
    unit = scenario_units_from_frame(frame)[0]
    assert unit.equipment == {"AFR2": 1, "VENT": 1, "WINCH": 1}


def test_alpha_can_recommend_afr2_unit_from_dropdown():
    frame = pd.DataFrame([
        {
            "Unit ID": "M421", "Unit Type": "M", "Beat": "421", "Station": "421",
            "Attributes": "TRANSPORT; MEDIC", "AFR Equipment": "",
            "Other Equipment": "", "M Skills": 1, "Test Distance": 5.0,
            "Pair Unit": "", "Typical ALS Equipment": ""
        },
        {
            "Unit ID": "TT425M", "Unit Type": "TT", "Beat": "425", "Station": "425",
            "Attributes": "TRUCK; HEAVY; BALLISTIC; EXTRICATION; ALS FIRST RESP",
            "AFR Equipment": "AFR2", "Other Equipment": "",
            "M Skills": 1, "Test Distance": 2.0,
            "Pair Unit": "TT425", "Typical ALS Equipment": "AFR1 or AFR2"
        },
    ])
    units = scenario_units_from_frame(frame)
    state = simulate_alpha(units)
    got = [(a.requirement, a.unit_id) for a in state.assignments]
    assert ("AFR2", "TT425M") in got
