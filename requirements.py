from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Requirement:
    name: str
    quantity: int = 1
    unit_type: Optional[str] = None
    unit_id: Optional[str] = None
    attributes: tuple[str, ...] = field(default_factory=tuple)
    attribute_mode: str = "ALL"
    equipment: tuple[str, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)
    beat_option: str = "ALL"
    skill_option: str = "ANY_PERSON"
    equipment_skill_option: str = "ANY_UNIT"
    notes: str = ""


REQUIREMENTS: dict[str, Requirement] = {
    "M": Requirement("M", unit_type="M"),
    "A": Requirement("A", unit_type="A"),
    "A FIRST DUE": Requirement("A FIRST DUE", unit_type="A", beat_option="PRIMARY"),
    "CHASE CAR": Requirement("CHASE CAR", attributes=("CHASE CAR",)),
    "ALS CHASE CAR": Requirement("ALS CHASE CAR", unit_type="ALS"),
    "EMS": Requirement("EMS", unit_type="EMS", equipment_skill_option="SINGLE_UNIT"),
    "EMS COUNTY": Requirement(
        "EMS COUNTY", unit_type="EMS", attributes=("COUNTY",),
        equipment_skill_option="SINGLE_UNIT"
    ),
    "E": Requirement("E", unit_type="E"),
    "T": Requirement("T", attributes=("TRUCK",)),
    "TL": Requirement("TL", unit_type="TL", attributes=("TRUCK",)),
    "TT": Requirement("TT", unit_type="TT", attributes=("TRUCK",)),
    "R": Requirement("R", attributes=("RESCUE",), attribute_mode="ANY"),
    "AFR1": Requirement("AFR1", equipment=("AFR1",), equipment_skill_option="SINGLE_UNIT"),
    "AFR2": Requirement("AFR2", equipment=("AFR2",), equipment_skill_option="SINGLE_UNIT"),
    "ALS_SKILL": Requirement(
        "ALS_SKILL", quantity=2, skills=("M",),
        skill_option="ANY_PERSON", equipment_skill_option="ANY_UNIT",
        notes="Two rostered personnel with skill M; may be supplied across recommended units."
    ),
    "SUPPRESSION UNIT": Requirement("SUPPRESSION UNIT", attributes=("HEAVY",)),
    "HM401": Requirement("HM401", unit_id="HM401"),
    "HM401M": Requirement("HM401M", unit_id="HM401M"),
    "BC": Requirement("BC", unit_type="BC"),
    "BCCNTY": Requirement("BCCNTY", unit_type="BC", attributes=("COUNTY",)),
    "BCCITY": Requirement("BCCITY", unit_type="BC", attributes=("CITY",)),
}
