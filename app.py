from __future__ import annotations

import math
import pandas as pd
import pydeck as pdk
import streamlit as st

from catalog import load_catalog
from requirements import REQUIREMENTS
from alpha_plan import ALPHA_STEPS
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
    filter_route_rows_for_map,
    format_duration,
    RoutingError,
)

st.set_page_config(page_title="CAD Response Designer v0.5.3", layout="wide")
st.title("CAD Response Designer — Prototype v0.5.3")
st.caption(
    "Current ALPHA response-plan model with the complete CADDBM unit catalog "
    "and an editable operational test scenario."
)

catalog = load_catalog()
stations = load_station_crosswalk()

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

scenario_tab, station_tab, catalog_tab, req_tab = st.tabs(
    ["Scenario & ALPHA", "Station Directory", "Unit Catalog", "Requirement Library"]
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


with scenario_tab:
    st.subheader("Operational test scenario")
    st.write(
        "Choose which CADDBM units are in service, then edit the variables that change most often. "
        "These values affect only the test scenario and do not alter CADDBM."
    )

    routing_mode = st.radio(
        "Routing Mode",
        ["OpenStreetMap / OSRM", "Manual Test Distance"],
        horizontal=True,
        help=(
            "OSM mode geocodes the incident and station addresses, then ranks candidates "
            "by estimated travel time on the OpenStreetMap road network. Manual mode uses "
            "a user-entered test time in minutes."
        ),
    )

    incident_point = None
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
            )
        else:
            c1, c2 = st.columns(2)
            with c1:
                incident_lat = st.number_input(
                    "Incident latitude",
                    min_value=-90.0,
                    max_value=90.0,
                    value=38.8500,
                    format="%.6f",
                )
            with c2:
                incident_lon = st.number_input(
                    "Incident longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    value=-77.3000,
                    format="%.6f",
                )

    selected_ids = st.multiselect(
        "Units in service",
        options=catalog["unit_id"].tolist(),
        default=default_units,
        help="Search by typing a Unit ID. Only selected units participate in the simulation."
    )

    map_scope = "Dispatched units only"
    map_extra_units = []
    if routing_mode == "OpenStreetMap / OSRM":
        map_scope = st.radio(
            "Map route visibility",
            [
                "Dispatched units only",
                "Dispatched + selected in-service units",
                "All in-service units",
            ],
            index=0,
            help=(
                "The map defaults to dispatched units only. Use the middle option to add "
                "specific non-dispatched units for comparison. Show all routes only when "
                "you deliberately want a full-system routing view."
            ),
        )
        if map_scope == "Dispatched + selected in-service units":
            map_extra_units = st.multiselect(
                "Additional in-service units to show on the map",
                options=selected_ids,
                default=[],
                help=(
                    "These routes are shown in addition to the dispatched units. "
                    "Units at the same station share one route line."
                ),
            )

    selected = catalog[catalog["unit_id"].isin(selected_ids)].copy().sort_values("unit_id")

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
            "Equipment": _equipment_list_from_saved(saved, r.get("default_equipment", "")),
            "M Skills": saved.get("M Skills", int(r["default_m_skill"])),
            "Test Time (min)": saved.get(
                "Test Time (min)", saved.get("Test Distance", 5.0)
            ),
            "Typical ALS Equipment": r["typical_als_equipment"],
        })

    scenario_df = pd.DataFrame(rows)

    if not scenario_df.empty:
        st.caption(
            "Unit ID and Unit Type are locked. Beat and Station are single-select dropdowns. "
            "Attributes and Equipment are multi-select fields. In OSM mode, the manual test time is "
            "ignored. ALPHA's CAD 'Max Distance 10' setting is treated as a 10-minute travel-time threshold."
        )

        edited = st.data_editor(
            scenario_df,
            hide_index=True,
            use_container_width=True,
            disabled=[
                "Unit ID", "Unit Type", "Typical ALS Equipment"
            ],
            column_config={
                "Beat": st.column_config.SelectboxColumn(
                    "Beat",
                    options=BEAT_OPTIONS,
                    help="Select one current beat for the unit."
                ),
                "Station": st.column_config.SelectboxColumn(
                    "Station",
                    options=STATION_OPTIONS,
                    help="Select one current station for the unit."
                ),
                "Attributes": st.column_config.MultiselectColumn(
                    "Attributes",
                    options=ATTRIBUTE_OPTIONS,
                    accept_new_options=True,
                    help="Select one or more unit attributes. New attribute codes may also be entered for testing.",
                    width="large",
                ),
                "Equipment": st.column_config.MultiselectColumn(
                    "Equipment",
                    options=EQUIPMENT_OPTIONS,
                    accept_new_options=True,
                    help=(
                        "Select one or more equipment codes. "
                        "New codes may also be entered for testing."
                    ),
                    width="large",
                ),
                "M Skills": st.column_config.SelectboxColumn(
                    "M Skills",
                    options=[0, 1, 2, 3, 4],
                    help="Number of rostered personnel with personnel skill M. Typical test range is 0-4."
                ),
                "Test Time (min)": st.column_config.NumberColumn(
                    "Test Time (min)",
                    min_value=0.0,
                    step=0.1,
                    help=(
                        "Manual-mode stand-in for CAD travel time. "
                        "ALPHA's configured value of 10 is treated as a 10-minute threshold."
                    )
                ),
                "Typical ALS Equipment": st.column_config.TextColumn(
                    "Typical ALS Equipment",
                    help="Reference only. M-suffix units typically carry AFR1 or AFR2."
                ),
            },
            key="scenario_editor",
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

        # Make missing ALS equipment conspicuous for M-suffix units that normally carry it.
        m_suffix_missing_afr = []
        for _, row in edited.iterrows():
            uid = str(row["Unit ID"])
            typical = str(row.get("Typical ALS Equipment", ""))
            equipment = row.get("Equipment", [])
            if not isinstance(equipment, list):
                equipment = [] if pd.isna(equipment) else [str(equipment)]
            if typical in {"AFR1", "AFR2", "AFR1 or AFR2"} and not ({"AFR1", "AFR2"} & set(equipment)):
                m_suffix_missing_afr.append(uid)

        if m_suffix_missing_afr:
            st.warning(
                "AFR equipment is not assigned for these units that normally carry AFR1 or AFR2: "
                + ", ".join(m_suffix_missing_afr)
                + ". Add AFR1 or AFR2 in the Equipment field before testing ALS/AFR logic."
            )

        # Pair checking is still active internally, but the Pair Unit column is no longer shown.
        conflicts = pair_conflicts(edited)
        if conflicts:
            pairs = ", ".join(f"{a} + {b}" for a, b in conflicts)
            st.warning(
                "Operational realism warning: both members of a base/M pair are in service: "
                + pairs
                + ". This is allowed for testing, but normal operations use one or the other."
            )

        button_label = (
            "Route & Simulate ALPHA"
            if routing_mode == "OpenStreetMap / OSRM"
            else "Simulate ALPHA"
        )

        if st.button(button_label, type="primary"):
            routed_frame = None
            route_df = None
            route_map_rows = []

            if routing_mode == "OpenStreetMap / OSRM":
                try:
                    if incident_mode == "Street Address":
                        if not incident_address.strip():
                            raise RoutingError("Enter an incident address before routing.")
                        incident_point = _point_from_cached(_cached_geocode(incident_address.strip()))
                    else:
                        incident_point = parse_lat_lon(incident_lat, incident_lon)

                    with st.spinner("Calculating OpenStreetMap road-network routes..."):
                        routed_frame, route_df, route_map_rows, route_failures = _routing_dataframe(
                            edited, incident_point
                        )

                    st.markdown("#### Routing diagnostics")
                    st.caption(
                        f"Incident: {incident_point.label}. "
                        "This table is diagnostic only and is not the CAD dispatch/display order."
                    )

                    if route_failures:
                        failure_text = "; ".join(
                            f"{sid}: {reason}" for sid, reason in route_failures
                        )
                        st.warning(
                            "Some station origins could not be routed and their units will not be "
                            f"eligible in OSM mode: {failure_text}"
                        )

                    if route_df is not None and not route_df.empty:
                        with st.expander("Routing diagnostics — all in-service unit origins"):
                            st.caption(
                                "This table includes all routed in-service station origins. "
                                "It is diagnostic only and does not control map visibility or dispatch order."
                            )
                            st.dataframe(
                                route_df.drop(columns=["Travel Time (sec)", "Latitude", "Longitude"]),
                                hide_index=True,
                                use_container_width=True,
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

                st.markdown("#### Recommended resources — response-plan dispatch order")
                if state.assignments:
                    st.dataframe(
                        _result_table(state, routed_frame),
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No resources were recommended from the current scenario.")

                if routing_mode == "OpenStreetMap / OSRM" and route_map_rows:
                    dispatched_ids = [
                        a.unit_id for a in assignments_in_dispatch_order(state)
                    ]
                    show_all_routes = map_scope == "All in-service units"
                    additional_ids = (
                        map_extra_units
                        if map_scope == "Dispatched + selected in-service units"
                        else []
                    )

                    visible_route_rows = filter_route_rows_for_map(
                        route_map_rows,
                        dispatched_ids,
                        show_all=show_all_routes,
                        additional_unit_ids=additional_ids,
                    )

                    st.markdown("#### Route map")
                    if map_scope == "Dispatched units only":
                        st.caption(
                            "Showing dispatched units only. Each station route is drawn once; "
                            "if multiple dispatched units originate from the same station, they share that route."
                        )
                    elif map_scope == "Dispatched + selected in-service units":
                        st.caption(
                            "Showing dispatched units plus the additional in-service units you selected."
                        )
                    else:
                        st.caption(
                            "Showing all routed in-service units. This view can become dense in large scenarios."
                        )

                    deck = _route_map(visible_route_rows, incident_point)
                    if deck is not None:
                        st.pydeck_chart(deck, use_container_width=True, height=600)
                    else:
                        st.info("No route geometry is available for the current map filter.")

                st.markdown("#### Explanation trace")
                st.code("\n".join(state.trace), language="text")

    else:
        st.info("Select at least one unit to build a scenario.")

    with st.expander("Current ALPHA flow modeled in v0.5.3"):
        for n in sorted(ALPHA_STEPS):
            s = ALPHA_STEPS[n]
            if s.kind == "GROUP":
                detail = " OR ".join(s.alternatives)
            elif s.requirement:
                detail = s.requirement
            else:
                detail = ""
            extra = (
                f" | CAD Max Distance {s.max_time_minutes:g} = {s.max_time_minutes:g} min"
                if s.max_time_minutes is not None else ""
            )
            st.write(f"**Step {s.number}: {s.label}** — {detail}{extra}")

    st.info(
        "OpenStreetMap / OSRM mode calculates actual road-network routes and ranks "
        "eligible candidates by estimated travel time. The map defaults to dispatched units only. "
        "ALPHA's CAD Max Distance 10 setting is treated as a 10-minute travel-time threshold. "
        "Manual Test Time remains available as a diagnostic fallback. OSM/OSRM results are an independent routing "
        "model and are not expected to exactly reproduce Hexagon routing."
    )


with station_tab:
    st.subheader("Regional station directory")
    st.write(
        f"Routable station crosswalk entries: **{len(stations[stations['active']]):,} active** "
        f"across the requested Washington-region jurisdictions."
    )
    station_search = st.text_input("Search stations", "", key="station_search")
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
    st.caption(
        "The three-digit CAD Station ID is the routing crosswalk key. "
        "Inactive facilities remain visible for traceability but are not routed."
    )

with catalog_tab:
    st.subheader("CADDBM unit catalog")
    st.write(f"Imported unit records: **{len(catalog):,}**")
    search = st.text_input("Search Unit ID / type / beat / station", "")
    type_values = ["All"] + sorted(x for x in catalog["unit_type"].unique() if x)
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
        "attribute_source": "Attribute Source"
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

with req_tab:
    st.subheader("Requirement library used by ALPHA")
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
    "Prototype only. No connection to production I/CAD. "
    "OpenStreetMap data © OpenStreetMap contributors. Geocoding uses the public Nominatim service "
    "and routing uses OSRM for prototype validation. Scenario edits are temporary and may reset "
    "when Streamlit redeploys."
)
