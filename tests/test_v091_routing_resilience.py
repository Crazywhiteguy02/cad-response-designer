from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import routing


def test_station_429_is_current_active_site_with_stored_coordinates():
    stations = routing.load_station_crosswalk().set_index("cad_station_id")
    row = stations.loc["429"]
    assert bool(row["active"]) is True
    assert row["address"] == "1560 Spring Hill Road, McLean, VA 22102"
    assert row["latitude"] != ""
    assert row["longitude"] != ""
    assert "Proposed replacement station is excluded" in row["notes"]


def test_proposed_loudoun_station_remains_inactive():
    stations = routing.load_station_crosswalk().set_index("cad_station_id")
    assert bool(stations.loc["628", "active"]) is False


def test_stored_station_point_avoids_geocoding():
    stations = routing.load_station_crosswalk().set_index("cad_station_id")
    record = stations.loc["429"].to_dict()
    point = routing.station_point_from_record(record)
    assert point is not None
    assert round(point.lat, 6) == 38.929214
    assert round(point.lon, 6) == -77.239308


def test_seeded_government_center_address_requires_no_http(monkeypatch):
    def unexpected_http(*args, **kwargs):
        raise AssertionError("seeded address should not make an HTTP request")

    monkeypatch.setattr(routing.requests, "get", unexpected_http)
    point = routing.geocode_address("12099 government center pkwy")
    assert round(point.lat, 6) == 38.857506
    assert round(point.lon, 6) == -77.362860


def test_nominatim_429_returns_clean_routing_error(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.headers = {}

        def json(self):
            return self._payload

    calls = {"count": 0}

    def fake_get(url, *args, **kwargs):
        calls["count"] += 1
        if "census.gov" in url:
            return FakeResponse(200, {"result": {"addressMatches": []}})
        return FakeResponse(429, [])

    monkeypatch.setattr(routing.requests, "get", fake_get)
    monkeypatch.setattr(routing, "_throttle_nominatim", lambda: None)
    monkeypatch.setattr(routing.time, "sleep", lambda *_: None)

    with pytest.raises(routing.RoutingError) as exc:
        routing.geocode_address("99999 unseeded test road nowhere va")

    message = str(exc.value)
    assert "Address lookup is temporarily unavailable" in message
    assert "429 Client Error" not in message
    assert "nominatim.openstreetmap.org" not in message
    assert calls["count"] == 4  # Census once + Nominatim three attempts


def test_app_prefers_stored_station_coordinates():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "station_point_from_record(rec)" in app
    assert 'persist="disk"' in app
    assert "try the full street address" in (ROOT / "routing.py").read_text(encoding="utf-8").lower()
