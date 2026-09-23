from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PlanStep:
    number: int
    kind: str  # REQUIREMENT | GROUP | CONDITION | STOP
    label: str
    requirement: Optional[str] = None
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    yes_step: Optional[int] = None
    no_step: Optional[int] = None
    next_step: Optional[int] = None
    max_distance: Optional[float] = None
    display_order: Optional[int] = None


# Transcribed from the user-provided current ALPHA response-plan flowchart.
# Hatched/blank branches are modeled as pass-through paths.
ALPHA_STEPS: dict[int, PlanStep] = {
    1: PlanStep(
        1, "REQUIREMENT", "Initial medic (Max Distance 10)",
        requirement="M", yes_step=3, no_step=2, max_distance=10.0
    ),
    2: PlanStep(
        2, "GROUP", "Fallback if initial M cannot be recommended",
        alternatives=("M", "ALS CHASE CAR", "EMS"), next_step=3
    ),
    3: PlanStep(
        3, "CONDITION", "M Recommended?", requirement="M",
        yes_step=5, no_step=4
    ),
    4: PlanStep(
        4, "GROUP", "Add transport-capable unit if M is still not recommended",
        alternatives=("M", "A"), next_step=5
    ),
    5: PlanStep(
        5, "CONDITION", "CHASE CAR Recommended?", requirement="CHASE CAR",
        yes_step=6, no_step=7
    ),
    6: PlanStep(
        6, "GROUP", "Resource group when chase-car capability is already present",
        alternatives=("AFR1", "AFR2", "E", "T", "TL", "TT", "R", "HM401", "HM401M"),
        next_step=8, display_order=1
    ),
    7: PlanStep(
        7, "GROUP", "Resource group when chase-car capability is not yet present",
        alternatives=("AFR1", "AFR2", "ALS CHASE CAR", "EMS COUNTY", "E", "T", "TL", "TT", "R", "HM401", "HM401M"),
        next_step=8, display_order=1
    ),
    8: PlanStep(
        8, "CONDITION", "ALS_SKILL Recommended?", requirement="ALS_SKILL",
        yes_step=10, no_step=9
    ),
    9: PlanStep(
        9, "GROUP", "Add ALS capability when ALS_SKILL is not yet satisfied",
        alternatives=("ALS CHASE CAR", "EMS", "AFR1", "AFR2"), next_step=10
    ),
    10: PlanStep(
        10, "CONDITION", "SUPPRESSION UNIT Recommended?", requirement="SUPPRESSION UNIT",
        yes_step=12, no_step=11
    ),
    11: PlanStep(
        11, "GROUP", "Add suppression resource",
        alternatives=("AFR1", "AFR2", "E", "T", "TL", "TT", "R", "HM401", "HM401M"),
        next_step=12
    ),
    12: PlanStep(12, "STOP", "End"),
}
