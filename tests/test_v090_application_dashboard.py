from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v090_uses_dashboard_baseline_navigation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    for label in [
        "Dashboard",
        "Response Plans",
        "Units & Resources",
        "Capabilities",
        "Equipment",
        "Scenarios",
        "Analysis",
        "Reports",
        "Settings",
    ]:
        assert f'"{label}"' in app
    assert 'key="cadence_page_v090"' in app


def test_v090_has_persistent_topbar_and_search():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'key="global_topbar"' in app
    assert "Search plans, units, or scenarios..." in app
    assert 'class="top-avatar"' in app


def test_v090_dashboard_matches_brand_board_structure():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'Build. Validate. Optimize. Deploy.' in app
    assert 'class="dashboard-kpis"' in app
    assert 'class="kpi-card"' in app
    assert 'class="panel-shell"' in app
    assert 'class="app-table"' in app
    for label in ["Response Plans", "Unit Types", "Capabilities", "Equipment Items"]:
        assert label in app


def test_v090_reorganizes_existing_functionality_into_app_sections():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if page == "Scenarios":' in app
    assert 'if page == "Units & Resources":' in app
    assert 'if page == "Response Plans":' in app
    assert 'if page == "Capabilities":' in app
    assert 'if page == "Equipment":' in app
    assert 'if page == "Settings":' in app


def test_v090_preserves_simulator_and_station_controls():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Run Dispatch Simulation"' in app
    assert "station_active_overrides" in app
    assert "def _incident_star_polygon" in app
    assert "assignments_in_dispatch_order" in app
