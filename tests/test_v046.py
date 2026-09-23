from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog import load_catalog


def test_hm401m_defaults_to_afr2_and_one_m_skill():
    df = load_catalog().set_index("unit_id")
    assert df.loc["HM401M", "default_equipment"] == "AFR2"
    assert df.loc["HM401M", "typical_als_equipment"] == "AFR2"
    assert df.loc["HM401M", "default_m_skill"] == 1
