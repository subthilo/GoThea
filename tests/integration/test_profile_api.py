def test_get_profile(client):
    response = client.get("/api/v1/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Thea"
    assert data["grade_level"] == 7
    assert data["school_type"] == "Gymnasium"
    assert data["federal_state"] == "Brandenburg"

def test_patch_profile_valid(client):
    response = client.patch("/api/v1/profile", json={"grade_level": 8, "name": "Thea M."})
    assert response.status_code == 200
    data = response.json()
    assert data["grade_level"] == 8
    assert data["name"] == "Thea M."

    # Erneut abrufen zur Verifikation der Persistenz
    verify_res = client.get("/api/v1/profile")
    assert verify_res.json()["grade_level"] == 8

def test_patch_profile_invalid_grade(client):
    # Ungültige Klassenstufe (z. B. 15)
    response = client.patch("/api/v1/profile", json={"grade_level": 15})
    assert response.status_code == 422  # Pydantic Validierungsfehler
