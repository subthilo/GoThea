import io
from pypdf import PdfWriter

def test_annotation_lifecycle(client):
    # 1. Dummy-Material anlegen
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    files = {"file": ("notizen_test.pdf", buf.getvalue(), "application/pdf")}
    res_pre = client.post("/api/v1/materials/pre-analyze", files=files)
    assert res_pre.status_code == 200
    token = res_pre.json()["upload_token"]

    confirm_res = client.post("/api/v1/materials/confirm", json={
        "upload_token": token,
        "subject_id": "sub_math",
        "title": "Übungsblatt Notizen",
        "kind": "Arbeitsblatt"
    })
    assert confirm_res.status_code == 201
    mat_id = confirm_res.json()["id"]

    # 2. Anfangs keine Annotationen vorhanden
    get_res = client.get(f"/api/v1/materials/{mat_id}/pages/1/annotations")
    assert get_res.status_code == 200
    assert get_res.json()["strokes"] == []

    # 3. Handschriftliche Striche speichern
    sample_strokes = [
        {
            "tool": "pen",
            "color": "#3b82f6",
            "size": 3,
            "points": [[10, 20, 0.5], [15, 25, 0.8], [20, 30, 0.6]]
        },
        {
            "tool": "highlighter",
            "color": "#eab308",
            "size": 18,
            "points": [[50, 100, 1.0], [150, 100, 1.0]]
        }
    ]
    put_res = client.put(f"/api/v1/materials/{mat_id}/pages/1/annotations", json={"strokes": sample_strokes})
    assert put_res.status_code == 200
    assert len(put_res.json()["strokes"]) == 2

    # 4. Abrufen und überprüfen
    get_res2 = client.get(f"/api/v1/materials/{mat_id}/pages/1/annotations")
    assert get_res2.status_code == 200
    strokes_loaded = get_res2.json()["strokes"]
    assert len(strokes_loaded) == 2
    assert strokes_loaded[0]["tool"] == "pen"
    assert strokes_loaded[1]["tool"] == "highlighter"

    # 4b. Speichern mit strokes_json
    import json
    put_res_json = client.put(
        f"/api/v1/materials/{mat_id}/pages/1/annotations",
        json={"strokes_json": json.dumps(sample_strokes)}
    )
    assert put_res_json.status_code == 200
    assert len(put_res_json.json()["strokes"]) == 2

    # 5. Löschen
    del_res = client.delete(f"/api/v1/materials/{mat_id}/pages/1/annotations")
    assert del_res.status_code == 200

    # 6. Nach Löschen wieder leer
    get_res3 = client.get(f"/api/v1/materials/{mat_id}/pages/1/annotations")
    assert get_res3.status_code == 200
    assert get_res3.json()["strokes"] == []


def test_annotation_multipage_isolation_and_edge_cases(client):
    # 1. 2-seitiges PDF erzeugen
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    files = {"file": ("multipage_note.pdf", buf.getvalue(), "application/pdf")}
    res_pre = client.post("/api/v1/materials/pre-analyze", files=files)
    token = res_pre.json()["upload_token"]

    confirm_res = client.post("/api/v1/materials/confirm", json={
        "upload_token": token,
        "subject_id": "sub_math",
        "title": "Zweiseitiges Arbeitsblatt",
        "kind": "Arbeitsblatt"
    })
    mat_id = confirm_res.json()["id"]

    # 2. Seite 1 annotieren
    stroke_p1 = [{"tool": "pen", "color": "#2563eb", "points": [{"x": 0.1, "y": 0.2}]}]
    client.put(f"/api/v1/materials/{mat_id}/pages/1/annotations", json={"strokes": stroke_p1})

    # 3. Seite 2 annotieren
    stroke_p2 = [{"tool": "highlighter", "color": "#facc15", "points": [{"x": 0.5, "y": 0.5}]}]
    client.put(f"/api/v1/materials/{mat_id}/pages/2/annotations", json={"strokes": stroke_p2})

    # 4. Isolation verifizieren: Seite 1 hat nur stroke_p1, Seite 2 nur stroke_p2
    res_p1 = client.get(f"/api/v1/materials/{mat_id}/pages/1/annotations").json()
    res_p2 = client.get(f"/api/v1/materials/{mat_id}/pages/2/annotations").json()
    assert len(res_p1["strokes"]) == 1
    assert res_p1["strokes"][0]["tool"] == "pen"
    assert len(res_p2["strokes"]) == 1
    assert res_p2["strokes"][0]["tool"] == "highlighter"

    # 5. Nicht existentes Material -> 404
    res_404 = client.get("/api/v1/materials/mat_non_existent_999/pages/1/annotations")
    assert res_404.status_code == 404

