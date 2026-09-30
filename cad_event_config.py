from __future__ import annotations

from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
EVENT_PLAN_FILE = DATA_DIR / "event_type_plan_map.csv"
EVENT_TYPES_FILE = DATA_DIR / "event_types_fire.csv"


def load_event_plan_map() -> pd.DataFrame:
    df = pd.read_csv(EVENT_PLAN_FILE, dtype=str).fillna("")
    df["operational_condition"] = df["operational_condition"].astype(str)
    return df


def load_event_types() -> pd.DataFrame:
    return pd.read_csv(EVENT_TYPES_FILE, dtype=str).fillna("")


def operational_conditions(df: pd.DataFrame | None = None) -> list[dict]:
    df = load_event_plan_map() if df is None else df
    out = (
        df[["operational_condition", "condition_name"]]
        .drop_duplicates()
        .sort_values("operational_condition")
    )
    return out.to_dict("records")


def event_types_for_condition(
    operational_condition: str,
    df: pd.DataFrame | None = None,
) -> list[dict]:
    df = load_event_plan_map() if df is None else df
    view = df[df["operational_condition"] == str(operational_condition)]
    out = view[["event_type", "description", "response_plan_id"]].drop_duplicates().sort_values("event_type")
    return out.to_dict("records")


def resolve_response_plan(
    event_type: str,
    operational_condition: str,
    df: pd.DataFrame | None = None,
) -> dict:
    df = load_event_plan_map() if df is None else df
    match = df[
        (df["event_type"] == str(event_type))
        & (df["operational_condition"] == str(operational_condition))
    ]
    if match.empty:
        raise KeyError(
            f"No response-plan mapping for event type {event_type} "
            f"under operational condition {operational_condition}."
        )
    return match.iloc[0].to_dict()


def response_plan_changes_by_condition(
    event_type: str,
    df: pd.DataFrame | None = None,
) -> bool:
    df = load_event_plan_map() if df is None else df
    plans = {
        p for p in df.loc[df["event_type"] == str(event_type), "response_plan_id"].astype(str)
        if p
    }
    return len(plans) > 1
