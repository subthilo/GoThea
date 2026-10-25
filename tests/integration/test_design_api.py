"""Thea wählt ihr Farbschema selbst – ohne PIN; die Wahl liegt auf dem Server."""
import pytest

from backend.app import config


@pytest.fixture(autouse=True)
def own_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def test_default_theme_and_list(strict_client):
    data = strict_client.get("/api/v1/design").json()
    assert data["theme"] == "indigo"
    ids = [t["id"] for t in data["themes"]]
    assert ids[0] == "indigo" and "orange" in ids
    assert all(t["bg"].startswith("#") and t["accent"].startswith("#") for t in data["themes"])


def test_thea_can_choose_without_pin(strict_client):
    res = strict_client.put("/api/v1/design/theme", json={"theme": "orange"})
    assert res.status_code == 200
    assert strict_client.get("/api/v1/design").json()["theme"] == "orange"


def test_unknown_theme_is_rejected(strict_client):
    res = strict_client.put("/api/v1/design/theme", json={"theme": "zauberwelt"})
    assert res.status_code == 422
    assert strict_client.get("/api/v1/design").json()["theme"] == "indigo"


def test_damaged_settings_fall_back_to_default(strict_client, tmp_path):
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "settings.json").write_text("{kaputt", encoding="utf-8")
    assert strict_client.get("/api/v1/design").json()["theme"] == "indigo"


def test_old_theme_name_is_mapped(strict_client, tmp_path):
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "settings.json").write_text('{"theme": "nature"}', encoding="utf-8")
    assert strict_client.get("/api/v1/design").json()["theme"] == "gruen"
