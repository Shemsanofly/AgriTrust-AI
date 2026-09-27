"""Several crops per farm, and crop photos that only the farm's owner can see."""

from datetime import date, timedelta

import pytest

from app.config import get_settings

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def my_farm(client, headers):
    return next(f for f in client.get("/farms", headers=headers).json() if f["name"] == "Shamba")


def crop_body(**extra):
    return {"crop_type": "beans", "planting_date": date.today().isoformat(), "expected_harvest_date": (date.today() + timedelta(days=90)).isoformat(), "growth_stage": "initial", **extra}


def test_farm_can_hold_several_crops(client, login):
    farmer = login("farmer")
    farm = my_farm(client, farmer)
    before = len(farm["crops"])
    assert client.post(f"/farms/{farm['id']}/crops", json=crop_body(acreage=1), headers=farmer).status_code == 201
    assert client.post(f"/farms/{farm['id']}/crops", json=crop_body(crop_type="sunflower", acreage=1.5), headers=farmer).status_code == 201
    crops = my_farm(client, farmer)["crops"]
    assert len(crops) == before + 2 and {"beans", "sunflower"} <= {c["crop_type"] for c in crops}
    # Intercropping is fine (the maize already covers all 5 acres), but one crop can't be bigger than the farm.
    over = client.post(f"/farms/{farm['id']}/crops", json=crop_body(acreage=6), headers=farmer)
    assert over.status_code == 422 and over.json()["detail"] == "crop_area_exceeds_farm"
    assert client.post(f"/farms/{farm['id']}/crops", json=crop_body(crop_type="cassava!"), headers=farmer).status_code == 422
    backwards = crop_body(expected_harvest_date=(date.today() - timedelta(days=1)).isoformat())
    assert client.post(f"/farms/{farm['id']}/crops", json=backwards, headers=farmer).json()["detail"] == "harvest_before_planting"


def test_upload_view_and_delete_crop_photo(client, login, uploads):
    farmer = login("farmer")
    crop = my_farm(client, farmer)["crops"][0]
    res = client.post(f"/crops/{crop['id']}/photos", files={"file": ("leaf.jpg", JPEG, "image/jpeg")}, data={"caption": "Leaves at 6 weeks"}, headers=farmer)
    assert res.status_code == 201, res.text
    photo = res.json()
    assert photo["caption"] == "Leaves at 6 weeks"
    stored = list((uploads / "crops").iterdir())
    assert len(stored) == 1 and "leaf" not in stored[0].name  # random name, not the phone's
    img = client.get(photo["url"], headers=farmer)
    assert img.status_code == 200 and img.content == JPEG and img.headers["content-type"] == "image/jpeg"
    assert my_farm(client, farmer)["crops"][0]["photos"][0]["id"] == photo["id"]
    assert client.post(f"/crops/{crop['id']}/photos", files={"file": ("x.png", PNG, "image/png")}, headers=farmer).status_code == 201
    assert client.delete(photo["url"], headers=farmer).status_code == 204
    assert client.get(photo["url"], headers=farmer).status_code == 404
    assert len(list((uploads / "crops").iterdir())) == 1


def test_only_real_small_images_are_accepted(client, login, monkeypatch):
    from app import files
    from app.routers import photos

    farmer = login("farmer")
    crop = my_farm(client, farmer)["crops"][0]
    fake = client.post(f"/crops/{crop['id']}/photos", files={"file": ("virus.jpg", b"MZ\x90\x00 not an image", "image/jpeg")}, headers=farmer)
    assert fake.status_code == 415 and fake.json()["detail"] == "not_an_image"
    monkeypatch.setattr(files, "MAX_BYTES", 100)
    big = client.post(f"/crops/{crop['id']}/photos", files={"file": ("big.jpg", JPEG, "image/jpeg")}, headers=farmer)
    assert big.status_code == 413
    monkeypatch.setattr(files, "MAX_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(photos, "MAX_PER_CROP", 1)
    assert client.post(f"/crops/{crop['id']}/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}, headers=farmer).status_code == 201
    assert client.post(f"/crops/{crop['id']}/photos", files={"file": ("b.jpg", JPEG, "image/jpeg")}, headers=farmer).status_code == 409


def test_photos_are_private_to_the_farm_owner(client, login):
    farmer, buyer = login("farmer"), login("buyer")
    other = {"Authorization": "Bearer " + client.post("/auth/login", json={"phone": "+255700000008", "pin": "1234"}).json()["access_token"]}
    crop = my_farm(client, farmer)["crops"][0]
    photo = client.post(f"/crops/{crop['id']}/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}, headers=farmer).json()
    for who in (buyer, other):
        assert client.get(photo["url"], headers=who).status_code == 403
        assert client.post(f"/crops/{crop['id']}/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}, headers=who).status_code == 403
        assert client.delete(photo["url"], headers=who).status_code == 403
    assert client.get(photo["url"]).status_code == 401
