from __future__ import annotations
import pandas as pd
import streamlit as st

from catalog import load_catalog
from requirements import REQUIREMENTS
from alpha_plan import ALPHA_STEPS
from engine import scenario_units_from_frame, simulate_alpha, pair_conflicts

st.set_page_config(page_title="CAD Response Designer v0.4.1", layout="wide")
st.title("CAD Response Designer — Prototype v0.4.1")
st.caption(
    "Current ALPHA response-plan model with the complete CADDBM unit catalog "
    "and an editable operational test scenario."
)

catalog = load_catalog()

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

        # Backward compatibility with the v0.4 free-text Equipment field, if it exists
        # in session state from the current Streamlit session.
        old_equipment = str(saved.get("Equipment", ""))
        old_codes = [x.strip() for x in old_equipment.replace(";", ",").split(",") if x.strip()]
        old_afr = next((x for x in old_codes if x in {"AFR1", "AFR2"}), "")
        old_other = ", ".join(x for x in old_codes if x not in {"AFR1", "AFR2"})

        rows.append({
            "Unit ID": uid,
            "Unit Type": r["unit_type"],
            "Beat": saved.get("Beat", r["beat"]),
            "Station": r["station_id"],
            "Attributes": saved.get("Attributes", r["default_attributes"]),
            "AFR Equipment": saved.get("AFR Equipment", old_afr),
            "Other Equipment": saved.get("Other Equipment", old_other),
            "M Skills": saved.get("M Skills", int(r["default_m_skill"])),
            "Test Distance": saved.get("Test Distance", 5.0),
            "Pair Unit": r["pair_unit_id"],
            "Typical ALS Equipment": r["typical_als_equipment"],
        })

    scenario_df = pd.DataFrame(rows)

    if not scenario_df.empty:
        st.caption(
            "Use the AFR Equipment dropdown to assign AFR1 or AFR2. "
            "Use Other Equipment for additional equipment codes, separated by commas. "
            "M-suffix units normally have AFR1 or AFR2, but the app does not guess which one."
        )

        edited = st.data_editor(
            scenario_df,
            hide_index=True,
            use_container_width=True,
            disabled=[
                "Unit ID", "Unit Type", "Station", "Pair Unit",
                "Typical ALS Equipment"
            ],
            column_config={
                "AFR Equipment": st.column_config.SelectboxColumn(
                    "AFR Equipment",
                    options=["", "AFR1", "AFR2"],
                    help="Select the currently assigned ALS first-response equipment for this unit."
                ),
                "Other Equipment": st.column_config.TextColumn(
                    "Other Equipment",
                    help="Optional comma-separated equipment codes."
                ),
                "M Skills": st.column_config.NumberColumn(
                    "M Skills", min_value=0, step=1,
                    help="Number of rostered personnel with personnel skill M."
                ),
                "Test Distance": st.column_config.NumberColumn(
                    "Test Distance", min_value=0.0, step=0.1,
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
            st.session_state.scenario_overrides[str(row["Unit ID"])] = {
                "Beat": str(row["Beat"]),
                "Attributes": str(row["Attributes"]),
                "AFR Equipment": str(row["AFR Equipment"]),
                "Other Equipment": str(row["Other Equipment"]),
                "M Skills": int(row["M Skills"]),
                "Test Distance": float(row["Test Distance"]),
            }

        # Make missing ALS equipment conspicuous for the common M-suffix operational units.
        m_suffix_missing_afr = []
        for _, row in edited.iterrows():
            uid = str(row["Unit ID"])
            typical = str(row.get("Typical ALS Equipment", ""))
            afr = str(row.get("AFR Equipment", ""))
            if typical == "AFR1 or AFR2" and afr not in {"AFR1", "AFR2"}:
                m_suffix_missing_afr.append(uid)

        if m_suffix_missing_afr:
            st.warning(
                "AFR equipment is not assigned for these units that normally carry AFR1 or AFR2: "
                + ", ".join(m_suffix_missing_afr)
                + ". Select AFR1 or AFR2 in the AFR Equipment column before testing ALS/AFR logic."
            )

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

    with st.expander("Current ALPHA flow modeled in v0.4.1"):
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
        "pair_unit_id": "Pair Unit",
        "default_attributes": "Modeled Attributes",
        "default_m_skill": "Default M Skills",
        "typical_als_equipment": "Typical ALS Equipment",
        "attribute_source": "Attribute Source"
    })[
        [
            "Unit ID", "Unit Type", "Beat", "Station", "Pair Unit",
            "Modeled Attributes", "Default M Skills",
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
