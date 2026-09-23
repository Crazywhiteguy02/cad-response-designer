# CAD Response Designer — Prototype v0.1

This local prototype models a subset of Hexagon I/CAD-style fire/EMS response-plan behavior.

## What v0.1 validates

- A physical unit may occupy only one exclusive response slot.
- A multi-qualified unit may be eligible for several requirement definitions, but once assigned to one slot it is consumed for other exclusive slots.
- Personnel skill `M` is distinct from Unit Type `M`.
- Personnel skills are derived from roster assignments by Employee ID.
- `ALS_SKILL` may be satisfied by M-skilled personnel already present on recommended units.
- RE433 may qualify for either `E` or `R`, but not both simultaneously.
- BC443 is Unit Type `BC` with `CITY`; county BCs use `COUNTY`.
- The simulator produces an explanation trace.

## Scope

The included plan is `AFR_ALS_PROTOTYPE`. It is a validation plan, not a claim that it reproduces the entire current Fairfax production AFR plan.

Distance/travel-time recommendation ordering is not modeled yet. A numeric priority field is used as a deterministic stand-in so the recommendation logic can be tested first.

## Run

1. Install Python 3.11+.
2. Open a terminal in this folder.
3. Install Streamlit:

   `pip install -r requirements.txt`

4. Run tests:

   `python -m unittest discover -s tests -v`

5. Start the interface:

   `streamlit run app.py`

The SQLite database is created automatically if it does not exist.

## Files

- `app.py` — Streamlit UI
- `db.py` — SQLite schema and representative test data
- `engine.py` — deterministic qualification/simulation logic
- `tests/test_engine.py` — acceptance tests
- `cad.db` — seeded local database

## Next steps after validation

- Import exact CADDBM response-plan graphs
- Requirement-group alternatives and ordering
- Assigned/Recommended Requirement conditions
- Nested plans
- Beat/station constraints
- Travel-time/street-network ordering
- Import of actual unit, requirement, personnel-profile, and roster data
