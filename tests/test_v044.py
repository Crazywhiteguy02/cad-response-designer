from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scenario_units_from_frame


def test_multiselect_attributes_are_loaded_as_set():
    frame = pd.DataFrame([{
        "Unit ID": "E421M",
        "Unit Type": "E",
        "Beat": "421",
        "Station": "421",
        "Attributes": ["ENGINE", "HEAVY", "ALS FIRST RESP"],
        "Equipment": ["AFR1"],
        "M Skills": 1,
        "Test Distance": 2.0,
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])

    unit = scenario_units_from_frame(frame)[0]
    assert unit.attributes == {"ENGINE", "HEAVY", "ALS FIRST RESP"}


def test_single_station_and_beat_values_are_preserved():
    frame = pd.DataFrame([{
        "Unit ID": "E421M",
        "Unit Type": "E",
        "Beat": "426",
        "Station": "426",
        "Attributes": ["ENGINE", "HEAVY", "ALS FIRST RESP"],
        "Equipment": ["AFR1"],
        "M Skills": 1,
        "Test Distance": 2.0,
        "Typical ALS Equipment": "AFR1 or AFR2",
    }])

    unit = scenario_units_from_frame(frame)[0]
    assert unit.beat == "426"
    assert unit.station_id == "426"
