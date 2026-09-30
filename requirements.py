from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFINE_FILE = DATA_DIR / "cad_define_requirement.csv"
RESOURCE_FILE = DATA_DIR / "cad_requirement_resources.csv"

ZERO_MASK = "0x" + "0" * 64

# Attribute bits confirmed from the raw DEFINE REQUIREMENT data and previously
# validated CADDBM examples. Unknown bits are preserved rather than guessed.
KNOWN_ATTRIBUTE_BITS: dict[int, str] = {
    int("0x0000010000000000000000000000000000000000000000000000000000000000", 16): "TRUCK",
    int("0x0200000000000000000000000000000000000000000000000000000000000000", 16): "RESCUE",
    int("0x4000000000000000000000000000000000000000000000000000000000000000", 16): "COUNTY",
    int("0x2000000000000000000000000000000000000000000000000000000000000000", 16): "CITY",
    int("0x0400000000000000000000000000000000000000000000000000000000000000", 16): "HAZMAT",
    int("0x0000000200000000000000000000000000000000000000000000000000000000", 16): "BALLISTIC",
    int("0x0000001000000000000000000000000000000000000000000000000000000000", 16): "CHASE CAR",
    int("0x0000000800000000000000000000000000000000000000000000000000000000", 16): "EXTRICATION",
    int("0x0000000400000000000000000000000000000000000000000000000000000000", 16): "COMMAND BC",
    int("0x0020000000000000000000000000000000000000000000000000000000000000", 16): "FDU",
    int("0x0010000000000000000000000000000000000000000000000000000000000000", 16): "TRANSPORT",
    int("0x0000080000000000000000000000000000000000000000000000000000000000", 16): "HEAVY",
    int("0x0080000000000000000000000000000000000000000000000000000000000000", 16): "BLOODHOUND",
}


def decode_attribute_mask(mask: str) -> tuple[tuple[str, ...], str]:
    mask = str(mask or "").strip()
    if not mask or mask == ZERO_MASK:
        return (), ""
    try:
        value = int(mask, 16)
    except ValueError:
        return (), mask

    names: list[str] = []
    remaining = value
    for bit, name in KNOWN_ATTRIBUTE_BITS.items():
        if value & bit:
            names.append(name)
            remaining &= ~bit
    unresolved = "" if remaining == 0 else f"0x{remaining:064X}"
    return tuple(names), unresolved


def _int(value, default=0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RequirementLine:
    line_number: int
    quantity: int = 1
    unit_type: Optional[str] = None
    unit_id: Optional[str] = None
    station: Optional[str] = None
    attributes: tuple[str, ...] = field(default_factory=tuple)
    unresolved_attribute_mask: str = ""
    attribute_mode: str = "ALL"
    equipment: tuple[str, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)
    beat_option: str = "ALL"
    specified_beat: Optional[str] = None
    same_beat: bool = False
    skill_option: str = "ANY_PERSON"
    equipment_skill_option: str = "ANY_UNIT"
    route_target: str = "EVENT"
    raw_attribute_mask: str = ZERO_MASK


@dataclass(frozen=True)
class Requirement:
    name: str
    quantity: int = 1
    unit_type: Optional[str] = None
    unit_id: Optional[str] = None
    station: Optional[str] = None
    attributes: tuple[str, ...] = field(default_factory=tuple)
    attribute_mode: str = "ALL"
    equipment: tuple[str, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)
    beat_option: str = "ALL"
    specified_beat: Optional[str] = None
    skill_option: str = "ANY_PERSON"
    equipment_skill_option: str = "ANY_UNIT"
    notes: str = ""
    lines: tuple[RequirementLine, ...] = field(default_factory=tuple)
    unresolved_attribute_mask: str = ""

    @property
    def executable(self) -> bool:
        return all(not line.unresolved_attribute_mask for line in self.lines)


def load_requirement_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    definitions = pd.read_csv(DEFINE_FILE, dtype=str).fillna("")
    resources = pd.read_csv(RESOURCE_FILE, dtype=str).fillna("")
    return definitions, resources


def _build_requirements() -> dict[str, Requirement]:
    definitions, resources = load_requirement_source()
    resource_groups = {
        (str(req_name), _int(line_number)): group
        for (req_name, line_number), group in resources.groupby(["req_name", "line_number"], sort=False)
    }

    result: dict[str, Requirement] = {}
    for req_name, group in definitions.groupby("req_name", sort=False):
        lines: list[RequirementLine] = []
        for _, row in group.sort_values("line_number", key=lambda s: pd.to_numeric(s, errors="coerce")).iterrows():
            line_number = _int(row.get("line_number"))
            attrs, unresolved = decode_attribute_mask(row.get("ext_unitattr", ""))
            linked = resource_groups.get((str(req_name), line_number))
            equipment: list[str] = []
            skills: list[str] = []
            if linked is not None:
                linked = linked.sort_values("res_order", key=lambda s: pd.to_numeric(s, errors="coerce"))
                for _, rr in linked.iterrows():
                    if str(rr.get("res_type", "")) == "1":
                        equipment.append(str(rr.get("res_name", "")).strip())
                    elif str(rr.get("res_type", "")) == "2":
                        skills.append(str(rr.get("res_name", "")).strip())

            beat_code = str(row.get("beat_opt", "0"))
            beat_option = {"0": "ALL", "1": "PRIMARY", "2": "BACKUP", "3": "SPECIFIED"}.get(beat_code, f"RAW_{beat_code}")
            resource_code = str(row.get("resource_restrict", "1"))
            equipment_skill_option = {"0": "SINGLE_UNIT", "1": "ANY_UNIT"}.get(resource_code, f"RAW_{resource_code}")
            skill_code = str(row.get("skill_restrict", "0"))
            skill_option = {"0": "ANY_PERSON"}.get(skill_code, f"RAW_{skill_code}")

            lines.append(
                RequirementLine(
                    line_number=line_number,
                    quantity=max(1, _int(row.get("quan"), 1)),
                    unit_type=str(row.get("unityp", "")).strip() or None,
                    unit_id=str(row.get("unid", "")).strip() or None,
                    station=str(row.get("station", "")).strip() or None,
                    attributes=attrs,
                    unresolved_attribute_mask=unresolved,
                    attribute_mode="ANY" if str(row.get("attr_opt", "0")) == "1" else "ALL",
                    equipment=tuple(e for e in equipment if e),
                    skills=tuple(s for s in skills if s),
                    beat_option=beat_option,
                    specified_beat=str(row.get("lev3", "")).strip() or None,
                    same_beat=str(row.get("same_beat", "0")) == "1",
                    skill_option=skill_option,
                    equipment_skill_option=equipment_skill_option,
                    route_target="EVENT" if str(row.get("route_target", "0")) == "0" else f"RAW_{row.get('route_target')}",
                    raw_attribute_mask=str(row.get("ext_unitattr", ZERO_MASK)),
                )
            )

        first = lines[0]
        notes = ""
        if len(lines) > 1:
            notes = f"Composite CAD requirement with {len(lines)} criteria lines."
        result[str(req_name)] = Requirement(
            name=str(req_name),
            quantity=first.quantity,
            unit_type=first.unit_type,
            unit_id=first.unit_id,
            station=first.station,
            attributes=first.attributes,
            attribute_mode=first.attribute_mode,
            equipment=first.equipment,
            skills=first.skills,
            beat_option=first.beat_option,
            specified_beat=first.specified_beat,
            skill_option=first.skill_option,
            equipment_skill_option=first.equipment_skill_option,
            notes=notes,
            lines=tuple(lines),
            unresolved_attribute_mask=first.unresolved_attribute_mask,
        )
    return result


REQUIREMENTS: dict[str, Requirement] = _build_requirements()
