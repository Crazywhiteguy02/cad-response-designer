# CAD Response Designer — Prototype v0.5.1.2

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

The unit-definition report supplies Unit ID, Unit Type, Agency, Dispatch Group, Beat, and Station ID. It does **not** include every unit's attributes, equipment, or current roster. v0.5.1.2 therefore only pre-populates attributes where the user explicitly supplied a family or exact-unit rule. Other catalog records remain `Unknown / not modeled` rather than being guessed.

`AFR1` / `AFR2` equipment is intentionally not auto-assigned to every M-suffix resource because the user stated those units typically use either AFR1 or AFR2, but the exact equipment assignment varies. Enter the actual equipment in the Scenario editor for the test being run.

## Running on Streamlit Community Cloud

Replace the files in the existing GitHub repository with this package. Streamlit should redeploy automatically. The entrypoint remains:

`app.py`

## v0.5.1.2 ALPHA flow

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

## v0.5.1.2 equipment-entry fix

- Adds a dedicated AFR Equipment dropdown in the operational scenario.
- AFR Equipment choices are blank, AFR1, or AFR2.
- Keeps a separate Other Equipment field for additional equipment codes.
- Warns when an M-suffix unit that normally carries AFR1/AFR2 has no AFR equipment assigned.
- The recommendation engine now combines AFR Equipment and Other Equipment when evaluating requirements.

## v0.5.1 scenario editor update

- Combines AFR Equipment and Other Equipment into one Equipment field.
- Equipment is an editable multi-select dropdown.
- Multiple equipment codes can be assigned to the same unit.
- The dropdown includes known equipment codes and permits new codes for testing.
- Removes the visible Pair Unit column from both the scenario editor and unit catalog.
- Base/M-pair conflict warnings still work by deriving the pair from the Unit ID suffix.

## v0.5.1 scenario editor refinements

- Changes M Skills from a free-number field to a dropdown with values 0 through 4.
- Removes `40mm` and `AIUEQ` from the Equipment dropdown because they are not used by the fire department.
- Retains the multi-select Equipment field and all v0.4.2 ALPHA logic.

## v0.5.1 scenario editor controls

- Unit ID and Unit Type remain locked/read-only.
- Beat is now a single-select dropdown populated from the CADDBM unit catalog.
- Station is now a single-select dropdown populated from the CADDBM unit catalog.
- Attributes are now an editable multi-select dropdown and support multiple attributes.
- Attribute selections and station changes are retained for the active Streamlit session.

## v0.5.1 staffing and AFR defaults

- Engine-family units with an `M` suffix default to `AFR1` and 1 personnel skill `M`.
- Truck (`T`), Tower (`TL`), Tiller (`TT`), and Rescue (`R`) units with an `M` suffix default to `AFR2` and 1 personnel skill `M`.
- `HM440M` defaults to `AFR2` and 1 personnel skill `M`.
- `ALS401` through `ALS404` default to 1 personnel skill `M`.
- Modeled Fairfax/City `EMS` units default to 1 personnel skill `M`.
- `HM401M` retains 1 personnel skill `M`; its AFR1-vs-AFR2 default is not guessed because an exact assignment has not yet been supplied.
- All defaults remain editable in the scenario editor.

## v0.5.1 HM401M default correction

- `HM401M` now defaults to `AFR2`.
- `HM401M` defaults to 1 personnel skill `M`.
- This aligns the current HM401M resource with the supplied operational configuration.


## v0.5.1 OpenStreetMap routing prototype

This version preserves the validated v0.4.6 ALPHA logic and adds a separate
routing layer.

### Routing modes

- **OpenStreetMap / OSRM**: station and incident locations are geocoded with
  OpenStreetMap Nominatim. Candidate routes are calculated against the OSM road
  network using OSRM.
- **Manual Test Distance**: preserves the validated v0.4.6 behavior for
  diagnostic testing.

In OSM mode:

- candidate ordering uses **estimated travel time**;
- ALPHA's CAD `Max Distance 10` setting is interpreted as a **10-minute travel-time threshold**;
- units at the same station share the same station-origin route;
- unresolved or inactive station origins are excluded from that OSM simulation;
- the route table is displayed before the recommendation output.

### Regional station numbering

The station crosswalk follows the supplied CAD numbering convention:

- Arlington County: `1##`
- Alexandria City: `2##`
- Metropolitan Washington Airports Authority: `3##`
- Fairfax County / Fairfax City: `4##`
- Prince William County: `5##`
- Loudoun County: `6##`
- Montgomery County: `7##`
- Prince George's County: `8##`

### Important prototype limitation

The online routing service uses a general driving profile. It does not reproduce
Hexagon's street database, emergency-apparatus speeds, turn penalties, closures,
or agency-specific routing configuration. It should therefore be used as an
independent routing model for comparison and plan design, not as a replacement
for production CAD routing.

The public Nominatim service is rate-limited, so geocoding results are cached.
For a production deployment, use a self-hosted or contracted geocoding/routing
service rather than relying on public community endpoints.


## v0.5.1 CAD time-threshold and display-order correction

Two CAD semantics were corrected from v0.5.0:

1. ALPHA's configured `Max Distance 10` value is not a ten-mile cutoff. It is
   treated as a **10-minute travel-time threshold**. In OSM mode the simulator
   checks calculated route time; in manual mode it checks `Test Time (min)`.

2. Estimated arrival time is used only to rank eligible candidate units.
   The **displayed recommendation sequence is controlled by the response plan**,
   not projected arrival order. Explicit CADDBM `Display Order` values are
   honored, and remaining recommendations retain response-plan sequence.

The routing table is now labeled as diagnostic and is not presented as dispatch
order.
