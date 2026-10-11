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

    # 5b. Preview Bild abrufen
    res_prev = client.get(f"/api/v1/materials/{mat_id}/preview?page=1")
    assert res_prev.status_code == 200
    assert len(res_prev.content) > 0
    assert "image" in res_prev.headers["content-type"]

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

def test_confirm_material_with_dossier_and_pages(client, db_session):
    from backend.app.models.dossier import Dossier
    # 1. Dossier anlegen
    dossier = Dossier(
        id="dos_test_bio_hefter",
        user_id="usr_thea_default",
        subject_id="sub_bio",
        title="Biologie Hefter 1. Halbjahr",
        kind="hefter"
    )
    db_session.add(dossier)
    db_session.commit()

    # 2. Upload vorab analysieren
    pdf_bytes = create_sample_pdf_bytes("Biologie Kapitel 2 Zellteilung")
    files = {"file": ("kapitel_2.pdf", pdf_bytes, "application/pdf")}
    res_pre = client.post("/api/v1/materials/pre-analyze", files=files)
    assert res_pre.status_code == 200
    token = res_pre.json()["upload_token"]

    # 3. Mit dossier_id bestätigen
    confirm_payload = {
        "upload_token": token,
        "subject_id": "sub_bio",
        "dossier_id": "dos_test_bio_hefter",
        "dossier_order": 2,
        "title": "Kapitel 2: Zellteilung",
        "kind": "Hefter"
    }
    res_confirm = client.post("/api/v1/materials/confirm", json=confirm_payload)
    assert res_confirm.status_code == 201
    mat = res_confirm.json()
    assert mat["dossier_id"] == "dos_test_bio_hefter"
    assert mat["dossier_title"] == "Biologie Hefter 1. Halbjahr"

    # 4. Liste prüfen
    res_list = client.get("/api/v1/materials?subject_id=sub_bio")
    assert res_list.status_code == 200
    items = res_list.json()
    found = next((m for m in items if m["id"] == mat["id"]), None)
    assert found is not None
    assert found["dossier_title"] == "Biologie Hefter 1. Halbjahr"

def test_update_material_reassign_subject_and_metadata(client):
    # Material erstellen
    pdf_bytes = create_sample_pdf_bytes("Zellaufbau")
    res_pre = client.post("/api/v1/materials/pre-analyze", files={"file": ("blatt.pdf", pdf_bytes, "application/pdf")})
    token = res_pre.json()["upload_token"]

    res_conf = client.post("/api/v1/materials/confirm", json={
        "upload_token": token,
        "subject_id": "sub_bio",
        "title": "Zellbiologie",
        "kind": "Arbeitsblatt"
    })
    mat = res_conf.json()
    mat_id = mat["id"]
    assert mat["subject_id"] == "sub_bio"

    # Fächerwechsel von Biologie zu Geographie
    res_patch = client.patch(f"/api/v1/materials/{mat_id}", json={
        "subject_id": "sub_geo",
        "title": "Vegetationszonen der Erde",
        "kind": "Hefter"
    })
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["subject_id"] == "sub_geo"
    assert updated["subject_name"] == "Geografie"
    assert updated["title"] == "Vegetationszonen der Erde"
    assert updated["kind"] == "Hefter"

    # Verifizieren, dass das Material nun unter Geografie und nicht mehr unter Biologie gelistet ist
    geo_list = client.get("/api/v1/materials?subject_id=sub_geo").json()
    assert any(m["id"] == mat_id for m in geo_list)
    bio_list = client.get("/api/v1/materials?subject_id=sub_bio").json()
    assert not any(m["id"] == mat_id for m in bio_list)

def test_merge_materials_workflow(client):
    # Zwei Dokumente hochladen
    p1 = create_sample_pdf_bytes("Teil 1: Einführung")
    p2 = create_sample_pdf_bytes("Teil 2: Vertiefung")

    t1 = client.post("/api/v1/materials/pre-analyze", files={"file": ("teil1.pdf", p1, "application/pdf")}).json()["upload_token"]
    m1 = client.post("/api/v1/materials/confirm", json={"upload_token": t1, "subject_id": "sub_math", "title": "Teil 1", "kind": "Arbeitsblatt"}).json()

    t2 = client.post("/api/v1/materials/pre-analyze", files={"file": ("teil2.pdf", p2, "application/pdf")}).json()["upload_token"]
    m2 = client.post("/api/v1/materials/confirm", json={"upload_token": t2, "subject_id": "sub_math", "title": "Teil 2", "kind": "Arbeitsblatt"}).json()

    # Zusammenführen
    res_merge = client.post("/api/v1/materials/merge", json={
        "material_ids": [m1["id"], m2["id"]],
        "target_title": "Mathe Komplett: Teil 1 & 2",
        "target_subject_id": "sub_math",
        "delete_sources": True
    })
    assert res_merge.status_code == 201
    merged = res_merge.json()
    assert merged["title"] == "Mathe Komplett: Teil 1 & 2"
    assert merged["page_count"] == 2
    assert merged["subject_id"] == "sub_math"

    # Quelldokumente sollten gelöscht sein
    assert client.get(f"/api/v1/materials/{m1['id']}").status_code == 404
    assert client.get(f"/api/v1/materials/{m2['id']}").status_code == 404

def test_reorder_material_pages_workflow(client):
    # Dokument mit 3 Seiten erzeugen
    w = PdfWriter()
    w.add_blank_page(width=100, height=100) # Seite 1
    w.add_blank_page(width=200, height=200) # Seite 2
    w.add_blank_page(width=300, height=300) # Seite 3
    buf = io.BytesIO()
    w.write(buf)
    pdf_3p = buf.getvalue()

    tok = client.post("/api/v1/materials/pre-analyze", files={"file": ("drei_seiten.pdf", pdf_3p, "application/pdf")}).json()["upload_token"]
    mat = client.post("/api/v1/materials/confirm", json={"upload_token": tok, "subject_id": "sub_german", "title": "Gedichtsanalyse", "kind": "Arbeitsblatt"}).json()
    assert mat["page_count"] == 3

    # Reihenfolge auf [3, 1, 2] ändern
    res_reorder = client.post(f"/api/v1/materials/{mat['id']}/reorder-pages", json={"page_order": [3, 1, 2]})
    assert res_reorder.status_code == 200
    reordered = res_reorder.json()
    assert reordered["page_count"] == 3

    # Einzelne Seite verwerfen: Nur [2, 1] behalten (Seite 3 entfällt)
    res_drop = client.post(f"/api/v1/materials/{mat['id']}/reorder-pages", json={"page_order": [2, 1]})
    assert res_drop.status_code == 200
    dropped = res_drop.json()
    assert dropped["page_count"] == 2

