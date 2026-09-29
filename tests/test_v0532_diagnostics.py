from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_route_color_is_hidden_from_diagnostics_table():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Route Color"' in app
    table_block = app.split('["Routing diagnostics", "Explanation trace", "Response-plan flow"]', 1)[1]
    assert '"Route Color",' in table_block
