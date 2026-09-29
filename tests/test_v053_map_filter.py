from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routing import filter_route_rows_for_map


ROUTES = [
    {
        "station": "421",
        "unit_ids": ["M421", "A421"],
        "units": "M421, A421",
        "label": "Station 421 | M421, A421",
        "path": [[-77.4, 38.8], [-77.3, 38.9]],
    },
    {
        "station": "425",
        "unit_ids": ["TT425M"],
        "units": "TT425M",
        "label": "Station 425 | TT425M",
        "path": [[-77.5, 38.8], [-77.3, 38.9]],
    },
]


def test_default_map_shows_only_dispatched_units():
    visible = filter_route_rows_for_map(ROUTES, ["M421"])
    assert len(visible) == 1
    assert visible[0]["station"] == "421"
    assert visible[0]["units"] == "M421"
    assert visible[0]["label"] == "Station 421 | M421"


def test_additional_in_service_unit_can_be_overlaid():
    visible = filter_route_rows_for_map(
        ROUTES,
        ["M421"],
        additional_unit_ids=["TT425M"],
    )
    assert [r["station"] for r in visible] == ["421", "425"]


def test_non_dispatched_unit_at_same_station_is_hidden_from_label():
    visible = filter_route_rows_for_map(ROUTES, ["M421"])
    assert "A421" not in visible[0]["units"]


def test_show_all_restores_all_routes_and_units():
    visible = filter_route_rows_for_map(
        ROUTES,
        ["M421"],
        show_all=True,
    )
    assert len(visible) == 2
    assert visible[0]["units"] == "M421, A421"
    assert visible[1]["units"] == "TT425M"


def test_duplicate_station_route_is_not_created_by_filter():
    visible = filter_route_rows_for_map(ROUTES, ["M421", "A421"])
    assert len(visible) == 1
    assert visible[0]["units"] == "M421, A421"
