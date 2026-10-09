from datetime import date, timedelta

def test_create_and_list_test(client):
    today = date.today()
    exam_date = (today + timedelta(days=7)).isoformat()

    payload = {
        "subject_id": "sub_math",
        "kind": "Klassenarbeit",
        "date": exam_date,
        "note": "Lineare Gleichungen und Terme"
    }

    # 1. Anlegen
    res_create = client.post("/api/v1/tests", json=payload)
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["kind"] == "Klassenarbeit"
    assert created["subject_name"] == "Mathematik"

    # 2. In Liste finden
    res_list = client.get("/api/v1/tests")
    assert res_list.status_code == 200
    tests = res_list.json()
    assert any(t["id"] == created["id"] for t in tests)

    # 3. Löschen
    del_res = client.delete(f"/api/v1/tests/{created['id']}")
    assert del_res.status_code == 200


def test_study_block_crud(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "date": tomorrow,
        "type": "all"
    }

    res_post = client.post("/api/v1/plan/block", json=payload)
    assert res_post.status_code == 201
    block_id = res_post.json()["id"]

    # Duplikat muss 400 geben
    dup_res = client.post("/api/v1/plan/block", json=payload)
    assert dup_res.status_code == 400

    # Löschen
    del_res = client.delete(f"/api/v1/plan/block/{block_id}")
    assert del_res.status_code == 200


def test_plan_calculation_and_task_toggle(client):
    today = date.today()
    exam_date = (today + timedelta(days=5)).isoformat()

    # 1. Test anlegen
    test_res = client.post("/api/v1/tests", json={
        "subject_id": "sub_bio",
        "kind": "Test",
        "date": exam_date,
        "note": "Fotosynthese"
    })
    test_id = test_res.json()["id"]

    # 2. Plan abrufen
    plan_res = client.get("/api/v1/plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert "today_plan" in plan_data
    assert "next_7_days" in plan_data

    # Heute sollte ein Task für den Test existieren
    today_tasks = plan_data["today_plan"]["tasks"]
    matching = [t for t in today_tasks if t["test_id"] == test_id]
    assert len(matching) == 1
    task = matching[0]
    assert task["days_until_test"] == 5
    assert task["target_minutes"] == 20
    assert not task["is_completed"]

    # 3. Task als erledigt abhaken
    toggle_res = client.post("/api/v1/plan/complete-task", json={
        "test_id": test_id,
        "date": today.isoformat(),
        "completed": True
    })
    assert toggle_res.status_code == 200

    # 4. Plan erneut abrufen -> muss als erledigt markiert sein
    plan_res2 = client.get("/api/v1/plan")
    today_tasks2 = plan_res2.json()["today_plan"]["tasks"]
    matching2 = [t for t in today_tasks2 if t["test_id"] == test_id]
    assert matching2[0]["is_completed"] is True


def test_staging_seed_dummies(client):
    res = client.post("/api/v1/staging/seed-dummy-tests")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["created_count"] == 3

    # Tests abrufen
    tests_res = client.get("/api/v1/tests")
    assert len(tests_res.json()) >= 3
