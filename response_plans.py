from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
ITEMS_FILE = DATA_DIR / "cad_response_plan_items.csv.gz"
META_FILE = DATA_DIR / "cad_response_plan_meta.csv"
ALARM_FILE = DATA_DIR / "event_alarm_levels.csv"

ITEM_TYPE_NAMES = {
    0: "Connector / no-action",
    1: "Requirement Group",
    2: "Condition",
    3: "Referenced Response Plan",
}

# The supplied ALPHA configuration confirms condition type 1 is a
# requirement-based condition. Type 2 is retained separately because its exact
# Assigned-vs-Recommended label has not yet been confirmed from CADDBM.
CONDITION_TYPE_NAMES = {
    0: "Not a condition",
    1: "Requirement condition",
    2: "Requirement condition (type 2)",
}

RECOMMEND_MODE_NAMES = {
    1: "Street Network",
    2: "Beats",
    3: "Use Default",
}


def _int(value, default=0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _float_or_none(value):
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PlanAlternative:
    requirement: str
    order: int
    quantity: int
    display_order: int | None
    max_route: float | None
    recommend_mode_raw: int
    recommend_mode: str
    max_beat: int
    alt_unit_count: int
    equivalent_delta: float | None
    role_designator: str


@dataclass(frozen=True)
class PlanItem:
    item_id: int
    item_type: int
    item_type_name: str
    cond_type: int
    condition_type_name: str
    alternatives: tuple[PlanAlternative, ...]
    plan_ref: str
    success_item_id: int
    failure_item_id: int
    item_row: int
    item_col: int
    comment: str
    param_name: str
    param_value: str
    unit_statuses: str

    @property
    def next_item_id(self) -> int:
        if self.success_item_id == self.failure_item_id:
            return self.success_item_id
        return 0


@dataclass(frozen=True)
class ResponsePlan:
    name: str
    resp_type: int
    is_ad_hoc: bool
    items: dict[int, PlanItem]


@lru_cache(maxsize=1)
def load_response_plan_items() -> pd.DataFrame:
    return pd.read_csv(ITEMS_FILE, dtype=str).fillna("")


@lru_cache(maxsize=1)
def load_response_plan_meta() -> pd.DataFrame:
    df = pd.read_csv(META_FILE, dtype=str).fillna("")
    df["is_ad_hoc"] = df["is_ad_hoc"].astype(str).str.lower().eq("true")
    return df


@lru_cache(maxsize=1)
def load_alarm_levels() -> pd.DataFrame:
    df = pd.read_csv(ALARM_FILE, dtype=str).fillna("")
    df["alarm_level"] = pd.to_numeric(df["alarm_level"], errors="coerce").fillna(0).astype(int)
    return df


def alarm_levels_for_event(event_type: str, df: pd.DataFrame | None = None) -> list[dict]:
    df = load_alarm_levels() if df is None else df
    view = df[df["event_type"] == str(event_type)].sort_values("alarm_level")
    return view.to_dict("records")


def next_alarm_for_event(event_type: str, current_alarm_level: int, df: pd.DataFrame | None = None) -> dict | None:
    rows = alarm_levels_for_event(event_type, df)
    for row in rows:
        if int(row["alarm_level"]) > int(current_alarm_level):
            return row
    return None


def ad_hoc_plan_names(meta: pd.DataFrame | None = None) -> list[str]:
    meta = load_response_plan_meta() if meta is None else meta
    return sorted(meta.loc[meta["is_ad_hoc"], "resp_plan_name"].astype(str).tolist())


def get_response_plan(name: str, items_df: pd.DataFrame | None = None, meta_df: pd.DataFrame | None = None) -> ResponsePlan:
    items_df = load_response_plan_items() if items_df is None else items_df
    meta_df = load_response_plan_meta() if meta_df is None else meta_df
    view = items_df[items_df["resp_plan_name"] == str(name)]
    if view.empty:
        raise KeyError(f"Unknown response plan: {name}")

    meta_match = meta_df[meta_df["resp_plan_name"] == str(name)]
    resp_type = _int(meta_match.iloc[0]["resp_type"] if not meta_match.empty else view.iloc[0].get("resp_type", 0))
    is_ad_hoc = bool(meta_match.iloc[0]["is_ad_hoc"]) if not meta_match.empty else resp_type == 1

    items: dict[int, PlanItem] = {}
    for item_id, group in view.groupby("item_id", sort=False):
        group = group.copy()
        group["_req_order"] = pd.to_numeric(group["req_number"], errors="coerce").fillna(0)
        group = group.sort_values("_req_order")
        first = group.iloc[0]
        alternatives: list[PlanAlternative] = []
        for _, row in group.iterrows():
            req_name = str(row.get("req_name", "")).strip()
            if not req_name:
                continue
            display_order_raw = _int(row.get("req_display_order", 0))
            alternatives.append(
                PlanAlternative(
                    requirement=req_name,
                    order=_int(row.get("req_number", 0)),
                    quantity=max(1, _int(row.get("req_quan", 1))),
                    display_order=(display_order_raw if display_order_raw > 0 else None),
                    max_route=_float_or_none(row.get("req_max_route", "")),
                    recommend_mode_raw=_int(row.get("recommend_mode", 3), 3),
                    recommend_mode=RECOMMEND_MODE_NAMES.get(_int(row.get("recommend_mode", 3), 3), f"Raw {_int(row.get('recommend_mode', 3), 3)}"),
                    max_beat=_int(row.get("req_max_beat", 0)),
                    alt_unit_count=_int(row.get("alt_unit_count", 0)),
                    equivalent_delta=_float_or_none(row.get("equivalent_delta", "")),
                    role_designator=str(row.get("role_designator", "")).strip(),
                )
            )
        item_type = _int(first.get("item_type", 0))
        cond_type = _int(first.get("cond_type", 0))
        items[_int(item_id)] = PlanItem(
            item_id=_int(item_id),
            item_type=item_type,
            item_type_name=ITEM_TYPE_NAMES.get(item_type, f"Raw type {item_type}"),
            cond_type=cond_type,
            condition_type_name=CONDITION_TYPE_NAMES.get(cond_type, f"Raw condition {cond_type}"),
            alternatives=tuple(alternatives),
            plan_ref=str(first.get("plan_ref", "")).strip(),
            success_item_id=_int(first.get("success_item_id", 0)),
            failure_item_id=_int(first.get("failure_item_id", 0)),
            item_row=_int(first.get("item_row", 0)),
            item_col=_int(first.get("item_col", 0)),
            comment=str(first.get("comm", "")).strip(),
            param_name=str(first.get("param_name", "")).strip(),
            param_value=str(first.get("param_value", "")).strip(),
            unit_statuses=str(first.get("unit_statuses", "")).strip(),
        )

    return ResponsePlan(name=str(name), resp_type=resp_type, is_ad_hoc=is_ad_hoc, items=items)


def plan_flow_rows(name: str, items_df: pd.DataFrame | None = None, meta_df: pd.DataFrame | None = None) -> list[dict]:
    plan = get_response_plan(name, items_df, meta_df)
    rows: list[dict] = []
    for item_id in sorted(plan.items):
        item = plan.items[item_id]
        rows.append({
            "Item": item_id,
            "Type": item.item_type_name,
            "Condition Type": item.condition_type_name if item.item_type == 2 else "",
            "Requirements": " OR ".join(a.requirement for a in item.alternatives),
            "Referenced Plan": item.plan_ref,
            "Yes / Success": item.success_item_id or "",
            "No / Failure": item.failure_item_id or "",
            "Display Order": ", ".join(str(a.display_order) for a in item.alternatives if a.display_order is not None),
            "Recommend Mode": ", ".join(dict.fromkeys(a.recommend_mode for a in item.alternatives)),
        })
    return rows
