from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from db import connect, init_db
from engine import (
    Assignment,
    SimulationState,
    choose_unit_for_requirement,
    load_requirement,
    load_units,
    reusable_requirement_status,
    simulate_plan,
    unit_qualifies,
)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        init_db(self.db_path, reset=True)
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_re433_qualifies_for_e_and_r_but_only_one_slot(self):
        units = load_units(self.conn)
        re433 = next(u for u in units if u.unit_id == "RE433M")
        req_e = load_requirement(self.conn, "E")
        req_r = load_requirement(self.conn, "R")

        self.assertTrue(unit_qualifies(re433, req_e)[0])
        self.assertTrue(unit_qualifies(re433, req_r)[0])

        state = SimulationState(assignments=[Assignment("E", "RE433M")])
        selected, _ = choose_unit_for_requirement(req_r, units, state)
        self.assertNotEqual(selected.unit_id if selected else None, "RE433M")

    def test_bc443_city_not_county(self):
        units = load_units(self.conn)
        bc443 = next(u for u in units if u.unit_id == "BC443")
        self.assertTrue(unit_qualifies(bc443, load_requirement(self.conn, "BC"))[0])
        self.assertTrue(unit_qualifies(bc443, load_requirement(self.conn, "BCCITY"))[0])
        self.assertFalse(unit_qualifies(bc443, load_requirement(self.conn, "BCCNTY"))[0])

    def test_county_bc_not_city(self):
        units = load_units(self.conn)
        bc401 = next(u for u in units if u.unit_id == "BC401")
        self.assertTrue(unit_qualifies(bc401, load_requirement(self.conn, "BC"))[0])
        self.assertTrue(unit_qualifies(bc401, load_requirement(self.conn, "BCCNTY"))[0])
        self.assertFalse(unit_qualifies(bc401, load_requirement(self.conn, "BCCITY"))[0])

    def test_als_skill_counts_rostered_personnel(self):
        units = load_units(self.conn)
        unit_map = {u.unit_id: u for u in units}
        req = load_requirement(self.conn, "ALS_SKILL")

        ok, detail = reusable_requirement_status(req, [unit_map["E421M"], unit_map["M421"]])
        self.assertTrue(ok)
        self.assertIn("available=2", detail)

    def test_prototype_plan_uses_e_and_m_then_satisfies_als_skill(self):
        state = simulate_plan(self.conn, "AFR_ALS_PROTOTYPE")
        self.assertEqual([(a.requirement, a.unit_id) for a in state.assignments],
                         [("E", "E421M"), ("M", "M421")])
        self.assertIn("ALS_SKILL", state.satisfied_requirements)

    def test_m_skill_is_distinct_from_unit_type_m(self):
        units = load_units(self.conn)
        e421 = next(u for u in units if u.unit_id == "E421M")
        m421 = next(u for u in units if u.unit_id == "M421")

        self.assertEqual(e421.unit_type, "E")
        self.assertEqual(e421.skills.get("M"), 1)
        self.assertEqual(m421.unit_type, "M")
        self.assertEqual(m421.skills.get("M"), 1)


if __name__ == "__main__":
    unittest.main()
