import pytest

def test_get_timetable_overview(client):
    res = client.get("/api/v1/timetable")
    assert res.status_code == 200
    data = res.json()
    assert data["class_name"] == "Klasse 7D"
    assert "Humboldt" in data["school_name"]
    assert len(data["periods"]) == 9
    assert len(data["slots"]) > 0

    # Prüfen, dass Deutsch am Montag existiert
    mo_slots = [s for s in data["slots"] if s["day_of_week"] == "Montag"]
    assert any(s["subject_code"] == "D" for s in mo_slots)
    assert any(s["subject_code"] == "Ma" for s in mo_slots)

def test_timetable_week_a_and_b_differences(client):
    # Abfrage für A-Woche
    res_a = client.get("/api/v1/timetable?week_type=A")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["current_week_type"] == "A"
    mo_5_a = [s for s in data_a["slots"] if s["day_of_week"] == "Montag" and s["period"] == 5 and s["week_type"] == "A"]
    assert len(mo_5_a) == 1
    assert mo_5_a[0]["subject_code"] == "*Sp"

    # Abfrage für B-Woche
    res_b = client.get("/api/v1/timetable?week_type=B")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["current_week_type"] == "B"
    mo_5_b = [s for s in data_b["slots"] if s["day_of_week"] == "Montag" and s["period"] == 5 and s["week_type"] == "B"]
    assert len(mo_5_b) == 1
    assert mo_5_b[0]["subject_code"] == "En"

def test_get_today_timetable(client):
    res = client.get("/api/v1/timetable/today")
    assert res.status_code == 200
    data = res.json()
    assert "day" in data
    assert "lessons" in data
    assert isinstance(data["lessons"], list)

def test_reset_timetable(client):
    res = client.post("/api/v1/timetable/reset")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

def test_slot_crud_lifecycle(client):
    # 1. Neuen Slot erstellen
    new_slot_payload = {
        "day_of_week": "Freitag",
        "period": 8,
        "period_label": "8. Std",
        "start_time": "14:40",
        "end_time": "15:25",
        "subject_id": "sub_math",
        "subject_code": "Ma-AG",
        "subject_name": "Mathe Olympiade AG",
        "teacher": "HORN",
        "room": "303",
        "week_type": "both",
        "is_double_period": False,
        "is_break": False,
        "note": "Mathe AG Vorbereitung"
    }
    create_res = client.post("/api/v1/timetable/slot", json=new_slot_payload)
    assert create_res.status_code == 201
    created_slot = create_res.json()
    slot_id = created_slot["id"]
    assert slot_id.startswith("slot_")
    assert created_slot["subject_code"] == "Ma-AG"
    assert created_slot["teacher"] == "HORN"
    assert created_slot["room"] == "303"

    # 2. Prüfen, dass Slot im Gesamt-Stundenplan auftaucht
    overview_res = client.get("/api/v1/timetable")
    assert overview_res.status_code == 200
    all_slots = overview_res.json()["slots"]
    assert any(s["id"] == slot_id for s in all_slots)

    # 3. Slot aktualisieren
    update_payload = {
        **new_slot_payload,
        "room": "305",
        "note": "Raumwechsel auf 305"
    }
    update_res = client.put(f"/api/v1/timetable/slot/{slot_id}", json=update_payload)
    assert update_res.status_code == 200
    updated_slot = update_res.json()
    assert updated_slot["room"] == "305"
    assert updated_slot["note"] == "Raumwechsel auf 305"

    # 4. Slot löschen
    delete_res = client.delete(f"/api/v1/timetable/slot/{slot_id}")
    assert delete_res.status_code == 204

    # 5. Prüfen, dass Slot nicht mehr da ist
    overview_after_res = client.get("/api/v1/timetable")
    all_slots_after = overview_after_res.json()["slots"]
    assert not any(s["id"] == slot_id for s in all_slots_after)

def test_slot_crud_not_found_handling(client):
    dummy_payload = {
        "day_of_week": "Montag",
        "period": 1,
        "subject_name": "Test"
    }
    # Update auf nicht existierenden Slot
    put_res = client.put("/api/v1/timetable/slot/non_existent_slot_999", json=dummy_payload)
    assert put_res.status_code == 404
    assert "nicht gefunden" in put_res.json()["detail"]

    # Delete auf nicht existierenden Slot
    del_res = client.delete("/api/v1/timetable/slot/non_existent_slot_999")
    assert del_res.status_code == 404
    assert "nicht gefunden" in del_res.json()["detail"]
