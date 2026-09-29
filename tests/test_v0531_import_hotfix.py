from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_does_not_import_map_filter_helper_from_routing():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    import_block = app.split("from routing import (", 1)[1].split(")", 1)[0]
    assert "filter_route_rows_for_map" not in import_block
    assert "def _filter_route_rows_for_map(" in app
