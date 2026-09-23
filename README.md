# CAD Response Designer — Prototype v0.4.4.2

This version moves the prototype to the current **ALPHA** response plan and imports the complete unit catalog supplied from CADDBM.

## What changed

- Imports 5,757 FIRE/F1 unit records from the supplied 191-page `All unit definitions.pdf` report.
- Adds a searchable Unit Catalog tab.
- Uses the current ALPHA response-plan flow instead of the legacy AFR plan.
- Adds current requirements for `CHASE CAR`, `ALS CHASE CAR`, `EMS COUNTY`, `HM401`, and `HM401M`.
- Models `ALS401`–`ALS404` as Unit Type `ALS` with `COUNTY` and `CHASE CAR`.
- Models Fairfax/City EMS units as `COUNTY`, `BALLISTIC`, and `CHASE CAR`.
- Models the M-suffix rule for local engines, trucks, towers, tillers, rescues, and HM401M.
- Detects base/M-pair conflicts in a test scenario.
- Adds editable scenario values for Beat, Attributes, Equipment, M-skill count, and Test Distance.
- Enforces ALPHA's initial M `Max Distance 10` against the editable Test Distance value.

## Important modeling boundary

The unit-definition report supplies Unit ID, Unit Type, Agency, Dispatch Group, Beat, and Station ID. It does **not** include every unit's attributes, equipment, or current roster. v0.4.4.2 therefore only pre-populates attributes where the user explicitly supplied a family or exact-unit rule. Other catalog records remain `Unknown / not modeled` rather than being guessed.

`AFR1` / `AFR2` equipment is intentionally not auto-assigned to every M-suffix resource because the user stated those units typically use either AFR1 or AFR2, but the exact equipment assignment varies. Enter the actual equipment in the Scenario editor for the test being run.

## Running on Streamlit Community Cloud

Replace the files in the existing GitHub repository with this package. Streamlit should redeploy automatically. The entrypoint remains:

`app.py`

## v0.4.4.2 ALPHA flow

1. `M`, Max Distance 10.
2. If that fails: `M OR ALS CHASE CAR OR EMS`.
3. `M Recommended?`; if No: `M OR A`.
4. `CHASE CAR Recommended?`.
   - Yes: `AFR1 OR AFR2 OR E OR T OR TL OR TT OR R OR HM401 OR HM401M`.
   - No: `AFR1 OR AFR2 OR ALS CHASE CAR OR EMS COUNTY OR E OR T OR TL OR TT OR R OR HM401 OR HM401M`.
5. `ALS_SKILL Recommended?`; if No: `ALS CHASE CAR OR EMS OR AFR1 OR AFR2`.
6. `SUPPRESSION UNIT Recommended?`; if No: `AFR1 OR AFR2 OR E OR T OR TL OR TT OR R OR HM401 OR HM401M`.

Hatched/blank branches in the supplied ALPHA flowchart are represented as pass-through branches.

## Routing limitation

The prototype does not have I/CAD street-network travel calculations. `Test Distance` is an explicit simulation input used to rank candidates and to test the Max Distance 10 rule. This is not presented as actual CAD travel distance.

## v0.4.4.2 equipment-entry fix

- Adds a dedicated AFR Equipment dropdown in the operational scenario.
- AFR Equipment choices are blank, AFR1, or AFR2.
- Keeps a separate Other Equipment field for additional equipment codes.
- Warns when an M-suffix unit that normally carries AFR1/AFR2 has no AFR equipment assigned.
- The recommendation engine now combines AFR Equipment and Other Equipment when evaluating requirements.

## v0.4.4 scenario editor update

- Combines AFR Equipment and Other Equipment into one Equipment field.
- Equipment is an editable multi-select dropdown.
- Multiple equipment codes can be assigned to the same unit.
- The dropdown includes known equipment codes and permits new codes for testing.
- Removes the visible Pair Unit column from both the scenario editor and unit catalog.
- Base/M-pair conflict warnings still work by deriving the pair from the Unit ID suffix.

## v0.4.4 scenario editor refinements

- Changes M Skills from a free-number field to a dropdown with values 0 through 4.
- Removes `40mm` and `AIUEQ` from the Equipment dropdown because they are not used by the fire department.
- Retains the multi-select Equipment field and all v0.4.2 ALPHA logic.

## v0.4.4 scenario editor controls

- Unit ID and Unit Type remain locked/read-only.
- Beat is now a single-select dropdown populated from the CADDBM unit catalog.
- Station is now a single-select dropdown populated from the CADDBM unit catalog.
- Attributes are now an editable multi-select dropdown and support multiple attributes.
- Attribute selections and station changes are retained for the active Streamlit session.
