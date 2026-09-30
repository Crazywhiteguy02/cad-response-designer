from __future__ import annotations

import math
import html
import pandas as pd
import pydeck as pdk
import streamlit as st

from catalog import load_catalog
from requirements import REQUIREMENTS
from alpha_plan import ALPHA_STEPS
from event_config import (
    load_event_plan_map,
    operational_conditions,
    event_types_for_condition,
    resolve_response_plan,
)
from engine import (
    scenario_units_from_frame,
    simulate_alpha,
    pair_conflicts,
    assignments_in_dispatch_order,
)
from routing import (
    load_station_crosswalk,
    station_record,
    geocode_address,
    parse_lat_lon,
    route_table,
    route_geometry,
    format_duration,
    RoutingError,
)

st.set_page_config(
    page_title="CADence v0.8.0",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --brand-navy: #011340;
        --action-blue: #0162E8;
        --accent-cyan: #00D9FC;
        --neutral-gray: #C0C0C2;
        --charcoal: #24262A;
        --slate-700: #425466;
        --slate-500: #718096;
        --slate-300: #d9e1e8;
        --slate-200: #e7edf2;
        --slate-100: #F7F9FC;
        --surface: #FFFFFF;
        --success-bg: #e8f5ef;
        --success-fg: #236148;
    }

    html, body, [class*="css"] {
        font-family: Montserrat, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-feature-settings: "tnum" 1, "ss01" 1;
    }

    .stApp {
        color: var(--charcoal);
        background:
            radial-gradient(circle at 82% -10%, rgba(0,217,252,.07), transparent 24rem),
            linear-gradient(180deg, #F7F9FC 0%, #F3F6FA 100%);
    }

    .block-container {
        max-width: 1600px;
        padding-top: .8rem;
        padding-bottom: 3rem;
    }

    /* Application bar */
    .appbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: .8rem 1rem .8rem .85rem;
        margin-bottom: .9rem;
        border-radius: 22px;
        background: rgba(255,255,255,.96);
        border: 1px solid rgba(192,192,194,.42);
        box-shadow: 0 8px 26px rgba(1,19,64,.07);
    }

    .brand-wrap {
        display: flex;
        align-items: center;
        gap: .78rem;
        min-width: 0;
    }

    .brand-mark {
        position: relative;
        width: 42px;
        height: 42px;
        border-radius: 14px;
        display: grid;
        place-items: center;
        flex: 0 0 auto;
        background: #F7F9FC;
        border: 1px solid rgba(1,98,232,.12);
        box-shadow: 0 5px 14px rgba(1,19,64,.10);
    }


    .brand-title {
        color: var(--brand-navy);
        font-size: 1.22rem;
        line-height: 1.08;
        font-weight: 800;
    }

    .brand-sub {
        color: var(--slate-500);
        margin-top: .16rem;
        font-size: .78rem;
    }

    .appbar-right {
        display: flex;
        align-items: center;
        gap: .5rem;
        flex-wrap: wrap;
        justify-content: flex-end;
    }

    .app-status {
        border-radius: 999px;
        padding: .28rem .62rem;
        background: #EEF5FF;
        color: #0162E8;
        border: 1px solid #D9E8FF;
        font-size: .73rem;
        font-weight: 700;
        white-space: nowrap;
    }

    .version-chip {
        border-radius: 999px;
        padding: .28rem .62rem;
        background: var(--action-blue);
        color: white;
        border: 1px solid rgba(0,217,252,.24);
        font-size: .72rem;
        font-weight: 760;
        white-space: nowrap;
    }

    /* Primary navigation */
    div[data-baseweb="tab-list"] {
        gap: .15rem;
        background: transparent;
        padding: .1rem .05rem .45rem .05rem;
        border-bottom: 1px solid var(--slate-200);
        margin-bottom: 1rem;
        overflow-x: auto;
    }

    button[data-baseweb="tab"] {
        border-radius: 999px;
        padding: .48rem .9rem;
        font-weight: 700;
        color: #5a6b7b;
        border: 1px solid transparent;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background: var(--brand-navy);
        color: white;
        box-shadow: 0 4px 12px rgba(1,19,64,.12);
    }

    /* Surface cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255,255,255,.96);
        border: 1px solid rgba(192,192,194,.46) !important;
        border-radius: 24px !important;
        box-shadow: 0 10px 30px rgba(11,28,44,.055);
        padding: .12rem;
    }

    .section-kicker {
        color: #007C98;
        font-weight: 800;
        font-size: .67rem;
        letter-spacing: .13em;
        text-transform: uppercase;
        margin-bottom: .12rem;
    }

    .section-title {
        color: var(--brand-navy);
        font-size: 1.18rem;
        font-weight: 790;
        margin-bottom: .1rem;
    }

    .small-muted {
        color: var(--slate-500);
        font-size: .8rem;
    }

    /* Inputs */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        border-radius: 14px !important;
        border-color: var(--slate-300);
        min-height: 2.65rem;
    }

    div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
        border-radius: 999px;
    }

    /* Segmented controls: app-like toggle groups */
    div[data-testid="stSegmentedControl"] {
        margin-top: .1rem;
    }

    div[data-testid="stSegmentedControl"] button {
        border-radius: 999px !important;
        min-height: 2.55rem;
        font-weight: 700;
    }

    /* Metrics */
    div[data-testid="stMetric"] {
        background: #f8fafb;
        border: 0;
        padding: .68rem .84rem;
        border-radius: 16px;
        box-shadow: none;
    }

    div[data-testid="stMetric"] label {
        color: var(--slate-500);
    }

    /* Primary action */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, var(--action-blue), #014FB8);
        border: 0;
        color: white;
        font-weight: 820;
        border-radius: 999px;
        min-height: 3.15rem;
        box-shadow: 0 8px 20px rgba(1,98,232,.22);
        letter-spacing: .01em;
    }

    div[data-testid="stButton"] > button[kind="primary"]:hover {
        filter: brightness(.96);
        box-shadow: 0 10px 24px rgba(1,98,232,.26);
    }

    div[data-testid="stButton"] > button:not([kind="primary"]) {
        border-radius: 999px;
    }

    /* Expanders and data surfaces */
    div[data-testid="stExpander"] {
        background: rgba(248,250,251,.82);
        border: 1px solid rgba(192,192,194,.44);
        border-radius: 18px;
        overflow: hidden;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(192,192,194,.44);
        border-radius: 16px;
        overflow: hidden;
        background: white;
    }

    div[data-testid="stAlert"] {
        border-radius: 16px;
    }

    /* Context ribbon */
    .context-strip {
        display: flex;
        align-items: center;
        gap: .55rem;
        flex-wrap: wrap;
        margin-top: .65rem;
    }

    .context-pill {
        background: #eaf0f4;
        color: var(--action-blue);
        border-radius: 999px;
        padding: .3rem .66rem;
        font-size: .74rem;
        font-weight: 760;
    }

    .context-main {
        color: var(--brand-navy);
        font-size: .95rem;
        font-weight: 820;
    }

    .context-desc {
        color: var(--slate-500);
        font-size: .82rem;
    }

    /* Simulation summary */
    .result-summary {
        display: flex;
        flex-wrap: wrap;
        gap: .5rem;
        margin: .7rem 0 .9rem 0;
    }

    .summary-pill {
        border-radius: 999px;
        padding: .38rem .72rem;
        background: #eef3f6;
        color: var(--slate-700);
        font-size: .78rem;
        font-weight: 700;
    }

    .summary-pill strong {
        color: var(--brand-navy);
        margin-left: .2rem;
    }

    .summary-pill.success {
        background: var(--success-bg);
        color: var(--success-fg);
    }

    /* Dispatch cards */
    .dispatch-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(235px, 1fr));
        gap: .72rem;
        margin-top: .45rem;
    }

    .dispatch-card {
        position: relative;
        min-height: 92px;
        padding: .85rem .9rem .82rem 3.65rem;
        border-radius: 19px;
        background: linear-gradient(155deg, #ffffff, #f8fafb);
        border: 1px solid rgba(192,192,194,.44);
        box-shadow: 0 5px 16px rgba(11,28,44,.045);
    }

    .dispatch-order {
        position: absolute;
        left: .86rem;
        top: .82rem;
        width: 2.15rem;
        height: 2.15rem;
        display: grid;
        place-items: center;
        border-radius: 12px;
        background: var(--brand-navy);
        color: white;
        font-weight: 850;
        font-size: .86rem;
    }

    .dispatch-unit {
        color: var(--brand-navy);
        font-size: 1.08rem;
        line-height: 1.05;
        font-weight: 850;
    }

    .dispatch-req {
        color: var(--action-blue);
        font-size: .73rem;
        font-weight: 780;
        letter-spacing: .02em;
        margin-top: .28rem;
    }

    .dispatch-meta {
        color: var(--slate-500);
        font-size: .74rem;
        margin-top: .32rem;
    }

    .map-shell {
        overflow: hidden;
        border-radius: 20px;
    }

    hr {
        border-color: rgba(192,192,194,.52) !important;
    }

    /* CADence desktop navigation rail */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #011340 0%, #021B4F 100%);
        border-right: 1px solid rgba(0,217,252,.12);
    }

    section[data-testid="stSidebar"] > div {
        padding-top: .8rem;
    }

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: white;
    }

    .sidebar-brand {
        padding: .7rem .55rem 1.05rem .55rem;
        border-bottom: 1px solid rgba(255,255,255,.10);
        margin-bottom: .7rem;
    }

    .sidebar-wordmark {
        font-size: 1.42rem;
        font-weight: 850;
        letter-spacing: -.025em;
        color: #FFFFFF;
    }

    .sidebar-wordmark .cad { color: #00D9FC; }

    .sidebar-tagline {
        margin-top: .2rem;
        color: rgba(255,255,255,.58);
        font-size: .64rem;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: .22rem;
    }

    section[data-testid="stSidebar"] label[data-baseweb="radio"] {
        border-radius: 12px;
        padding: .58rem .68rem;
        color: rgba(255,255,255,.80);
        transition: background .15s ease;
    }

    section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
        background: linear-gradient(135deg, #0162E8, #0756C7);
        color: #FFFFFF;
        box-shadow: 0 6px 16px rgba(1,98,232,.24);
    }

    section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
        display: none;
    }

    .page-eyebrow {
        color: #0162E8;
        font-size: .68rem;
        font-weight: 800;
        letter-spacing: .13em;
        text-transform: uppercase;
    }

    .page-title {
        margin-top: .12rem;
        color: #011340;
        font-size: 1.65rem;
        line-height: 1.1;
        font-weight: 850;
    }

    .page-subtitle {
        margin-top: .28rem;
        color: #718096;
        font-size: .88rem;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .8rem;
        margin: .95rem 0 1rem 0;
    }

    .dashboard-stat {
        position: relative;
        overflow: hidden;
        background: #FFFFFF;
        border: 1px solid rgba(192,192,194,.42);
        border-radius: 18px;
        padding: .95rem 1rem;
        box-shadow: 0 8px 24px rgba(1,19,64,.055);
    }

    .dashboard-stat:before {
        content: "";
        position: absolute;
        left: 0; top: 0; bottom: 0; width: 4px;
        background: #0162E8;
    }

    .dashboard-stat.cyan:before { background: #00D9FC; }
    .dashboard-stat.navy:before { background: #011340; }

    .dashboard-stat .number {
        color: #011340;
        font-size: 1.55rem;
        font-weight: 850;
    }

    .dashboard-stat .label {
        color: #718096;
        font-size: .76rem;
        margin-top: .12rem;
    }

    .plan-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: .8rem .9rem;
        border-radius: 14px;
        background: #F7F9FC;
        border: 1px solid rgba(192,192,194,.36);
    }

    .plan-name { color: #0162E8; font-weight: 800; }
    .plan-desc { color: #718096; font-size: .78rem; margin-top: .12rem; }
    .active-badge {
        background: #E8F5EF; color: #236148; border-radius: 999px;
        padding: .25rem .55rem; font-size: .7rem; font-weight: 800;
    }

    @media (max-width: 1000px) {
        .dashboard-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    /* Phone / narrow layout */
    @media (max-width: 768px) {
        .block-container {
            padding-left: .65rem;
            padding-right: .65rem;
            padding-top: .55rem;
        }

        .appbar {
            border-radius: 18px;
            padding: .7rem;
        }

        .brand-mark {
            width: 38px;
            height: 38px;
            border-radius: 12px;
        }

        .brand-title {
            font-size: 1.02rem;
        }

        .brand-sub {
            display: none;
        }

        .app-status {
            display: none;
        }

        .version-chip {
            font-size: .68rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 20px !important;
        }

        .dispatch-grid {
            grid-template-columns: 1fr;
        }

        .dashboard-grid {
            grid-template-columns: 1fr 1fr;
        }

        button[data-baseweb="tab"] {
            white-space: nowrap;
            padding-left: .72rem;
            padding-right: .72rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="appbar">
      <div class="brand-wrap">
        <div class="brand-mark"><svg viewBox="0 0 64 64" width="34" height="34" aria-label="CADence mark" role="img">
<path d="M48 12 L32 8 L17 18 L11 32 L18 47 L33 55 L49 49" fill="none" stroke="#0162E8" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M48 12 L57 20 M49 49 L57 42" fill="none" stroke="#00D9FC" stroke-width="5" stroke-linecap="round"/>
<circle cx="48" cy="12" r="5" fill="#00D9FC"/><circle cx="11" cy="32" r="5" fill="#0162E8"/><circle cx="33" cy="55" r="5" fill="#00D9FC"/><circle cx="57" cy="20" r="6" fill="#00D9FC"/><circle cx="57" cy="42" r="6" fill="#00D9FC"/>
</svg></div>
        <div>
          <div class="brand-title">CADence</div>
          <div class="brand-sub">Intelligent Response Planning</div>
        </div>
      </div>
      <div class="appbar-right">
        <span class="app-status">Simulation environment</span>
        <span class="version-chip">v0.8.0</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

catalog = load_catalog()
stations = load_station_crosswalk()
event_plan_map = load_event_plan_map()

BEAT_OPTIONS = sorted(
    {str(x).strip() for x in catalog["beat"].tolist() if str(x).strip()}
)
STATION_OPTIONS = sorted(
    {str(x).strip() for x in catalog["station_id"].tolist() if str(x).strip()}
)

# Known equipment codes gathered from the supplied CADDBM screenshots/data.
# The editor also accepts new values so this list does not limit future testing.
EQUIPMENT_OPTIONS = [
    "4X4",
    "4X4PASS",
    "AFR1",
    "AFR2",
    "BLOOD",
    "CAFS",
    "CHAIN SAW",
    "CSU DUTY",
    "DUTY INV",
    "OPS BC",
    "OPS DC",
    "PLOW",
    "RSI",
    "TOW",
    "VENT",
    "WINCH",
]

ATTRIBUTE_OPTIONS = [
    "FOAM",
    "RESCUE",
    "HAZMAT",
    "ENGINE",
    "TROT",
    "CITY",
    "COUNTY",
    "OJ",
    "AR-AFFF",
    "AFFF",
    "ARFF",
    "FOAM-INDUSTRIAL",
    "TRANSPORT",
    "FDU",
    "ALS FIRST RESP",
    "BLOODHOUND",
    "TRUCK",
    "MEDIC",
    "AMBULANCE",
    "HEAVY",
    "FIRE UNITS",
    "AUTO ARRIVE",
    "AVL EQUIPPED",
    "AR-FOAM",
    "FOAM SUPPORT",
    "BALLISTIC",
    "COMMAND BC",
    "EXTRICATION",
    "CHASE CAR",
]

default_units = [
    "M421", "A421", "E426", "E435", "TT425M", "ALS401",
    "EMS401", "HM401M", "BC401", "BC443"
]
default_units = [u for u in default_units if u in set(catalog["unit_id"])]

if "scenario_overrides" not in st.session_state:
    st.session_state.scenario_overrides = {}

if "station_active_overrides" not in st.session_state:
    st.session_state.station_active_overrides = {}

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <div style="display:flex;align-items:center;gap:.55rem;"><div style="width:30px;height:30px;display:grid;place-items:center;"><svg viewBox="0 0 64 64" width="30" height="30" aria-label="CADence mark" role="img">
<path d="M48 12 L32 8 L17 18 L11 32 L18 47 L33 55 L49 49" fill="none" stroke="#0162E8" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M48 12 L57 20 M49 49 L57 42" fill="none" stroke="#00D9FC" stroke-width="5" stroke-linecap="round"/>
<circle cx="48" cy="12" r="5" fill="#00D9FC"/><circle cx="11" cy="32" r="5" fill="#0162E8"/><circle cx="33" cy="55" r="5" fill="#00D9FC"/><circle cx="57" cy="20" r="6" fill="#00D9FC"/><circle cx="57" cy="42" r="6" fill="#00D9FC"/>
</svg></div><div class="sidebar-wordmark"><span class="cad">CAD</span>ence</div></div>
          <div class="sidebar-tagline">Intelligent Response Planning</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Navigation",
        ["Dashboard", "Dispatch Simulator", "Stations", "Units & Resources", "Configuration"],
        label_visibility="collapsed",
        key="cadence_page_v080",
    )
    st.markdown(
        '<div style="margin-top:1rem;color:rgba(255,255,255,.38);font-size:.68rem;">CADence v0.8.0</div>',
        unsafe_allow_html=True,
    )


def _equipment_list_from_saved(saved: dict, default_value="") -> list[str]:
    """Normalize equipment while preserving an intentional empty user override."""
    if "Equipment" in saved:
        value = saved.get("Equipment")
        if isinstance(value, (list, tuple, set)):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]
        return []

    # Migrate v0.4.1 split equipment fields if they exist in the session.
    if "AFR Equipment" in saved or "Other Equipment" in saved:
        parts = []
        afr = str(saved.get("AFR Equipment", "") or "").strip()
        other = str(saved.get("Other Equipment", "") or "").strip()
        if afr:
            parts.append(afr)
        if other:
            parts.extend(x.strip() for x in other.replace(";", ",").split(",") if x.strip())
        return list(dict.fromkeys(parts))

    if isinstance(default_value, (list, tuple, set)):
        return [str(x).strip() for x in default_value if str(x).strip()]
    text = str(default_value or "").strip()
    return [x.strip() for x in text.replace(";", ",").split(",") if x.strip()]


def _attribute_list_from_value(value) -> list[str]:
    """Normalize attributes from stored lists or legacy delimited text."""
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    # Previous versions stored attributes as semicolon-separated text.
    delimiter = ";" if ";" in text else ","
    return [x.strip() for x in text.split(delimiter) if x.strip()]


def _effective_stations() -> pd.DataFrame:
    """Apply session-scoped station availability without requiring a routing.py helper."""
    effective = stations.copy()
    overrides = st.session_state.get("station_active_overrides", {})
    for sid, enabled in overrides.items():
        mask = effective["cad_station_id"].astype(str) == str(sid)
        effective.loc[mask, "active"] = bool(enabled)
    return effective


@st.cache_data(ttl=30 * 24 * 3600, show_spinner=False)
def _cached_geocode(query: str):
    point = geocode_address(query)
    return {"lat": point.lat, "lon": point.lon, "label": point.label}


@st.cache_data(ttl=15 * 60, show_spinner=False)
def _cached_route_table(origin_payload, destination_payload):
    from routing import GeoPoint
    origins = [GeoPoint(lat=float(x[0]), lon=float(x[1]), label=str(x[2])) for x in origin_payload]
    destination = GeoPoint(
        lat=float(destination_payload[0]),
        lon=float(destination_payload[1]),
        label=str(destination_payload[2]),
    )
    metrics = route_table(origins, destination)
    return [
        None if m is None else {
            "distance_miles": m.distance_miles,
            "duration_seconds": m.duration_seconds,
        }
        for m in metrics
    ]


@st.cache_data(ttl=15 * 60, show_spinner=False)
def _cached_route_geometry(origin_payload, destination_payload):
    from routing import GeoPoint
    origin = GeoPoint(
        lat=float(origin_payload[0]),
        lon=float(origin_payload[1]),
        label=str(origin_payload[2]),
    )
    destination = GeoPoint(
        lat=float(destination_payload[0]),
        lon=float(destination_payload[1]),
        label=str(destination_payload[2]),
    )
    return route_geometry(origin, destination)


ROUTE_COLORS = [
    [0, 114, 178, 220],
    [213, 94, 0, 220],
    [0, 158, 115, 220],
    [204, 121, 167, 220],
    [230, 159, 0, 220],
    [86, 180, 233, 220],
    [240, 228, 66, 220],
    [128, 64, 0, 220],
    [106, 61, 154, 220],
    [0, 0, 0, 220],
]


def _filter_route_rows_for_map(
    route_rows,
    dispatched_unit_ids,
    *,
    show_all=False,
    additional_unit_ids=None,
):
    """Filter station-route rows for the map.

    Defaults to dispatched units only. Additional in-service units may be
    overlaid without requiring routing.py to provide this UI-only helper.
    """
    dispatched = {str(x) for x in dispatched_unit_ids}
    additional = {str(x) for x in (additional_unit_ids or [])}
    visible = dispatched | additional

    filtered = []
    for original in route_rows:
        row = dict(original)
        unit_ids = row.get("unit_ids", [])

        if isinstance(unit_ids, str):
            unit_ids = [x.strip() for x in unit_ids.split(",") if x.strip()]
        else:
            unit_ids = [str(x) for x in unit_ids]

        if show_all:
            visible_here = unit_ids
        else:
            visible_here = [uid for uid in unit_ids if uid in visible]

        if not visible_here:
            continue

        row["visible_unit_ids"] = visible_here
        row["units"] = ", ".join(visible_here)
        row["label"] = f"Station {row.get('station', '')} | {', '.join(visible_here)}"
        filtered.append(row)

    return filtered


def _point_from_cached(payload):
    from routing import GeoPoint
    return GeoPoint(lat=float(payload["lat"]), lon=float(payload["lon"]), label=str(payload["label"]))


def _routing_dataframe(edited: pd.DataFrame, incident_point):
    """Resolve station origins, calculate metrics, and retrieve actual route geometry."""
    unique_station_ids = list(dict.fromkeys(str(x) for x in edited["Station"].tolist()))
    station_points = {}
    station_meta = {}
    failures = []

    for sid in unique_station_ids:
        rec = station_record(sid, _effective_stations())
        if rec is None:
            failures.append((sid, "No station crosswalk entry"))
            continue
        if not bool(rec.get("active", False)):
            failures.append((sid, "Station is marked inactive"))
            continue
        query = str(rec.get("address", "")).strip()
        if not query:
            failures.append((sid, "No routing/geocoding address"))
            continue
        try:
            cached = _cached_geocode(query)
            point = _point_from_cached(cached)
            station_points[sid] = point
            station_meta[sid] = rec
        except Exception as exc:
            failures.append((sid, str(exc)))

    if not station_points:
        raise RoutingError("None of the selected unit stations could be resolved for routing.")

    ordered_ids = list(station_points)
    origin_payload = tuple(
        (station_points[sid].lat, station_points[sid].lon, station_points[sid].label)
        for sid in ordered_ids
    )
    destination_payload = (incident_point.lat, incident_point.lon, incident_point.label)
    raw_metrics = _cached_route_table(origin_payload, destination_payload)

    metrics_by_station = {}
    for sid, raw in zip(ordered_ids, raw_metrics):
        if raw is None:
            failures.append((sid, "No drivable OSRM route"))
        else:
            metrics_by_station[sid] = raw

    # Geometry requires one OSRM route request per unique station origin.
    # Results are cached so repeated scenarios do not repeatedly request the same route.
    geometry_by_station = {}
    destination_payload = (incident_point.lat, incident_point.lon, incident_point.label)
    for sid in ordered_ids:
        if sid not in metrics_by_station:
            continue
        point = station_points[sid]
        origin_payload_one = (point.lat, point.lon, point.label)
        try:
            geometry = _cached_route_geometry(origin_payload_one, destination_payload)
            if geometry and geometry.get("path"):
                geometry_by_station[sid] = geometry
            else:
                failures.append((sid, "Route metrics available but route geometry was unavailable"))
        except Exception as exc:
            failures.append((sid, f"Route geometry: {exc}"))

    routed = edited.copy()
    routed["Routing Mode"] = "osm"
    routed["Route Distance Miles"] = pd.NA
    routed["Route Time Seconds"] = pd.NA

    for idx, row in routed.iterrows():
        sid = str(row["Station"])
        metric = metrics_by_station.get(sid)
        if metric:
            routed.at[idx, "Route Distance Miles"] = float(metric["distance_miles"])
            routed.at[idx, "Route Time Seconds"] = float(metric["duration_seconds"])

    route_rows = []
    route_map_rows = []
    for color_index, sid in enumerate(sorted(metrics_by_station)):
        metric = metrics_by_station[sid]
        rec = station_meta[sid]
        units_here = edited.loc[
            edited["Station"].astype(str) == sid, "Unit ID"
        ].astype(str).tolist()
        point = station_points[sid]
        color = ROUTE_COLORS[color_index % len(ROUTE_COLORS)]

        route_rows.append({
            "Station": sid,
            "Station Name": rec.get("station_name", ""),
            "Jurisdiction": rec.get("jurisdiction", ""),
            "Units": ", ".join(units_here),
            "Road Distance (mi)": round(float(metric["distance_miles"]), 2),
            "Estimated Travel Time": format_duration(float(metric["duration_seconds"])),
            "Travel Time (sec)": float(metric["duration_seconds"]),
            "Latitude": point.lat,
            "Longitude": point.lon,
            "Route Color": f"rgb({color[0]}, {color[1]}, {color[2]})",
        })

        geometry = geometry_by_station.get(sid)
        if geometry:
            route_map_rows.append({
                "station": sid,
                "station_name": rec.get("station_name", ""),
                "jurisdiction": rec.get("jurisdiction", ""),
                "unit_ids": units_here,
                "units": ", ".join(units_here),
                "label": f"Station {sid} | {', '.join(units_here)}",
                "path": geometry["path"],
                "color": color,
                "position": [point.lon, point.lat],
                "distance": round(float(metric["distance_miles"]), 2),
                "eta": format_duration(float(metric["duration_seconds"])),
            })

    route_df = pd.DataFrame(route_rows)
    if not route_df.empty:
        # Diagnostic routing table only. Do not present ETA order as dispatch order.
        route_df = route_df.sort_values(["Station"])

    return routed, route_df, route_map_rows, failures


def _map_view_state(route_map_rows, incident_point):
    coords = [[incident_point.lon, incident_point.lat]]
    for row in route_map_rows:
        coords.extend(row["path"])

    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    center_lon = (min(lons) + max(lons)) / 2
    center_lat = (min(lats) + max(lats)) / 2

    span = max(max(lons) - min(lons), max(lats) - min(lats), 0.002)
    # Simple viewport approximation that works well across the regional scale.
    zoom = max(7.0, min(15.5, 10.8 - math.log2(span / 0.08)))

    return pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=0,
        bearing=0,
    )



def _incident_star_polygon(incident_point):
    """Create a five-point geographic star around the incident location."""
    outer = 0.0020
    inner = 0.00085
    lat = float(incident_point.lat)
    lon = float(incident_point.lon)
    lon_scale = max(math.cos(math.radians(lat)), 0.35)

    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        radius = outer if i % 2 == 0 else inner
        dlat = radius * math.sin(angle)
        dlon = (radius * math.cos(angle)) / lon_scale
        points.append([lon + dlon, lat + dlat])

    return [{
        "polygon": points,
        "location": incident_point.label,
    }]

def _route_map(route_map_rows, incident_point):
    if not route_map_rows:
        return None

    path_layer = pdk.Layer(
        "PathLayer",
        data=route_map_rows,
        get_path="path",
        get_color="color",
        width_scale=1,
        get_width=5,
        width_min_pixels=3,
        width_max_pixels=8,
        pickable=True,
        auto_highlight=True,
    )

    # Station markers use the same color as their route.
    station_layer = pdk.Layer(
        "ScatterplotLayer",
        data=route_map_rows,
        get_position="position",
        get_fill_color="color",
        get_line_color=[255, 255, 255, 255],
        get_radius=70,
        radius_min_pixels=7,
        radius_max_pixels=12,
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )

    station_label_layer = pdk.Layer(
        "TextLayer",
        data=route_map_rows,
        get_position="position",
        get_text="label",
        get_color=[20, 20, 20, 255],
        get_size=13,
        get_pixel_offset=[0, -18],
        get_text_anchor='"middle"',
        get_alignment_baseline='"bottom"',
        billboard=True,
        pickable=False,
    )

    incident_star_layer = pdk.Layer(
        "PolygonLayer",
        data=_incident_star_polygon(incident_point),
        get_polygon="polygon",
        get_fill_color=[190, 0, 0, 245],
        get_line_color=[255, 255, 255, 255],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=False,
    )

    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=_map_view_state(route_map_rows, incident_point),
        layers=[
            path_layer,
            station_layer,
            station_label_layer,
            incident_star_layer,
        ],
        tooltip={
            "html": (
                "<b>Station {station}</b><br/>"
                "{station_name}<br/>"
                "<b>Units:</b> {units}<br/>"
                "<b>Distance:</b> {distance} mi<br/>"
                "<b>ETA:</b> {eta}"
            ),
            "style": {
                "backgroundColor": "rgba(30, 30, 30, 0.92)",
                "color": "white",
            },
        },
    )


def _result_table(state, routed_frame: pd.DataFrame | None = None):
    by_unit = {}
    if routed_frame is not None and not routed_frame.empty:
        for _, r in routed_frame.iterrows():
            by_unit[str(r["Unit ID"])] = r

    output = []
    ordered = assignments_in_dispatch_order(state)
    for dispatch_index, a in enumerate(ordered, start=1):
        row = {
            "Dispatch Order": dispatch_index,
            "Step": a.step,
            "Requirement": a.requirement,
            "Unit": a.unit_id,
        }
        if a.unit_id in by_unit:
            source = by_unit[a.unit_id]
            if not pd.isna(source.get("Route Distance Miles", pd.NA)):
                row["Road Distance (mi)"] = round(float(source["Route Distance Miles"]), 2)
                row["Estimated Travel Time"] = format_duration(float(source["Route Time Seconds"]))
        output.append(row)
    return output



def _section_header(kicker: str, title: str, note: str | None = None):
    note_html = f'<div class="small-muted">{note}</div>' if note else ""
    st.markdown(
        f'<div class="section-kicker">{kicker}</div>'
        f'<div class="section-title">{title}</div>'
        f'{note_html}',
        unsafe_allow_html=True,
    )


def _render_dispatch_cards(result_rows: list[dict]):
    """Render the primary dispatch result as application cards rather than a spreadsheet."""
    cards = []
    for row in result_rows:
        order = html.escape(str(row.get("Dispatch Order", "")))
        unit = html.escape(str(row.get("Unit", "")))
        requirement = html.escape(str(row.get("Requirement", "")))

        meta_parts = []
        if row.get("Estimated Travel Time"):
            meta_parts.append(html.escape(str(row["Estimated Travel Time"])))
        if row.get("Road Distance (mi)") not in (None, ""):
            try:
                meta_parts.append(f'{float(row["Road Distance (mi)"]):.2f} mi')
            except (TypeError, ValueError):
                pass

        meta = " · ".join(meta_parts)
        meta_html = f'<div class="dispatch-meta">{meta}</div>' if meta else ""

        cards.append(
            '<div class="dispatch-card">'
            f'<div class="dispatch-order">{order}</div>'
            f'<div class="dispatch-unit">{unit}</div>'
            f'<div class="dispatch-req">{requirement}</div>'
            f'{meta_html}'
            '</div>'
        )

    st.markdown(
        '<div class="dispatch-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


if page == "Dashboard":
    _section_header(
        "Workspace",
        "Dashboard",
        "Build, validate, and simulate response planning configurations.",
    )

    active_station_count = int(_effective_stations()["active"].sum())
    unit_type_count = catalog["unit_type"].replace("", pd.NA).dropna().nunique()
    requirement_count = len(REQUIREMENTS)
    event_type_count = event_plan_map["event_type"].nunique()

    st.markdown(
        f"""
        <div class="dashboard-grid">
          <div class="dashboard-stat navy"><div class="number">1</div><div class="label">Response Plan Modeled</div></div>
          <div class="dashboard-stat"><div class="number">{unit_type_count}</div><div class="label">Unit Types</div></div>
          <div class="dashboard-stat cyan"><div class="number">{requirement_count}</div><div class="label">Requirements Defined</div></div>
          <div class="dashboard-stat"><div class="number">{active_station_count}</div><div class="label">Active Stations</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.55, 1.0], gap="large")
    with left:
        with st.container(border=True):
            _section_header("Response plans", "Current modeled plan")
            st.markdown(
                """
                <div class="plan-row">
                  <div><div class="plan-name">ALPHA</div><div class="plan-desc">EMS LEVEL 1 · All operational conditions</div></div>
                  <span class="active-badge">Active</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("Additional event types and response plans will populate this workspace as they are modeled.")

    with right:
        with st.container(border=True):
            _section_header("Environment", "Configuration status")
            st.markdown(
                f"""
                <div class="result-summary">
                  <span class="summary-pill">Event Types <strong>{event_type_count}</strong></span>
                  <span class="summary-pill">Conditions <strong>3</strong></span>
                  <span class="summary-pill">Units <strong>{len(catalog):,}</strong></span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.info("Simulation environment. No connection to production I/CAD.")


if page == "Dispatch Simulator":
    condition_records = operational_conditions(event_plan_map)
    condition_ids = [r["operational_condition"] for r in condition_records]
    condition_names = {
        r["operational_condition"]: r["condition_name"] for r in condition_records
    }

    with st.container(border=True):
        _section_header("Dispatch setup", "Operational context")

        condition_label_by_id = {
            cid: condition_names[cid] for cid in condition_ids
        }
        condition_id_by_label = {
            label: cid for cid, label in condition_label_by_id.items()
        }
        condition_labels = [condition_label_by_id[cid] for cid in condition_ids]

        condition_choice = st.segmented_control(
            "Operational Condition",
            options=condition_labels,
            default=condition_labels[0],
            selection_mode="single",
            key="operational_condition_v070",
            width="stretch",
        )
        condition_choice = condition_choice or condition_labels[0]
        condition_id = condition_id_by_label.get(condition_choice, condition_ids[0])

        event_records = event_types_for_condition(condition_id, event_plan_map)
        event_ids = [r["event_type"] for r in event_records]
        event_descriptions = {r["event_type"]: r["description"] for r in event_records}

        event_type = st.selectbox(
            "Event Type",
            options=event_ids,
            format_func=lambda x: f"{x} — {event_descriptions[x]}",
            key="event_type_v070",
        )

        mapping = resolve_response_plan(event_type, condition_id, event_plan_map)
        response_plan_id = mapping["response_plan_id"]

        st.markdown(
            f"""
            <div class="context-strip">
              <span class="context-pill">Condition {condition_id}</span>
              <span class="context-main">{html.escape(event_type)}</span>
              <span class="context-desc">{html.escape(event_descriptions[event_type])}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    with st.container(border=True):
        _section_header("Incident", "Location")

        route_choice = st.segmented_control(
            "Routing",
            options=["Road Network", "Manual Time"],
            default="Road Network",
            selection_mode="single",
            key="routing_mode_v070",
            width="stretch",
            help=(
                "Road Network uses OpenStreetMap / OSRM travel time. "
                "Manual Time uses the test time entered for each unit."
            ),
        )
        route_choice = route_choice or "Road Network"
        routing_mode = (
            "OpenStreetMap / OSRM"
            if route_choice == "Road Network"
            else "Manual Test Time"
        )

        incident_point = None
        incident_mode = None
        incident_address = ""
        incident_lat = 38.8500
        incident_lon = -77.3000

        if routing_mode == "OpenStreetMap / OSRM":
            incident_choice = st.segmented_control(
                "Location Input",
                options=["Address", "Coordinates"],
                default="Address",
                selection_mode="single",
                key="incident_mode_v070",
                width="stretch",
            )
            incident_choice = incident_choice or "Address"
            incident_mode = (
                "Street Address"
                if incident_choice == "Address"
                else "Latitude / Longitude"
            )

            if incident_mode == "Street Address":
                incident_address = st.text_input(
                    "Incident address",
                    placeholder="12000 Government Center Pkwy, Fairfax, VA 22035",
                    label_visibility="collapsed",
                    key="incident_address_v070",
                )
            else:
                lat_c, lon_c = st.columns(2)
                with lat_c:
                    incident_lat = st.number_input(
                        "Latitude",
                        min_value=-90.0,
                        max_value=90.0,
                        value=38.8500,
                        format="%.6f",
                        key="incident_lat_v070",
                    )
                with lon_c:
                    incident_lon = st.number_input(
                        "Longitude",
                        min_value=-180.0,
                        max_value=180.0,
                        value=-77.3000,
                        format="%.6f",
                        key="incident_lon_v070",
                    )
        else:
            st.caption("Manual Time uses the Test Time value in Unit Configuration.")

    st.write("")

    with st.container(border=True):
        _section_header("Resources", "Units in service")

        selected_ids = st.multiselect(
            "Available units",
            options=catalog["unit_id"].tolist(),
            default=default_units,
            help="Only selected units participate in the simulation.",
            key="units_in_service_v070",
        )

        selected = (
            catalog[catalog["unit_id"].isin(selected_ids)]
            .copy()
            .sort_values("unit_id")
        )

        unit_count = len(selected_ids)
        station_count = (
            selected["station_id"].replace("", pd.NA).dropna().nunique()
            if not selected.empty else 0
        )
        st.markdown(
            f"""
            <div class="result-summary">
              <span class="summary-pill">Units <strong>{unit_count}</strong></span>
              <span class="summary-pill">Stations <strong>{station_count}</strong></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        rows = []
        for _, r in selected.iterrows():
            uid = r["unit_id"]
            saved = st.session_state.scenario_overrides.get(uid, {})
            rows.append({
                "Unit ID": uid,
                "Unit Type": r["unit_type"],
                "Beat": saved.get("Beat", r["beat"]),
                "Station": saved.get("Station", r["station_id"]),
                "Attributes": _attribute_list_from_value(
                    saved.get("Attributes", r["default_attributes"])
                ),
                "Equipment": _equipment_list_from_saved(
                    saved, r.get("default_equipment", "")
                ),
                "M Skills": saved.get("M Skills", int(r["default_m_skill"])),
                "Test Time (min)": saved.get(
                    "Test Time (min)", saved.get("Test Distance", 5.0)
                ),
                "Typical ALS Equipment": r["typical_als_equipment"],
            })

        scenario_df = pd.DataFrame(rows)
        edited = scenario_df

        if not scenario_df.empty:
            with st.expander("Unit Configuration", expanded=False):
                edited = st.data_editor(
                    scenario_df,
                    hide_index=True,
                    use_container_width=True,
                    disabled=["Unit ID", "Unit Type", "Typical ALS Equipment"],
                    column_config={
                        "Beat": st.column_config.SelectboxColumn(
                            "Beat",
                            options=BEAT_OPTIONS,
                        ),
                        "Station": st.column_config.SelectboxColumn(
                            "Station",
                            options=STATION_OPTIONS,
                        ),
                        "Attributes": st.column_config.MultiselectColumn(
                            "Attributes",
                            options=ATTRIBUTE_OPTIONS,
                            accept_new_options=True,
                            width="large",
                        ),
                        "Equipment": st.column_config.MultiselectColumn(
                            "Equipment",
                            options=EQUIPMENT_OPTIONS,
                            accept_new_options=True,
                            width="large",
                        ),
                        "M Skills": st.column_config.SelectboxColumn(
                            "M Skills",
                            options=[0, 1, 2, 3, 4],
                        ),
                        "Test Time (min)": st.column_config.NumberColumn(
                            "Test Time (min)",
                            min_value=0.0,
                            step=0.1,
                        ),
                        "Typical ALS Equipment": st.column_config.TextColumn(
                            "Typical ALS Equipment",
                        ),
                    },
                    key="scenario_editor_v070",
                )

            for _, row in edited.iterrows():
                equipment = row.get("Equipment", [])
                if not isinstance(equipment, list):
                    equipment = [] if pd.isna(equipment) else [str(equipment)]
                attributes = row.get("Attributes", [])
                if not isinstance(attributes, list):
                    attributes = [] if pd.isna(attributes) else [str(attributes)]

                st.session_state.scenario_overrides[str(row["Unit ID"])] = {
                    "Beat": str(row["Beat"]),
                    "Station": str(row["Station"]),
                    "Attributes": attributes,
                    "Equipment": equipment,
                    "M Skills": int(row["M Skills"]),
                    "Test Time (min)": float(row["Test Time (min)"]),
                }

            m_suffix_missing_afr = []
            for _, row in edited.iterrows():
                uid = str(row["Unit ID"])
                typical = str(row.get("Typical ALS Equipment", ""))
                equipment = row.get("Equipment", [])
                if not isinstance(equipment, list):
                    equipment = [] if pd.isna(equipment) else [str(equipment)]
                if (
                    typical in {"AFR1", "AFR2", "AFR1 or AFR2"}
                    and not ({"AFR1", "AFR2"} & set(equipment))
                ):
                    m_suffix_missing_afr.append(uid)

            if m_suffix_missing_afr:
                st.warning(
                    "Missing AFR equipment: " + ", ".join(m_suffix_missing_afr)
                )

            conflicts = pair_conflicts(edited)
            if conflicts:
                pairs = ", ".join(f"{a} + {b}" for a, b in conflicts)
                st.warning("Base/M operational conflict: " + pairs)

        map_scope = "Dispatched units only"
        map_extra_units = []
        if routing_mode == "OpenStreetMap / OSRM":
            with st.expander("Map Display", expanded=False):
                map_choice = st.segmented_control(
                    "Routes shown",
                    options=["Dispatched", "Dispatched + Selected", "All In Service"],
                    default="Dispatched",
                    selection_mode="single",
                    key="map_scope_v070",
                    width="stretch",
                )
                map_choice = map_choice or "Dispatched"
                if map_choice == "Dispatched + Selected":
                    map_scope = "Dispatched + selected in-service units"
                    map_extra_units = st.multiselect(
                        "Additional units",
                        options=selected_ids,
                        default=[],
                        key="map_extra_v070",
                    )
                elif map_choice == "All In Service":
                    map_scope = "All in-service units"

    st.write("")

    run_disabled = scenario_df.empty
    if run_disabled:
        st.info("Select at least one unit before running the simulation.")

    run_simulation = st.button(
        "Run Dispatch Simulation",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
    )

    if run_simulation:
        routed_frame = None
        route_df = None
        route_map_rows = []
        route_failures = []

        if response_plan_id != "ALPHA":
            st.error(
                f"Response plan {response_plan_id} is mapped correctly, but its simulator "
                "has not been implemented yet."
            )
        else:
            if routing_mode == "OpenStreetMap / OSRM":
                try:
                    if incident_mode == "Street Address":
                        if not incident_address.strip():
                            raise RoutingError("Enter an incident address before routing.")
                        incident_point = _point_from_cached(
                            _cached_geocode(incident_address.strip())
                        )
                    else:
                        incident_point = parse_lat_lon(incident_lat, incident_lon)

                    with st.spinner("Calculating road-network routes..."):
                        routed_frame, route_df, route_map_rows, route_failures = (
                            _routing_dataframe(edited, incident_point)
                        )

                    units = scenario_units_from_frame(routed_frame)
                except Exception as exc:
                    st.error(f"Routing failed: {exc}")
                    units = []
            else:
                manual_frame = edited.copy()
                manual_frame["Routing Mode"] = "manual"
                units = scenario_units_from_frame(manual_frame)

            if units:
                state = simulate_alpha(units)
                ordered_assignments = assignments_in_dispatch_order(state)
                result_rows = _result_table(state, routed_frame)

                st.write("")
                with st.container(border=True):
                    _section_header(
                        "Simulation result",
                        "Dispatch recommendation",
                        "Response-plan dispatch order",
                    )

                    st.markdown(
                        f"""
                        <div class="result-summary">
                          <span class="summary-pill success">Simulation complete</span>
                          <span class="summary-pill">Event <strong>{html.escape(event_type)}</strong></span>
                          <span class="summary-pill">Plan <strong>{html.escape(response_plan_id)}</strong></span>
                          <span class="summary-pill">Condition <strong>{html.escape(condition_id)}</strong></span>
                          <span class="summary-pill">Units <strong>{len(ordered_assignments)}</strong></span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if result_rows:
                        _render_dispatch_cards(result_rows)

                        with st.expander("Table View", expanded=False):
                            result_df = pd.DataFrame(result_rows)
                            st.dataframe(
                                result_df,
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    "Dispatch Order": st.column_config.NumberColumn(
                                        "Order", width="small"
                                    ),
                                    "Road Distance (mi)": st.column_config.NumberColumn(
                                        "Road mi", format="%.2f"
                                    ),
                                },
                            )
                    else:
                        st.info("No resources were recommended from the current scenario.")

                if routing_mode == "OpenStreetMap / OSRM" and route_map_rows:
                    dispatched_ids = [a.unit_id for a in ordered_assignments]
                    visible_route_rows = _filter_route_rows_for_map(
                        route_map_rows,
                        dispatched_ids,
                        show_all=(map_scope == "All in-service units"),
                        additional_unit_ids=(
                            map_extra_units
                            if map_scope == "Dispatched + selected in-service units"
                            else []
                        ),
                    )

                    st.write("")
                    with st.container(border=True):
                        _section_header(
                            "Route map",
                            "Dispatched units",
                            "The red star marks the incident.",
                        )
                        deck = _route_map(visible_route_rows, incident_point)
                        if deck is not None:
                            st.pydeck_chart(
                                deck,
                                use_container_width=True,
                                height=560,
                            )
                        else:
                            st.info(
                                "No route geometry is available for the selected map filter."
                            )

                with st.expander("Technical Details", expanded=False):
                    tech_tabs = st.tabs(["Routing", "Trace", "Plan Flow"])

                    with tech_tabs[0]:
                        if routing_mode != "OpenStreetMap / OSRM":
                            st.info("Routing diagnostics are available in Road Network mode.")
                        elif route_df is None or route_df.empty:
                            st.info("No routing diagnostics are available.")
                        else:
                            if route_failures:
                                failure_text = "; ".join(
                                    f"{sid}: {reason}" for sid, reason in route_failures
                                )
                                st.warning(failure_text)
                            st.dataframe(
                                route_df.drop(
                                    columns=[
                                        "Travel Time (sec)",
                                        "Latitude",
                                        "Longitude",
                                        "Route Color",
                                    ]
                                ),
                                hide_index=True,
                                use_container_width=True,
                            )

                    with tech_tabs[1]:
                        st.code("\n".join(state.trace), language="text")

                    with tech_tabs[2]:
                        for n in sorted(ALPHA_STEPS):
                            s = ALPHA_STEPS[n]
                            if s.kind == "GROUP":
                                detail = " OR ".join(s.alternatives)
                            elif s.requirement:
                                detail = s.requirement
                            else:
                                detail = ""
                            extra = (
                                f" | CAD Max Distance {s.max_time_minutes:g} = "
                                f"{s.max_time_minutes:g} min"
                                if s.max_time_minutes is not None
                                else ""
                            )
                            st.write(f"**Step {s.number}: {s.label}** — {detail}{extra}")

    st.caption(
        "Road Network uses OpenStreetMap / OSRM and may differ from Hexagon routing."
    )


if page == "Stations":
    _section_header(
        "Stations",
        "Regional station availability",
        "Turn stations on or off for routing scenarios. Changes apply to the current app session.",
    )

    effective_stations = _effective_stations()

    active_station_count = int(effective_stations["active"].sum())
    jurisdiction_count = (
        effective_stations["jurisdiction"].replace("", pd.NA).dropna().nunique()
    )
    st.markdown(
        f"""
        <div class="result-summary">
          <span class="summary-pill">Active Stations <strong>{active_station_count}</strong></span>
          <span class="summary-pill">Jurisdictions <strong>{jurisdiction_count}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_c, reset_c = st.columns([3.0, 1.0], gap="large")
    with search_c:
        station_search = st.text_input(
            "Search station ID, jurisdiction, name, or address",
            "",
            key="station_search_v070",
        )
    with reset_c:
        st.write("")
        st.write("")
        if st.button("Restore station defaults", use_container_width=True):
            st.session_state.station_active_overrides = {}
            st.session_state.pop("station_editor_v070", None)
            st.rerun()

    station_view = effective_stations.copy()
    if station_search.strip():
        s = station_search.strip().lower()
        mask = (
            station_view["cad_station_id"].str.lower().str.contains(s, regex=False)
            | station_view["jurisdiction"].str.lower().str.contains(s, regex=False)
            | station_view["station_name"].str.lower().str.contains(s, regex=False)
            | station_view["address"].str.lower().str.contains(s, regex=False)
        )
        station_view = station_view[mask]

    display_stations = station_view.rename(columns={
        "cad_station_id": "CAD Station ID",
        "jurisdiction": "Jurisdiction",
        "local_station_number": "Local Station",
        "station_name": "Station Name",
        "address": "Routing Address",
        "active": "Active",
    })[
        [
            "Active", "CAD Station ID", "Jurisdiction", "Local Station",
            "Station Name", "Routing Address"
        ]
    ]

    st.caption("Uncheck **Active** to exclude a station and its assigned units from OSM routing.")

    edited_stations = st.data_editor(
        display_stations,
        hide_index=True,
        use_container_width=True,
        disabled=[
            "CAD Station ID",
            "Jurisdiction",
            "Local Station",
            "Station Name",
            "Routing Address",
        ],
        column_config={
            "Active": st.column_config.CheckboxColumn(
                "Active",
                help="Enabled stations may be used as routing origins.",
                width="small",
            ),
            "CAD Station ID": st.column_config.TextColumn("Station", width="small"),
            "Jurisdiction": st.column_config.TextColumn("Jurisdiction", width="medium"),
            "Local Station": st.column_config.TextColumn("Local", width="small"),
            "Station Name": st.column_config.TextColumn("Station Name", width="medium"),
            "Routing Address": st.column_config.TextColumn("Routing Address", width="large"),
        },
        key="station_editor_v070",
    )

    for _, row in edited_stations.iterrows():
        sid = str(row["CAD Station ID"])
        st.session_state.station_active_overrides[sid] = bool(row["Active"])


if page == "Units & Resources":
    _section_header(
        "Reference data",
        "CADDBM unit catalog",
        "Search the imported unit inventory and modeled default capabilities.",
    )

    unit_type_count = catalog["unit_type"].replace("", pd.NA).dropna().nunique()
    unit_station_count = catalog["station_id"].replace("", pd.NA).dropna().nunique()
    st.markdown(
        f"""
        <div class="result-summary">
          <span class="summary-pill">Units <strong>{len(catalog):,}</strong></span>
          <span class="summary-pill">Types <strong>{unit_type_count}</strong></span>
          <span class="summary-pill">Stations <strong>{unit_station_count}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_c, type_c = st.columns([2.2, 1.0])
    with search_c:
        search = st.text_input(
            "Search Unit ID / type / beat / station",
            "",
            key="unit_search_v070",
        )
    with type_c:
        type_values = ["All"] + sorted(
            x for x in catalog["unit_type"].unique() if x
        )
        selected_type = st.selectbox("Unit Type", type_values)

    view = catalog.copy()
    if search.strip():
        s = search.strip().lower()
        mask = (
            view["unit_id"].str.lower().str.contains(s, regex=False)
            | view["unit_type"].str.lower().str.contains(s, regex=False)
            | view["beat"].str.lower().str.contains(s, regex=False)
            | view["station_id"].str.lower().str.contains(s, regex=False)
        )
        view = view[mask]
    if selected_type != "All":
        view = view[view["unit_type"] == selected_type]

    display = view.rename(columns={
        "unit_id": "Unit ID",
        "unit_type": "Unit Type",
        "beat": "Beat",
        "station_id": "Station",
        "default_attributes": "Modeled Attributes",
        "default_m_skill": "Default M Skills",
        "default_equipment": "Default Equipment",
        "typical_als_equipment": "Typical ALS Equipment",
        "attribute_source": "Attribute Source",
    })[
        [
            "Unit ID", "Unit Type", "Beat", "Station",
            "Modeled Attributes", "Default M Skills", "Default Equipment",
            "Typical ALS Equipment", "Attribute Source"
        ]
    ]
    st.dataframe(display.head(1000), hide_index=True, use_container_width=True)
    if len(display) > 1000:
        st.caption(
            f"Showing the first 1,000 of {len(display):,} matching records. "
            "Narrow the search to see a specific unit."
        )


if page == "Configuration":
    _section_header(
        "Configuration",
        "Event types, operating conditions, and response-plan definitions",
        "The dispatcher-facing event type is kept separate from the response plan it invokes.",
    )

    mapping_tab, requirements_tab = st.tabs(
        ["Event Type → Response Plan", "Requirement Library"]
    )

    with mapping_tab:
        st.markdown("#### Operational conditions")
        st.write(
            "**Condition 1:** Normal Operations  ·  "
            "**Condition 2:** High Call Volume  ·  "
            "**Condition 3:** >50% Unit Utilization"
        )

        mapping_display = event_plan_map.rename(columns={
            "event_type": "Event Type",
            "description": "Description",
            "operational_condition": "Condition",
            "condition_name": "Condition Name",
            "response_plan_id": "Response Plan",
        })[
            ["Condition", "Condition Name", "Event Type", "Description", "Response Plan"]
        ]
        st.dataframe(mapping_display, hide_index=True, use_container_width=True)
        st.info(
            "ALPHA — EMS LEVEL 1 is explicitly mapped to response plan ALPHA under all "
            "three operational conditions. Future event types can map to different plans by condition."
        )

    with requirements_tab:
        req_rows = []
        for name, r in REQUIREMENTS.items():
            req_rows.append({
                "Requirement": name,
                "Quantity": r.quantity,
                "Unit Type": r.unit_type or "",
                "Unit ID": r.unit_id or "",
                "Attributes": ", ".join(r.attributes),
                "Equipment": ", ".join(r.equipment),
                "Skills": ", ".join(r.skills),
                "Beat": r.beat_option,
                "Eq/Skill Option": r.equipment_skill_option,
            })
        st.dataframe(pd.DataFrame(req_rows), hide_index=True, use_container_width=True)


st.divider()
st.caption(
    "CADence simulation environment · No connection to production I/CAD · "
    "OpenStreetMap data © OpenStreetMap contributors · Routing via OSRM"
)
