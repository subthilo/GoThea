import io
from pypdf import PdfWriter

def create_sample_pdf_bytes(text: str = "Biologie Klasse 7: Pflanzenzelle und Vakuole.") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # Für echten extrahierbaren Text schreiben wir Metadaten oder Seiteninhalt
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

def test_pre_analyze_empty_file_fails(client):
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    res = client.post("/api/v1/materials/pre-analyze", files=files)
    assert res.status_code == 400
    assert "leer" in res.json()["detail"].lower()

def test_pre_analyze_and_confirm_workflow(client):
    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("biologie_pflanzenzelle_uebung.pdf", pdf_bytes, "application/pdf")}

    # 1. Stufe 1: Vorab-Analyse
    res_pre = client.post("/api/v1/materials/pre-analyze", files=files)
    assert res_pre.status_code == 200
    pre_data = res_pre.json()

    assert pre_data["upload_token"].startswith("upl_")
    assert pre_data["predicted_subject_id"] == "sub_bio"
    assert "Biologie Pflanzenzelle Uebung" in pre_data["predicted_title"]
    assert pre_data["predicted_kind"] == "Arbeitsblatt"

    upload_token = pre_data["upload_token"]

    # Thema dynamisch über die Taxonomie-API ermitteln
    topics_res = client.get("/api/v1/taxonomy/topics?subject_id=sub_bio")
    assert topics_res.status_code == 200
    bio_topics = topics_res.json()
    assert len(bio_topics) > 0
    topic_id = bio_topics[0]["id"]

    # 2. Stufe 2: Human-in-the-Loop Bestätigung
    confirm_payload = {
        "upload_token": upload_token,
        "subject_id": "sub_bio",
        "topic_id": topic_id,
        "title": "Aufbau der Pflanzenzelle",
        "kind": "Arbeitsblatt",
        "summary": "Wichtiges Merkblatt für die Klausur"
    }
    res_confirm = client.post("/api/v1/materials/confirm", json=confirm_payload)
    assert res_confirm.status_code == 201
    mat = res_confirm.json()

    assert mat["id"].startswith("mat_")
    assert mat["title"] == "Aufbau der Pflanzenzelle"
    assert mat["subject_name"] == "Biologie"
    assert mat["topic_name"] == bio_topics[0]["name"]
    assert mat["kind"] == "Arbeitsblatt"

    mat_id = mat["id"]

    # 3. Liste abrufen (gefiltert nach Biologie)
    res_list = client.get(f"/api/v1/materials?subject_id=sub_bio")
    assert res_list.status_code == 200
    materials = res_list.json()
    assert any(m["id"] == mat_id for m in materials)

    # 4. Detail abrufen
    res_detail = client.get(f"/api/v1/materials/{mat_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["title"] == "Aufbau der Pflanzenzelle"

    # 5. Datei abrufen
    res_file = client.get(f"/api/v1/materials/{mat_id}/file")
    assert res_file.status_code == 200
    assert len(res_file.content) == len(pdf_bytes)

    # 6. Löschen
    res_del = client.delete(f"/api/v1/materials/{mat_id}")
    assert res_del.status_code == 204

    # 7. Gelöscht verifizieren
    res_gone = client.get(f"/api/v1/materials/{mat_id}")
    assert res_gone.status_code == 404

def test_confirm_invalid_token_fails(client):
    payload = {
        "upload_token": "upl_ungueltig_12345",
        "subject_id": "sub_bio",
        "title": "Test Material"
    }
    res = client.post("/api/v1/materials/confirm", json=payload)
    assert res.status_code == 400
    assert "nicht gefunden" in res.json()["detail"].lower()

def test_confirm_invalid_subject_fails(client):
    payload = {
        "upload_token": "upl_irgendein_token",
        "subject_id": "sub_unbekannt_999",
        "title": "Test Material"
    }
    res = client.post("/api/v1/materials/confirm", json=payload)
    assert res.status_code == 404
    assert "schulfach" in res.json()["detail"].lower()

def test_confirm_invalid_topic_fails(client):
    payload = {
        "upload_token": "upl_irgendein_token",
        "subject_id": "sub_bio",
        "topic_id": "top_ungueltig_999",
        "title": "Test Material"
    }
    res = client.post("/api/v1/materials/confirm", json=payload)
    assert res.status_code == 404
    assert "thema" in res.json()["detail"].lower()
