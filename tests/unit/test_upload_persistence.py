import os
import time
from unittest.mock import patch

from backend.app.models.taxonomy import Topic


def test_ai_created_topic_survives_end_of_pre_analysis_request(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.database import Base
    from backend.app.services.seeder import seed_database
    from backend.app.services.document_analyzer import analyze_document_content

    # Eigene Datenbank: Voranalyse und Bestätigung laufen in getrennten Sessions (= Requests)
    engine = create_engine(f"sqlite:///{tmp_path / 'requests.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as setup:
        seed_database(setup)

    pdf = tmp_path / "blatt.pdf"
    pdf.write_bytes(b"%PDF-dummy")
    ai_data = {"fach": "Biologie", "oberthema": "Verhütung und Familienplanung (Testthema)",
               "dokumentart": "Arbeitsblatt", "inhaltlicher_titel": "Verhütungsmittel"}

    pre_analysis = Session()
    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), \
         patch("backend.app.services.document_analyzer.query_openai_analyzer", return_value=ai_data):
        result = analyze_document_content(pre_analysis, pdf, "", "application/pdf")
    pre_analysis.close()  # Request-Ende ohne weiteres commit

    with Session() as confirm:
        assert result.topic_id is not None
        assert confirm.query(Topic).filter_by(id=result.topic_id).first() is not None
    engine.dispose()


def test_cleanup_temp_uploads_removes_only_old_files(tmp_path, monkeypatch):
    from backend.app.services import material_ingestion as mi
    monkeypatch.setattr(mi, "TEMP_UPLOADS_DIR", tmp_path)
    old = tmp_path / "upl_old.pdf"
    fresh = tmp_path / "upl_fresh.pdf"
    other = tmp_path / "keep.txt"
    for f in (old, fresh, other):
        f.write_bytes(b"x")
    two_days_ago = time.time() - 48 * 3600
    os.utime(old, (two_days_ago, two_days_ago))
    os.utime(other, (two_days_ago, two_days_ago))

    assert mi.cleanup_temp_uploads() == 1
    assert not old.exists() and fresh.exists() and other.exists()
