from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scenario_units_from_frame


def test_m_skill_dropdown_values_zero_to_four_are_supported():
    rows = []
    for n in range(5):
        rows.append({
            "Unit ID": f"TEST{n}",
            "Unit Type": "E",
            "Beat": "400",
            "Station": "400",
            "Attributes": "ENGINE; HEAVY",
            "Equipment": [],
            "M Skills": n,
            "Test Distance": 1.0,
            "Typical ALS Equipment": "",
        })

    units = scenario_units_from_frame(pd.DataFrame(rows))
    assert [u.m_skill_count for u in units] == [0, 1, 2, 3, 4]
