from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scenario_units_from_frame, pair_conflicts


def test_multiselect_equipment_supports_multiple_codes():
    frame = pd.DataFrame([{
        "Unit ID": "TT425M",
        "Unit Type": "TT",
        "Beat": "425",
        "Station": "425",
        "Attributes": "TRUCK; HEAVY; BALLISTIC; EXTRICATION; ALS FIRST RESP",
        "Equipment": ["AFR2", "VENT", "WINCH"],
        "M Skills": 1,
        "Test Distance": 3.0,
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])

    unit = scenario_units_from_frame(frame)[0]
    assert unit.equipment == {"AFR2": 1, "VENT": 1, "WINCH": 1}


def test_multiselect_equipment_supports_both_afr_codes_for_testing():
    frame = pd.DataFrame([{
        "Unit ID": "E421M",
        "Unit Type": "E",
        "Beat": "421",
        "Station": "421",
        "Attributes": "ENGINE; HEAVY; ALS FIRST RESP",
        "Equipment": ["AFR1", "AFR2"],
        "M Skills": 1,
        "Test Distance": 2.0,
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])

    unit = scenario_units_from_frame(frame)[0]
    assert unit.equipment == {"AFR1": 1, "AFR2": 1}


def test_pair_conflicts_no_longer_needs_pair_unit_column():
    frame = pd.DataFrame([
        {"Unit ID": "E421"},
        {"Unit ID": "E421M"},
        {"Unit ID": "M421"},
    ])
    assert pair_conflicts(frame) == [("E421", "E421M")]


def test_b_suffix_pair_detection():
    frame = pd.DataFrame([
        {"Unit ID": "E421B"},
        {"Unit ID": "E421BM"},
    ])
    assert pair_conflicts(frame) == [("E421B", "E421BM")]
