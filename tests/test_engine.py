from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db import connect, init_db
from engine import simulate_plan


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


if __name__ == "__main__":
    unittest.main()
