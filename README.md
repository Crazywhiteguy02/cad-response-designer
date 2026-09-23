# CAD Response Designer — Prototype v0.3

v0.3 keeps the v0.2.1 AFR/ALS OR-group logic and detailed resource table, and corrects the resource profiles based on the latest CAD configuration information.

## v0.3 changes

- `ALS FIRST RESP` is no longer treated as a standard attribute on all engines.
- For representative engines, trucks, towers, tillers, and rescues, `ALS FIRST RESP` follows the `M`-suffix unit.
- `E426` and `E435` therefore do **not** carry `ALS FIRST RESP`.
- `E421M`, `RE433M`, `R421M`, `T421M`, `TL440M`, and `TT425M` do carry `ALS FIRST RESP`.
- Current hazmat resources were added to the catalog:
  - `HM401` — Unit Type `HM`; RESCUE, HAZMAT, HEAVY, EXTRICATION
  - `HM401M` — Unit Type `HM`; ALS FIRST RESP, RESCUE, HAZMAT, HEAVY, EXTRICATION
  - Both use Station `440` and Beat `440` as shown in the supplied unit definitions.
- `HM401` and `HM401M` default to unavailable in the historical AFR_ALS test scenario so they do not silently alter the 2022 validation case. You can toggle them on manually.
- No personnel skill `M` or equipment has been assumed for HM401/HM401M because those details have not yet been supplied.
- Historical `HM440` / `HM440M` response-plan references remain historical and unresolved. They are not automatically rewritten to HM401/HM401M.

## Historical AFR_ALS flow currently modeled

- Initial group: AFR1 / AFR2 / AFR3 / AFR4 / HM440M / E / T / TL / TT / R / HM440 / A
- M
- ALS_SKILL Recommended?
- If NO: AFR1 / AFR2 / AFR3 / AFR4 / EMS
- SUPPRESSION UNIT Recommended?
- If NO: AFR1 / AFR2 / HM440M / E / T / TL / TT / R / HM440

AFR3, AFR4, HM440M, HM440, and generic A remain explicitly unresolved until their exact requirement definitions are supplied.

For Streamlit Community Cloud, replace the existing project files in GitHub with the v0.3 files. Streamlit should redeploy automatically.
