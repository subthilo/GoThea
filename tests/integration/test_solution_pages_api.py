"""Lösungsseiten sieht Thea nicht: Seitenbild als Schloss, kein Download, kein Volltext (services/solution_pages.py)."""
import io

import pytest
from pypdf import PdfWriter

from backend.app.models.material import Material
from backend.app.services import solution_pages


def _material(db_session, tmp_path, kind="Arbeitsblatt", solution_pages_json="[2]"):
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=200, height=280)
    buf = io.BytesIO()
    writer.write(buf)
    path = tmp_path / "blatt.pdf"
    path.write_bytes(buf.getvalue())
    mat = Material(subject_id="sub_bio", title="Blatt mit Lösung", kind=kind, filename="blatt.pdf",
                   file_path=str(path), page_count=2, solution_pages_json=solution_pages_json,
                   extracted_text="--- Seite 2 ---\nLösung: Vakuole")
    db_session.add(mat)
    db_session.commit()
    return mat


def _token(client):
    return client.post("/api/v1/auth/parent/unlock", json={"pin": "1234"}).json()["token"]


def test_rule_uses_kind_and_confirmed_pages():
    class M:
        kind, solution_pages_json = "Arbeitsblatt", "[2]"
    assert not solution_pages.is_solution_page(M, 1)
    assert solution_pages.is_solution_page(M, 2)
    M.kind = "Lösungsheft"
    assert solution_pages.is_solution_page(M, 1)
    M.kind, M.solution_pages_json = "Buchauszug", "kaputt"
    assert not solution_pages.is_solution_page(M, 1)


def test_thea_sees_a_lock_instead_of_the_solution_page(strict_client, db_session, tmp_path):
    mat = _material(db_session, tmp_path)
    task = strict_client.get(f"/api/v1/materials/{mat.id}/preview?page=1")
    assert task.status_code == 200 and task.headers["content-type"].startswith("image/jpeg")
    assert "no-store" not in task.headers["cache-control"]
    locked = strict_client.get(f"/api/v1/materials/{mat.id}/preview?page=2")
    assert locked.status_code == 200
    assert locked.headers["content-type"].startswith("image/svg+xml")
    assert locked.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("send", ["header", "cookie"])
def test_parents_see_the_solution_page_but_it_is_never_cached(strict_client, db_session, tmp_path, send):
    mat = _material(db_session, tmp_path)
    token = _token(strict_client)
    headers = {"X-Parent-Token": token} if send == "header" else {}
    if send == "cookie":
        strict_client.cookies.set("gothea_parent", token)
    res = strict_client.get(f"/api/v1/materials/{mat.id}/preview?page=2", headers=headers)
    assert res.headers["content-type"].startswith("image/jpeg")
    assert res.headers["cache-control"] == "no-store"


def test_whole_solution_booklet_is_locked(strict_client, db_session, tmp_path):
    mat = _material(db_session, tmp_path, kind="Lösungsheft", solution_pages_json=None)
    res = strict_client.get(f"/api/v1/materials/{mat.id}/preview?page=1")
    assert res.headers["content-type"].startswith("image/svg+xml")


def test_download_only_for_parents(strict_client, db_session, tmp_path):
    mat = _material(db_session, tmp_path, solution_pages_json=None)
    assert strict_client.get(f"/api/v1/materials/{mat.id}/file").status_code == 403
    strict_client.cookies.set("gothea_parent", _token(strict_client))
    assert strict_client.get(f"/api/v1/materials/{mat.id}/file").status_code == 200


def test_full_text_only_for_parents(strict_client, db_session, tmp_path):
    mat = _material(db_session, tmp_path)
    assert strict_client.get(f"/api/v1/materials/{mat.id}").json()["extracted_text"] is None
    res = strict_client.get(f"/api/v1/materials/{mat.id}", headers={"X-Parent-Token": _token(strict_client)})
    assert "Vakuole" in res.json()["extracted_text"]


def test_cookie_never_unlocks_changes(strict_client, db_session, tmp_path):
    # Das Cookie gilt nur zum Ansehen; Änderungen brauchen den Header (sonst könnte eine fremde Seite sie auslösen)
    mat = _material(db_session, tmp_path)
    strict_client.cookies.set("gothea_parent", _token(strict_client))
    assert strict_client.delete(f"/api/v1/materials/{mat.id}").status_code == 403


def _is_locked(client, mat):
    return client.get(f"/api/v1/materials/{mat.id}/preview?page=2").headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("flag", ["worked_on_paper", "teacher_graded"])
def test_solutions_open_once_the_sheet_was_done_on_paper(strict_client, db_session, tmp_path, flag):
    mat = _material(db_session, tmp_path)
    setattr(mat, flag, True)
    db_session.commit()
    assert not _is_locked(strict_client, mat)


def test_solutions_open_once_every_exercise_from_the_sheet_was_solved(strict_client, db_session, tmp_path,
                                                                     monkeypatch):
    from datetime import datetime
    from backend.app.models.practice_attempt import PracticeAttempt
    from backend.app.services import practice_exercises

    mat = _material(db_session, tmp_path)
    assert _is_locked(strict_client, mat)  # ohne Übungen: nur der Scan gibt frei
    monkeypatch.setattr(practice_exercises, "list_exercises", lambda include_drafts=False: [
        {"id": "bio-a", "zwillinge": ["bio-a-z1"], "quelle": {"material_id": mat.id}},
        {"id": "bio-b", "zwillinge": [], "quelle": {"material_id": mat.id}},
        {"id": "anderes", "zwillinge": [], "quelle": {"material_id": "mat_anderes"}},
    ])

    def attempt(exercise_id, solved):
        db_session.add(PracticeAttempt(exercise_id=exercise_id, stage=1, solved_at=datetime.utcnow() if solved else None))
        db_session.commit()

    attempt("bio-a-z1", solved=True)   # Zwilling zählt für das Original
    attempt("bio-b", solved=False)     # angefangen ist nicht geschafft
    assert _is_locked(strict_client, mat)
    attempt("bio-b", solved=True)
    assert not _is_locked(strict_client, mat)
