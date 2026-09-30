# CADence — v0.10.0

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

The unit-definition report supplies Unit ID, Unit Type, Agency, Dispatch Group, Beat, and Station ID. It does **not** include every unit's attributes, equipment, or current roster. v0.7.1.2 therefore only pre-populates attributes where the user explicitly supplied a family or exact-unit rule. Other catalog records remain `Unknown / not modeled` rather than being guessed.

`AFR1` / `AFR2` equipment is intentionally not auto-assigned to every M-suffix resource because the user stated those units typically use either AFR1 or AFR2, but the exact equipment assignment varies. Enter the actual equipment in the Scenario editor for the test being run.

## Running on Streamlit Community Cloud

Replace the files in the existing GitHub repository with this package. Streamlit should redeploy automatically. The entrypoint remains:

`app.py`

## v0.7.1.2 ALPHA flow

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

## v0.7.1.2 equipment-entry fix

- Adds a dedicated AFR Equipment dropdown in the operational scenario.
- AFR Equipment choices are blank, AFR1, or AFR2.
- Keeps a separate Other Equipment field for additional equipment codes.
- Warns when an M-suffix unit that normally carries AFR1/AFR2 has no AFR equipment assigned.
- The recommendation engine now combines AFR Equipment and Other Equipment when evaluating requirements.

## v0.7.1 scenario editor update

- Combines AFR Equipment and Other Equipment into one Equipment field.
- Equipment is an editable multi-select dropdown.
- Multiple equipment codes can be assigned to the same unit.
- The dropdown includes known equipment codes and permits new codes for testing.
- Removes the visible Pair Unit column from both the scenario editor and unit catalog.
- Base/M-pair conflict warnings still work by deriving the pair from the Unit ID suffix.

## v0.7.1 scenario editor refinements

- Changes M Skills from a free-number field to a dropdown with values 0 through 4.
- Removes `40mm` and `AIUEQ` from the Equipment dropdown because they are not used by the fire department.
- Retains the multi-select Equipment field and all v0.4.2 ALPHA logic.

## v0.7.1 scenario editor controls

- Unit ID and Unit Type remain locked/read-only.
- Beat is now a single-select dropdown populated from the CADDBM unit catalog.
- Station is now a single-select dropdown populated from the CADDBM unit catalog.
- Attributes are now an editable multi-select dropdown and support multiple attributes.
- Attribute selections and station changes are retained for the active Streamlit session.

## v0.7.1 staffing and AFR defaults

- Engine-family units with an `M` suffix default to `AFR1` and 1 personnel skill `M`.
- Truck (`T`), Tower (`TL`), Tiller (`TT`), and Rescue (`R`) units with an `M` suffix default to `AFR2` and 1 personnel skill `M`.
- `HM440M` defaults to `AFR2` and 1 personnel skill `M`.
- `ALS401` through `ALS404` default to 1 personnel skill `M`.
- Modeled Fairfax/City `EMS` units default to 1 personnel skill `M`.
- `HM401M` retains 1 personnel skill `M`; its AFR1-vs-AFR2 default is not guessed because an exact assignment has not yet been supplied.
- All defaults remain editable in the scenario editor.

## v0.7.1 HM401M default correction

- `HM401M` now defaults to `AFR2`.
- `HM401M` defaults to 1 personnel skill `M`.
- This aligns the current HM401M resource with the supplied operational configuration.


## v0.7.1 OpenStreetMap routing prototype

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


## v0.7.1 CAD time-threshold and display-order correction

Two CAD semantics were corrected from v0.7.1:

1. ALPHA's configured `Max Distance 10` value is not a ten-mile cutoff. It is
   treated as a **10-minute travel-time threshold**. In OSM mode the simulator
   checks calculated route time; in manual mode it checks `Test Time (min)`.

2. Estimated arrival time is used only to rank eligible candidate units.
   The **displayed recommendation sequence is controlled by the response plan**,
   not projected arrival order. Explicit CADDBM `Display Order` values are
   honored, and remaining recommendations retain response-plan sequence.

The routing table is now labeled as diagnostic and is not presented as dispatch
order.


## v0.7.1 route map

The OSM routing view now displays the actual OSRM road route from each unique
station origin to the incident instead of only plotting origin/destination points.

- Each station route receives a distinct color.
- Units assigned to the same station share the same route and color.
- Station markers are circular and use the route color.
- Each station label shows the CAD station ID and the unit(s) routed from that station.
- The incident uses a red star symbol and an `INCIDENT` label so it is visually
  distinct from station markers.
- Hovering a route or station displays station, unit, distance, and ETA details.
- The routing map remains diagnostic only; the recommended-resource table is
  still displayed in response-plan dispatch order rather than ETA order.

OSRM route geometry is requested only for unique station origins and is cached
for 15 minutes to reduce repeated public-routing requests.


## v0.7.1 scalable route-map filtering

The route map now defaults to **dispatched units only** so large regional
scenarios do not become unreadable as the unit catalog grows.

Three map scopes are available:

- **Dispatched units only** — default and recommended operational view.
- **Dispatched + selected in-service units** — overlays specific non-dispatched
  units for comparison/troubleshooting.
- **All in-service units** — deliberate full-system routing view.

Additional behavior:

- A station route is drawn only once even when multiple visible units share the
  same station.
- Station labels list only the units currently visible under the map filter.
- The all-in-service routing table remains available in a collapsed diagnostic
  expander and does not control dispatch order or map visibility.
- Recommendation display order remains controlled by the response plan, not ETA.


## v0.7.1 Streamlit import hotfix

The route-map filtering helper is now defined in `app.py` instead of being
required as a new import from `routing.py`. This prevents an import-time crash
if Streamlit Cloud temporarily serves a stale `routing.py` during a multi-file
GitHub update. The v0.7.1 map filtering behavior is otherwise unchanged.


## v0.7.1 routing diagnostics cleanup

- Removes the `Route Color` column from the routing diagnostics table.
- Route colors are still used internally on the map to distinguish route lines.
- Station and unit labels remain the primary identification method.


## v0.7.1 GUI / workflow redesign

v0.7.1 is the first interface-focused release. The validated ALPHA simulation,
unit modeling, station crosswalk, routing, 10-minute threshold, response-plan
dispatch order, and route-map filtering remain intact.

### Primary workflow

The Dispatch Simulator is organized around the operational workflow:

1. Select the **Operational Condition**.
2. Select the dispatcher-facing **Event Type**.
3. The application resolves the **Associated Response Plan** automatically.
4. Enter the incident and choose OSM/OSRM or Manual Test Time routing.
5. Select and edit the units in service.
6. Run the dispatch simulation.
7. Review the dispatch-order recommendation and dispatched-route map.
8. Open Technical Details only when routing diagnostics, trace output, or plan
   logic are needed.

### Event type and operational-condition model

The event-type mapping is now data-driven in `data/event_type_plan_map.csv`.

Current ALPHA mapping:

- Condition 1 — Normal Operations → `ALPHA`
- Condition 2 — High Call Volume → `ALPHA`
- Condition 3 — >50% Unit Utilization → `ALPHA`

The dispatcher-facing event type is `ALPHA`, description `EMS LEVEL 1`.
The data model does not assume that future event-type names and response-plan
names match, and it allows the same event type to map to different response
plans under different operational conditions.

### Interface organization

Top-level areas are now:

- **Dispatch Simulator**
- **Stations**
- **Units**
- **Configuration**

Configuration contains the Event Type → Response Plan mapping and Requirement
Library. Routing diagnostics, explanation trace, and ALPHA plan flow are
collapsed under Technical Details after a simulation.

### Routing terminology

The manual routing option is now labeled **Manual Test Time** throughout the
primary interface. ALPHA's CAD `Max Distance 10` continues to be modeled as a
10-minute travel-time threshold, not a mileage threshold.


## v0.7.1 UI refinement

This release focuses on making the application feel more like an operational
tool and less like a development prototype.

### Dispatch Simulator cleanup

Removed redundant setup text and cards:

- removed the `Dispatch-facing event type and description` caption;
- removed the prominent Associated Response Plan card from Dispatch Setup;
- removed the `Unit ID and Unit Type remain locked` resource note;
- removed the Routing metric from Resources.

The simulator is now organized into bordered application cards for Operational
Context, Incident, Resources, Dispatch Recommendation, and Dispatched Routes.
Navigation, buttons, cards, tabs, and section headings received a stronger
public-safety-oriented visual treatment.

### Incident map marker

The incident is now drawn as a red five-point star polygon. The word `INCIDENT`
is no longer drawn on the map. Station markers remain circular and route colors
remain available for route differentiation.

### Station availability

The Stations tab now provides an editable `Active` checkbox for every station.

- Active stations may be used as OSM routing origins.
- Turning a station off excludes it and units assigned there from OSM routing.
- Changes are session-scoped.
- `Restore station defaults` returns all station availability values to the
  configured dataset defaults.

The Stations tab no longer shows the Directory Rows metric, Notes column, or
Source column.


## v0.7.1 Streamlit import hotfix

The station availability override logic is now local to `app.py`. The app no
longer imports the newly introduced `apply_station_active_overrides` helper from
`routing.py`.

This avoids an import-time failure if Streamlit Cloud temporarily runs the new
`app.py` against an older cached or partially updated `routing.py` during a
multi-file GitHub deployment. No v0.6.1 UI or station-toggle behavior changes.


## v0.7.1 Application-shell redesign

v0.7.1 is a visual and responsive interface release. The validated ALPHA
response logic, routing behavior, station availability overrides, event-type
mapping, and dispatch-order logic are unchanged.

### Application look and feel

The Streamlit page now uses a conventional application shell:

- compact application bar with product identity and version status;
- pill-style primary navigation;
- softer 24-pixel-radius surfaces with lighter borders and shadows;
- pill-shaped primary actions and segmented controls;
- less explanatory chrome on the normal simulation path;
- responsive styling for tablet and phone browser widths.

### Dispatch workflow

Operational Condition, Routing Mode, Incident Location Input, and Map Display
use segmented controls instead of traditional radio-button forms. The Unit
Configuration editor is collapsed by default so the normal workflow stays
focused on selection and simulation.

### Dispatch results

The primary recommendation is now rendered as responsive dispatch cards. Each
card emphasizes dispatch order, unit ID, satisfied requirement, and routing
metadata when available. The traditional result table remains available under
a collapsed `Table View` for detailed review.

### Mobile browser behavior

The same Streamlit application is used on desktop, tablet, and phone browsers.
At narrow widths the application bar compacts, dispatch cards become
single-column, and navigation remains horizontally usable. This is responsive
web behavior rather than a separate native mobile application.


## v0.7.1 CADence branding

The product name is now **CADence**.

The application uses the CADence brand palette:

- Brand Navy: `#011340`
- Action Blue: `#0162E8`
- Technology Accent: `#00D9FC`
- Neutral Gray: `#C0C0C2`
- Charcoal: `#24262A`
- App Background: `#F7F9FC`
- Cards / Surfaces: `#FFFFFF`

Navy is the dominant brand surface, electric blue is reserved for primary
actions and selected controls, and cyan is used sparingly as a technology
accent rather than as a dominant interface color.

## v0.9.0 — CADence brand-system release

v0.9.0 applies the approved CADence brand board as the visual baseline for the application. The validated ALPHA simulation logic and routing behavior remain unchanged.

### Brand system
- CADence wordmark treatment and connected-node C mark
- Tagline: Intelligent Response Planning
- Deep Navy `#011340`
- Electric Blue `#0162E8`
- Cyan `#00D9FC`
- Light Gray `#C0C0C2`
- Charcoal `#24262A`
- Background `#F7F9FC`
- Surface `#FFFFFF`
- Montserrat-first typography stack with platform fallbacks

### Application shell
The desktop experience now uses a dark CADence navigation rail with Dashboard, Dispatch Simulator, Stations, Units & Resources, and Configuration destinations. The main workspace uses white rounded surfaces on the approved light background, with Electric Blue interaction states and restrained Cyan accents.

### Dashboard
A new Dashboard landing screen summarizes the modeled response plan, unit types, requirements, active stations, event types, operational conditions, and catalog size. ALPHA / EMS LEVEL 1 is surfaced as the current modeled plan.

The mobile browser experience continues to use Streamlit's responsive sidebar/drawer behavior while preserving the same CADence visual system.


## v0.9.0 Application Dashboard release

v0.9.0 restructures CADence around the approved Application Dashboard brand
baseline while preserving the validated simulation engine.

### Persistent application shell

- fixed Deep Navy CADence navigation rail;
- CADence connected-node mark and `Intelligent Response Planning` tagline;
- white top application bar;
- global search field;
- notification/avatar treatment;
- persistent workspace shell across all primary sections.

### Information architecture

The primary navigation now follows the CADence product model:

- Dashboard
- Response Plans
- Units & Resources
- Capabilities
- Equipment
- Scenarios
- Analysis
- Reports
- Settings

The existing Dispatch Simulator is now the operational workflow inside
**Scenarios**. Stations are consolidated under **Units & Resources** rather than
occupying a separate top-level destination.

### Dashboard

The dashboard now follows the brand-board composition more closely:

- page title and `Build. Validate. Optimize. Deploy.` subtitle;
- four compact summary cards for Response Plans, Unit Types, Capabilities, and
  Equipment Items;
- application-style Response Plans table;
- quick-access operational summary cards;
- global search filtering for modeled response plans.

Counts shown on the dashboard are derived from the current CADence data rather
than copying the example numbers from the brand board.

### Current boundaries

Analysis and Reports have application-ready landing screens but their full
workflows are not yet implemented. No production I/CAD connection is present.


## v0.9.1 — Routing resilience hotfix

This release hardens CADence against public geocoder throttling without changing
the validated ALPHA recommendation logic.

### Stored station coordinates

`station_crosswalk.csv` now supports permanent `latitude`, `longitude`, and
`coordinate_source` fields. CADence uses those values before attempting any
external station geocoding. The current Fairfax stations used by the validated
ALPHA test scenario are seeded in this release, including Station 429.

Station 429 remains the active Tysons Corner station at:

`1560 Spring Hill Road, McLean, VA 22102`

The proposed replacement station is intentionally excluded from active routing
until it becomes operational.

### Address lookup resilience

Incident-address lookup now follows this order:

1. local seeded address cache;
2. U.S. Census street-address geocoder;
3. throttled Nominatim fallback with retry/backoff.

The geocode result cache uses Streamlit disk persistence where available. A
Nominatim HTTP 429 is no longer exposed directly to the user. If all lookup
methods fail, CADence displays a concise message and suggests using the full
street address or switching to coordinate input.

### Current scope

Not every regional station has a permanently seeded coordinate yet. Stations
without stored coordinates still use the resilient geocoding fallback and are
cached. Additional station coordinates can be added to the crosswalk
incrementally without changing the routing engine.


## v0.10.0 — Data-driven CAD configuration release

v0.10.0 moves CADence from a primarily hard-coded ALPHA prototype to an imported CAD configuration model.

### Imported CAD data

- 1,014 unique DEFINE REQUIREMENT definitions from 1,015 criteria rows.
- 348 requirement-to-resource links from `resp_req_res`.
- 5,394 response plans represented by 36,784 plan-detail rows.
- 111 response plans flagged as Ad Hoc (`resp_type = 1`).
- 110 FIRE Event Types with all three Operational Condition response-plan mappings.
- 93 additional-alarm rows transcribed from the supplied CADDBM alarm-level grids.

### Response-plan engine

The new imported-plan engine supports:

- Requirement Group items (`item_type = 1`).
- Condition items (`item_type = 2`).
- Connector / no-action items (`item_type = 0`).
- Referenced / nested response plans (`item_type = 3`).
- Yes/No traversal using `success_item_id` and `failure_item_id`.
- Requirement alternatives ordered by `req_number`.
- Display Order preservation within each applied plan batch.
- `req_max_route` as the CAD time threshold used by the current configuration.
- Recommend Mode values: `1 = Street Network`, `2 = Beats`, `3 = Use Default`.
  The current CAD default is Street Network, so modes 1 and 3 are operationally equivalent today while remaining semantically distinct.

ALPHA is now executable from the imported raw response-plan and requirement data. The earlier hard-coded ALPHA simulator remains in the codebase only as a regression baseline.

### Post-dispatch incident workflow

The Scenarios workspace now maintains an active incident state after the initial dispatch. The user can:

- apply the next configured additional alarm level;
- apply any imported Ad Hoc response plan;
- preserve resources already on the incident;
- evaluate subsequent plans against the current incident capability state;
- review an incident history showing which plans were applied;
- reset the active incident and start a new scenario.

Additional-alarm and Ad Hoc plans are applied as later recommendation batches, so their Display Order values do not reorder resources ahead of the original dispatch.

### Dynamic equipment and personnel capability

Equipment and personnel skill M remain scenario-time operational state rather than permanent unit properties. This matches the clarified CAD workflow:

- equipment is selected by end users when signing units on;
- personnel skill M depends on current staffing;
- CADence does not store individual employee identities for response-plan simulation.

### Data-quality boundaries

Unknown unit-attribute bits, unsupported personnel skills other than M, and unmodeled Backup Beat behavior fail explicitly rather than being silently ignored.

The alarm-level screenshots reference `2ND_ALARM_PLUS` and `3RD_ALARM_PLUS` for FBULK. Those response-plan names are not present in the supplied `Response_Plans.xlsx` export. CADence preserves the alarm mapping and disables execution of a missing referenced plan instead of inventing its content.

The additional-alarm table in this release is screenshot-derived. Replace it with the raw CAD alarm-level table when that export becomes available.

### Routing scope

v0.10.0 retains the v0.9.1 routing-resilience changes. Permanent coordinates are present for the validated Fairfax routing set, including active Station 429 at 1560 Spring Hill Road. The full regional permanent-coordinate validation pass remains a separate data-quality task; stations without stored coordinates continue to use the resilient geocoding fallback and cache.
