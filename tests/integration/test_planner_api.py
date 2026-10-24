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


def _topic(client, subject_id, name):
    res = client.post("/api/v1/taxonomy/topics", json={"subject_id": subject_id, "name": name, "grade_level": 7})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_test_carries_topics_chosen_from_the_catalog(client):
    terms = _topic(client, "sub_math", "Terme und Gleichungen")
    fractions = _topic(client, "sub_math", "Bruchrechnung")
    exam = (date.today() + timedelta(days=7)).isoformat()
    created = client.post("/api/v1/tests", json={"subject_id": "sub_math", "kind": "Test", "date": exam,
                                                 "topic_ids": [terms]}).json()
    assert [t["name"] for t in created["topics"]] == ["Terme und Gleichungen"]
    # Ändern: Themen austauschen, Rest bleibt
    changed = client.patch(f"/api/v1/tests/{created['id']}", json={"topic_ids": [fractions, terms]}).json()
    assert [t["name"] for t in changed["topics"]] == ["Bruchrechnung", "Terme und Gleichungen"]
    assert changed["kind"] == "Test" and changed["date"] == exam
    # Themen erscheinen auch im Plan
    plan = client.get("/api/v1/plan").json()
    listed = next(t for t in plan["upcoming_tests"] if t["id"] == created["id"])
    assert len(listed["topics"]) == 2


def test_test_topics_must_belong_to_its_subject(client):
    other = _topic(client, "sub_german", "Balladen")
    exam = (date.today() + timedelta(days=7)).isoformat()
    res = client.post("/api/v1/tests", json={"subject_id": "sub_math", "date": exam, "topic_ids": [other]})
    assert res.status_code == 422
    res = client.post("/api/v1/tests", json={"subject_id": "sub_math", "date": exam, "topic_ids": ["top_gibtsnicht"]})
    assert res.status_code == 422


def test_topic_can_be_marked_current(client):
    topic = _topic(client, "sub_math", "Prozentrechnung")
    on = client.put(f"/api/v1/taxonomy/topics/{topic}/current", json={"current": True}).json()
    assert on["current_since"] is not None
    # Erneutes Setzen behält das Datum
    assert client.put(f"/api/v1/taxonomy/topics/{topic}/current", json={"current": True}).json()["current_since"] == on["current_since"]
    listed = next(t for t in client.get("/api/v1/taxonomy/topics?subject_id=sub_math").json() if t["id"] == topic)
    assert listed["current_since"] == on["current_since"]
    assert client.put(f"/api/v1/taxonomy/topics/{topic}/current", json={"current": False}).json()["current_since"] is None


def test_changing_tests_and_topics_needs_parent_mode(strict_client):
    exam = (date.today() + timedelta(days=7)).isoformat()
    assert strict_client.post("/api/v1/tests", json={"subject_id": "sub_math", "date": exam}).status_code == 403
    assert strict_client.patch("/api/v1/tests/tst_x", json={"note": "x"}).status_code == 403
    assert strict_client.put("/api/v1/taxonomy/topics/top_x/current", json={"current": True}).status_code == 403


def _chapter(db_session):
    """Arbeitsheft mit einem Kapitel (10 Seiten) – nur die Datensätze, ohne Datei."""
    from backend.app.models.material import Material
    common = dict(user_id="usr_thea", subject_id="sub_math", filename="x.pdf", file_path="/tmp/x.pdf",
                  mime_type="application/pdf")
    db_session.add(Material(id="mat_heft", title="Mathe Arbeitsheft 7", kind="Buch", page_count=40, **common))
    db_session.add(Material(id="mat_heft_ch01", title="Kapitel 1", kind="Buchauszug", page_count=10,
                            parent_id="mat_heft", start_page=1, end_page=10, **common))
    db_session.commit()
    return "mat_heft_ch01"


def test_test_carries_book_sections(client, db_session):
    chapter = _chapter(db_session)
    exam = (date.today() + timedelta(days=7)).isoformat()
    section = {"material_id": chapter, "start_page": 3, "end_page": 5, "title": "Brüche", "book_page": 3}
    created = client.post("/api/v1/tests", json={"subject_id": "sub_math", "date": exam, "sections": [section]}).json()
    assert created["sections"] == [{**section, "book_title": "Mathe Arbeitsheft 7", "subject_id": "sub_math"}]
    # Ändern ersetzt die Abschnitte; Themen bleiben unberührt
    whole = {"material_id": chapter, "start_page": 1, "end_page": 10, "title": "Kapitel 1"}
    changed = client.patch(f"/api/v1/tests/{created['id']}", json={"sections": [whole]}).json()
    assert [s["title"] for s in changed["sections"]] == ["Kapitel 1"]
    # Seiten außerhalb des Kapitels oder falsches Fach werden abgelehnt
    bad = {**section, "end_page": 11}
    assert client.patch(f"/api/v1/tests/{created['id']}", json={"sections": [bad]}).status_code == 422
    assert client.post("/api/v1/tests", json={"subject_id": "sub_bio", "date": exam,
                                              "sections": [section]}).status_code == 422


def test_current_sections_are_replaced_per_subject(client, db_session):
    chapter = _chapter(db_session)
    first = {"material_id": chapter, "start_page": 1, "end_page": 2, "title": "Zahlen"}
    second = {"material_id": chapter, "start_page": 3, "end_page": 5, "title": "Brüche"}
    res = client.put("/api/v1/plan/current-sections", json={"subject_id": "sub_math", "sections": [first, second]})
    assert [s["title"] for s in res.json()] == ["Zahlen", "Brüche"]
    res = client.put("/api/v1/plan/current-sections", json={"subject_id": "sub_math", "sections": [second]})
    assert [s["title"] for s in res.json()] == ["Brüche"]
    assert [s["title"] for s in client.get("/api/v1/plan/current-sections").json()] == ["Brüche"]
    assert client.get("/api/v1/plan/current-sections?subject_id=sub_bio").json() == []


def test_current_sections_need_parent_mode(strict_client):
    assert strict_client.put("/api/v1/plan/current-sections",
                             json={"subject_id": "sub_math", "sections": []}).status_code == 403
