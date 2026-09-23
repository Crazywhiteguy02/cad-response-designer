from __future__ import annotations

import pandas as pd
import streamlit as st

from catalog import load_catalog
from requirements import REQUIREMENTS
from alpha_plan import ALPHA_STEPS
from engine import scenario_units_from_frame, simulate_alpha, pair_conflicts

st.set_page_config(page_title="CAD Response Designer v0.4.6", layout="wide")
st.title("CAD Response Designer — Prototype v0.4.6")
st.caption(
    "Current ALPHA response-plan model with the complete CADDBM unit catalog "
    "and an editable operational test scenario."
)

catalog = load_catalog()

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

scenario_tab, catalog_tab, req_tab = st.tabs(
    ["Scenario & ALPHA", "Unit Catalog", "Requirement Library"]
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


with scenario_tab:
    st.subheader("Operational test scenario")
    st.write(
        "Choose which CADDBM units are in service, then edit the variables that change most often. "
        "These values affect only the test scenario and do not alter CADDBM."
    )

    selected_ids = st.multiselect(
        "Units in service",
        options=catalog["unit_id"].tolist(),
        default=default_units,
        help="Search by typing a Unit ID. Only selected units participate in the simulation."
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
            "Test Distance": saved.get("Test Distance", 5.0),
            "Typical ALS Equipment": r["typical_als_equipment"],
        })

    scenario_df = pd.DataFrame(rows)

    if not scenario_df.empty:
        st.caption(
            "Unit ID and Unit Type are locked. Beat and Station are single-select dropdowns. "
            "Attributes and Equipment are multi-select fields so multiple values can be assigned."
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
                "Test Distance": st.column_config.NumberColumn(
                    "Test Distance",
                    min_value=0.0,
                    step=0.1,
                    help="Temporary stand-in for CAD routing/proximity."
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
                "Test Distance": float(row["Test Distance"]),
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

        if st.button("Simulate ALPHA", type="primary"):
            units = scenario_units_from_frame(edited)
            state = simulate_alpha(units)

            st.markdown("#### Recommended resources")
            if state.assignments:
                st.dataframe(
                    [
                        {
                            "Step": a.step,
                            "Requirement": a.requirement,
                            "Unit": a.unit_id
                        }
                        for a in state.assignments
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No resources were recommended from the current scenario.")

            st.markdown("#### Explanation trace")
            st.code("\n".join(state.trace), language="text")
    else:
        st.info("Select at least one unit to build a scenario.")

    with st.expander("Current ALPHA flow modeled in v0.4.6"):
        for n in sorted(ALPHA_STEPS):
            s = ALPHA_STEPS[n]
            if s.kind == "GROUP":
                detail = " OR ".join(s.alternatives)
            elif s.requirement:
                detail = s.requirement
            else:
                detail = ""
            extra = f" | Max Distance {s.max_distance:g}" if s.max_distance is not None else ""
            st.write(f"**Step {s.number}: {s.label}** — {detail}{extra}")

    st.info(
        "This prototype does not have Hexagon street-network/routing data. "
        "Test Distance is therefore used as the candidate-ordering stand-in. "
        "The ALPHA Max Distance 10 rule is enforced against that test value."
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
    "Scenario edits are temporary and may reset when Streamlit redeploys."
)
