from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("cad.db")


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def init_db(db_path: Path | str = DB_PATH, reset: bool = False) -> None:
    db_path = Path(db_path)
    if reset and db_path.exists():
        db_path.unlink()

    conn = connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS units (
            unit_id TEXT PRIMARY KEY,
            unit_type TEXT NOT NULL,
            agency TEXT NOT NULL DEFAULT 'FIRE',
            station TEXT,
            beat TEXT,
            recommendable INTEGER NOT NULL DEFAULT 1,
            available INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 999,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS unit_attributes (
            unit_id TEXT NOT NULL,
            attribute TEXT NOT NULL,
            PRIMARY KEY (unit_id, attribute)
        );
        CREATE TABLE IF NOT EXISTS unit_equipment (
            unit_id TEXT NOT NULL,
            equipment_code TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (unit_id, equipment_code)
        );
        CREATE TABLE IF NOT EXISTS personnel (employee_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS personnel_skills (
            employee_id TEXT NOT NULL,
            skill_code TEXT NOT NULL,
            PRIMARY KEY (employee_id, skill_code)
        );
        CREATE TABLE IF NOT EXISTS roster (
            employee_id TEXT PRIMARY KEY,
            unit_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requirements (
            name TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_type TEXT,
            attributes_json TEXT NOT NULL DEFAULT '[]',
            attribute_mode TEXT NOT NULL DEFAULT 'ALL',
            equipment_json TEXT NOT NULL DEFAULT '[]',
            skills_json TEXT NOT NULL DEFAULT '[]',
            beat_option TEXT NOT NULL DEFAULT 'ALL',
            allow_existing_units INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS plans (
            plan_name TEXT PRIMARY KEY,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS plan_steps (
            plan_name TEXT NOT NULL,
            step_no INTEGER NOT NULL,
            step_kind TEXT NOT NULL,
            requirement_name TEXT,
            condition_requirement TEXT,
            on_yes_step INTEGER,
            on_no_step INTEGER,
            label TEXT,
            PRIMARY KEY (plan_name, step_no)
        );
        CREATE TABLE IF NOT EXISTS plan_group_members (
            plan_name TEXT NOT NULL,
            step_no INTEGER NOT NULL,
            member_order INTEGER NOT NULL,
            requirement_name TEXT NOT NULL,
            PRIMARY KEY (plan_name, step_no, member_order)
        );
        """
    )
    if not _has_column(conn, "requirements", "definition_status"):
        conn.execute(
            "ALTER TABLE requirements ADD COLUMN definition_status TEXT NOT NULL DEFAULT 'DEFINED'"
        )
    conn.commit()

    if cur.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 0:
        seed_base(conn)

    ensure_v03_data(conn)
    conn.close()


def _insert_unit(conn, unit_id, unit_type, attrs, equipment=(), station=None, beat=None,
                 priority=999, recommendable=True, notes=None):
    conn.execute(
        """INSERT INTO units
           (unit_id, unit_type, agency, station, beat, recommendable, available, priority, notes)
           VALUES (?, ?, 'FIRE', ?, ?, ?, 1, ?, ?)""",
        (unit_id, unit_type, station, beat, int(recommendable), priority, notes),
    )
    conn.executemany(
        "INSERT INTO unit_attributes(unit_id, attribute) VALUES (?, ?)",
        [(unit_id, a) for a in attrs],
    )
    conn.executemany(
        "INSERT INTO unit_equipment(unit_id, equipment_code, quantity) VALUES (?, ?, ?)",
        [(unit_id, code, qty) for code, qty in equipment],
    )


def _insert_person(conn, employee_id, skills, unit_id):
    conn.execute("INSERT INTO personnel(employee_id) VALUES (?)", (employee_id,))
    conn.executemany(
        "INSERT INTO personnel_skills(employee_id, skill_code) VALUES (?, ?)",
        [(employee_id, s) for s in skills],
    )
    conn.execute("INSERT INTO roster(employee_id, unit_id) VALUES (?, ?)", (employee_id, unit_id))


def _insert_requirement(conn, name, quantity=1, unit_type=None, attributes=(),
                        attribute_mode="ALL", equipment=(), skills=(),
                        beat_option="ALL", allow_existing_units=False,
                        notes=None, definition_status="DEFINED"):
    conn.execute(
        """INSERT OR REPLACE INTO requirements
           (name, quantity, unit_type, attributes_json, attribute_mode,
            equipment_json, skills_json, beat_option, allow_existing_units, notes, definition_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name, quantity, unit_type, json.dumps(list(attributes)), attribute_mode,
            json.dumps(list(equipment)), json.dumps(list(skills)), beat_option,
            int(allow_existing_units), notes, definition_status,
        ),
    )


def seed_base(conn):
    _insert_unit(conn, "E421M", "E", ["ENGINE", "ALS FIRST RESP", "HEAVY"],
                 [("AFR1", 1)], "421", "421", 10)
    _insert_unit(conn, "E426", "E", ["ENGINE", "HEAVY"], [], "426", "426", 20)
    _insert_unit(conn, "E435", "E", ["ENGINE", "HEAVY"], [], "435", "435", 30)
    _insert_unit(conn, "RE433M", "E", ["RESCUE", "ENGINE", "HEAVY", "BALLISTIC", "EXTRICATION", "ALS FIRST RESP"],
                 [("AFR2", 1)], "433", "433", 15)
    _insert_unit(conn, "R421M", "R", ["RESCUE", "HAZMAT", "TROT", "HEAVY", "BALLISTIC", "EXTRICATION", "ALS FIRST RESP"],
                 [("AFR1", 1)], "421", "421", 12)
    _insert_unit(conn, "T421M", "T", ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION", "ALS FIRST RESP"],
                 [("AFR2", 1)], "421", "421", 14)
    _insert_unit(conn, "TL440M", "TL", ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION", "ALS FIRST RESP"],
                 [("AFR1", 1)], "440", "440", 40)
    _insert_unit(conn, "TT425M", "TT", ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION", "ALS FIRST RESP"],
                 [("AFR2", 1)], "425", "425", 35)
    _insert_unit(conn, "A421", "A", ["COUNTY", "TRANSPORT", "AMBULANCE"], [], "421", "421", 25)
    _insert_unit(conn, "M421", "M", ["TRANSPORT", "MEDIC"], [], "421", "421", 11)
    _insert_unit(conn, "EMS401", "EMS", ["COUNTY", "BALLISTIC", "CHASE CAR"], [], "442", "442", 50)
    _insert_unit(conn, "BC401", "BC", ["COUNTY", "BALLISTIC", "COMMAND BC"], [], "425", "404", 60)
    _insert_unit(conn, "BC443", "BC", ["CITY", "BALLISTIC", "COMMAND BC"], [], "403", "403", 61)
    _insert_unit(conn, "HM401", "HM", ["RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"], [], "440", "440", 70,
                 notes="Current hazmat unit. Not explicitly substituted for historical HM440 response-plan references.")
    _insert_unit(conn, "HM401M", "HM", ["ALS FIRST RESP", "RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"], [], "440", "440", 71,
                 notes="Current ALS hazmat unit. Personnel skill M staffing has not yet been supplied.")
    conn.execute("UPDATE units SET available=0 WHERE unit_id IN ('HM401','HM401M')")

    for eid, unit in [
        ("TEST1001", "E421M"), ("TEST1003", "RE433M"), ("TEST1004", "R421M"),
        ("TEST1005", "T421M"), ("TEST1006", "TL440M"), ("TEST1007", "TT425M"),
        ("TEST1008", "M421"),
    ]:
        _insert_person(conn, eid, ["FRD", "M"], unit)

    conn.commit()


def ensure_v03_data(conn):
    # v0.3 resource-state corrections. For operational E/T/TL/TT/R resources,
    # ALS FIRST RESP follows the M-suffix version rather than the base unit.
    operational_types = ("E", "T", "TL", "TT", "R")
    for row in conn.execute(
        "SELECT unit_id, unit_type FROM units WHERE unit_type IN ('E','T','TL','TT','R')"
    ).fetchall():
        unit_id = row["unit_id"]
        if unit_id.endswith("M"):
            conn.execute(
                "INSERT OR IGNORE INTO unit_attributes(unit_id, attribute) VALUES (?, 'ALS FIRST RESP')",
                (unit_id,),
            )
        else:
            conn.execute(
                "DELETE FROM unit_attributes WHERE unit_id=? AND attribute='ALS FIRST RESP'",
                (unit_id,),
            )

    # Current hazmat resources. Keep them separate from historical HM440/HM440M
    # response-plan references until current plans are loaded.
    for unit_id, attrs, available, priority in [
        ("HM401", ["RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"], 0, 70),
        ("HM401M", ["ALS FIRST RESP", "RESCUE", "HAZMAT", "HEAVY", "EXTRICATION"], 0, 71),
    ]:
        conn.execute(
            """INSERT OR IGNORE INTO units
               (unit_id, unit_type, agency, station, beat, recommendable, available, priority, notes)
               VALUES (?, 'HM', 'FIRE', '440', '440', 1, ?, ?, ?)""",
            (unit_id, available, priority,
             "Current hazmat resource; not automatically substituted for historical HM440/HM440M plan references."),
        )
        conn.execute("UPDATE units SET unit_type='HM', station='440', beat='440' WHERE unit_id=?", (unit_id,))
        conn.execute("DELETE FROM unit_attributes WHERE unit_id=?", (unit_id,))
        conn.executemany(
            "INSERT INTO unit_attributes(unit_id, attribute) VALUES (?, ?)",
            [(unit_id, attr) for attr in attrs],
        )

    # Known requirement definitions.
    _insert_requirement(conn, "ALS_SKILL", 2, skills=["M"], allow_existing_units=True,
                        notes="Two personnel with skill M; any qualifying recommended units can contribute.")
    _insert_requirement(conn, "SUPPRESSION UNIT", 1, attributes=["HEAVY"])
    _insert_requirement(conn, "M", 1, unit_type="M")
    _insert_requirement(conn, "E", 1, unit_type="E")
    _insert_requirement(conn, "T", 1, attributes=["TRUCK"])
    _insert_requirement(conn, "TL", 1, unit_type="TL", attributes=["TRUCK"])
    _insert_requirement(conn, "TT", 1, unit_type="TT", attributes=["TRUCK"])
    _insert_requirement(conn, "R", 1, attributes=["RESCUE"], attribute_mode="ANY")
    _insert_requirement(conn, "AFR1", 1, equipment=["AFR1"])
    _insert_requirement(conn, "AFR2", 1, equipment=["AFR2"])
    _insert_requirement(conn, "EMS", 1, unit_type="EMS")
    _insert_requirement(conn, "BC", 1, unit_type="BC")
    _insert_requirement(conn, "BCCITY", 1, unit_type="BC", attributes=["CITY"])
    _insert_requirement(conn, "BCCNTY", 1, unit_type="BC", attributes=["COUNTY"])

    # These appear in AFR_ALS, but their exact requirement definitions have not been supplied.
    for name in ["AFR3", "AFR4", "HM440M", "HM440", "A"]:
        _insert_requirement(
            conn, name, definition_status="UNRESOLVED",
            notes="Referenced by AFR_ALS; exact CADDBM requirement definition not yet loaded."
        )

    conn.execute("DELETE FROM plan_group_members WHERE plan_name='AFR_ALS_2022'")
    conn.execute("DELETE FROM plan_steps WHERE plan_name='AFR_ALS_2022'")
    conn.execute("DELETE FROM plans WHERE plan_name='AFR_ALS_2022'")
    conn.execute(
        "INSERT INTO plans(plan_name, description) VALUES (?, ?)",
        ("AFR_ALS_2022", "Historical AFR_ALS flow from the supplied July 2022 response-plan PDF."),
    )
    steps = [
        ("AFR_ALS_2022", 1, "GROUP", None, None, 2, 2, "Initial response resource"),
        ("AFR_ALS_2022", 2, "REQUIREMENT", "M", None, 3, 3, "Add medic"),
        ("AFR_ALS_2022", 3, "CONDITION", None, "ALS_SKILL", 6, 4, "ALS_SKILL Recommended?"),
        ("AFR_ALS_2022", 4, "GROUP", None, None, 5, 5, "Add ALS resource"),
        ("AFR_ALS_2022", 5, "CONDITION", None, "SUPPRESSION UNIT", 6, 7, "SUPPRESSION UNIT Recommended?"),
        ("AFR_ALS_2022", 6, "STOP", None, None, None, None, "End"),
        ("AFR_ALS_2022", 7, "GROUP", None, None, 6, 6, "Add suppression resource"),
    ]
    conn.executemany(
        """INSERT INTO plan_steps
           (plan_name, step_no, step_kind, requirement_name, condition_requirement,
            on_yes_step, on_no_step, label)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        steps,
    )
    groups = {
        1: ["AFR1", "AFR2", "AFR3", "AFR4", "HM440M", "E", "T", "TL", "TT", "R", "HM440", "A"],
        4: ["AFR1", "AFR2", "AFR3", "AFR4", "EMS"],
        7: ["AFR1", "AFR2", "HM440M", "E", "T", "TL", "TT", "R", "HM440"],
    }
    for step_no, members in groups.items():
        conn.executemany(
            "INSERT INTO plan_group_members(plan_name, step_no, member_order, requirement_name) VALUES (?, ?, ?, ?)",
            [("AFR_ALS_2022", step_no, i + 1, req) for i, req in enumerate(members)],
        )
    conn.commit()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Initialized {DB_PATH}")
