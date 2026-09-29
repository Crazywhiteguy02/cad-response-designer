from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_station_toggle_logic_is_local_to_app():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def _effective_stations()" in app
    assert 'effective.loc[mask, "active"] = bool(enabled)' in app


def test_dispatch_setup_redundant_copy_removed():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Dispatch-facing event type and description." not in app
    assert "Same plan under all 3 conditions" not in app
    assert "Unit ID and Unit Type remain locked." not in app
    assert 'metric("Routing"' not in app


def test_station_directory_is_simplified_and_editable():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'metric("Directory rows"' not in app
    assert '"Notes", "Source"' not in app
    assert "CheckboxColumn" in app
    assert "station_active_overrides" in app


def test_incident_uses_star_polygon_without_incident_word_label():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'def _incident_star_polygon' in app
    assert '"PolygonLayer"' in app
    assert '"label": "INCIDENT"' not in app
    assert 'incident_label_layer' not in app


def test_v061_has_card_based_application_styling():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "with st.container(border=True):" in app
    assert "--cad-red" in app
    assert "context-strip" in app
