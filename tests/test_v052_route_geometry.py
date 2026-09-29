from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routing import _parse_route_geometry_response


def test_route_geometry_parser():
    payload = {
        "code": "Ok",
        "routes": [{
            "distance": 3218.688,
            "duration": 420.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-77.3000, 38.8500],
                    [-77.2900, 38.8600],
                    [-77.2800, 38.8700],
                ],
            },
        }],
    }
    result = _parse_route_geometry_response(payload)
    assert result is not None
    assert round(result["distance_miles"], 2) == 2.00
    assert result["duration_seconds"] == 420.0
    assert result["path"][0] == [-77.3, 38.85]
    assert len(result["path"]) == 3


def test_route_geometry_parser_rejects_missing_geometry():
    payload = {
        "code": "Ok",
        "routes": [{
            "distance": 1000.0,
            "duration": 100.0,
            "geometry": {"type": "LineString", "coordinates": []},
        }],
    }
    assert _parse_route_geometry_response(payload) is None
