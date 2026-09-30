from __future__ import annotations

import math
import copy
import html
import pandas as pd
import pydeck as pdk
import streamlit as st

from catalog import load_catalog
from requirements import REQUIREMENTS, load_requirement_source
from response_plans import (
    load_response_plan_items,
    load_response_plan_meta,
    load_alarm_levels,
    ad_hoc_plan_names,
    next_alarm_for_event,
    plan_flow_rows,
)
from event_config import (
    load_event_plan_map,
    operational_conditions,
    event_types_for_condition,
    resolve_response_plan,
)
from engine import (
    scenario_units_from_frame,
    simulate_response_plan,
    UnsupportedConfigurationError,
    SimulationState,
    pair_conflicts,
    assignments_in_dispatch_order,
)
from routing import (
    load_station_crosswalk,
    station_record,
    station_point_from_record,
    geocode_address,
    parse_lat_lon,
    route_table,
    route_geometry,
    format_duration,
    RoutingError,
)

st.set_page_config(
    page_title="CADence v0.10.0",
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
    /* v0.9 dashboard shell */
    section[data-testid="stSidebar"] {
        width: 250px !important;
        min-width: 250px !important;
    }

    section[data-testid="stSidebar"] .stRadio label {
        min-height: 2.35rem;
        display: flex;
        align-items: center;
        font-size: .82rem;
        font-weight: 650;
    }

    .st-key-global_topbar {
        background: #FFFFFF;
        border: 1px solid rgba(192,192,194,.42);
        border-radius: 18px;
        padding: .42rem .6rem .35rem .6rem;
        margin-bottom: 1rem;
        box-shadow: 0 6px 18px rgba(1,19,64,.05);
    }

    .st-key-global_topbar div[data-baseweb="input"] > div {
        background: #F7F9FC;
        border: 1px solid rgba(192,192,194,.55);
        border-radius: 10px !important;
        min-height: 2.35rem;
    }

    .top-user {
        min-height: 2.35rem;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: .58rem;
        white-space: nowrap;
    }

    .top-bell {
        width: 31px;
        height: 31px;
        display: grid;
        place-items: center;
        border-radius: 9px;
        color: #011340;
        background: #F7F9FC;
        border: 1px solid rgba(192,192,194,.44);
        font-size: .88rem;
    }

    .top-avatar {
        width: 31px;
        height: 31px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        color: #FFFFFF;
        background: #0162E8;
        font-size: .72rem;
        font-weight: 800;
    }

    .top-user-name {
        color: #24262A;
        font-size: .78rem;
        font-weight: 700;
    }

    .workspace-heading {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        margin: .3rem 0 .85rem 0;
    }

    .workspace-title {
        color: #011340;
        font-size: 1.72rem;
        line-height: 1.05;
        font-weight: 850;
        letter-spacing: -.025em;
    }

    .workspace-subtitle {
        margin-top: .28rem;
        color: #718096;
        font-size: .83rem;
    }

    .dashboard-kpis {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .75rem;
        margin-bottom: .9rem;
    }

    .kpi-card {
        display: grid;
        grid-template-columns: 44px 1fr;
        align-items: center;
        gap: .72rem;
        min-height: 92px;
        padding: .78rem .85rem;
        background: #FFFFFF;
        border: 1px solid rgba(192,192,194,.40);
        border-radius: 14px;
        box-shadow: 0 5px 18px rgba(1,19,64,.045);
    }

    .kpi-icon {
        width: 42px;
        height: 42px;
        display: grid;
        place-items: center;
        border-radius: 12px;
        color: #FFFFFF;
        font-size: 1.05rem;
        font-weight: 800;
    }

    .kpi-icon.blue { background: linear-gradient(145deg,#0162E8,#0756C7); }
    .kpi-icon.cyan { background: linear-gradient(145deg,#00BFD9,#00D9FC); }
    .kpi-icon.navy { background: linear-gradient(145deg,#011340,#02215F); }
    .kpi-icon.charcoal { background: linear-gradient(145deg,#24262A,#454950); }

    .kpi-label {
        color: #718096;
        font-size: .68rem;
        font-weight: 650;
    }

    .kpi-number {
        color: #011340;
        font-size: 1.38rem;
        font-weight: 850;
        line-height: 1.02;
        margin-top: .05rem;
    }

    .kpi-caption {
        color: #718096;
        font-size: .66rem;
        margin-top: .13rem;
    }

    .panel-shell {
        background: #FFFFFF;
        border: 1px solid rgba(192,192,194,.40);
        border-radius: 15px;
        padding: .9rem;
        box-shadow: 0 5px 18px rgba(1,19,64,.04);
        margin-bottom: .8rem;
    }

    .panel-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .8rem;
        margin-bottom: .65rem;
    }

    .panel-title {
        color: #011340;
        font-size: .96rem;
        font-weight: 800;
    }

    .panel-link {
        color: #0162E8;
        font-size: .7rem;
        font-weight: 750;
    }

    .app-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        overflow: hidden;
        border-radius: 11px;
        border: 1px solid rgba(192,192,194,.36);
    }

    .app-table th {
        padding: .56rem .65rem;
        background: #F7F9FC;
        color: #4B5563;
        font-size: .65rem;
        text-align: left;
        font-weight: 750;
        border-bottom: 1px solid rgba(192,192,194,.34);
    }

    .app-table td {
        padding: .62rem .65rem;
        color: #24262A;
        font-size: .72rem;
        background: #FFFFFF;
        border-bottom: 1px solid rgba(192,192,194,.24);
    }

    .app-table tr:last-child td { border-bottom: 0; }
    .table-link { color: #0162E8; font-weight: 780; }

    .status-active {
        display: inline-block;
        padding: .18rem .45rem;
        border-radius: 999px;
        background: #E8F5EF;
        color: #236148;
        font-size: .64rem;
        font-weight: 800;
    }

    .status-modeled {
        display: inline-block;
        padding: .18rem .45rem;
        border-radius: 999px;
        background: #EEF5FF;
        color: #0162E8;
        font-size: .64rem;
        font-weight: 800;
    }

    .quick-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .72rem;
    }

    .quick-card {
        min-height: 88px;
        padding: .8rem;
        border-radius: 14px;
        background: #FFFFFF;
        border: 1px solid rgba(192,192,194,.38);
        box-shadow: 0 4px 15px rgba(1,19,64,.035);
    }

    .quick-title { color:#011340; font-size:.78rem; font-weight:800; }
    .quick-copy { color:#718096; font-size:.68rem; margin-top:.25rem; line-height:1.4; }

    @media (max-width: 1050px) {
        .dashboard-kpis { grid-template-columns: repeat(2,minmax(0,1fr)); }
        .quick-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 768px) {
        section[data-testid="stSidebar"] {
            width: auto !important;
            min-width: auto !important;
        }
        .dashboard-kpis { grid-template-columns: 1fr 1fr; }
        .top-user-name { display:none; }
        .workspace-title { font-size:1.45rem; }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


catalog = load_catalog()
stations = load_station_crosswalk()
event_plan_map = load_event_plan_map()
response_plan_items = load_response_plan_items()
response_plan_meta = load_response_plan_meta()
alarm_levels = load_alarm_levels()
requirement_source, requirement_resources = load_requirement_source()

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
        [
            "Dashboard",
            "Response Plans",
            "Units & Resources",
            "Capabilities",
            "Equipment",
            "Scenarios",
            "Analysis",
            "Reports",
            "Settings",
        ],
        label_visibility="collapsed",
        key="cadence_page_v090",
    )
    st.markdown(
        '<div style="margin-top:1rem;color:rgba(255,255,255,.38);font-size:.68rem;">CADence v0.10.0</div>',
        unsafe_allow_html=True,
    )


with st.container(key="global_topbar"):
    search_col, user_col = st.columns([4.6, 1.4], vertical_alignment="center")
    with search_col:
        global_search = st.text_input(
            "Global search",
            placeholder="Search plans, units, or scenarios...",
            label_visibility="collapsed",
            key="cadence_global_search_v090",
        )
    with user_col:
        st.markdown(
            """
            <div class="top-user">
              <div class="top-bell">◌</div>
              <div class="top-avatar">C</div>
              <div class="top-user-name">CADence User ▾</div>
            </div>
            """,
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


@st.cache_data(ttl=30 * 24 * 3600, persist="disk", show_spinner=False)
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
        # Prefer permanent station coordinates. Only fall back to geocoding
        # for stations that have not yet been seeded in the crosswalk.
        point = station_point_from_record(rec)
        if point is None:
            query = str(rec.get("address", "")).strip()
            if not query:
                failures.append((sid, "No routing coordinates or geocoding address"))
                continue
            try:
                cached = _cached_geocode(query)
                point = _point_from_cached(cached)
            except Exception as exc:
                failures.append((sid, str(exc)))
                continue

        station_points[sid] = point
        station_meta[sid] = rec

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
            "Source": getattr(a, "source_kind", "Initial") or "Initial",
            "Plan": getattr(a, "source_plan", "") or "ALPHA",
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


def _workspace_header(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="workspace-heading">
          <div>
            <div class="workspace-title">{html.escape(title)}</div>
            <div class="workspace-subtitle">{html.escape(subtitle)}</div>
          </div>
        </div>
        """,
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
        if row.get("Source"):
            source_label = str(row.get("Source", ""))
            plan_label = str(row.get("Plan", ""))
            meta_parts.append(html.escape(f"{source_label}: {plan_label}" if plan_label else source_label))
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
    _workspace_header("Dashboard", "Build. Validate. Optimize. Deploy.")

    active_station_count = int(_effective_stations()["active"].sum())
    unit_type_count = catalog["unit_type"].replace("", pd.NA).dropna().nunique()
    response_plan_count = int(response_plan_meta["resp_plan_name"].nunique())
    capability_count = len(REQUIREMENTS)
    equipment_count = len(EQUIPMENT_OPTIONS)

    st.markdown(
        f"""
        <div class="dashboard-kpis">
          <div class="kpi-card">
            <div class="kpi-icon blue">▤</div>
            <div>
              <div class="kpi-label">Response Plans</div>
              <div class="kpi-number">{response_plan_count}</div>
              <div class="kpi-caption">Imported from CAD</div>
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon cyan">◎</div>
            <div>
              <div class="kpi-label">Unit Types</div>
              <div class="kpi-number">{unit_type_count}</div>
              <div class="kpi-caption">Configured in catalog</div>
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon navy">✦</div>
            <div>
              <div class="kpi-label">Capabilities</div>
              <div class="kpi-number">{capability_count}</div>
              <div class="kpi-caption">Imported requirements</div>
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-icon charcoal">◇</div>
            <div>
              <div class="kpi-label">Equipment Items</div>
              <div class="kpi-number">{equipment_count}</div>
              <div class="kpi-caption">Modeled equipment codes</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    plan_rows = (
        event_plan_map[
            ["response_plan_id", "event_type", "description"]
        ]
        .drop_duplicates()
        .sort_values(["response_plan_id", "event_type"])
    )
    if global_search.strip():
        q = global_search.strip().lower()
        plan_rows = plan_rows[
            plan_rows.astype(str).apply(
                lambda row: row.str.lower().str.contains(q, regex=False).any(),
                axis=1,
            )
        ]

    table_rows = []
    for _, row in plan_rows.iterrows():
        plan_id = html.escape(str(row["response_plan_id"]))
        event_code = html.escape(str(row["event_type"]))
        desc = html.escape(str(row["description"]))
        table_rows.append(
            "<tr>"
            f'<td><span class="table-link">{plan_id}</span></td>'
            f"<td>{event_code}</td>"
            f"<td>{desc}</td>"
            '<td><span class="status-active">Active</span></td>'
            "<td>•••</td>"
            "</tr>"
        )

    st.markdown(
        f"""
        <div class="panel-shell">
          <div class="panel-heading">
            <div class="panel-title">Response Plans</div>
            <div class="panel-link">Current modeled configuration</div>
          </div>
          <table class="app-table">
            <thead>
              <tr>
                <th>Plan Name</th>
                <th>Event Type</th>
                <th>Description</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {''.join(table_rows) if table_rows else '<tr><td colspan="5">No matching plans</td></tr>'}
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="quick-grid">
          <div class="quick-card">
            <div class="quick-title">Scenario Simulator</div>
            <div class="quick-copy">Run an event type against available units, operational conditions, and road-network routing.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Regional Resources</div>
            <div class="quick-copy">{len(catalog):,} imported unit records across {active_station_count} active routing stations.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Operational Conditions</div>
            <div class="quick-copy">Condition 1 Normal Operations, Condition 2 High Call Volume, and Condition 3 &gt;50% Unit Utilization.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if page == "Response Plans":
    _workspace_header(
        "Response Plans",
        "Imported CAD response plans, event mappings, Ad Hoc availability, and additional-alarm configuration.",
    )

    plan_count = int(response_plan_meta["resp_plan_name"].nunique())
    adhoc_count = int(response_plan_meta["is_ad_hoc"].sum())
    event_count = int(event_plan_map["event_type"].nunique())
    mapped_count = int(event_plan_map["response_plan_id"].replace("", pd.NA).dropna().nunique())

    st.markdown(
        f"""
        <div class="dashboard-kpis">
          <div class="kpi-card"><div class="kpi-icon blue">▤</div><div><div class="kpi-label">Response Plans</div><div class="kpi-number">{plan_count:,}</div><div class="kpi-caption">Imported from CAD</div></div></div>
          <div class="kpi-card"><div class="kpi-icon cyan">+</div><div><div class="kpi-label">Ad Hoc Plans</div><div class="kpi-number">{adhoc_count:,}</div><div class="kpi-caption">Available post-dispatch</div></div></div>
          <div class="kpi-card"><div class="kpi-icon navy">E</div><div><div class="kpi-label">FIRE Event Types</div><div class="kpi-number">{event_count:,}</div><div class="kpi-caption">Imported event definitions</div></div></div>
          <div class="kpi-card"><div class="kpi-icon charcoal">↔</div><div><div class="kpi-label">Mapped Plans</div><div class="kpi-number">{mapped_count:,}</div><div class="kpi-caption">Used by operational conditions</div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mapping_tab, library_tab, alarms_tab = st.tabs([
        "Event Type Mappings",
        "Plan Library",
        "Additional Alarms",
    ])

    with mapping_tab:
        mapping_display = event_plan_map.rename(columns={
            "event_type": "Event Type",
            "description": "Description",
            "operational_condition": "Condition",
            "condition_name": "Condition Name",
            "response_plan_id": "Response Plan",
        })[["Condition", "Condition Name", "Event Type", "Description", "Response Plan"]]
        st.dataframe(mapping_display, hide_index=True, use_container_width=True)
        st.caption(
            "The three condition columns are imported from the FIRE Event Type table. Blank response-plan values are preserved as blank rather than inferred."
        )

    with library_tab:
        plan_names = sorted(response_plan_meta["resp_plan_name"].astype(str).tolist())
        default_index = plan_names.index("ALPHA") if "ALPHA" in plan_names else 0
        selected_plan = st.selectbox(
            "Response Plan",
            options=plan_names,
            index=default_index,
            key="response_plan_library_v010",
        )
        meta_row = response_plan_meta[response_plan_meta["resp_plan_name"] == selected_plan].iloc[0]
        ad_hoc_label = "Yes" if bool(meta_row["is_ad_hoc"]) else "No"
        st.markdown(
            f"""
            <div class="result-summary">
              <span class="summary-pill">Plan <strong>{html.escape(selected_plan)}</strong></span>
              <span class="summary-pill">Ad Hoc <strong>{ad_hoc_label}</strong></span>
              <span class="summary-pill">Items <strong>{int(float(meta_row['unique_items']))}</strong></span>
              <span class="summary-pill">Raw rows <strong>{int(float(meta_row['item_rows']))}</strong></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            flow = pd.DataFrame(plan_flow_rows(selected_plan, response_plan_items, response_plan_meta))
            st.dataframe(flow, hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Unable to display plan structure: {exc}")
        st.caption(
            "Recommend Mode mapping: 1 = Street Network, 2 = Beats, 3 = Use Default. In the current CAD configuration, Use Default resolves to Street Network."
        )

    with alarms_tab:
        if alarm_levels.empty:
            st.info("No additional-alarm configuration has been imported yet.")
        else:
            alarm_display = alarm_levels.rename(columns={
                "event_type": "Event Type",
                "event_description": "Description",
                "alarm_level": "Alarm Level",
                "response_plan": "Response Plan",
                "pager_id": "Pager ID",
                "instructions": "Instructions",
            })[["Event Type", "Description", "Alarm Level", "Response Plan", "Pager ID", "Instructions"]]
            st.dataframe(alarm_display, hide_index=True, use_container_width=True)
            st.caption(
                "Additional-alarm rows in v0.10 were transcribed from the CADDBM alarm-level grids you supplied. They can be replaced directly when the raw alarm-level table is available."
            )


if page == "Units & Resources":
    _workspace_header("Units & Resources", "Manage the regional unit inventory and station availability.")

    units_tab, stations_tab = st.tabs(["Units", "Stations"])

    with units_tab:
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
            unit_search = st.text_input(
                "Search unit ID, type, beat, or station",
                value=global_search if global_search else "",
                key="unit_search_v090",
            )
        with type_c:
            type_values = ["All"] + sorted(
                x for x in catalog["unit_type"].unique() if x
            )
            selected_type = st.selectbox("Unit Type", type_values, key="unit_type_filter_v090")

        view = catalog.copy()
        if unit_search.strip():
            q = unit_search.strip().lower()
            mask = (
                view["unit_id"].str.lower().str.contains(q, regex=False)
                | view["unit_type"].str.lower().str.contains(q, regex=False)
                | view["beat"].str.lower().str.contains(q, regex=False)
                | view["station_id"].str.lower().str.contains(q, regex=False)
            )
            view = view[mask]
        if selected_type != "All":
            view = view[view["unit_type"] == selected_type]

        display = view.rename(columns={
            "unit_id": "Unit ID",
            "unit_type": "Unit Type",
            "beat": "Beat",
            "station_id": "Station",
            "default_attributes": "Capabilities",
            "default_m_skill": "M Skills",
            "default_equipment": "Equipment",
            "typical_als_equipment": "Typical ALS Equipment",
        })[
            ["Unit ID", "Unit Type", "Beat", "Station", "Capabilities", "M Skills", "Equipment", "Typical ALS Equipment"]
        ]
        st.dataframe(display.head(1000), hide_index=True, use_container_width=True)

    with stations_tab:
        effective_stations = _effective_stations()
        active_station_count = int(effective_stations["active"].sum())
        jurisdiction_count = effective_stations["jurisdiction"].replace("", pd.NA).dropna().nunique()

        st.markdown(
            f"""
            <div class="result-summary">
              <span class="summary-pill">Active Stations <strong>{active_station_count}</strong></span>
              <span class="summary-pill">Jurisdictions <strong>{jurisdiction_count}</strong></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        station_search = st.text_input(
            "Search station ID, jurisdiction, name, or address",
            key="station_search_v090",
        )
        station_view = effective_stations.copy()
        if station_search.strip():
            q = station_search.strip().lower()
            mask = (
                station_view["cad_station_id"].str.lower().str.contains(q, regex=False)
                | station_view["jurisdiction"].str.lower().str.contains(q, regex=False)
                | station_view["station_name"].str.lower().str.contains(q, regex=False)
                | station_view["address"].str.lower().str.contains(q, regex=False)
            )
            station_view = station_view[mask]

        station_display = station_view.rename(columns={
            "active": "Active",
            "cad_station_id": "CAD Station ID",
            "jurisdiction": "Jurisdiction",
            "local_station_number": "Local Station",
            "station_name": "Station Name",
            "address": "Routing Address",
        })[
            ["Active", "CAD Station ID", "Jurisdiction", "Local Station", "Station Name", "Routing Address"]
        ]

        edited_stations = st.data_editor(
            station_display,
            hide_index=True,
            use_container_width=True,
            disabled=["CAD Station ID", "Jurisdiction", "Local Station", "Station Name", "Routing Address"],
            column_config={
                "Active": st.column_config.CheckboxColumn("Active", width="small"),
                "CAD Station ID": st.column_config.TextColumn("Station", width="small"),
                "Jurisdiction": st.column_config.TextColumn("Jurisdiction", width="medium"),
                "Local Station": st.column_config.TextColumn("Local", width="small"),
                "Station Name": st.column_config.TextColumn("Station Name", width="medium"),
                "Routing Address": st.column_config.TextColumn("Routing Address", width="large"),
            },
            key="station_editor_v090",
        )
        for _, row in edited_stations.iterrows():
            sid = str(row["CAD Station ID"])
            st.session_state.station_active_overrides[sid] = bool(row["Active"])


if page == "Capabilities":
    _workspace_header(
        "Capabilities",
        "Imported DEFINE REQUIREMENT criteria, linked equipment/resources, unit attributes, and personnel skill M.",
    )

    executable_count = sum(1 for r in REQUIREMENTS.values() if r.executable)
    linked_resource_count = len(requirement_resources)
    criteria_count = len(requirement_source)

    st.markdown(
        f"""
        <div class="dashboard-kpis">
          <div class="kpi-card"><div class="kpi-icon blue">R</div><div><div class="kpi-label">Requirements</div><div class="kpi-number">{len(REQUIREMENTS):,}</div><div class="kpi-caption">Unique CAD definitions</div></div></div>
          <div class="kpi-card"><div class="kpi-icon cyan">≡</div><div><div class="kpi-label">Criteria Rows</div><div class="kpi-number">{criteria_count:,}</div><div class="kpi-caption">DEFINE REQUIREMENT rows</div></div></div>
          <div class="kpi-card"><div class="kpi-icon navy">◇</div><div><div class="kpi-label">Resource Links</div><div class="kpi-number">{linked_resource_count:,}</div><div class="kpi-caption">Equipment / skills</div></div></div>
          <div class="kpi-card"><div class="kpi-icon charcoal">✓</div><div><div class="kpi-label">Decoded</div><div class="kpi-number">{executable_count:,}</div><div class="kpi-caption">No unresolved attribute bits</div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    req_search = st.text_input(
        "Search requirements",
        placeholder="AFR1, ALS_SKILL, SUPPRESSION UNIT...",
        key="requirement_search_v010",
    )
    req_rows = []
    for name, r in REQUIREMENTS.items():
        lines = list(r.lines)
        req_rows.append({
            "Requirement": name,
            "Criteria Lines": len(lines),
            "Quantity": ", ".join(str(line.quantity) for line in lines),
            "Unit Type": ", ".join(filter(None, [line.unit_type for line in lines])),
            "Unit ID": ", ".join(filter(None, [line.unit_id for line in lines])),
            "Station": ", ".join(filter(None, [line.station for line in lines])),
            "Attributes": ", ".join(dict.fromkeys(a for line in lines for a in line.attributes)),
            "Equipment": ", ".join(dict.fromkeys(e for line in lines for e in line.equipment)),
            "Skills": ", ".join(dict.fromkeys(skill for line in lines for skill in line.skills)),
            "Beat": ", ".join(dict.fromkeys(line.beat_option for line in lines)),
            "Eq/Skill Option": ", ".join(dict.fromkeys(line.equipment_skill_option for line in lines)),
            "Decoded": "Yes" if r.executable else "Needs attribute lookup",
        })
    req_df = pd.DataFrame(req_rows)
    if req_search.strip():
        q = req_search.strip().lower()
        req_df = req_df[
            req_df.astype(str).apply(
                lambda row: row.str.lower().str.contains(q, regex=False).any(), axis=1
            )
        ]
    st.dataframe(req_df, hide_index=True, use_container_width=True)

    with st.expander("Imported field mappings", expanded=False):
        st.write(
            "`has_res`: 0 = no equipment/skill criteria; 1 = equipment and/or skill criteria. "
            "`res_type`: 1 = equipment; 2 = personnel skill. "
            "`recommend_mode`: 1 = Street Network; 2 = Beats; 3 = Use Default."
        )
        st.write(
            "CADence currently evaluates personnel skill `M`. Equipment and M staffing remain dynamic scenario state rather than permanent unit capability."
        )

    with st.expander("Known Unit Attributes", expanded=False):
        st.write(", ".join(ATTRIBUTE_OPTIONS))


if page == "Equipment":
    _workspace_header("Equipment", "Equipment codes used for unit capability and response-plan qualification.")

    equipment_rows = [{"Equipment Code": code, "Status": "Modeled"} for code in EQUIPMENT_OPTIONS]
    st.markdown(
        f"""
        <div class="dashboard-kpis">
          <div class="kpi-card"><div class="kpi-icon blue">◇</div><div><div class="kpi-label">Equipment Items</div><div class="kpi-number">{len(EQUIPMENT_OPTIONS)}</div><div class="kpi-caption">Current modeled codes</div></div></div>
          <div class="kpi-card"><div class="kpi-icon cyan">1</div><div><div class="kpi-label">ALS Level 1</div><div class="kpi-number">AFR1</div><div class="kpi-caption">Typical engine ALS equipment</div></div></div>
          <div class="kpi-card"><div class="kpi-icon navy">2</div><div><div class="kpi-label">ALS Level 2</div><div class="kpi-number">AFR2</div><div class="kpi-caption">Typical special-service ALS equipment</div></div></div>
          <div class="kpi-card"><div class="kpi-icon charcoal">M</div><div><div class="kpi-label">Skill Model</div><div class="kpi-number">M</div><div class="kpi-caption">Tracked separately from equipment</div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(equipment_rows), hide_index=True, use_container_width=True)


if page == "Scenarios":
    _workspace_header(
        "Scenarios",
        "Simulate an event type against operational conditions, available units, and routing.",
    )

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

        incident_beat = st.text_input(
            "Incident Beat (optional)",
            value="",
            placeholder="Example: 421",
            help="Required only when the imported CAD requirement uses Primary Beat. CADence does not infer CAD beats from the street address.",
            key="incident_beat_v010",
        ).strip()

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

    run_disabled = scenario_df.empty or not str(response_plan_id).strip()
    if scenario_df.empty:
        st.info("Select at least one unit before running the simulation.")
    elif not str(response_plan_id).strip():
        st.info("This Event Type has no response plan configured for the selected Operational Condition.")

    run_simulation = st.button(
        "Run Initial Dispatch",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
        key="run_initial_dispatch_v010",
    )

    if run_simulation:
        routed_frame = None
        route_df = None
        route_map_rows = []
        route_failures = []
        units = []

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
            except RoutingError as exc:
                st.error(str(exc))
                st.caption(
                    "You can also switch Location Input to Coordinates and run the scenario without address geocoding."
                )
            except Exception as exc:
                st.error("Routing is temporarily unavailable. Try again shortly or use Manual Time.")
                st.caption(str(exc))
        else:
            manual_frame = edited.copy()
            manual_frame["Routing Mode"] = "manual"
            units = scenario_units_from_frame(manual_frame)

        if units:
            try:
                state = simulate_response_plan(
                    response_plan_id,
                    units,
                    source_kind="Initial",
                    incident_beat=incident_beat,
                )
                st.session_state.incident_v010 = {
                    "event_type": event_type,
                    "event_description": event_descriptions[event_type],
                    "condition_id": condition_id,
                    "condition_name": condition_names[condition_id],
                    "initial_response_plan": response_plan_id,
                    "current_alarm_level": 1,
                    "routing_mode": routing_mode,
                    "incident_beat": incident_beat,
                    "state": state,
                    "units": units,
                    "routed_frame": routed_frame,
                    "route_df": route_df,
                    "route_map_rows": route_map_rows,
                    "route_failures": route_failures,
                    "incident_point": incident_point,
                }
            except UnsupportedConfigurationError as exc:
                st.error(f"This imported plan cannot yet be fully simulated: {exc}")
            except Exception as exc:
                st.error(f"Simulation failed: {exc}")

    incident = st.session_state.get("incident_v010")
    if incident:
        state = incident["state"]
        units = incident["units"]
        routed_frame = incident.get("routed_frame")
        route_df = incident.get("route_df")
        route_map_rows = incident.get("route_map_rows") or []
        route_failures = incident.get("route_failures") or []
        incident_point_active = incident.get("incident_point")
        ordered_assignments = assignments_in_dispatch_order(state)
        result_rows = _result_table(state, routed_frame)

        st.write("")
        with st.container(border=True):
            _section_header(
                "Active incident",
                "Dispatch recommendation",
                "Initial response plus any additional alarm or Ad Hoc plans applied to the same incident state.",
            )
            st.markdown(
                f"""
                <div class="result-summary">
                  <span class="summary-pill success">Incident active</span>
                  <span class="summary-pill">Event <strong>{html.escape(str(incident['event_type']))}</strong></span>
                  <span class="summary-pill">Initial Plan <strong>{html.escape(str(incident['initial_response_plan']))}</strong></span>
                  <span class="summary-pill">Condition <strong>{html.escape(str(incident['condition_id']))}</strong></span>
                  <span class="summary-pill">Alarm Level <strong>{int(incident['current_alarm_level'])}</strong></span>
                  <span class="summary-pill">Units <strong>{len(ordered_assignments)}</strong></span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if result_rows:
                _render_dispatch_cards(result_rows)
                with st.expander("Table View", expanded=False):
                    st.dataframe(
                        pd.DataFrame(result_rows),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Dispatch Order": st.column_config.NumberColumn("Order", width="small"),
                            "Road Distance (mi)": st.column_config.NumberColumn("Road mi", format="%.2f"),
                        },
                    )
            else:
                st.info("No resources were recommended from the current incident state.")

        with st.container(border=True):
            _section_header(
                "Post-dispatch actions",
                "Escalate or supplement the incident",
                "Additional alarms and Ad Hoc plans evaluate against resources already on the incident.",
            )

            next_alarm = next_alarm_for_event(
                incident["event_type"],
                int(incident["current_alarm_level"]),
                alarm_levels,
            )
            action_left, action_right = st.columns(2)

            with action_left:
                if next_alarm is None:
                    st.caption("No higher alarm level is configured for this Event Type in the imported alarm table.")
                else:
                    level = int(next_alarm["alarm_level"])
                    next_alarm_plan = str(next_alarm["response_plan"])
                    alarm_plan_available = next_alarm_plan in set(response_plan_meta["resp_plan_name"].astype(str))
                    st.write(f"**Next Alarm:** Level {level} → `{next_alarm_plan}`")
                    if not alarm_plan_available:
                        st.warning(
                            "This CAD alarm-level record references a response plan that is not present in the supplied Response_Plans export. The mapping is preserved, but CADence will not invent the missing plan."
                        )
                    if st.button(
                        f"Add Alarm Level {level}",
                        use_container_width=True,
                        disabled=not alarm_plan_available,
                        key=f"add_alarm_v010_{incident['event_type']}_{level}",
                    ):
                        working_state = copy.deepcopy(state)
                        try:
                            new_state = simulate_response_plan(
                                next_alarm_plan,
                                units,
                                state=working_state,
                                source_kind=f"Alarm {level}",
                                incident_beat=str(incident.get("incident_beat", "")),
                            )
                            incident["state"] = new_state
                            incident["current_alarm_level"] = level
                            st.session_state.incident_v010 = incident
                            st.rerun()
                        except UnsupportedConfigurationError as exc:
                            st.error(f"Alarm plan cannot yet be fully simulated: {exc}")
                        except Exception as exc:
                            st.error(f"Unable to apply alarm plan: {exc}")

            with action_right:
                ad_hoc_options = ad_hoc_plan_names(response_plan_meta)
                selected_ad_hoc = st.selectbox(
                    "Ad Hoc Response Plan",
                    options=ad_hoc_options,
                    index=None,
                    placeholder="Select an Ad Hoc plan",
                    key="ad_hoc_plan_v010",
                )
                if st.button(
                    "Apply Ad Hoc Plan",
                    use_container_width=True,
                    disabled=not selected_ad_hoc,
                    key="apply_ad_hoc_v010",
                ):
                    working_state = copy.deepcopy(state)
                    try:
                        new_state = simulate_response_plan(
                            str(selected_ad_hoc),
                            units,
                            state=working_state,
                            source_kind="Ad Hoc",
                            incident_beat=str(incident.get("incident_beat", "")),
                        )
                        incident["state"] = new_state
                        st.session_state.incident_v010 = incident
                        st.rerun()
                    except UnsupportedConfigurationError as exc:
                        st.error(f"Ad Hoc plan cannot yet be fully simulated: {exc}")
                    except Exception as exc:
                        st.error(f"Unable to apply Ad Hoc plan: {exc}")

            if st.button("Reset Active Incident", use_container_width=True, key="reset_incident_v010"):
                del st.session_state["incident_v010"]
                st.rerun()

        if incident.get("routing_mode") == "OpenStreetMap / OSRM" and route_map_rows and incident_point_active is not None:
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
                _section_header("Route map", "Incident resources", "The red star marks the incident.")
                deck = _route_map(visible_route_rows, incident_point_active)
                if deck is not None:
                    st.pydeck_chart(deck, use_container_width=True, height=560)
                else:
                    st.info("No route geometry is available for the selected map filter.")

        with st.expander("Technical Details", expanded=False):
            tech_tabs = st.tabs(["Routing", "Trace", "Plan Flow", "Incident History"])

            with tech_tabs[0]:
                if incident.get("routing_mode") != "OpenStreetMap / OSRM":
                    st.info("Routing diagnostics are available in Road Network mode.")
                elif route_df is None or route_df.empty:
                    st.info("No routing diagnostics are available.")
                else:
                    if route_failures:
                        failure_text = "; ".join(f"{sid}: {reason}" for sid, reason in route_failures)
                        st.warning(failure_text)
                    st.dataframe(
                        route_df.drop(
                            columns=["Travel Time (sec)", "Latitude", "Longitude", "Route Color"],
                            errors="ignore",
                        ),
                        hide_index=True,
                        use_container_width=True,
                    )

            with tech_tabs[1]:
                st.code("\n".join(state.trace), language="text")

            with tech_tabs[2]:
                applied_top_level = []
                for kind, plan_name in state.applied_plans:
                    if str(kind).startswith("Nested from"):
                        continue
                    pair = (kind, plan_name)
                    if pair not in applied_top_level:
                        applied_top_level.append(pair)
                flow_plan_options = [p for _, p in applied_top_level] or [incident["initial_response_plan"]]
                flow_plan = st.selectbox(
                    "Applied plan",
                    options=flow_plan_options,
                    key="technical_plan_flow_v010",
                )
                st.dataframe(
                    pd.DataFrame(plan_flow_rows(flow_plan, response_plan_items, response_plan_meta)),
                    hide_index=True,
                    use_container_width=True,
                )

            with tech_tabs[3]:
                history_rows = []
                for idx, (kind, plan_name) in enumerate(state.applied_plans, start=1):
                    if str(kind).startswith("Nested from"):
                        continue
                    history_rows.append({"Sequence": idx, "Action": kind, "Response Plan": plan_name})
                st.dataframe(pd.DataFrame(history_rows), hide_index=True, use_container_width=True)

    st.caption(
        "Road Network uses OpenStreetMap / OSRM and may differ from Hexagon routing. Imported CAD criteria that are not yet decoded fail explicitly rather than being ignored."
    )


if page == "Analysis":
    _workspace_header("Analysis", "Compare response behavior, requirements, and resource utilization.")

    st.markdown(
        """
        <div class="quick-grid">
          <div class="quick-card">
            <div class="quick-title">Scenario Comparison</div>
            <div class="quick-copy">Compare the same incident across operational conditions or future response-plan revisions.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Over-Recommendation Review</div>
            <div class="quick-copy">Future analysis will identify resources recommended beyond the operational requirement set.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Coverage Analysis</div>
            <div class="quick-copy">Evaluate how routing, unit availability, and station status affect candidate selection.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Analysis workflows will expand as additional response plans are modeled.")


if page == "Reports":
    _workspace_header("Reports", "Create auditable outputs from modeled response plans and simulation scenarios.")

    st.markdown(
        """
        <div class="quick-grid">
          <div class="quick-card">
            <div class="quick-title">Simulation Report</div>
            <div class="quick-copy">Planned output: event type, condition, selected units, satisfied requirements, and routing details.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Response Plan Comparison</div>
            <div class="quick-copy">Planned output: side-by-side differences between production and proposed response-plan structures.</div>
          </div>
          <div class="quick-card">
            <div class="quick-title">Configuration Audit</div>
            <div class="quick-copy">Planned output: event-type mappings, requirements, capabilities, equipment, and station state.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Report generation is not yet enabled in this release.")


if page == "Settings":
    _workspace_header("Settings", "Operational-condition definitions and simulation environment settings.")

    with st.container(border=True):
        _section_header("Operational conditions", "CADence environment")
        st.write(
            "**Condition 1:** Normal Operations  ·  "
            "**Condition 2:** High Call Volume  ·  "
            "**Condition 3:** >50% Unit Utilization"
        )
        st.caption(
            "Event types remain dispatcher-facing identifiers. The associated response plan "
            "is resolved from the event type and operational condition."
        )

    with st.container(border=True):
        _section_header("Routing", "Current engine")
        st.write("OpenStreetMap / OSRM")
        st.caption(
            "Routing is independent of Hexagon street-network configuration and may produce different travel times."
        )

    with st.container(border=True):
        _section_header("Environment", "Deployment status")
        st.write("Simulation environment")
        st.caption("No connection to production I/CAD.")


st.divider()
st.caption(
    "CADence simulation environment · No connection to production I/CAD · "
    "OpenStreetMap data © OpenStreetMap contributors · Routing via OSRM"
)
