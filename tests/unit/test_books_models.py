import pytest
from backend.app.models.material import Material
from backend.app.models.dossier import Dossier
from backend.app.models.taxonomy import Subject, Topic
from backend.app.services.book_seeder import seed_textbooks_if_empty

def test_seed_textbooks_if_empty_lifecycle(db_session):
    # Vorher: Kein Buch vorhanden
    assert db_session.query(Material).filter_by(kind="Buch").count() == 0

    # 1. Seeder ausführen
    book_id = seed_textbooks_if_empty(db_session, user_id="usr_thea")
    assert book_id is not None
    assert book_id == "mat_book_math_7"

    # Master-Material prüfen
    master = db_session.query(Material).filter_by(id=book_id).first()
    assert master is not None
    assert "Mathematik" in master.title
    assert master.page_count == 196
    assert master.kind == "Buch"
    assert master.parent_id is None

    # Dossier prüfen
    dossier = db_session.query(Dossier).filter_by(id="dos_math_book_7").first()
    assert dossier is not None
    assert dossier.kind == "lehrbuch"

    # Kinder / Kapitel prüfen
    children = db_session.query(Material).filter_by(parent_id=book_id).order_by(Material.dossier_order).all()
    assert len(children) == 11

    # Kapitel 8 (Pythagoras) verifizieren
    ch8 = next((c for c in children if "Pythagoras" in c.title or "Metrische Beziehungen" in c.title), None)
    assert ch8 is not None
    assert ch8.start_page == 152
    assert ch8.end_page == 173
    assert ch8.page_count == 22
    assert ch8.kind == "Buchauszug"
    assert ch8.parent.id == master.id

    # 2. Idempotenz: Zweiter Aufruf darf keine Duplikate anlegen
    second_id = seed_textbooks_if_empty(db_session, user_id="usr_thea")
    assert second_id == book_id
    assert db_session.query(Material).filter_by(kind="Buch").count() == 1
    assert db_session.query(Material).filter_by(parent_id=book_id).count() == 11
