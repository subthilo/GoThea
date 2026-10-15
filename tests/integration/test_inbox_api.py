from backend.app.config import INBOX_DIR
from tests.unit.test_inbox_service import create_sample_pdf_bytes

def test_get_inbox_status_api(client):
    res = client.get("/api/v1/inbox/status")
    assert res.status_code == 200
    data = res.json()
    assert "pending_count" in data
    assert "errors_count" in data
    assert "files" in data
    assert isinstance(data["files"], list)

def test_process_inbox_api_flow(client):
    # Test-PDF in den Inbox-Ordner legen
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    test_file = INBOX_DIR / "biologie_pflanzenzelle_test.pdf"
    test_file.write_bytes(create_sample_pdf_bytes("Biologie Pflanzenzelle Aufbau"))

    # Vor dem Process Status abfragen
    res_status = client.get("/api/v1/inbox/status")
    assert res_status.status_code == 200
    assert any(f["filename"] == "biologie_pflanzenzelle_test.pdf" for f in res_status.json()["files"])

    # Processing anstoßen
    res_process = client.post("/api/v1/inbox/process")
    assert res_process.status_code == 200
    result = res_process.json()

    assert result["processed_count"] >= 1
    assert result["errors_count"] == 0
    assert any(item["title"] == "Biologie Pflanzenzelle Test" for item in result["processed_items"])

    # Datei muss aus inbox/ verschwunden sein!
    assert not test_file.exists()

    # Nach dem Process: Status muss 0 für diese Datei sein
    res_status_after = client.get("/api/v1/inbox/status")
    assert res_status_after.status_code == 200
    assert not any(f["filename"] == "biologie_pflanzenzelle_test.pdf" for f in res_status_after.json()["files"])
