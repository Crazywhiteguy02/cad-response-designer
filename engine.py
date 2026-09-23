from __future__ import annotations

from dataclasses import dataclass, field
import json
import sqlite3


@dataclass
class Requirement:
    name: str
    quantity: int
    unit_type: str | None
    attributes: list[str]
    attribute_mode: str
    equipment: list[str]
    skills: list[str]
    beat_option: str
    allow_existing_units: bool
    notes: str | None
    definition_status: str


@dataclass
class UnitState:
    unit_id: str
    unit_type: str
    attributes: set[str]
    equipment: dict[str, int]
    skills: dict[str, int]
    priority: int
    available: bool
    recommendable: bool
    station: str | None = None
    beat: str | None = None


@dataclass
class Assignment:
    requirement: str
    unit_id: str
    source_step: int


@dataclass
class SimulationState:
    assignments: list[Assignment] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    @property
    def consumed_units(self) -> set[str]:
        return {a.unit_id for a in self.assignments}


def load_requirement(conn: sqlite3.Connection, name: str) -> Requirement:
    row = conn.execute("SELECT * FROM requirements WHERE name=?", (name,)).fetchone()
    if not row:
        raise KeyError(f"Unknown requirement: {name}")
    return Requirement(
        row["name"], row["quantity"], row["unit_type"],
        json.loads(row["attributes_json"]), row["attribute_mode"],
        json.loads(row["equipment_json"]), json.loads(row["skills_json"]),
        row["beat_option"], bool(row["allow_existing_units"]), row["notes"],
        row["definition_status"],
    )


def load_units(conn: sqlite3.Connection) -> list[UnitState]:
    units = []
    for row in conn.execute("SELECT * FROM units"):
        attrs = {r["attribute"] for r in conn.execute(
            "SELECT attribute FROM unit_attributes WHERE unit_id=?", (row["unit_id"],)
        )}
        equipment = {r["equipment_code"]: r["quantity"] for r in conn.execute(
            "SELECT equipment_code, quantity FROM unit_equipment WHERE unit_id=?", (row["unit_id"],)
        )}
        skill_rows = conn.execute(
            """SELECT ps.skill_code, COUNT(*) AS n
               FROM roster r JOIN personnel_skills ps ON ps.employee_id=r.employee_id
               WHERE r.unit_id=? GROUP BY ps.skill_code""",
            (row["unit_id"],),
        ).fetchall()
        skills = {r["skill_code"]: r["n"] for r in skill_rows}
        units.append(UnitState(
            row["unit_id"], row["unit_type"], attrs, equipment, skills,
            row["priority"], bool(row["available"]), bool(row["recommendable"]),
            row["station"], row["beat"],
        ))
    return units


def unit_qualifies(unit: UnitState, req: Requirement) -> tuple[bool, list[str]]:
    if req.definition_status != "DEFINED":
        return False, [f"{req.name} definition unresolved"]
    if not unit.available:
        return False, ["unit unavailable"]
    if not unit.recommendable:
        return False, ["unit not recommendable"]

    reasons = []
    if req.unit_type:
        if unit.unit_type != req.unit_type:
            return False, [f"Unit Type {unit.unit_type} != {req.unit_type}"]
        reasons.append(f"Unit Type {unit.unit_type}")

    if req.attributes:
        matches = [a for a in req.attributes if a in unit.attributes]
        if req.attribute_mode.upper() == "ANY":
            if not matches:
                return False, [f"no matching attribute from {', '.join(req.attributes)}"]
            reasons.append(f"attribute {', '.join(matches)}")
        else:
            missing = [a for a in req.attributes if a not in unit.attributes]
            if missing:
                return False, [f"missing attributes {', '.join(missing)}"]
            reasons.append(f"attributes {', '.join(req.attributes)}")

    if req.equipment:
        missing = [e for e in req.equipment if unit.equipment.get(e, 0) < 1]
        if missing:
            return False, [f"missing equipment {', '.join(missing)}"]
        reasons.append(f"equipment {', '.join(req.equipment)}")

    return True, reasons


def selected_satisfies_requirement(req: Requirement, selected_units: list[UnitState]) -> tuple[bool, str]:
    if req.definition_status != "DEFINED":
        return False, f"{req.name} definition unresolved"

    if req.skills:
        total = 0
        contributions = []
        for skill in req.skills:
            for unit in selected_units:
                count = unit.skills.get(skill, 0)
                total += count
                if count:
                    contributions.append(f"{unit.unit_id}={count} {skill}")
        return total >= req.quantity, (
            f"required={req.quantity}; available={total}; "
            + ("; ".join(contributions) if contributions else "no contributions")
        )

    matching = []
    for unit in selected_units:
        ok, _ = unit_qualifies(unit, req)
        if ok:
            matching.append(unit.unit_id)
    return len(matching) >= req.quantity, (
        f"required={req.quantity}; matching selected units="
        + (", ".join(matching) if matching else "none")
    )


def choose_unit_for_requirement(req: Requirement, units: list[UnitState], state: SimulationState):
    candidates = []
    for unit in units:
        if unit.unit_id in state.consumed_units:
            continue
        ok, reasons = unit_qualifies(unit, req)
        if ok:
            candidates.append((unit.priority, unit.unit_id, unit, reasons))
    if not candidates:
        return None, ["no eligible unconsumed unit found"]
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2], candidates[0][3]


def choose_unit_for_group(conn, plan_name, step_no, units, state):
    members = conn.execute(
        """SELECT member_order, requirement_name FROM plan_group_members
           WHERE plan_name=? AND step_no=? ORDER BY member_order""",
        (plan_name, step_no),
    ).fetchall()

    candidates = []
    unresolved = []
    for member in members:
        req = load_requirement(conn, member["requirement_name"])
        if req.definition_status != "DEFINED":
            unresolved.append(req.name)
            continue
        for unit in units:
            if unit.unit_id in state.consumed_units:
                continue
            ok, reasons = unit_qualifies(unit, req)
            if ok:
                # Temporary stand-in: unit priority approximates proximity/routing.
                # Group order is only a tie-breaker here.
                candidates.append(
                    (unit.priority, member["member_order"], unit.unit_id, req, unit, reasons)
                )

    if not candidates:
        return None, None, None, unresolved
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    _, _, _, req, unit, reasons = candidates[0]
    return req, unit, reasons, unresolved


def simulate_plan(conn: sqlite3.Connection, plan_name: str) -> SimulationState:
    state = SimulationState()
    units = load_units(conn)
    unit_map = {u.unit_id: u for u in units}
    steps = {r["step_no"]: r for r in conn.execute(
        "SELECT * FROM plan_steps WHERE plan_name=?", (plan_name,)
    )}
    if not steps:
        raise KeyError(f"Unknown plan: {plan_name}")

    current = min(steps)
    guard = 0
    while current is not None:
        guard += 1
        if guard > 100:
            raise RuntimeError("Plan exceeded 100 steps; possible loop")
        step = steps[current]
        state.trace.append(f"STEP {current}: {step['label']}")

        if step["step_kind"] == "STOP":
            state.trace.append("Plan complete.")
            break

        if step["step_kind"] == "REQUIREMENT":
            req = load_requirement(conn, step["requirement_name"])
            selected, reasons = choose_unit_for_requirement(req, units, state)
            if selected:
                state.assignments.append(Assignment(req.name, selected.unit_id, current))
                state.trace.append(f"{req.name}: selected {selected.unit_id} — {'; '.join(reasons)}")
                if selected.skills.get("M", 0):
                    state.trace.append(f"{selected.unit_id} contributes {selected.skills['M']} personnel skill M")
            else:
                state.trace.append(f"{req.name}: FAILED — {'; '.join(reasons)}")
            current = step["on_yes_step"]
            continue

        if step["step_kind"] == "GROUP":
            req, selected, reasons, unresolved = choose_unit_for_group(
                conn, plan_name, current, units, state
            )
            if unresolved:
                state.trace.append(
                    "Unresolved alternatives retained but not evaluated: " + ", ".join(unresolved)
                )
            if selected:
                state.assignments.append(Assignment(req.name, selected.unit_id, current))
                state.trace.append(
                    f"GROUP selected {selected.unit_id} via {req.name} — {'; '.join(reasons)}"
                )
                if selected.skills.get("M", 0):
                    state.trace.append(f"{selected.unit_id} contributes {selected.skills['M']} personnel skill M")
            else:
                state.trace.append("GROUP FAILED — no eligible unconsumed unit from loaded definitions")
            current = step["on_yes_step"]
            continue

        if step["step_kind"] == "CONDITION":
            req = load_requirement(conn, step["condition_requirement"])
            selected_units = [unit_map[a.unit_id] for a in state.assignments]
            result, detail = selected_satisfies_requirement(req, selected_units)
            state.trace.append(f"CONDITION {req.name}: {'YES' if result else 'NO'} — {detail}")
            current = step["on_yes_step"] if result else step["on_no_step"]
            continue

        raise ValueError(f"Unsupported step kind: {step['step_kind']}")

    return state
