from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import pandas as pd

from cad_requirements import REQUIREMENTS, Requirement, RequirementLine
from cad_alpha_plan import ALPHA_STEPS, PlanStep
from cad_response_plans import get_response_plan
from cad_catalog import attributes_from_text, equipment_from_text


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
    source_plan: str = ""
    source_kind: str = "Initial"
    batch_id: int = 0


@dataclass
class SimulationState:
    assignments: list[Assignment] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    applied_plans: list[tuple[str, str]] = field(default_factory=list)

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
    """Return recommendations in plan display order while preserving incident batches.

    Within each applied response-plan batch, explicit CADDBM Display Order values
    are honored first. Separate post-dispatch alarm/ad-hoc batches remain after
    earlier incident recommendations and are never moved ahead of the initial
    dispatch merely because they use a low Display Order value.
    """
    result: list[Assignment] = []
    batches = sorted({getattr(a, "batch_id", 0) for a in state.assignments})
    for batch_id in batches:
        batch = [a for a in state.assignments if getattr(a, "batch_id", 0) == batch_id]
        explicit = [a for a in batch if a.display_order is not None]
        implicit = [a for a in batch if a.display_order is None]
        explicit.sort(key=lambda a: (a.display_order, a.sequence))
        implicit.sort(key=lambda a: a.sequence)
        result.extend(explicit + implicit)
    return result


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



class UnsupportedConfigurationError(RuntimeError):
    pass


def _line_as_requirement(line: RequirementLine) -> Requirement:
    return Requirement(
        name=f"line {line.line_number}",
        quantity=line.quantity,
        unit_type=line.unit_type,
        unit_id=line.unit_id,
        station=line.station,
        attributes=line.attributes,
        attribute_mode=line.attribute_mode,
        equipment=line.equipment,
        skills=line.skills,
        beat_option=line.beat_option,
        specified_beat=line.specified_beat,
        skill_option=line.skill_option,
        equipment_skill_option=line.equipment_skill_option,
        unresolved_attribute_mask=line.unresolved_attribute_mask,
        lines=(line,),
    )


def _unit_matches_line(unit: ScenarioUnit, line: RequirementLine, *, incident_beat: str = "") -> tuple[bool, list[str]]:
    if line.unresolved_attribute_mask:
        raise UnsupportedConfigurationError(
            f"Requirement attribute mask {line.unresolved_attribute_mask} has not yet been decoded."
        )

    if line.unit_id and unit.unit_id != line.unit_id:
        return False, [f"Unit ID {unit.unit_id} != {line.unit_id}"]
    if line.unit_type and unit.unit_type != line.unit_type:
        return False, [f"Unit Type {unit.unit_type} != {line.unit_type}"]
    if line.station and unit.station_id != line.station:
        return False, [f"Station {unit.station_id} != {line.station}"]

    reasons: list[str] = []
    if line.unit_id:
        reasons.append(f"Unit ID {unit.unit_id}")
    if line.unit_type:
        reasons.append(f"Unit Type {unit.unit_type}")
    if line.station:
        reasons.append(f"Station {unit.station_id}")

    if line.attributes:
        matches = [a for a in line.attributes if a in unit.attributes]
        if line.attribute_mode.upper() == "ANY":
            if not matches:
                return False, [f"no required attribute present: {', '.join(line.attributes)}"]
            reasons.append(f"attribute {', '.join(matches)}")
        else:
            missing = [a for a in line.attributes if a not in unit.attributes]
            if missing:
                return False, [f"missing attributes: {', '.join(missing)}"]
            reasons.append(f"attributes {', '.join(line.attributes)}")

    if line.equipment:
        missing = [e for e in line.equipment if unit.equipment.get(e, 0) < 1]
        if missing:
            return False, [f"missing equipment: {', '.join(missing)}"]
        reasons.append(f"equipment {', '.join(line.equipment)}")

    if line.skills:
        if set(line.skills) == {"M"}:
            if unit.m_skill_count < 1:
                return False, ["no personnel skill M"]
            reasons.append(f"M skill={unit.m_skill_count}")
        else:
            raise UnsupportedConfigurationError(
                f"Personnel skills {', '.join(line.skills)} are present in CAD data; v0.10 models M only."
            )

    if line.beat_option == "SPECIFIED" and line.specified_beat:
        if unit.beat != line.specified_beat:
            return False, [f"Beat {unit.beat} != specified beat {line.specified_beat}"]
        reasons.append(f"specified beat {line.specified_beat}")
    elif line.beat_option == "PRIMARY":
        if not incident_beat:
            raise UnsupportedConfigurationError(
                "This requirement uses Primary Beat. Enter an Incident Beat to evaluate it."
            )
        if unit.beat != incident_beat:
            return False, [f"Beat {unit.beat} != incident beat {incident_beat}"]
        reasons.append(f"primary beat {incident_beat}")
    elif line.beat_option == "BACKUP":
        raise UnsupportedConfigurationError(
            "Backup Beat recommendation is present in CAD data but has not yet been modeled in CADence."
        )

    return True, reasons


def _selected_units(state: SimulationState, unit_by_id: dict[str, ScenarioUnit]) -> list[ScenarioUnit]:
    seen: set[str] = set()
    result: list[ScenarioUnit] = []
    for assignment in state.assignments:
        if assignment.unit_id in seen:
            continue
        unit = unit_by_id.get(assignment.unit_id)
        if unit is not None:
            seen.add(unit.unit_id)
            result.append(unit)
    return result


def _line_satisfied_by_existing(
    line: RequirementLine,
    needed: int,
    selected: list[ScenarioUnit],
    *,
    incident_beat: str = "",
) -> tuple[bool, str]:
    # M is modeled as a personnel capability and may be aggregated across units
    # when CAD's resource option allows Any Unit.
    if line.skills and set(line.skills) == {"M"} and line.equipment_skill_option == "ANY_UNIT":
        total = sum(u.m_skill_count for u in selected)
        return total >= needed, f"required={needed} M; available={total}"

    matches: list[str] = []
    for unit in selected:
        ok, _ = _unit_matches_line(unit, line, incident_beat=incident_beat)
        if ok:
            matches.append(unit.unit_id)
    return len(matches) >= needed, f"required={needed}; existing={', '.join(matches) if matches else 'none'}"


def requirement_satisfied_by_incident(
    req_name: str,
    state: SimulationState,
    units: list[ScenarioUnit],
    *,
    multiplier: int = 1,
    incident_beat: str = "",
) -> tuple[bool, str]:
    req = REQUIREMENTS.get(req_name)
    if req is None:
        raise UnsupportedConfigurationError(f"Requirement {req_name} is not present in the imported DEFINE REQUIREMENT table.")
    unit_by_id = {u.unit_id: u for u in units}
    selected = _selected_units(state, unit_by_id)
    details: list[str] = []
    for line in req.lines or ():
        needed = max(1, line.quantity * max(1, multiplier))
        satisfied, detail = _line_satisfied_by_existing(
            line, needed, selected, incident_beat=incident_beat
        )
        details.append(f"line {line.line_number}: {detail}")
        if not satisfied:
            return False, "; ".join(details)
    return True, "; ".join(details)


def _preview_requirement_additions(
    req_name: str,
    units: list[ScenarioUnit],
    state: SimulationState,
    *,
    multiplier: int = 1,
    max_time_minutes: float | None = None,
    incident_beat: str = "",
) -> tuple[list[tuple[ScenarioUnit, list[str]]], list[str]]:
    req = REQUIREMENTS.get(req_name)
    if req is None:
        raise UnsupportedConfigurationError(f"Requirement {req_name} is not present in the imported DEFINE REQUIREMENT table.")

    unit_by_id = {u.unit_id: u for u in units}
    selected = _selected_units(state, unit_by_id)
    reserved = set(state.consumed_units)
    additions: list[tuple[ScenarioUnit, list[str]]] = []
    detail: list[str] = []

    for line in req.lines or ():
        needed = max(1, line.quantity * max(1, multiplier))
        satisfied, existing_detail = _line_satisfied_by_existing(
            line, needed, selected, incident_beat=incident_beat
        )
        # Existing response slots can satisfy a pure equipment/skill capability
        # requirement without consuming the same physical unit in another slot.
        pure_capability = bool(line.equipment or line.skills) and not (
            line.unit_type or line.unit_id or line.station or line.attributes
        )
        if satisfied and pure_capability:
            detail.append(f"line {line.line_number} already satisfied: {existing_detail}")
            continue

        # Response/resource slots are exclusive. Existing incident units may
        # satisfy conditions and pure equipment/skill capability checks, but a
        # previously consumed physical unit cannot fill a new non-capability
        # response slot a second time.
        remaining = needed

        for _ in range(remaining):
            candidates = []
            for unit in units:
                if unit.unit_id in reserved:
                    continue
                if not _route_ready(unit):
                    continue
                if max_time_minutes is not None and _time_for_limit_minutes(unit) > max_time_minutes:
                    continue
                ok, reasons = _unit_matches_line(unit, line, incident_beat=incident_beat)
                if ok:
                    candidates.append((_ordering_value(unit), unit.unit_id, unit, reasons))
            if not candidates:
                return [], detail + [f"line {line.line_number}: no eligible unconsumed unit"]
            candidates.sort(key=lambda x: (x[0], x[1]))
            _, _, chosen, reasons = candidates[0]
            additions.append((chosen, reasons))
            reserved.add(chosen.unit_id)
            selected.append(chosen)
        detail.append(f"line {line.line_number}: selected {remaining} new unit(s)")

    return additions, detail


def simulate_response_plan(
    plan_name: str,
    units: list[ScenarioUnit],
    *,
    state: SimulationState | None = None,
    source_kind: str = "Initial",
    incident_beat: str = "",
    _stack: tuple[str, ...] = (),
    _batch_id: int | None = None,
) -> SimulationState:
    """Execute an imported CAD response-plan graph against the current incident state.

    v0.10 supports requirement groups, requirement conditions, connector/no-action
    nodes, and nested response plans. Unknown attribute bits and unmodeled beat
    semantics fail explicitly rather than being silently ignored.
    """
    if plan_name in _stack:
        raise RuntimeError(f"Nested response-plan loop detected: {' -> '.join(_stack + (plan_name,))}")
    if len(_stack) > 25:
        raise RuntimeError("Nested response-plan depth exceeded 25")

    plan = get_response_plan(plan_name)
    if state is None:
        state = SimulationState()
    if _batch_id is None:
        _batch_id = max((getattr(a, "batch_id", 0) for a in state.assignments), default=-1) + 1
    state.applied_plans.append((source_kind, plan_name))
    state.trace.append(f"=== {source_kind.upper()} PLAN {plan_name} ===")

    if not plan.items:
        state.trace.append("Plan contains no items.")
        return state

    current = min(plan.items)
    guard = 0
    while current:
        guard += 1
        if guard > 500:
            raise RuntimeError(f"{plan_name} exceeded 500 plan items; possible flow loop")
        item = plan.items.get(current)
        if item is None:
            raise RuntimeError(f"{plan_name} references missing item {current}")

        state.trace.append(f"{plan_name} ITEM {item.item_id}: {item.item_type_name}")

        if item.item_type == 0:
            current = item.next_item_id
            continue

        if item.item_type == 3:
            if item.plan_ref:
                simulate_response_plan(
                    item.plan_ref, units, state=state, source_kind=f"Nested from {plan_name}",
                    incident_beat=incident_beat, _stack=_stack + (plan_name,), _batch_id=_batch_id,
                )
            current = item.next_item_id
            continue

        if item.item_type == 2:
            if not item.alternatives:
                result, detail = False, "condition has no requirement"
            else:
                alt = item.alternatives[0]
                result, detail = requirement_satisfied_by_incident(
                    alt.requirement, state, units, multiplier=alt.quantity, incident_beat=incident_beat
                )
            req_label = item.alternatives[0].requirement if item.alternatives else "(none)"
            state.trace.append(
                f"CONDITION {req_label}: {'YES' if result else 'NO'} — {detail} "
                f"[cond_type={item.cond_type}]"
            )
            current = item.success_item_id if result else item.failure_item_id
            continue

        if item.item_type == 1:
            previews = []
            for alt in item.alternatives:
                try:
                    additions, detail = _preview_requirement_additions(
                        alt.requirement, units, state, multiplier=alt.quantity,
                        max_time_minutes=alt.max_route if alt.max_route and alt.max_route > 0 else None,
                        incident_beat=incident_beat,
                    )
                except UnsupportedConfigurationError:
                    raise
                if additions or any("already satisfied" in d for d in detail):
                    first_score = min((_ordering_value(u) for u, _ in additions), default=-1.0)
                    previews.append((first_score, alt.order, alt, additions, detail))

            if not previews:
                state.trace.append("REQUIREMENT GROUP FAILED — no eligible alternative")
                current = item.failure_item_id
                continue

            previews.sort(key=lambda x: (x[0], x[1]))
            _, _, chosen_alt, additions, detail = previews[0]
            if additions:
                for unit, reasons in additions:
                    state.assignments.append(
                        Assignment(
                            item.item_id, chosen_alt.requirement, unit.unit_id,
                            sequence=len(state.assignments) + 1,
                            display_order=chosen_alt.display_order,
                            source_plan=plan_name, source_kind=source_kind, batch_id=_batch_id,
                        )
                    )
                    state.trace.append(
                        f"GROUP selected {unit.unit_id} via {chosen_alt.requirement} — "
                        + "; ".join(reasons) + _routing_trace(unit)
                    )
            else:
                state.trace.append(
                    f"GROUP {chosen_alt.requirement} satisfied by existing incident capability — "
                    + "; ".join(detail)
                )
            current = item.success_item_id
            continue

        raise UnsupportedConfigurationError(
            f"Response plan {plan_name} uses unsupported item_type {item.item_type}."
        )

    state.trace.append(f"=== END {plan_name} ===")
    return state
