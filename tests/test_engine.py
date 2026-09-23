from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db import connect, init_db
from engine import load_requirement, load_units, simulate_plan


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        init_db(self.db_path, reset=True)
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def set_available(self, unit_ids):
        self.conn.execute("UPDATE units SET available=0")
        self.conn.executemany(
            "UPDATE units SET available=1 WHERE unit_id=?",
            [(u,) for u in unit_ids],
        )
        self.conn.commit()

    def test_reported_scenario_adds_afr2_resource(self):
        self.set_available([
            "A421", "BC401", "BC443", "E426", "E435", "EMS401", "M421", "TT425M"
        ])
        state = simulate_plan(self.conn, "AFR_ALS_2022")
        got = [(a.requirement, a.unit_id) for a in state.assignments]
        self.assertEqual(got, [("E", "E426"), ("M", "M421"), ("AFR2", "TT425M")])
        trace = "\n".join(state.trace)
        self.assertIn("CONDITION ALS_SKILL: NO", trace)
        self.assertIn("GROUP selected TT425M via AFR2", trace)
        self.assertIn("CONDITION SUPPRESSION UNIT: YES", trace)

    def test_ems_is_fallback_group_alternative(self):
        self.set_available(["E426", "M421", "EMS401"])
        state = simulate_plan(self.conn, "AFR_ALS_2022")
        got = [(a.requirement, a.unit_id) for a in state.assignments]
        self.assertEqual(got, [("E", "E426"), ("M", "M421"), ("EMS", "EMS401")])

    def test_m_suffix_als_first_resp_attribute_rule(self):
        units = {u.unit_id: u for u in load_units(self.conn)}
        self.assertNotIn("ALS FIRST RESP", units["E426"].attributes)
        self.assertNotIn("ALS FIRST RESP", units["E435"].attributes)
        for unit_id in ["E421M", "RE433M", "R421M", "T421M", "TL440M", "TT425M"]:
            self.assertIn("ALS FIRST RESP", units[unit_id].attributes)

    def test_current_hazmat_profiles(self):
        units = {u.unit_id: u for u in load_units(self.conn)}
        self.assertEqual(units["HM401"].unit_type, "HM")
        self.assertEqual(units["HM401"].station, "440")
        self.assertEqual(units["HM401"].beat, "440")
        self.assertEqual(
            units["HM401"].attributes,
            {"RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"},
        )
        self.assertEqual(
            units["HM401M"].attributes,
            {"ALS FIRST RESP", "RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"},
        )
        self.assertEqual(units["HM401M"].skills.get("M", 0), 0)

    def test_historical_hm440_not_rewritten_to_hm401(self):
        self.assertEqual(load_requirement(self.conn, "HM440").definition_status, "UNRESOLVED")
        self.assertEqual(load_requirement(self.conn, "HM440M").definition_status, "UNRESOLVED")



if __name__ == "__main__":
    unittest.main()
