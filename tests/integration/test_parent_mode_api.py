"""Tests für den Eltern-/Thea-Modus (PIN, Tokens, Rechteprüfung)."""
import time

from backend.app.services import parent_auth


def _unlock(client, pin="1234"):
    return client.post("/api/v1/auth/parent/unlock", json={"pin": pin})


def test_unlock_with_default_pin(strict_client):
    res = _unlock(strict_client)
    assert res.status_code == 200
    data = res.json()
    assert data["token"]
    assert data["expires_at"] > time.time()
    assert data["is_default_pin"] is True


def test_unlock_with_wrong_pin(strict_client):
    res = _unlock(strict_client, "0000")
    assert res.status_code == 401
    assert "Falsche PIN" in res.json()["detail"]


def test_lockout_after_too_many_failed_attempts(strict_client):
    for _ in range(parent_auth.MAX_FAILED_ATTEMPTS - 1):
        assert _unlock(strict_client, "9999").status_code == 401
    assert _unlock(strict_client, "9999").status_code == 429
    # Auch die richtige PIN wird während der Sperre abgewiesen
    assert _unlock(strict_client, "1234").status_code == 429


def test_status_endpoint(strict_client):
    assert strict_client.get("/api/v1/auth/parent/status").json()["is_parent"] is False
    token = _unlock(strict_client).json()["token"]
    res = strict_client.get("/api/v1/auth/parent/status", headers={"X-Parent-Token": token})
    assert res.json()["is_parent"] is True


def test_thea_mode_blocks_destructive_actions(strict_client):
    blocked = [
        ("delete", "/api/v1/materials/mat_x"),
        ("patch", "/api/v1/materials/mat_x"),
        ("post", "/api/v1/materials/merge"),
        ("post", "/api/v1/tests"),
        ("delete", "/api/v1/tests/t1"),
        ("post", "/api/v1/plan/block"),
        ("delete", "/api/v1/plan/block/b1"),
        ("post", "/api/v1/timetable/reset"),
        ("delete", "/api/v1/timetable/slot/s1"),
        ("patch", "/api/v1/profile"),
        ("post", "/api/v1/materials/pre-analyze"),
        ("post", "/api/v1/materials/confirm"),
        ("post", "/api/v1/inbox/process"),
    ]
    for method, url in blocked:
        kwargs = {"json": {}} if method in ("post", "put", "patch") else {}
        res = getattr(strict_client, method)(url, **kwargs)
        assert res.status_code == 403, f"{method.upper()} {url} sollte gesperrt sein, war {res.status_code}"
        assert "Eltern-Modus" in res.json()["detail"]


def test_thea_mode_allows_learning_actions(strict_client):
    # Lesen & Aufgaben abhaken bleibt erlaubt
    assert strict_client.get("/api/v1/materials").status_code == 200
    assert strict_client.get("/api/v1/plan").status_code == 200
    res = strict_client.post("/api/v1/plan/complete-task", json={"test_id": "t1", "date": "2026-10-12", "completed": True})
    assert res.status_code == 200


def test_parent_token_allows_destructive_action(strict_client):
    token = _unlock(strict_client).json()["token"]
    res = strict_client.delete("/api/v1/materials/does_not_exist", headers={"X-Parent-Token": token})
    # Rechteprüfung bestanden -> fachlicher 404 statt 403
    assert res.status_code == 404


def test_tampered_or_expired_token_is_rejected(strict_client, monkeypatch):
    token = _unlock(strict_client).json()["token"]
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert strict_client.delete("/api/v1/materials/x", headers={"X-Parent-Token": tampered}).status_code == 403

    monkeypatch.setattr(parent_auth, "TOKEN_TTL_SECONDS", -10)
    expired, _ = parent_auth.issue_token()
    assert strict_client.delete("/api/v1/materials/x", headers={"X-Parent-Token": expired}).status_code == 403


def test_change_pin_invalidates_old_tokens(strict_client):
    token = _unlock(strict_client).json()["token"]
    res = strict_client.post(
        "/api/v1/auth/parent/change-pin",
        json={"current_pin": "1234", "new_pin": "4711"},
        headers={"X-Parent-Token": token},
    )
    assert res.status_code == 200
    new_token = res.json()["token"]

    # Alte PIN und altes Token gelten nicht mehr
    assert _unlock(strict_client, "1234").status_code == 401
    assert strict_client.get("/api/v1/auth/parent/status", headers={"X-Parent-Token": token}).json()["is_parent"] is False
    assert strict_client.get("/api/v1/auth/parent/status", headers={"X-Parent-Token": new_token}).json()["is_parent"] is True

    unlocked = _unlock(strict_client, "4711").json()
    assert unlocked["is_default_pin"] is False


def test_change_pin_validation(strict_client):
    token = _unlock(strict_client).json()["token"]
    headers = {"X-Parent-Token": token}
    assert strict_client.post("/api/v1/auth/parent/change-pin", json={"current_pin": "1234", "new_pin": "12"}, headers=headers).status_code == 400
    assert strict_client.post("/api/v1/auth/parent/change-pin", json={"current_pin": "1234", "new_pin": "abcd"}, headers=headers).status_code == 400
    assert strict_client.post("/api/v1/auth/parent/change-pin", json={"current_pin": "0000", "new_pin": "5555"}, headers=headers).status_code == 401
    # Ohne Eltern-Token gar nicht erreichbar
    assert strict_client.post("/api/v1/auth/parent/change-pin", json={"current_pin": "1234", "new_pin": "5555"}).status_code == 403
