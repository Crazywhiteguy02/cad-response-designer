from __future__ import annotations
from pathlib import Path
import pandas as pd

CATALOG_PATH = Path(__file__).with_name("data") / "unit_catalog.csv"


def load_catalog() -> pd.DataFrame:
    df = pd.read_csv(CATALOG_PATH, dtype=str).fillna("")
    df["default_m_skill"] = pd.to_numeric(df["default_m_skill"], errors="coerce").fillna(0).astype(int)
    return df


def attributes_from_text(text: str) -> set[str]:
    if not text:
        return set()
    return {x.strip() for x in text.replace(",", ";").split(";") if x.strip()}


def equipment_from_text(text: str) -> dict[str, int]:
    """Parse a simple comma/semicolon list such as 'AFR1, VENT'.

    v0.4 treats each listed equipment code as quantity 1. Quantity editing can be
    added later without changing the recommendation model.
    """
    if not text:
        return {}
    result = {}
    for raw in text.replace(";", ",").split(","):
        code = raw.strip()
        if code:
            result[code] = result.get(code, 0) + 1
    return result
