from __future__ import annotations

import streamlit as st

from db import connect, init_db
from engine import load_units, simulate_plan


st.set_page_config(page_title="CAD Response Designer v0.1", layout="wide")
init_db()

st.title("CAD Response Designer — Prototype v0.1")
st.caption(
    "Validation prototype for resource qualification, exclusive response slots, "
    "and roster-derived ALS personnel skills."
)

with st.sidebar:
    st.header("Controls")
    if st.button("Reset sample database"):
        init_db(reset=True)
        st.success("Database reset.")
        st.rerun()

conn = connect()

st.subheader("Representative resource state")
units = load_units(conn)

rows = []
for u in sorted(units, key=lambda x: (x.priority, x.unit_id)):
    rows.append(
        {
            "Unit ID": u.unit_id,
            "Type": u.unit_type,
            "Attributes": ", ".join(sorted(u.attributes)),
            "Equipment": ", ".join(f"{k} x{v}" for k, v in sorted(u.equipment.items())),
            "M-skilled personnel": u.skills.get("M", 0),
            "Available": u.available,
            "Priority": u.priority,
        }
    )

st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("Availability")
st.write(
    "Priority is currently a deterministic stand-in for CAD proximity/routing. "
    "Toggle units unavailable to test fallback behavior."
)

cols = st.columns(3)
for idx, u in enumerate(sorted(units, key=lambda x: x.unit_id)):
    with cols[idx % 3]:
        checked = st.checkbox(u.unit_id, value=u.available, key=f"avail_{u.unit_id}")
        if checked != u.available:
            conn.execute(
                "UPDATE units SET available = ? WHERE unit_id = ?",
                (int(checked), u.unit_id),
            )
            conn.commit()

st.subheader("Simulation")
plan = st.selectbox("Plan", ["AFR_ALS_PROTOTYPE"])

if st.button("Simulate", type="primary"):
    state = simulate_plan(conn, plan)

    st.markdown("#### Recommended resources")
    st.dataframe(
        [{"Requirement": a.requirement, "Unit": a.unit_id} for a in state.assignments],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Explanation trace")
    st.code("\n".join(state.trace), language="text")

st.divider()
st.caption(
    "This version validates the core rule engine. Exact response-plan graphs, routing, "
    "nested plans, and import workflows are intentionally deferred."
)

conn.close()
