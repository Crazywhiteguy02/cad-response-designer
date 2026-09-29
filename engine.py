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
    test_time_minutes: float
    routing_mode: str = "manual"
    route_distance_miles: float | None = None
    route_time_seconds: float | None = None


@dataclass
class Assignment:
    step: int
    requirement: str
    unit_id: str
    sequence: int = 0
    display_order: int | None = None


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
        # v0.4.2 uses one list-valued Equipment field. Older AFR/Other
        # and free-text Equipment formats are still accepted.
        if "Equipment" in frame.columns:
            raw_equipment = r.get("Equipment", [])
            if isinstance(raw_equipment, (list, tuple, set)):
                equipment_text = ", ".join(str(x).strip() for x in raw_equipment if str(x).strip())
            else:
                equipment_text = str(raw_equipment or "")
        elif "AFR Equipment" in frame.columns or "Other Equipment" in frame.columns:
            equipment_parts = []
            afr = str(r.get("AFR Equipment", "") or "").strip()
            other = str(r.get("Other Equipment", "") or "").strip()
            if afr:
                equipment_parts.append(afr)
            if other:
                equipment_parts.append(other)
            equipment_text = ", ".join(equipment_parts)
        else:
            equipment_text = ""

        units.append(
            ScenarioUnit(
                unit_id=str(r["Unit ID"]),
                unit_type=str(r["Unit Type"]),
                beat=str(r.get("Beat", "")),
                station_id=str(r.get("Station", "")),
                attributes=(
                    set(str(x).strip() for x in r.get("Attributes", []) if str(x).strip())
                    if isinstance(r.get("Attributes", []), (list, tuple, set))
                    else attributes_from_text(str(r.get("Attributes", "")))
                ),
                equipment=equipment_from_text(equipment_text),
                m_skill_count=int(r.get("M Skills", 0) or 0),
                test_time_minutes=float(
                    r.get("Test Time (min)", r.get("Test Distance", 999)) or 999
                ),
                routing_mode=str(r.get("Routing Mode", "manual") or "manual").lower(),
                route_distance_miles=(
                    None if pd.isna(r.get("Route Distance Miles", None))
                    else float(r.get("Route Distance Miles"))
                ),
                route_time_seconds=(
                    None if pd.isna(r.get("Route Time Seconds", None))
                    else float(r.get("Route Time Seconds"))
                ),
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


def _route_ready(unit: ScenarioUnit) -> bool:
    if unit.routing_mode != "osm":
        return True
    return unit.route_distance_miles is not None and unit.route_time_seconds is not None


def _time_for_limit_minutes(unit: ScenarioUnit) -> float:
    # CAD ALPHA "Max Distance 10" is operationally a 10-minute threshold.
    # In OSM mode, use calculated network travel time. In manual mode, use
    # the user-entered test time in minutes.
    if unit.routing_mode == "osm" and unit.route_time_seconds is not None:
        return unit.route_time_seconds / 60.0
    return unit.test_time_minutes


def _ordering_value(unit: ScenarioUnit) -> float:
    # Candidate selection uses travel time. OSM mode uses calculated seconds;
    # manual mode uses the entered test time.
    if unit.routing_mode == "osm" and unit.route_time_seconds is not None:
        return unit.route_time_seconds
    return unit.test_time_minutes * 60.0


def _routing_trace(unit: ScenarioUnit) -> str:
    if unit.routing_mode == "osm" and unit.route_distance_miles is not None and unit.route_time_seconds is not None:
        total = int(round(unit.route_time_seconds))
        minutes, seconds = divmod(total, 60)
        return f" | route={unit.route_distance_miles:.2f} mi, eta={minutes}:{seconds:02d}"
    return f" | test time={unit.test_time_minutes:.2f} min"


def choose_for_requirement(
    req_name: str,
    units: list[ScenarioUnit],
    state: SimulationState,
    *,
    max_time_minutes: float | None = None,
) -> tuple[ScenarioUnit | None, list[str]]:
    req = REQUIREMENTS[req_name]
    candidates = []
    for u in units:
        if u.unit_id in state.consumed_units:
            continue
        if not _route_ready(u):
            continue
        if max_time_minutes is not None and _time_for_limit_minutes(u) > max_time_minutes:
            continue
        ok, reasons = qualifies(u, req)
        if ok:
            candidates.append((_ordering_value(u), u.unit_id, u, reasons))
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
            if not _route_ready(u):
                continue
            ok, reasons = qualifies(u, req)
            if ok:
                # OSM mode ranks by estimated travel time. Manual mode ranks by
                # Test Distance. Requirement order breaks equal-routing ties.
                candidates.append((_ordering_value(u), alt_order, u.unit_id, req_name, u, reasons))
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
                step.requirement, units, state, max_time_minutes=step.max_time_minutes
            )
            if unit:
                state.assignments.append(
                    Assignment(
                        step.number,
                        step.requirement,
                        unit.unit_id,
                        sequence=len(state.assignments) + 1,
                        display_order=step.display_order,
                    )
                )
                max_note = (
                    f" within {step.max_time_minutes:g}-minute threshold"
                    if step.max_time_minutes is not None else ""
                )
                state.trace.append(
                    f"{step.requirement}: selected {unit.unit_id}{max_note} — "
                    + "; ".join(reasons)
                    + _routing_trace(unit)
                )
                current = step.yes_step if step.yes_step is not None else step.next_step
            else:
                state.trace.append(
                    f"{step.requirement}: no eligible unconsumed unit"
                    + (
                        f" within {step.max_time_minutes:g}-minute threshold"
                        if step.max_time_minutes is not None else ""
                    )
                )
                current = step.no_step if step.no_step is not None else step.next_step
            continue

        if step.kind == "GROUP":
            req_name, unit, reasons = choose_for_group(step.alternatives, units, state)
            if unit:
                state.assignments.append(
                    Assignment(
                        step.number,
                        req_name,
                        unit.unit_id,
                        sequence=len(state.assignments) + 1,
                        display_order=step.display_order,
                    )
                )
                state.trace.append(
                    f"GROUP selected {unit.unit_id} via {req_name} — "
                    + "; ".join(reasons)
                    + _routing_trace(unit)
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



def assignments_in_dispatch_order(state: SimulationState) -> list[Assignment]:
    """Return recommendations in response-plan display/dispatch order.

    Explicit CADDBM Display Order values are honored first. Items without an
    explicit Display Order retain their response-plan recommendation sequence.
    Routing ETA never controls the displayed recommendation sequence.
    """
    explicit = [a for a in state.assignments if a.display_order is not None]
    implicit = [a for a in state.assignments if a.display_order is None]

    explicit.sort(key=lambda a: (a.display_order, a.sequence))
    implicit.sort(key=lambda a: a.sequence)

    return explicit + implicit

def pair_conflicts(frame: pd.DataFrame) -> list[tuple[str, str]]:
    """Find simultaneous base/M-suffix unit pairs without exposing a Pair Unit column.

    Examples:
      E421 + E421M
      E421B + E421BM
      TT425 + TT425M
      HM401 + HM401M
    """
    selected = set(frame["Unit ID"].astype(str))
    pairs: set[tuple[str, str]] = set()

    for uid in selected:
        if uid.endswith("M") and len(uid) > 1:
            base = uid[:-1]
            if base in selected:
                pairs.add((base, uid))

    return sorted(pairs)

