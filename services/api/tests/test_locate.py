"""GPS -> place name for the farm form: OpenStreetMap when online, nearest region offline."""

import httpx
import pytest

from app.config import get_settings
from app.integrations import geocode


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.fixture()
def live(monkeypatch):
    monkeypatch.setattr(get_settings(), "geocode_mode", "live")
    geocode._lookup.cache_clear()
    yield
    geocode._lookup.cache_clear()


def test_offline_uses_nearest_region(client, login):
    farmer = login("farmer")
    data = client.get("/farms/locate?lat=-6.2512&lon=35.8431", headers=farmer).json()
    assert data["region"] == "Dodoma" and data["source"] == "offline"
    far = client.get("/farms/locate?lat=51.5&lon=-0.12", headers=farmer).json()
    assert far["region"] is None


def test_reads_region_from_iso_code_not_the_zone(client, login, live, monkeypatch):
    address = {
        "suburb": "Ubungo",
        "city_district": "Ubungo Municipal",
        "city": "Dar es Salaam",
        "ISO3166-2-lvl4": "TZ-02",
        "region": "Coastal Zone",
        "country": "Tanzania",
    }
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen.update(params=params, headers=headers)
        return FakeResponse({"address": address})

    monkeypatch.setattr(geocode.httpx, "get", fake_get)
    data = client.get("/farms/locate?lat=-6.7924&lon=39.2083", headers=login("farmer")).json()
    assert data["region"] == "Dar es Salaam"  # not "Coastal Zone"
    assert data["district"] == "Ubungo Municipal" and data["place"] == "Ubungo"
    assert data["label"] == "Ubungo, Ubungo Municipal, Dar es Salaam" and data["source"] == "osm"
    assert "ShambaniKifedha" in seen["headers"]["User-Agent"]


def test_network_failure_falls_back_offline(client, login, live, monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("no internet")

    monkeypatch.setattr(geocode.httpx, "get", boom)
    data = client.get("/farms/locate?lat=-8.9&lon=33.46", headers=login("farmer")).json()
    assert data["region"] == "Mbeya" and data["source"] == "offline"


def test_only_farmers_and_valid_coordinates(client, login):
    assert client.get("/farms/locate?lat=-6.2&lon=35.8", headers=login("buyer")).status_code == 403
    assert client.get("/farms/locate?lat=-120&lon=35.8", headers=login("farmer")).status_code == 422
