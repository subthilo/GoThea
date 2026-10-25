"""Ausmalbilder über die API: Eltern laden hoch und geben frei, Thea sieht nur freigegebene; das Original
geht nie an Theas Browser."""
import pytest

from backend.app import config
from backend.app.services import coloring_pages as svc
from backend.app.services.parent_auth import issue_token

pytest.importorskip("shapely")

GOOD = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        b'<path fill-rule="evenodd" d="M0 0H100V100H0Z M10 10H90V90H10Z"/><rect x="48" y="10" width="4" height="80"/>'
        b'<script>alert(1)</script></svg>')
COLOURED = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#ffd400"/></svg>'


class _Session:
    """Die Hintergrund-Berechnung öffnet eine eigene Sitzung; im Test ist es die Test-Datenbank."""

    def __init__(self, db):
        self.db = db

    def __getattr__(self, name):
        return getattr(self.db, name)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch, db_session):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(svc, "session_factory", lambda: _Session(db_session))


def parent():
    return {"X-Parent-Token": issue_token()[0]}


def _upload(client, data=GOOD, name="Probe"):
    res = client.post("/api/v1/coloring-pages", data={"name": name},
                      files={"file": ("bild.svg", data, "image/svg+xml")}, headers=parent())
    assert res.status_code == 201, res.text
    return res.json()


def test_parents_upload_and_the_fields_are_computed(strict_client):
    page = _upload(strict_client)
    assert page["status"] == "rechnet"
    # TestClient führt die Hintergrund-Aufgabe vor der Rückkehr aus
    pages = strict_client.get("/api/v1/coloring-pages", headers=parent()).json()
    assert pages[0]["status"] == "berechnet" and pages[0]["field_count"] == 2
    shapes = strict_client.get(pages[0]["shapes_url"], headers=parent()).json()
    assert len(shapes["fields"]) == 2 and shapes["ink"].startswith("M")
    thumb = strict_client.get(pages[0]["thumb_url"], headers=parent())
    assert thumb.headers["content-type"].startswith("image/svg+xml")
    assert b"script" not in thumb.content  # nur die berechneten Formen, nie das Original


def test_thea_cannot_upload_and_sees_only_released_pages(strict_client):
    res = strict_client.post("/api/v1/coloring-pages", files={"file": ("bild.svg", GOOD, "image/svg+xml")})
    assert res.status_code == 403
    page = _upload(strict_client)
    assert strict_client.get("/api/v1/coloring-pages").json() == []
    assert strict_client.get(f"/api/v1/coloring-pages/{page['id']}/shapes").status_code == 404

    res = strict_client.put(f"/api/v1/coloring-pages/{page['id']}/freigabe", json={"freigegeben": True})
    assert res.status_code == 403
    res = strict_client.put(f"/api/v1/coloring-pages/{page['id']}/freigabe", json={"freigegeben": True},
                            headers=parent())
    assert res.json()["status"] == "freigegeben"
    listed = strict_client.get("/api/v1/coloring-pages").json()
    assert [p["id"] for p in listed] == [page["id"]] and "error" not in listed[0]
    assert strict_client.get(listed[0]["shapes_url"]).status_code == 200
    # Original nur für Eltern, als Download
    assert strict_client.get(f"/api/v1/coloring-pages/{page['id']}/original").status_code == 403
    orig = strict_client.get(f"/api/v1/coloring-pages/{page['id']}/original", headers=parent())
    assert orig.content == GOOD and "attachment" in orig.headers["content-disposition"]


def test_unusable_files_end_as_error_with_a_reason(strict_client):
    page = _upload(strict_client, COLOURED, "Bunt")
    listed = strict_client.get("/api/v1/coloring-pages", headers=parent()).json()
    assert listed[0]["status"] == "fehler" and "farbig" in listed[0]["error"]
    res = strict_client.put(f"/api/v1/coloring-pages/{page['id']}/freigabe", json={"freigegeben": True},
                            headers=parent())
    assert res.status_code == 422
    res = strict_client.post("/api/v1/coloring-pages", files={"file": ("x.svg", b"hallo", "text/plain")},
                             headers=parent())
    assert res.status_code == 422


def test_removed_pages_leave_the_list_but_shapes_stay_for_painted_pictures(strict_client):
    page = _upload(strict_client)
    strict_client.put(f"/api/v1/coloring-pages/{page['id']}/freigabe", json={"freigegeben": True}, headers=parent())
    shapes_url = strict_client.get("/api/v1/coloring-pages").json()[0]["shapes_url"]
    assert strict_client.delete(f"/api/v1/coloring-pages/{page['id']}").status_code == 403
    assert strict_client.delete(f"/api/v1/coloring-pages/{page['id']}", headers=parent()).status_code == 204
    assert strict_client.get("/api/v1/coloring-pages").json() == []
    assert strict_client.get(shapes_url).status_code == 200


def test_interrupted_computations_become_errors(db_session):
    from backend.app.models.coloring_page import ColoringPage
    db_session.add(ColoringPage(id="cpg_test", name="X", status="rechnet"))
    db_session.commit()
    assert svc.recover_interrupted(db_session) == 1
    assert db_session.get(ColoringPage, "cpg_test").status == "fehler"
