from pathlib import Path
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.services.timetable_analyzer import (
    match_subject_to_canonical,
    sync_subjects_to_database,
    heuristic_timetable_analyzer,
    process_and_import_timetable
)

def test_match_subject_to_canonical():
    assert match_subject_to_canonical("ch")["name"] == "Chemie"
    assert match_subject_to_canonical("chemie")["name"] == "Chemie"
    assert match_subject_to_canonical("WAT")["name"] == "WAT / Wirtschaft"
    assert match_subject_to_canonical("ku")["name"] == "Kunst"
    assert match_subject_to_canonical("kunst")["name"] == "Kunst"
    assert match_subject_to_canonical("PB")["name"] == "Politische Bildung"
    assert match_subject_to_canonical("ler")["name"] == "LER / Ethik"
    assert match_subject_to_canonical("sp")["name"] == "Sport"
    assert match_subject_to_canonical("*Sp")["name"] == "Sport"
    assert match_subject_to_canonical("En(B)")["name"] == "Englisch"
    assert match_subject_to_canonical("D DÜCK 201")["name"] == "Deutsch"
    assert match_subject_to_canonical("Fr PAYS 203")["name"] == "Französisch"
    assert match_subject_to_canonical("Rel SCHN 302")["name"] == "Religion"
    assert match_subject_to_canonical("*GT-Mittag") is None
    assert match_subject_to_canonical("inf")["name"] == "Informatik"
    assert match_subject_to_canonical("ast")["name"] == "Astronomie"

def test_sync_subjects_adds_new_subjects_and_topics(db_session):
    # Vorher: nur Initial-Subjects
    assert db_session.query(Subject).filter_by(name="Chemie").first() is None
    assert db_session.query(Subject).filter_by(name="WAT / Wirtschaft").first() is None

    candidates = ["Chemie", "WAT", "Sport", "Mathematik"]
    created, existing = sync_subjects_to_database(db_session, candidates)

    # Mathematik existierte schon
    assert any(s.name == "Mathematik" for s in existing)

    # Chemie, WAT und Sport wurden neu angelegt
    assert any(s.name == "Chemie" for s in created)
    assert any(s.name == "WAT / Wirtschaft" for s in created)
    assert any(s.name == "Sport" for s in created)

    # Prüfen, dass Themen für Chemie angelegt wurden
    chem_sub = db_session.query(Subject).filter_by(name="Chemie").first()
    assert chem_sub is not None
    assert chem_sub.icon == "🧪"
    topics = db_session.query(Topic).filter_by(subject_id=chem_sub.id).all()
    assert len(topics) >= 2

def test_heuristic_timetable_parsing():
    sample_text = """
    Stundenplan Klasse 7a - Schuljahr 2026/27
    Montag: Ma, De, En, Bio, Ch
    Dienstag: Ph, Ku, Mu, Sp
    Mittwoch: Geo, Ge, PB, WAT
    Donnerstag: LER, Ma, De, En
    Freitag: Ch, Ph, Sp, Inf
    """
    res = heuristic_timetable_analyzer(Path("stundenplan.pdf"), sample_text)
    assert res["ist_stundenplan"] is True
    assert "Klasse 7" in res["klasse"]
    assert "Chemie" in res["erkannte_faecher"]
    assert "WAT / Wirtschaft" in res["erkannte_faecher"]
    assert "Sport" in res["erkannte_faecher"]
    assert "Politische Bildung" in res["erkannte_faecher"]

def test_process_and_import_timetable_workflow(db_session, tmp_path):
    pdf = tmp_path / "stundenplan_klasse_7a.pdf"
    # PDF mit Text erzeugen
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Stundenplan Klasse 7a\nMo: Ma, De, En, Ch, WAT\nDi: Ku, Mu, Sp, PB")
    doc.save(str(pdf))
    doc.close()

    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()

    res = process_and_import_timetable(
        db=db_session,
        file_path=pdf,
        materials_dir=materials_dir
    )

    assert "Stundenplan" in res.material_title
    assert len(res.created_subjects) >= 1
    # Prüfen, dass Material und Dossier existieren
    mat = db_session.query(Material).filter_by(id=res.material_id).first()
    assert mat is not None
    assert mat.kind == "Stundenplan"
    assert (materials_dir / f"{mat.id}.pdf").exists()

    dossier = db_session.query(Dossier).filter_by(id=res.dossier_id).first()
    assert dossier is not None
    assert dossier.kind == "organisation"
    assert "Stundenplan" in dossier.title

def test_import_timetable_api_endpoint(client, tmp_path):
    import fitz
    pdf_path = tmp_path / "stundenplan_7a.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Stundenplan 7a\nMontag: Mathe, Deutsch, Englisch, Chemie, Sport, Kunst")
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/v1/taxonomy/import-timetable",
            files={"file": ("stundenplan_7a.pdf", f, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Stundenplan" in data["material_title"]
    assert any(s["name"] == "Chemie" for s in data["created_subjects"] + data["existing_subjects"])

def test_get_or_create_organisation_subject(db_session):
    from backend.app.services.timetable_analyzer import get_or_create_organisation_subject
    sub = get_or_create_organisation_subject(db_session)
    assert sub.id == "sub_orga"
    assert sub.name == "Organisation"
    assert sub.icon == "📅"

    # Zweiter Aufruf liefert dasselbe Subjekt
    sub2 = get_or_create_organisation_subject(db_session)
    assert sub2.id == sub.id

def test_is_timetable_document_detection():
    from backend.app.services.timetable_analyzer import is_timetable_document

    assert is_timetable_document("Stundenplan_7D.pdf", "") is True
    assert is_timetable_document("wochenplan.pdf", "") is True
    assert is_timetable_document("thea_timetable.jpg", "") is True
    assert is_timetable_document("scan.pdf", "Montag Dienstag Mittwoch Donnerstag Freitag Stunde A-Woche B-Woche") is True
    assert is_timetable_document("scan.pdf", "irgendein arbeitsblatt", {"dokumentart": "Stundenplan"}) is True
    assert is_timetable_document("scan.pdf", "irgendein arbeitsblatt", {"fach": "Organisation"}) is True
    assert is_timetable_document("mathe_aufgaben.pdf", "Berechne die Nullstellen der Parabel") is False

def test_timetable_auto_routing_on_manual_upload(client, db_session, tmp_path):
    import fitz
    from backend.app.services.seeder import seed_database
    seed_database(db_session)

    pdf_path = tmp_path / "stundenplan_thea_7d.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Stundenplan Thea 7D\nMo: Französisch, Mathe\nDi: Deutsch, Englisch\nMi: Chemie, Kunst\nDo: Sport, Biologie\nFr: Geschichte")
    doc.save(str(pdf_path))
    doc.close()

    # 1. Pre-Analyze via Upload
    with open(pdf_path, "rb") as f:
        pre_res = client.post(
            "/api/v1/materials/pre-analyze",
            files={"file": ("stundenplan_thea_7d.pdf", f, "application/pdf")}
        )
    assert pre_res.status_code == 200
    pre_data = pre_res.json()
    assert pre_data["predicted_kind"] == "Stundenplan"
    assert pre_data["predicted_subject_id"] == "sub_orga"

    # 2. Confirm Upload — selbst wenn fälschlicherweise Französisch übergeben wird:
    confirm_payload = {
        "upload_token": pre_data["upload_token"],
        "subject_id": "sub_franzoesisch",  # Nutzer oder alter State wählte versehentlich Französisch
        "title": "Stundenplan Thea - Klasse 7D",
        "kind": "Stundenplan"
    }
    confirm_res = client.post("/api/v1/materials/confirm", json=confirm_payload)
    assert confirm_res.status_code == 201
    c_data = confirm_res.json()

    # Muss zwingend Organisation (sub_orga) sein!
    assert c_data["subject_id"] == "sub_orga"
    assert c_data["subject_name"] == "Organisation"
    assert c_data["subject_icon"] == "📅"
    assert c_data["kind"] == "Stundenplan"
    assert c_data["dossier_title"] == "Stundenplan & Organisation"

def test_seeder_migration_fixes_mistaken_timetable_subject(db_session):
    from backend.app.services.seeder import seed_database
    # Erstelle ein Material, das wie im Screenshot fälschlicherweise Französisch zugeordnet war
    sub_fr = Subject(id="sub_franzoesisch", name="Französisch", icon="🇫🇷", color_code="#2563eb", min_grade=7, max_grade=13)
    db_session.add(sub_fr)
    db_session.flush()

    wrong_mat = Material(
        id="mat_test_wrong_sub",
        user_id="usr_thea",
        subject_id="sub_franzoesisch",
        title="Stundenplan Thea - Klasse 7D (A-Woche)",
        kind="Stundenplan",
        filename="mat_test_wrong_sub.pdf",
        file_path="/tmp/test.pdf",
        file_size=1000,
        mime_type="application/pdf",
        page_count=1
    )
    db_session.add(wrong_mat)
    db_session.commit()

    # Seeder laufen lassen (wird beim App-Start aufgerufen)
    seed_database(db_session)

    # Prüfen, dass das Material automatisch zu sub_orga migriert wurde
    migrated_mat = db_session.query(Material).filter_by(id="mat_test_wrong_sub").first()
    assert migrated_mat.subject_id == "sub_orga"
    assert migrated_mat.dossier is not None
    assert migrated_mat.dossier.subject_id == "sub_orga"
    assert migrated_mat.dossier.title == "Stundenplan & Organisation"
