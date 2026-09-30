from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_does_not_import_station_override_helper_from_routing():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    import_block = app.split("from cad_routing import (", 1)[1].split(")", 1)[0]
    assert "apply_station_active_overrides" not in import_block
    assert "def _effective_stations()" in app
    assert "station_active_overrides" in app
