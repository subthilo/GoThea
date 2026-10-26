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


def test_own_paint_colors_without_pin(strict_client):
    assert strict_client.get("/api/v1/design").json()["paint_colors"] == []
    colors = ["#3A7D44"] + [f"#00000{i}" for i in range(9)] + ["#3a7d44"]
    res = strict_client.put("/api/v1/design/paint-colors", json={"colors": colors})
    assert res.status_code == 200
    saved = res.json()["paint_colors"]
    assert saved[0] == "#3a7d44" and len(saved) == 8 and len(set(saved)) == 8
    assert strict_client.get("/api/v1/design").json()["paint_colors"] == saved
    # Theas Farbschema bleibt davon unberührt
    assert strict_client.get("/api/v1/design").json()["theme"] == "indigo"


def test_paint_colors_must_be_colors(strict_client):
    res = strict_client.put("/api/v1/design/paint-colors", json={"colors": ["red"]})
    assert res.status_code == 422
