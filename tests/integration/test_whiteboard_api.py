import pytest

def test_create_and_get_whiteboard_session(client):
    payload = {
        "subject_id": "sub_math",
        "title": "Mathematik Tafelübung",
        "grade_level": 7
    }
    res = client.post("/api/v1/whiteboard/sessions", json=payload)
    assert res.status_code == 201
    data = res.json()
    session_id = data["id"]
    assert session_id.startswith("ses_")
    assert data["subject_id"] == "sub_math"
    assert data["subject_name"] == "Mathematik"
    assert data["end_time"] is None

    # Get single session
    get_res = client.get(f"/api/v1/whiteboard/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Mathematik Tafelübung"

def test_create_session_invalid_subject(client):
    payload = {
        "subject_id": "sub_nonexistent",
        "title": "Ungültig"
    }
    res = client.post("/api/v1/whiteboard/sessions", json=payload)
    assert res.status_code == 404

def test_active_session_lifecycle(client):
    # 1. Start a session
    res = client.post("/api/v1/whiteboard/sessions", json={"subject_id": "sub_bio", "title": "Bio Tafel"})
    assert res.status_code == 201
    session_id = res.json()["id"]

    # 2. Query active session
    active_res = client.get("/api/v1/whiteboard/sessions/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data is not None
    assert active_data["id"] == session_id

    # 3. Close the session
    close_res = client.post(f"/api/v1/whiteboard/sessions/{session_id}/close", json={"summary_notes": "Gut gearbeitet."})
    assert close_res.status_code == 200
    assert close_res.json()["end_time"] is not None
    assert close_res.json()["summary_notes"] == "Gut gearbeitet."

    # 4. Check active again (should be None or another session)
    active_res2 = client.get("/api/v1/whiteboard/sessions/active")
    assert active_res2.status_code == 200
    # Da es keine weitere offene Session gibt, muss None zurückkommen
    assert active_res2.json() is None

def test_update_session_state_and_snapshot(client):
    res = client.post("/api/v1/whiteboard/sessions", json={"subject_id": "sub_german"})
    session_id = res.json()["id"]

    mock_strokes = '[{"tool":"pen","color":"#3b82f6","width":4,"points":[{"x":10,"y":20,"pressure":0.7}]}]'
    mock_snapshot = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    update_payload = {
        "board_state_json": mock_strokes,
        "snapshot_data_url": mock_snapshot,
        "summary_notes": "Aufgabe 1 gelöst"
    }
    put_res = client.put(f"/api/v1/whiteboard/sessions/{session_id}/state", json=update_payload)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["board_state_json"] == mock_strokes
    assert data["snapshot_data_url"] == mock_snapshot
    assert data["summary_notes"] == "Aufgabe 1 gelöst"

def test_mock_tutor_hint(client):
    res = client.post("/api/v1/whiteboard/sessions", json={"subject_id": "sub_math"})
    session_id = res.json()["id"]

    hint_res = client.post(f"/api/v1/whiteboard/sessions/{session_id}/mock-tutor-hint")
    assert hint_res.status_code == 200
    data = hint_res.json()
    assert data["status"] == "success"
    assert len(data["actions"]) >= 1
    assert data["actions"][0]["action"] == "highlight_box"

def test_delete_session(client):
    res = client.post("/api/v1/whiteboard/sessions", json={"subject_id": "sub_physics"})
    session_id = res.json()["id"]

    del_res = client.delete(f"/api/v1/whiteboard/sessions/{session_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/v1/whiteboard/sessions/{session_id}")
    assert get_res.status_code == 404

def test_whiteboard_websocket_communication(client):
    res = client.post("/api/v1/whiteboard/sessions", json={"subject_id": "sub_math"})
    session_id = res.json()["id"]

    with client.websocket_connect(f"/ws/tutor/{session_id}") as ws:
        # 1. Connection ack
        welcome = ws.receive_json()
        assert welcome["type"] == "session_connected"
        assert welcome["session_id"] == session_id

        # 2. Ping / Pong
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"

        # 3. Canvas update
        ws.send_json({
            "type": "canvas_update",
            "strokes": [{"tool": "pen", "points": [{"x": 100, "y": 200}]}],
            "timestamp": 123456789
        })
        ack = ws.receive_json()
        assert ack["type"] == "canvas_ack"
        assert ack["strokes_count"] == 1

        # 4. User interrupt (barge-in)
        ws.send_json({
            "type": "user_interrupt",
            "reason": "pencil_touch"
        })
        intr_ack = ws.receive_json()
        assert intr_ack["type"] == "interrupt_ack"
        assert intr_ack["reason"] == "pencil_touch"

        # 5. Request hint
        ws.send_json({"type": "request_hint"})
        hint = ws.receive_json()
        assert hint["type"] == "board_actions"
        assert len(hint["actions"]) > 0
