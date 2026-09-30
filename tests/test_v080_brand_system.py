from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v080_uses_cadence_dashboard_shell():
    app=(ROOT / "app.py").read_text(encoding="utf-8")
    assert 'page_title="CADence v0.10.0"' in app
    assert '"Dashboard",' in app
    assert '"Response Plans",' in app
    assert '"Scenarios",' in app
    assert '"Settings",' in app
    assert 'class="sidebar-wordmark"' in app
    assert 'Intelligent Response Planning' in app

def test_v080_brand_board_visual_system():
    app=(ROOT / "app.py").read_text(encoding="utf-8")
    for value in ["#011340", "#0162E8", "#00D9FC", "#C0C0C2", "#24262A", "#F7F9FC", "#FFFFFF"]:
        assert value in app
    assert "font-family: Montserrat" in app
    assert '<svg viewBox="0 0 64 64"' in app

def test_v080_has_dashboard_summary():
    app=(ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if page == "Dashboard":' in app
    assert 'class="dashboard-kpis"' in app
    assert 'Response Plans' in app
    assert 'ALPHA' in app
