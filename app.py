from __future__ import annotations

import streamlit as st

from db import connect, init_db
from engine import load_units, simulate_plan

st.set_page_config(page_title="CAD Response Designer v0.3", layout="wide")
init_db()
conn = connect()

st.title("CAD Response Designer — Prototype v0.3")
st.caption(
    "AFR/ALS validation with corrected M-suffix ALS FIRST RESP attributes and current HM401/HM401M resource profiles."
)

with st.sidebar:
    st.header("Controls")
    if st.button("Reset sample database"):
        conn.close()
        init_db(reset=True)
        st.rerun()

# Restore the detailed resource table from v0.1.
st.subheader("Representative resource state")
units = load_units(conn)

resource_rows = []
for unit in sorted(units, key=lambda x: (x.priority, x.unit_id)):
    resource_rows.append(
        {
            "Unit ID": unit.unit_id,
            "Unit Type": unit.unit_type,
            "Attributes": ", ".join(sorted(unit.attributes)),
            "Equipment": ", ".join(
                f"{code} x{qty}" for code, qty in sorted(unit.equipment.items())
            ),
            "M-skilled personnel": unit.skills.get("M", 0),
            "Station": unit.station or "",
            "Beat": unit.beat or "",
            "Available": unit.available,
        }
    )

st.dataframe(resource_rows, use_container_width=True, hide_index=True)

st.caption(
    "Resource model note: for engines, trucks, towers, tillers, and rescues, "
    "ALS FIRST RESP is assigned to the M-suffix unit. HM401/HM401M are included in the "
    "resource catalog, but are not automatically substituted for historical HM440/HM440M plan references."
)

st.subheader("Unit availability")
cols = st.columns(3)
for idx, unit in enumerate(sorted(units, key=lambda x: x.unit_id)):
    with cols[idx % 3]:
        checked = st.checkbox(
            unit.unit_id,
            value=unit.available,
            key=f"avail_{unit.unit_id}",
        )
        if checked != unit.available:
            conn.execute(
                "UPDATE units SET available=? WHERE unit_id=?",
                (int(checked), unit.unit_id),
            )
            conn.commit()

st.subheader("Simulation")
st.write(
    "The historical AFR_ALS flow is represented with OR requirement groups. "
    "Actual routing/proximity is not implemented yet; sample Priority is a deterministic stand-in."
)

if st.button("Simulate", type="primary"):
    state = simulate_plan(conn, "AFR_ALS_2022")

    st.markdown("#### Recommended resources")
    st.dataframe(
        [
            {
                "Step": a.source_step,
                "Requirement": a.requirement,
                "Unit": a.unit_id,
            }
            for a in state.assignments
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Explanation trace")
    st.code("\n".join(state.trace), language="text")

st.subheader("Definitions still needed")
st.info(
    "AFR3, AFR4, HM440M, HM440, and generic A are present in the AFR_ALS response plan, "
    "but their exact requirement definitions have not yet been supplied. The simulator retains "
    "them in the plan and reports them as unresolved instead of guessing their criteria."
)

conn.close()
