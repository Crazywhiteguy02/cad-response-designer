from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("cad.db")


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


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

        CREATE TABLE IF NOT EXISTS personnel (
            employee_id TEXT PRIMARY KEY
        );

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
        """
    )
    conn.commit()

    if cur.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 0:
        seed(conn)

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
                        beat_option="ALL", allow_existing_units=False, notes=None):
    conn.execute(
        """INSERT INTO requirements
           (name, quantity, unit_type, attributes_json, attribute_mode,
            equipment_json, skills_json, beat_option, allow_existing_units, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            quantity,
            unit_type,
            json.dumps(list(attributes)),
            attribute_mode,
            json.dumps(list(equipment)),
            json.dumps(list(skills)),
            beat_option,
            int(allow_existing_units),
            notes,
        ),
    )


def seed(conn):
    # Representative Fairfax test fleet.
    _insert_unit(conn, "E421M", "E",
                 ["ENGINE", "ALS FIRST RESP", "HEAVY"],
                 [("AFR1", 1)], "421", "421", 10,
                 notes="M suffix is an operational indicator; rostered personnel profile is authoritative for skill M.")
    _insert_unit(conn, "E426", "E",
                 ["ENGINE", "ALS FIRST RESP", "HEAVY"],
                 [], "426", "426", 20)
    _insert_unit(conn, "E435", "E",
                 ["ENGINE", "ALS FIRST RESP", "HEAVY"],
                 [], "435", "435", 30)
    _insert_unit(conn, "RE433M", "E",
                 ["RESCUE", "ENGINE", "HEAVY", "BALLISTIC", "EXTRICATION"],
                 [("AFR2", 1)], "433", "433", 15,
                 notes="Can qualify for E or R, but can occupy only one exclusive slot.")
    _insert_unit(conn, "R421M", "R",
                 ["RESCUE", "HAZMAT", "TROT", "HEAVY", "BALLISTIC", "EXTRICATION"],
                 [("AFR1", 1)], "421", "421", 12)
    _insert_unit(conn, "T421M", "T",
                 ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION"],
                 [("AFR2", 1)], "421", "421", 14)
    _insert_unit(conn, "TL440M", "TL",
                 ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION"],
                 [("AFR1", 1)], "440", "440", 40)
    _insert_unit(conn, "TT425M", "TT",
                 ["TRUCK", "HEAVY", "BALLISTIC", "EXTRICATION"],
                 [("AFR2", 1)], "425", "425", 35)
    _insert_unit(conn, "A421", "A",
                 ["COUNTY", "TRANSPORT", "AMBULANCE"],
                 [], "421", "421", 25)
    _insert_unit(conn, "M421", "M",
                 ["TRANSPORT", "MEDIC"],
                 [], "421", "421", 11)
    _insert_unit(conn, "EMS401", "EMS",
                 ["COUNTY", "BALLISTIC", "CHASE CAR"],
                 [], "442", "442", 50)
    _insert_unit(conn, "BC401", "BC",
                 ["COUNTY", "BALLISTIC", "COMMAND BC"],
                 [], "425", "404", 60)
    _insert_unit(conn, "BC443", "BC",
                 ["CITY", "BALLISTIC", "COMMAND BC"],
                 [], "403", "403", 61)

    # Synthetic roster. Test IDs only.
    _insert_person(conn, "TEST1001", ["FRD", "M"], "E421M")
    _insert_person(conn, "TEST1002", ["FRD"], "E421M")
    _insert_person(conn, "TEST1003", ["FRD", "M"], "RE433M")
    _insert_person(conn, "TEST1004", ["FRD", "M"], "R421M")
    _insert_person(conn, "TEST1005", ["FRD", "M"], "T421M")
    _insert_person(conn, "TEST1006", ["FRD", "M"], "TL440M")
    _insert_person(conn, "TEST1007", ["FRD", "M"], "TT425M")
    _insert_person(conn, "TEST1008", ["FRD", "M"], "M421")
    _insert_person(conn, "TEST1009", ["FRD"], "M421")

    # Requirement definitions established during discovery.
    _insert_requirement(conn, "ALS_SKILL", 2, skills=["M"], allow_existing_units=True,
                        notes="Two personnel with skill M; reusable across already recommended units.")
    _insert_requirement(conn, "SUPPRESSION UNIT", 1, attributes=["HEAVY"])
    _insert_requirement(conn, "A FIRST DUE", 1, unit_type="A", beat_option="PRIMARY")
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
    _insert_requirement(conn, "BCFTBV", 1, unit_type="BCFTB",
                        notes="Observed as BCFTB in supplied screenshot; verify exact production code.")
    _insert_requirement(conn, "BCALX", 1, unit_type="BCALX")
    _insert_requirement(conn, "OPS BC", 1, equipment=["OPS BC"])

    # Small validation plan; not asserted to be the full production AFR plan.
    conn.execute(
        "INSERT INTO plans(plan_name, description) VALUES (?, ?)",
        ("AFR_ALS_PROTOTYPE",
         "Validation plan for exclusive resource slots and reusable ALS personnel skills.")
    )
    conn.executemany(
        """INSERT INTO plan_steps
           (plan_name, step_no, step_kind, requirement_name, condition_requirement,
            on_yes_step, on_no_step, label)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("AFR_ALS_PROTOTYPE", 1, "REQUIREMENT", "E", None, 2, 2, "Select engine"),
            ("AFR_ALS_PROTOTYPE", 2, "REQUIREMENT", "M", None, 3, 3, "Select medic"),
            ("AFR_ALS_PROTOTYPE", 3, "CONDITION", None, "ALS_SKILL", 5, 4, "ALS skill already present?"),
            ("AFR_ALS_PROTOTYPE", 4, "REQUIREMENT", "AFR1", None, 5, 5, "Add AFR1 resource if ALS skill not satisfied"),
            ("AFR_ALS_PROTOTYPE", 5, "STOP", None, None, None, None, "End"),
        ]
    )

    conn.commit()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Initialized {DB_PATH}")
