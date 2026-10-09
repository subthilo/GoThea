def test_list_subjects(client):
    response = client.get("/api/v1/taxonomy/subjects")
    assert response.status_code == 200
    subjects = response.json()
    assert len(subjects) >= 7
    subject_names = [s["name"] for s in subjects]
    assert "Mathematik" in subject_names
    assert "Biologie" in subject_names
    assert "Deutsch" in subject_names

def test_list_subjects_filter_by_grade(client):
    # Physik ist min_grade=7
    res_grade_7 = client.get("/api/v1/taxonomy/subjects?grade_level=7")
    names_7 = [s["name"] for s in res_grade_7.json()]
    assert "Physik" in names_7

    # Physik sollte in Klasse 4 nicht auftauchen
    res_grade_4 = client.get("/api/v1/taxonomy/subjects?grade_level=4")
    names_4 = [s["name"] for s in res_grade_4.json()]
    assert "Physik" not in names_4

def test_create_subject_success(client):
    new_sub = {
        "name": "Astronomie",
        "color_code": "#312e81",
        "icon": "🔭",
        "min_grade": 9,
        "max_grade": 12
    }
    response = client.post("/api/v1/taxonomy/subjects", json=new_sub)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Astronomie"
    assert data["icon"] == "🔭"

def test_create_subject_duplicate_fails(client):
    dup = {
        "name": "Mathematik",
        "color_code": "#000000",
        "icon": "📐"
    }
    response = client.post("/api/v1/taxonomy/subjects", json=dup)
    assert response.status_code == 400

def test_list_topics_filter(client):
    response = client.get("/api/v1/taxonomy/topics?subject_id=sub_math&grade_level=7")
    assert response.status_code == 200
    topics = response.json()
    assert len(topics) >= 1
    assert any("Rationale Zahlen" in t["name"] for t in topics)

def test_create_topic_success(client):
    new_topic = {
        "subject_id": "sub_bio",
        "name": "Genetik & Vererbung",
        "grade_level": 9,
        "rlp_level_code": "F",
        "standard_competencies": "Mendelsche Regeln, DNA-Aufbau"
    }
    response = client.post("/api/v1/taxonomy/topics", json=new_topic)
    assert response.status_code == 201
    assert response.json()["name"] == "Genetik & Vererbung"

def test_create_topic_invalid_subject(client):
    new_topic = {
        "subject_id": "sub_nonexistent",
        "name": "Test Topic",
        "grade_level": 7
    }
    response = client.post("/api/v1/taxonomy/topics", json=new_topic)
    assert response.status_code == 404
