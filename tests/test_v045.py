from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog import load_catalog


def test_engine_m_suffix_defaults():
    df = load_catalog().set_index("unit_id")
    for uid in ["E421M", "RE433M"]:
        assert df.loc[uid, "default_equipment"] == "AFR1"
        assert df.loc[uid, "default_m_skill"] == 1


def test_truck_tower_tiller_rescue_m_suffix_defaults():
    df = load_catalog().set_index("unit_id")
    for uid in ["T425M", "TL440M", "TT425M", "R421M"]:
        if uid in df.index:
            assert df.loc[uid, "default_equipment"] == "AFR2"
            assert df.loc[uid, "default_m_skill"] == 1


def test_hm440m_defaults():
    df = load_catalog().set_index("unit_id")
    assert df.loc["HM440M", "default_equipment"] == "AFR2"
    assert df.loc["HM440M", "default_m_skill"] == 1


def test_current_als_staffing_defaults():
    df = load_catalog().set_index("unit_id")
    for uid in ["ALS401", "ALS402", "ALS403", "ALS404"]:
        assert df.loc[uid, "default_m_skill"] == 1


def test_current_ems_staffing_defaults():
    df = load_catalog().set_index("unit_id")
    for uid in ["EMS401", "EMS402", "EMS403"]:
        assert df.loc[uid, "default_m_skill"] == 1


def test_hm401m_defaults():
    df = load_catalog().set_index("unit_id")
    assert df.loc["HM401M", "default_m_skill"] == 1
    assert df.loc["HM401M", "default_equipment"] == "AFR2"
