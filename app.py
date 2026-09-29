from __future__ import annotations

import math
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
    response_plan_changes_by_condition,
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
    page_title="CAD Response Designer v0.6.0",
    page_icon="🚒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1680px;
        padding-top: 1.25rem;
        padding-bottom: 3rem;
    }
    .cad-hero {
        border-radius: 14px;
        padding: 1.15rem 1.35rem;
        margin-bottom: 1rem;
        background: linear-gradient(110deg, #182536 0%, #223a50 62%, #28566a 100%);
        color: white;
        border: 1px solid rgba(255,255,255,.08);
    }
    .cad-hero .title {
        font-size: 1.7rem;
        font-weight: 750;
        line-height: 1.15;
        letter-spacing: .01em;
        margin: 0;
    }
    .cad-hero .sub {
        opacity: .82;
        font-size: .93rem;
        margin-top: .35rem;
    }
    .section-kicker {
        color: #64748b;
        font-weight: 700;
        font-size: .74rem;
        letter-spacing: .09em;
        text-transform: uppercase;
        margin-bottom: .2rem;
    }
    .section-title {
        font-size: 1.22rem;
        font-weight: 720;
        margin-bottom: .25rem;
    }
    .plan-card {
        min-height: 92px;
        border: 1px solid #d8e0e8;
        border-radius: 12px;
        padding: .85rem 1rem;
        background: #f8fafc;
    }
    .plan-card .label {
        color: #64748b;
        font-size: .76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .06em;
    }
    .plan-card .value {
        color: #102235;
        font-size: 1.35rem;
        font-weight: 760;
        margin-top: .18rem;
    }
    .plan-card .note {
        color: #526274;
        font-size: .79rem;
        margin-top: .15rem;
    }
    .status-chip {
        display: inline-block;
        border-radius: 999px;
        padding: .2rem .55rem;
        background: #e8f3ee;
        color: #205d46;
        border: 1px solid #cce4d8;
        font-weight: 650;
        font-size: .76rem;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dfe5eb;
        padding: .7rem .9rem;
        border-radius: 12px;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #dfe5eb;
        border-radius: 10px;
    }
    .small-muted {
        color: #64748b;
        font-size: .82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="cad-hero">
      <div class="title">CAD Response Designer</div>
      <div class="sub">Response-plan simulation, regional routing, and operational scenario testing · v0.6.0</div>
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

simulator_tab, station_tab, unit_tab, config_tab = st.tabs(
    ["Dispatch Simulator", "Stations", "Units", "Configuration"]
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
        rec = station_record(sid, stations)
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

    incident_data = [{
        "position": [incident_point.lon, incident_point.lat],
        "symbol": "★",
        "label": "INCIDENT",
        "location": incident_point.label,
    }]

    # The incident uses a star symbol, clearly different from circular station markers.
    incident_icon_layer = pdk.Layer(
        "TextLayer",
        data=incident_data,
        get_position="position",
        get_text="symbol",
        get_color=[190, 0, 0, 255],
        get_size=34,
        get_text_anchor='"middle"',
        get_alignment_baseline='"center"',
        billboard=True,
        pickable=True,
    )

    incident_label_layer = pdk.Layer(
        "TextLayer",
        data=incident_data,
        get_position="position",
        get_text="label",
        get_color=[140, 0, 0, 255],
        get_size=14,
        get_pixel_offset=[0, -24],
        get_text_anchor='"middle"',
        get_alignment_baseline='"bottom"',
        billboard=True,
        pickable=False,
    )

    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=_map_view_state(route_map_rows, incident_point),
        layers=[
            path_layer,
            station_layer,
            station_label_layer,
            incident_icon_layer,
            incident_label_layer,
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


with simulator_tab:
    _section_header(
        "Dispatch setup",
        "Build the operational scenario",
        "Select the operating condition and event type first. The associated response plan is resolved automatically.",
    )

    condition_records = operational_conditions(event_plan_map)
    condition_ids = [r["operational_condition"] for r in condition_records]
    condition_names = {
        r["operational_condition"]: r["condition_name"] for r in condition_records
    }

    setup_c1, setup_c2, setup_c3 = st.columns([1.35, 1.35, 1.0], gap="large")

    with setup_c1:
        condition_id = st.radio(
            "Operational Condition",
            options=condition_ids,
            format_func=lambda x: f"Condition {x} — {condition_names[x]}",
            horizontal=False,
            key="operational_condition",
        )

    event_records = event_types_for_condition(condition_id, event_plan_map)
    event_ids = [r["event_type"] for r in event_records]
    event_descriptions = {r["event_type"]: r["description"] for r in event_records}

    with setup_c2:
        event_type = st.selectbox(
            "Event Type",
            options=event_ids,
            format_func=lambda x: f"{x} — {event_descriptions[x]}",
            key="event_type",
        )
        st.caption("Dispatch-facing event type and description.")

    mapping = resolve_response_plan(event_type, condition_id, event_plan_map)
    response_plan_id = mapping["response_plan_id"]
    plan_is_constant = not response_plan_changes_by_condition(event_type, event_plan_map)

    with setup_c3:
        note = (
            "Same plan under all 3 conditions"
            if plan_is_constant
            else f"Mapped from Condition {condition_id}"
        )
        st.markdown(
            f"""
            <div class="plan-card">
              <div class="label">Associated Response Plan</div>
              <div class="value">{response_plan_id}</div>
              <div class="note">{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    _section_header(
        "Incident",
        "Location and routing",
        "Use the road network for operational testing, or switch to manual time for isolated plan validation.",
    )

    route_c1, route_c2 = st.columns([1.0, 2.2], gap="large")
    with route_c1:
        routing_mode = st.radio(
            "Routing Mode",
            ["OpenStreetMap / OSRM", "Manual Test Time"],
            horizontal=False,
            help=(
                "OSM mode ranks eligible candidates by estimated network travel time. "
                "Manual mode uses the entered test time in minutes."
            ),
        )

    incident_point = None
    incident_mode = None
    incident_address = ""
    incident_lat = 38.8500
    incident_lon = -77.3000

    with route_c2:
        if routing_mode == "OpenStreetMap / OSRM":
            incident_mode = st.radio(
                "Incident Location Input",
                ["Street Address", "Latitude / Longitude"],
                horizontal=True,
            )
            if incident_mode == "Street Address":
                incident_address = st.text_input(
                    "Incident address",
                    placeholder="Example: 12000 Government Center Pkwy, Fairfax, VA 22035",
                    label_visibility="collapsed",
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
                    )
                with lon_c:
                    incident_lon = st.number_input(
                        "Longitude",
                        min_value=-180.0,
                        max_value=180.0,
                        value=-77.3000,
                        format="%.6f",
                    )
        else:
            st.info(
                "Manual Test Time mode does not require an incident location. "
                "Enter the test time for each unit in the scenario editor below."
            )

    st.divider()

    _section_header(
        "Resources",
        "Units in service",
        "Select the available resources for this scenario. Unit ID and Unit Type remain locked.",
    )

    selected_ids = st.multiselect(
        "Units in service",
        options=catalog["unit_id"].tolist(),
        default=default_units,
        help="Search by Unit ID. Only selected units participate in the simulation.",
    )

    selected = catalog[catalog["unit_id"].isin(selected_ids)].copy().sort_values("unit_id")

    summary_c1, summary_c2, summary_c3 = st.columns(3)
    summary_c1.metric("Units in service", len(selected_ids))
    summary_c2.metric(
        "Stations represented",
        selected["station_id"].replace("", pd.NA).dropna().nunique() if not selected.empty else 0,
    )
    summary_c3.metric(
        "Routing",
        "OSM / OSRM" if routing_mode == "OpenStreetMap / OSRM" else "Manual time",
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
        with st.expander("Edit unit scenario", expanded=True):
            st.caption(
                "Beat and Station are single-select. Attributes and Equipment allow multiple values. "
                "Manual Test Time is ignored when OSM routing is active."
            )
            edited = st.data_editor(
                scenario_df,
                hide_index=True,
                use_container_width=True,
                disabled=["Unit ID", "Unit Type", "Typical ALS Equipment"],
                column_config={
                    "Beat": st.column_config.SelectboxColumn(
                        "Beat",
                        options=BEAT_OPTIONS,
                        help="Select one current beat for the unit.",
                    ),
                    "Station": st.column_config.SelectboxColumn(
                        "Station",
                        options=STATION_OPTIONS,
                        help="Select one current station for the unit.",
                    ),
                    "Attributes": st.column_config.MultiselectColumn(
                        "Attributes",
                        options=ATTRIBUTE_OPTIONS,
                        accept_new_options=True,
                        help="Select one or more unit attributes.",
                        width="large",
                    ),
                    "Equipment": st.column_config.MultiselectColumn(
                        "Equipment",
                        options=EQUIPMENT_OPTIONS,
                        accept_new_options=True,
                        help="Select one or more equipment codes.",
                        width="large",
                    ),
                    "M Skills": st.column_config.SelectboxColumn(
                        "M Skills",
                        options=[0, 1, 2, 3, 4],
                        help="Rostered personnel with personnel skill M.",
                    ),
                    "Test Time (min)": st.column_config.NumberColumn(
                        "Test Time (min)",
                        min_value=0.0,
                        step=0.1,
                        help="Manual-mode stand-in for CAD travel time.",
                    ),
                    "Typical ALS Equipment": st.column_config.TextColumn(
                        "Typical ALS Equipment",
                        help="Reference only.",
                    ),
                },
                key="scenario_editor_v060",
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
                "Missing AFR equipment assignment: "
                + ", ".join(m_suffix_missing_afr)
                + ". Add AFR1 or AFR2 before testing ALS/AFR logic."
            )

        conflicts = pair_conflicts(edited)
        if conflicts:
            pairs = ", ".join(f"{a} + {b}" for a, b in conflicts)
            st.warning(
                "Base/M operational conflict: "
                + pairs
                + ". Normal operations use one member of each pair."
            )

    map_scope = "Dispatched units only"
    map_extra_units = []
    if routing_mode == "OpenStreetMap / OSRM":
        with st.expander("Map display options", expanded=False):
            map_scope = st.radio(
                "Routes shown on map",
                [
                    "Dispatched units only",
                    "Dispatched + selected in-service units",
                    "All in-service units",
                ],
                index=0,
                help="Dispatched units only is recommended for large regional scenarios.",
            )
            if map_scope == "Dispatched + selected in-service units":
                map_extra_units = st.multiselect(
                    "Additional units to display",
                    options=selected_ids,
                    default=[],
                )

    st.divider()

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

                    with st.spinner("Calculating regional road-network routes..."):
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

                st.markdown("---")
                _section_header(
                    "Simulation result",
                    "Dispatch recommendation",
                    "Displayed in response-plan dispatch order. ETA does not control the displayed order.",
                )

                result_c1, result_c2, result_c3, result_c4 = st.columns(4)
                result_c1.metric("Event Type", event_type)
                result_c2.metric("Response Plan", response_plan_id)
                result_c3.metric("Dispatched Units", len(ordered_assignments))
                result_c4.metric("Condition", f"{condition_id}")

                st.markdown(
                    '<span class="status-chip">Simulation complete</span>',
                    unsafe_allow_html=True,
                )
                st.write("")

                if result_rows:
                    result_df = pd.DataFrame(result_rows)
                    st.dataframe(
                        result_df,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Dispatch Order": st.column_config.NumberColumn(
                                "Order", width="small"
                            ),
                            "Unit": st.column_config.TextColumn(
                                "Unit", width="medium"
                            ),
                            "Requirement": st.column_config.TextColumn(
                                "Requirement", width="medium"
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
                    _section_header(
                        "Map",
                        "Dispatched routes",
                        "Circular markers identify station origins; the red star identifies the incident.",
                    )
                    deck = _route_map(visible_route_rows, incident_point)
                    if deck is not None:
                        st.pydeck_chart(deck, use_container_width=True, height=620)
                    else:
                        st.info("No route geometry is available for the selected map filter.")

                with st.expander("Technical details", expanded=False):
                    tech_tabs = st.tabs(
                        ["Routing diagnostics", "Explanation trace", "Response-plan flow"]
                    )

                    with tech_tabs[0]:
                        if routing_mode != "OpenStreetMap / OSRM":
                            st.info("Routing diagnostics are available in OSM / OSRM mode.")
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
        "OSM / OSRM is an independent routing model and will not exactly reproduce "
        "Hexagon street data, emergency-response speeds, or agency-specific routing impedance."
    )


with station_tab:
    _section_header(
        "Reference data",
        "Regional station directory",
        "Three-digit CAD station IDs provide the jurisdiction-safe routing crosswalk.",
    )

    station_metrics = st.columns(3)
    station_metrics[0].metric("Active stations", int(stations["active"].sum()))
    station_metrics[1].metric(
        "Jurisdictions", stations["jurisdiction"].replace("", pd.NA).dropna().nunique()
    )
    station_metrics[2].metric("Directory rows", len(stations))

    station_search = st.text_input(
        "Search station ID, jurisdiction, name, or address",
        "",
        key="station_search_v060",
    )
    station_view = stations.copy()
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
        "notes": "Notes",
        "source_url": "Source",
    })[
        [
            "CAD Station ID", "Jurisdiction", "Local Station",
            "Station Name", "Routing Address", "Active", "Notes", "Source"
        ]
    ]
    st.dataframe(display_stations, hide_index=True, use_container_width=True)


with unit_tab:
    _section_header(
        "Reference data",
        "CADDBM unit catalog",
        "Search the imported unit inventory and modeled default capabilities.",
    )

    unit_metrics = st.columns(3)
    unit_metrics[0].metric("Imported units", f"{len(catalog):,}")
    unit_metrics[1].metric(
        "Unit types", catalog["unit_type"].replace("", pd.NA).dropna().nunique()
    )
    unit_metrics[2].metric(
        "Stations", catalog["station_id"].replace("", pd.NA).dropna().nunique()
    )

    search_c, type_c = st.columns([2.2, 1.0])
    with search_c:
        search = st.text_input(
            "Search Unit ID / type / beat / station",
            "",
            key="unit_search_v060",
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


with config_tab:
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
    "Prototype only · No connection to production I/CAD · "
    "OpenStreetMap data © OpenStreetMap contributors · Routing via OSRM"
)
