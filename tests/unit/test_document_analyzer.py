import json
from unittest.mock import MagicMock, patch
from backend.app.models.taxonomy import Topic
from backend.app.services.document_analyzer import (
    analyze_document_content,
    clean_title_from_filename,
    sanitize_filename_part
)

def test_clean_title_and_sanitize():
    assert clean_title_from_filename("mathe_blatt_1.pdf") == "Mathe Blatt 1"
    assert clean_title_from_filename("BS26NR1.pdf") == "Bs26nr1"
    assert sanitize_filename_part("Mathe & Geometrie: 7. Klasse!") == "Mathe_Geometrie_7_Klasse"

def test_heuristic_analysis_when_no_openai(db_session, tmp_path):
    pdf = tmp_path / "bio_pflanzenzelle_uebung.pdf"
    pdf.write_bytes(b"%PDF-dummy")

    result = analyze_document_content(
        db=db_session,
        file_path=pdf,
        extracted_text="Biologie Zellenlehre Pflanzenzelle Zellkern",
        mime_type="application/pdf"
    )

    assert result.subject_id == "sub_bio"
    assert "Pflanzenzelle" in result.title or "Bio" in result.title
    assert result.kind == "Arbeitsblatt"
    assert result.normalized_filename.endswith(".pdf")
    assert "Biologie" in result.normalized_filename or "Bio" in result.normalized_filename

def test_openai_analyzer_integration(db_session, tmp_path):
    pdf = tmp_path / "scan_xyz.pdf"
    pdf.write_bytes(b"%PDF-dummy")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "fach": "Mathematik",
        "oberthema": "Dreisatz und Prozentrechnung",
        "dokumentart": "Arbeitsblatt",
        "inhaltlicher_titel": "Dreisatz Berechnungen im Alltag",
        "normierter_dateiname": "Mathe_Dreisatz_Alltag.pdf",
        "zusammenfassung": "Übungen zum proportionalen Dreisatz an praktischen Beispielen."
    })
    mock_response.choices = [mock_choice]

    with patch("backend.app.services.document_analyzer.OPENAI_API_KEY", "sk-fakekey"):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            result = analyze_document_content(
                db=db_session,
                file_path=pdf,
                extracted_text="Dreisatz Berechnungen Text",
                mime_type="application/pdf"
            )

            assert result.subject_id == "sub_math"
            assert result.topic_name == "Dreisatz und Prozentrechnung"
            assert result.title == "Dreisatz Berechnungen im Alltag"
            assert result.normalized_filename == "Mathe_Dreisatz_Alltag.pdf"
            assert result.kind == "Arbeitsblatt"
            assert "Dreisatz" in result.dossier_title

            # Prüfen, dass neues Thema angelegt wurde
            new_top = db_session.query(Topic).filter_by(name="Dreisatz und Prozentrechnung").first()
            assert new_top is not None
            assert new_top.subject_id == "sub_math"
