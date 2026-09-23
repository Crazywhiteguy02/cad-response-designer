from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import pandas as pd

from requirements import REQUIREMENTS, Requirement
from alpha_plan import ALPHA_STEPS, PlanStep
from catalog import attributes_from_text, equipment_from_text


@dataclass
class ScenarioUnit:
    unit_id: str
    unit_type: str
    beat: str
    station_id: str
    attributes: set[str]
    equipment: dict[str, int]
    m_skill_count: int
    test_distance: float


@dataclass
class Assignment:
    step: int
    requirement: str
    unit_id: str


@dataclass
class SimulationState:
    assignments: list[Assignment] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    @property
    def consumed_units(self) -> set[str]:
        return {a.unit_id for a in self.assignments}


def scenario_units_from_frame(frame: pd.DataFrame) -> list[ScenarioUnit]:
    units: list[ScenarioUnit] = []
    for _, r in frame.iterrows():
        # v0.4.1 exposes AFR1/AFR2 as an explicit dropdown while preserving
        # a free-text field for all other equipment. Older frames containing
        # only an Equipment column remain supported.
        if "AFR Equipment" in frame.columns or "Other Equipment" in frame.columns:
            equipment_parts = []
            afr = str(r.get("AFR Equipment", "") or "").strip()
            other = str(r.get("Other Equipment", "") or "").strip()
            if afr:
                equipment_parts.append(afr)
            if other:
                equipment_parts.append(other)
            equipment_text = ", ".join(equipment_parts)
        else:
            equipment_text = str(r.get("Equipment", ""))

        units.append(
            ScenarioUnit(
                unit_id=str(r["Unit ID"]),
                unit_type=str(r["Unit Type"]),
                beat=str(r.get("Beat", "")),
                station_id=str(r.get("Station", "")),
                attributes=attributes_from_text(str(r.get("Attributes", ""))),
                equipment=equipment_from_text(equipment_text),
                m_skill_count=int(r.get("M Skills", 0) or 0),
                test_distance=float(r.get("Test Distance", 999) or 999),
            )
        )
    return units


def qualifies(unit: ScenarioUnit, req: Requirement) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if req.unit_id:
        if unit.unit_id != req.unit_id:
            return False, [f"Unit ID {unit.unit_id} != {req.unit_id}"]
        reasons.append(f"Unit ID {unit.unit_id}")

    if req.unit_type:
        if unit.unit_type != req.unit_type:
            return False, [f"Unit Type {unit.unit_type} != {req.unit_type}"]
        reasons.append(f"Unit Type {unit.unit_type}")

    if req.attributes:
        matches = [a for a in req.attributes if a in unit.attributes]
        if req.attribute_mode.upper() == "ANY":
            if not matches:
                return False, [f"no required attribute present: {', '.join(req.attributes)}"]
            reasons.append(f"attribute {', '.join(matches)}")
        else:
            missing = [a for a in req.attributes if a not in unit.attributes]
            if missing:
                return False, [f"missing attributes: {', '.join(missing)}"]
            reasons.append(f"attributes {', '.join(req.attributes)}")

    if req.equipment:
        missing = [e for e in req.equipment if unit.equipment.get(e, 0) < 1]
        if missing:
            return False, [f"missing equipment: {', '.join(missing)}"]
        reasons.append(f"equipment {', '.join(req.equipment)}")

    return True, reasons


def selected_satisfies(req: Requirement, selected: list[ScenarioUnit]) -> tuple[bool, str]:
    # Personnel-skill requirements can be supplied across already recommended units.
    if req.skills:
        if tuple(req.skills) == ("M",):
            contributions = [(u.unit_id, u.m_skill_count) for u in selected if u.m_skill_count]
            total = sum(n for _, n in contributions)
            detail = "; ".join(f"{uid}={n} M" for uid, n in contributions) or "no M-skill contributions"
            return total >= req.quantity, f"required={req.quantity}; available={total}; {detail}"
        return False, "v0.4 currently models personnel skill M only"

    matching = []
    for u in selected:
        ok, _ = qualifies(u, req)
        if ok:
            matching.append(u.unit_id)
    return len(matching) >= req.quantity, (
        f"required={req.quantity}; matching recommended units=" + (", ".join(matching) if matching else "none")
    )


def choose_for_requirement(
    req_name: str,
    units: list[ScenarioUnit],
    state: SimulationState,
    *,
    max_distance: float | None = None,
) -> tuple[ScenarioUnit | None, list[str]]:
    req = REQUIREMENTS[req_name]
    candidates = []
    for u in units:
        if u.unit_id in state.consumed_units:
            continue
        if max_distance is not None and u.test_distance > max_distance:
            continue
        ok, reasons = qualifies(u, req)
        if ok:
            candidates.append((u.test_distance, u.unit_id, u, reasons))
    if not candidates:
        return None, []
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, _, unit, reasons = candidates[0]
    return unit, reasons


def choose_for_group(
    alternatives: Iterable[str],
    units: list[ScenarioUnit],
    state: SimulationState,
) -> tuple[str | None, ScenarioUnit | None, list[str]]:
    candidates = []
    for alt_order, req_name in enumerate(alternatives):
        req = REQUIREMENTS[req_name]
        for u in units:
            if u.unit_id in state.consumed_units:
                continue
            ok, reasons = qualifies(u, req)
            if ok:
                # CAD routing/proximity is not available in v0.4. The user-editable
                # Test Distance is the stand-in; requirement order breaks equal-distance ties.
                candidates.append((u.test_distance, alt_order, u.unit_id, req_name, u, reasons))
    if not candidates:
        return None, None, []
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    _, _, _, req_name, unit, reasons = candidates[0]
    return req_name, unit, reasons


def simulate_alpha(units: list[ScenarioUnit]) -> SimulationState:
    state = SimulationState()
    unit_by_id = {u.unit_id: u for u in units}
    current = 1
    guard = 0

    while current is not None:
        guard += 1
        if guard > 100:
            raise RuntimeError("ALPHA exceeded 100 steps; possible flow loop")
        step = ALPHA_STEPS[current]
        state.trace.append(f"STEP {step.number}: {step.label}")

        if step.kind == "STOP":
            state.trace.append("Plan complete.")
            break

        if step.kind == "REQUIREMENT":
            unit, reasons = choose_for_requirement(
                step.requirement, units, state, max_distance=step.max_distance
            )
            if unit:
                state.assignments.append(Assignment(step.number, step.requirement, unit.unit_id))
                max_note = f" within max distance {step.max_distance:g}" if step.max_distance is not None else ""
                state.trace.append(
                    f"{step.requirement}: selected {unit.unit_id}{max_note} — " + "; ".join(reasons)
                )
                current = step.yes_step if step.yes_step is not None else step.next_step
            else:
                state.trace.append(
                    f"{step.requirement}: no eligible unconsumed unit"
                    + (f" within max distance {step.max_distance:g}" if step.max_distance is not None else "")
                )
                current = step.no_step if step.no_step is not None else step.next_step
            continue

        if step.kind == "GROUP":
            req_name, unit, reasons = choose_for_group(step.alternatives, units, state)
            if unit:
                state.assignments.append(Assignment(step.number, req_name, unit.unit_id))
                state.trace.append(
                    f"GROUP selected {unit.unit_id} via {req_name} — " + "; ".join(reasons)
                )
                if unit.m_skill_count:
                    state.trace.append(f"{unit.unit_id} contributes {unit.m_skill_count} personnel skill M")
                if step.display_order is not None:
                    state.trace.append(f"Display Order={step.display_order} (display only; not used for qualification)")
            else:
                state.trace.append("GROUP FAILED — no eligible unconsumed unit")
            current = step.next_step
            continue

        if step.kind == "CONDITION":
            req = REQUIREMENTS[step.requirement]
            selected = [unit_by_id[a.unit_id] for a in state.assignments]
            result, detail = selected_satisfies(req, selected)
            state.trace.append(f"CONDITION {req.name}: {'YES' if result else 'NO'} — {detail}")
            current = step.yes_step if result else step.no_step
            continue

        raise ValueError(f"Unsupported step kind: {step.kind}")

    return state


def pair_conflicts(frame: pd.DataFrame) -> list[tuple[str, str]]:
    selected = set(frame["Unit ID"].astype(str))
    pairs = []
    for _, row in frame.iterrows():
        pair = str(row.get("Pair Unit", ""))
        uid = str(row["Unit ID"])
        if pair and pair in selected and uid < pair:
            pairs.append((uid, pair))
    return pairs
