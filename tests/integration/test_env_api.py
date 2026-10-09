def test_get_env_info(client):
    response = client.get("/api/v1/env")
    assert response.status_code == 200
    data = response.json()
    assert "app_env" in data
    assert "is_staging" in data
    assert "env_label" in data

def test_staging_reset(client):
    response = client.post("/api/v1/staging/reset")
    # Im Test-Environment (default staging) muss der Reset 200 liefern
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verifizieren, dass der Standardbenutzer und Fächer wieder da sind
    prof_res = client.get("/api/v1/profile")
    assert prof_res.status_code == 200
    assert prof_res.json()["name"] == "Thea"
