from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v070_uses_app_shell_and_mobile_css():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'class="appbar"' in app
    assert 'class="brand-mark">CRD<' in app
    assert "@media (max-width: 768px)" in app
    assert "border-radius: 24px" in app


def test_v070_uses_segmented_operational_controls():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.segmented_control(' in app
    assert '"Operational Condition"' in app
    assert '"Road Network", "Manual Time"' in app
    assert '"Address", "Coordinates"' in app


def test_v070_primary_dispatch_result_is_card_based():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def _render_dispatch_cards" in app
    assert 'class="dispatch-card"' in app
    assert 'with st.expander("Table View"' in app


def test_unit_editor_is_secondary_by_default():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'with st.expander("Unit Configuration", expanded=False)' in app


def test_incident_star_behavior_is_preserved():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def _incident_star_polygon" in app
    assert '"PolygonLayer"' in app
    assert '"label": "INCIDENT"' not in app
