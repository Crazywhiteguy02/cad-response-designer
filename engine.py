from __future__ import annotations

from dataclasses import dataclass, field
import json
import sqlite3
from typing import Optional


@dataclass
class Requirement:
    name: str
    quantity: int = 1
    unit_type: Optional[str] = None
    attributes: list[str] = field(default_factory=list)
    attribute_mode: str = "ALL"
    equipment: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    beat_option: str = "ALL"
    allow_existing_units: bool = False
    notes: str | None = None


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


@dataclass
class SimulationState:
    assignments: list[Assignment] = field(default_factory=list)
    satisfied_requirements: set[str] = field(default_factory=set)
    trace: list[str] = field(default_factory=list)

    @property
    def consumed_units(self) -> set[str]:
        return {a.unit_id for a in self.assignments}


def load_requirement(conn: sqlite3.Connection, name: str) -> Requirement:
    row = conn.execute("SELECT * FROM requirements WHERE name = ?", (name,)).fetchone()
    if not row:
        raise KeyError(f"Unknown requirement: {name}")
    return Requirement(
        name=row["name"],
        quantity=row["quantity"],
        unit_type=row["unit_type"],
        attributes=json.loads(row["attributes_json"]),
        attribute_mode=row["attribute_mode"],
        equipment=json.loads(row["equipment_json"]),
        skills=json.loads(row["skills_json"]),
        beat_option=row["beat_option"],
        allow_existing_units=bool(row["allow_existing_units"]),
        notes=row["notes"],
    )


def load_units(conn: sqlite3.Connection) -> list[UnitState]:
    rows = conn.execute("SELECT * FROM units").fetchall()
    units = []

    for row in rows:
        attrs = {
            r["attribute"]
            for r in conn.execute(
                "SELECT attribute FROM unit_attributes WHERE unit_id = ?",
                (row["unit_id"],),
            )
        }
        equipment = {
            r["equipment_code"]: r["quantity"]
            for r in conn.execute(
                "SELECT equipment_code, quantity FROM unit_equipment WHERE unit_id = ?",
                (row["unit_id"],),
            )
        }
        skill_rows = conn.execute(
            """
            SELECT ps.skill_code, COUNT(*) AS n
            FROM roster r
            JOIN personnel_skills ps ON ps.employee_id = r.employee_id
            WHERE r.unit_id = ?
            GROUP BY ps.skill_code
            """,
            (row["unit_id"],),
        ).fetchall()
        skills = {r["skill_code"]: r["n"] for r in skill_rows}

        units.append(
            UnitState(
                unit_id=row["unit_id"],
                unit_type=row["unit_type"],
                attributes=attrs,
                equipment=equipment,
                skills=skills,
                priority=row["priority"],
                available=bool(row["available"]),
                recommendable=bool(row["recommendable"]),
                station=row["station"],
                beat=row["beat"],
            )
        )
    return units


def unit_qualifies(unit: UnitState, req: Requirement) -> tuple[bool, list[str]]:
    reasons = []

    if not unit.available:
        return False, ["unit unavailable"]
    if not unit.recommendable:
        return False, ["unit is not recommendable"]

    if req.unit_type:
        if unit.unit_type != req.unit_type:
            return False, [f"Unit Type {unit.unit_type} != required {req.unit_type}"]
        reasons.append(f"Unit Type {unit.unit_type} matches")

    if req.attributes:
        matches = [a for a in req.attributes if a in unit.attributes]
        if req.attribute_mode.upper() == "ANY":
            if not matches:
                return False, [f"none of required attributes present: {', '.join(req.attributes)}"]
            reasons.append(f"attribute match: {', '.join(matches)}")
        else:
            missing = [a for a in req.attributes if a not in unit.attributes]
            if missing:
                return False, [f"missing attributes: {', '.join(missing)}"]
            reasons.append(f"all required attributes present: {', '.join(req.attributes)}")

    if req.equipment:
        missing = [e for e in req.equipment if unit.equipment.get(e, 0) < 1]
        if missing:
            return False, [f"missing equipment: {', '.join(missing)}"]
        reasons.append(f"equipment present: {', '.join(req.equipment)}")

    return True, reasons


def reusable_requirement_status(req: Requirement, selected_units: list[UnitState]) -> tuple[bool, str]:
    if not req.allow_existing_units:
        return False, "requirement is not configured for existing-unit reuse"

    if req.skills:
        total = 0
        contributions = []
        for skill in req.skills:
            for u in selected_units:
                n = u.skills.get(skill, 0)
                total += n
                if n:
                    contributions.append(f"{u.unit_id}={n} {skill}")
        return total >= req.quantity, (
            f"required={req.quantity}; available={total}; "
            + ("; ".join(contributions) if contributions else "no contributions")
        )

    if req.equipment:
        total = 0
        contributions = []
        for code in req.equipment:
            for u in selected_units:
                n = u.equipment.get(code, 0)
                total += n
                if n:
                    contributions.append(f"{u.unit_id}={n} {code}")
        return total >= req.quantity, (
            f"required={req.quantity}; available={total}; "
            + ("; ".join(contributions) if contributions else "no contributions")
        )

    return False, "v0.1 reusable evaluator supports skill/equipment requirements only"


def choose_unit_for_requirement(req: Requirement, units: list[UnitState], state: SimulationState):
    candidates = []
    reasons_by_unit = {}

    for unit in units:
        if unit.unit_id in state.consumed_units:
            continue
        ok, reasons = unit_qualifies(unit, req)
        if ok:
            candidates.append(unit)
            reasons_by_unit[unit.unit_id] = reasons

    candidates.sort(key=lambda u: (u.priority, u.unit_id))

    if not candidates:
        return None, ["no eligible unconsumed unit found"]

    selected = candidates[0]
    return selected, reasons_by_unit[selected.unit_id]


def simulate_plan(conn: sqlite3.Connection, plan_name: str) -> SimulationState:
    state = SimulationState()
    units = load_units(conn)
    unit_map = {u.unit_id: u for u in units}

    rows = conn.execute(
        "SELECT * FROM plan_steps WHERE plan_name = ? ORDER BY step_no",
        (plan_name,),
    ).fetchall()
    steps = {r["step_no"]: r for r in rows}

    if not steps:
        raise KeyError(f"Unknown or empty plan: {plan_name}")

    current = min(steps)
    guard = 0

    while current is not None:
        guard += 1
        if guard > 100:
            raise RuntimeError("Plan exceeded 100 steps; possible loop.")

        step = steps[current]
        kind = step["step_kind"]
        label = step["label"] or ""
        state.trace.append(f"STEP {current}: {label}")

        if kind == "STOP":
            state.trace.append("Plan complete.")
            break

        if kind == "REQUIREMENT":
            req = load_requirement(conn, step["requirement_name"])

            if req.allow_existing_units:
                selected_units = [unit_map[a.unit_id] for a in state.assignments]
                satisfied, detail = reusable_requirement_status(req, selected_units)
                state.trace.append(f"{req.name}: reusable check -> {detail}")
                if satisfied:
                    state.satisfied_requirements.add(req.name)
                    state.trace.append(f"{req.name}: SATISFIED by existing recommended units.")
                else:
                    state.trace.append(f"{req.name}: NOT satisfied by existing recommended units.")
            else:
                selected, reasons = choose_unit_for_requirement(req, units, state)
                if selected is None:
                    state.trace.append(f"{req.name}: FAILED — {'; '.join(reasons)}")
                else:
                    state.assignments.append(Assignment(req.name, selected.unit_id))
                    state.satisfied_requirements.add(req.name)
                    state.trace.append(
                        f"{req.name}: selected {selected.unit_id} — {'; '.join(reasons)}"
                    )

            current = step["on_yes_step"]
            continue

        if kind == "CONDITION":
            req = load_requirement(conn, step["condition_requirement"])
            selected_units = [unit_map[a.unit_id] for a in state.assignments]

            if req.allow_existing_units:
                result, detail = reusable_requirement_status(req, selected_units)
            else:
                result = req.name in state.satisfied_requirements
                detail = (
                    "requirement has already been satisfied"
                    if result
                    else "requirement has not been satisfied"
                )

            state.trace.append(f"CONDITION {req.name}: {'YES' if result else 'NO'} — {detail}")
            if result:
                state.satisfied_requirements.add(req.name)
                current = step["on_yes_step"]
            else:
                current = step["on_no_step"]
            continue

        raise ValueError(f"Unsupported step kind: {kind}")

    return state
