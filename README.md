# CAD Response Designer — Prototype v0.2

v0.2 adds OR requirement-group support and corrects the AFR/ALS fallback logic.

The historical `AFR_ALS` flow now includes:

- Initial group: AFR1 / AFR2 / AFR3 / AFR4 / HM440M / E / T / TL / TT / R / HM440 / A
- M
- ALS_SKILL Recommended?
- If NO: AFR1 / AFR2 / AFR3 / AFR4 / EMS
- SUPPRESSION UNIT Recommended?
- If NO: AFR1 / AFR2 / HM440M / E / T / TL / TT / R / HM440

AFR3, AFR4, HM440M, HM440, and generic A remain explicitly unresolved until their exact requirement definitions are supplied.

For Streamlit Community Cloud, replace the prior project files in GitHub with the v0.2 files. Streamlit should redeploy automatically.
