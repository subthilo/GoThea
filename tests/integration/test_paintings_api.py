"""Theas gemalte Hintergründe und Kacheln: speichern, zuweisen, Rückfall-Kette, wegräumen, löschen nur Eltern."""
import json

import pytest

from backend.app import config
from backend.app.services.paintings import fallback_chain
from backend.app.services.parent_auth import issue_token

STROKES = json.dumps([{"tool": "pen", "color": "#f00", "width": 6, "points": [{"x": 1, "y": 2, "pressure": 0.5}]}])
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 fake"
PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture(autouse=True)
def own_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def _paint(client, kind="background", fmt="square", slot_key=None, image=WEBP):
    data = {"kind": kind, "format": fmt, "strokes_json": STROKES}
    if slot_key:
        data["slot_key"] = slot_key
    files = {"image": ("bild.webp", image, "image/webp")} if image else None
    res = client.post("/api/v1/paintings", data=data, files=files)
    assert res.status_code == 201, res.text
    return res.json()


def _resolve(client, *keys):
    res = client.get("/api/v1/paintings", params={"keys": ",".join(keys)})
    assert res.status_code == 200, res.text
    return res.json()["slots"]


def test_fallback_chain_drops_the_subject():
    assert fallback_chain("dashboard") == ["dashboard"]
    assert fallback_chain("subject-detail/sub_math") == ["subject-detail/sub_math", "subject-detail"]
    assert fallback_chain("dashboard/tile/sub_math") == ["dashboard/tile/sub_math", "dashboard/tile"]
    assert fallback_chain("subject-detail/sub_math/tile/tafel") == [
        "subject-detail/sub_math/tile/tafel", "subject-detail/tile/tafel"]


def test_thea_paints_without_pin_and_the_image_is_served(strict_client, tmp_path):
    p = _paint(strict_client, slot_key="dashboard")
    assert p["slots"] == ["dashboard"] and p["image_url"].startswith(f"/api/v1/paintings/{p['id']}/image?v=")
    assert (tmp_path / "paintings" / f"{p['id']}.webp").read_bytes() == WEBP

    img = strict_client.get(p["image_url"])
    assert img.status_code == 200 and img.content == WEBP
    assert img.headers["content-type"] == "image/webp"

    slot = _resolve(strict_client, "dashboard")["dashboard"]
    assert slot["id"] == p["id"] and slot["slot_key"] == "dashboard"
    assert strict_client.get(f"/api/v1/paintings/{p['id']}").json()["strokes_json"] == STROKES


def test_one_picture_for_all_subjects_unless_a_subject_has_its_own(strict_client):
    general = _paint(strict_client, slot_key="subject-detail")
    slots = _resolve(strict_client, "subject-detail/sub_math", "subject-detail/sub_bio", "dashboard")
    assert slots["subject-detail/sub_math"]["id"] == general["id"]
    assert slots["subject-detail/sub_math"]["slot_key"] == "subject-detail"
    assert slots["dashboard"] is None

    math = _paint(strict_client, slot_key="subject-detail/sub_math")
    slots = _resolve(strict_client, "subject-detail/sub_math", "subject-detail/sub_bio")
    assert slots["subject-detail/sub_math"]["id"] == math["id"]
    assert slots["subject-detail/sub_bio"]["id"] == general["id"]


def test_autosave_overwrites_and_changes_the_image_url(strict_client, tmp_path):
    p = _paint(strict_client, slot_key="dashboard")
    new_strokes = json.dumps([])
    res = strict_client.put(f"/api/v1/paintings/{p['id']}", data={"strokes_json": new_strokes},
                            files={"image": ("bild.png", PNG, "image/png")})
    assert res.status_code == 200
    assert strict_client.get(f"/api/v1/paintings/{p['id']}").json()["strokes_json"] == new_strokes
    # Format gewechselt: die alte Datei ist weg, die neue da
    assert not (tmp_path / "paintings" / f"{p['id']}.webp").exists()
    assert strict_client.get(res.json()["image_url"]).content == PNG


def test_reassigning_a_slot_keeps_the_old_picture(strict_client):
    old = _paint(strict_client, slot_key="dashboard")
    new = _paint(strict_client, slot_key="dashboard")
    assert _resolve(strict_client, "dashboard")["dashboard"]["id"] == new["id"]
    history = strict_client.get("/api/v1/paintings/slots/dashboard/history").json()
    assert [h["id"] for h in history] == [new["id"], old["id"]]
    assert history[1]["slots"] == []

    res = strict_client.put("/api/v1/paintings/slots/dashboard", json={"painting_id": old["id"]})
    assert res.status_code == 200
    assert _resolve(strict_client, "dashboard")["dashboard"]["id"] == old["id"]


def test_archived_picture_disappears_falls_back_and_comes_back(strict_client):
    general = _paint(strict_client, slot_key="subject-detail")
    math = _paint(strict_client, slot_key="subject-detail/sub_math")

    assert strict_client.post(f"/api/v1/paintings/{math['id']}/archive").json()["archived"] is True
    assert _resolve(strict_client, "subject-detail/sub_math")["subject-detail/sub_math"]["id"] == general["id"]
    history = strict_client.get("/api/v1/paintings/slots/subject-detail/sub_math/history").json()
    assert {h["id"]: h["archived"] for h in history} == {math["id"]: True, general["id"]: False}

    strict_client.put("/api/v1/paintings/slots/subject-detail/sub_math", json={"painting_id": math["id"]})
    assert _resolve(strict_client, "subject-detail/sub_math")["subject-detail/sub_math"]["id"] == math["id"]
    assert strict_client.get(f"/api/v1/paintings/{math['id']}").json()["archived"] is False


def test_only_parents_delete_for_good(strict_client, tmp_path):
    p = _paint(strict_client, slot_key="dashboard")
    assert strict_client.delete(f"/api/v1/paintings/{p['id']}").status_code == 403
    assert strict_client.get(f"/api/v1/paintings/{p['id']}").status_code == 200

    res = strict_client.delete(f"/api/v1/paintings/{p['id']}", headers={"X-Parent-Token": issue_token()[0]})
    assert res.status_code == 204
    assert strict_client.get(f"/api/v1/paintings/{p['id']}").status_code == 404
    assert _resolve(strict_client, "dashboard")["dashboard"] is None
    assert not (tmp_path / "paintings" / f"{p['id']}.webp").exists()


def test_tiles_and_backgrounds_do_not_mix(strict_client):
    tile = _paint(strict_client, kind="tile", fmt="subject-tile", slot_key="dashboard/tile/sub_math")
    assert _resolve(strict_client, "dashboard/tile/sub_bio")["dashboard/tile/sub_bio"] is None

    res = strict_client.put("/api/v1/paintings/slots/dashboard", json={"painting_id": tile["id"]})
    assert res.status_code == 422
    res = strict_client.post("/api/v1/paintings", data={"kind": "background", "format": "square",
                                                        "slot_key": "dashboard/tile/sub_math"})
    assert res.status_code == 422
    history = strict_client.get("/api/v1/paintings/slots/dashboard/tile/sub_math/history",
                                params={"format": "subject-tile"}).json()
    assert [h["id"] for h in history] == [tile["id"]]


@pytest.mark.parametrize("data, files", [
    ({"kind": "sticker", "format": "square"}, None),
    ({"kind": "background", "format": "wide"}, None),
    ({"kind": "background", "format": "square", "slot_key": "../etc"}, None),
    ({"kind": "background", "format": "square"}, {"image": ("x.svg", b"<svg/>", "image/svg+xml")}),
])
def test_invalid_input_is_rejected(strict_client, data, files):
    assert strict_client.post("/api/v1/paintings", data=data, files=files).status_code == 422


def test_invalid_slot_key_in_query_is_rejected(strict_client):
    assert strict_client.get("/api/v1/paintings", params={"keys": "Dashboard!"}).status_code == 422
