import json
from unittest.mock import MagicMock, patch

import pypdf

from backend.app.services.llm import chat_params, supports_temperature
from backend.app.prompts.book_toc import BOOK_TOC_SYSTEM_PROMPT
from backend.app.prompts.tutor import EXERCISE_SYSTEM_PROMPT, CLOZE_EVALUATION_SYSTEM_PROMPT, TUTOR_SYSTEM_PROMPT


def _mock_openai(content: dict):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(content)
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    return mock_client


def _blank_pdf(path, pages):
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_chat_params_drops_temperature_for_reasoning_models():
    assert supports_temperature("gpt-4o-mini") is True
    assert supports_temperature("gpt-6-luna") is False
    assert supports_temperature("o3") is False

    assert chat_params("gpt-4o-mini", temperature=0.1, messages=[])["temperature"] == 0.1
    params = chat_params("gpt-6-luna", temperature=0.1, messages=[])
    assert "temperature" not in params
    assert params["model"] == "gpt-6-luna"


def test_document_analysis_uses_analysis_model_and_page_count(db_session, tmp_path):
    pdf = _blank_pdf(tmp_path / "lehrbuch.pdf", 42)
    mock_client = _mock_openai({"fach": "Mathematik", "dokumentart": "Buch"})

    with patch("backend.app.services.document_analyzer.OPENAI_API_KEY", "sk-fake"), \
         patch("backend.app.services.document_analyzer.OPENAI_ANALYSIS_MODEL", "gpt-4o-mini"), \
         patch("openai.OpenAI", return_value=mock_client):
        from backend.app.services.document_analyzer import analyze_document_content
        analyze_document_content(db_session, pdf, extracted_text="Mathematik " * 60)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert "Seitenzahl des Dokuments: 42" in kwargs["messages"][1]["content"]


def test_book_toc_uses_main_model_and_pdf_page_markers(tmp_path):
    pdf = tmp_path / "buch.pdf"
    _blank_pdf(pdf, 30)
    mock_client = _mock_openai({"chapters": [{"unit_number": 1, "title": "Kapitel 1", "start_pdf_page": 5, "end_pdf_page": 30}]})
    toc_text = "Inhaltsverzeichnis Kapitel 1 Zahlen " * 10

    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), \
         patch("backend.app.config.OPENAI_MODEL", "gpt-6-luna"), \
         patch("openai.OpenAI", return_value=mock_client), \
         patch.object(pypdf._page.PageObject, "extract_text", return_value=toc_text):
        from backend.app.services.book_segmentation import extract_chapters_with_ai
        chapters = extract_chapters_with_ai(pdf, 30, title_hint="Testbuch")

    assert chapters[0]["start_pdf_page"] == 5
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-6-luna"
    assert "temperature" not in kwargs
    user_text = kwargs["messages"][1]["content"]
    assert "--- Dokumentseite im PDF: Seite 1 ---" in user_text
    assert "--- Dokumentseite im PDF: Seite 20 ---" in user_text
    assert "Dokumentseite im PDF" in BOOK_TOC_SYSTEM_PROMPT


def test_prompts_match_code_expectations():
    # Lückentexte liefern Alternativen, Schwierigkeitsgrade sind definiert
    assert '"alternatives"' in EXERCISE_SYSTEM_PROMPT
    for level in ("leicht", "mittel", "schwer"):
        assert f'"{level}"' in EXERCISE_SYSTEM_PROMPT
    # Handschrift wird wörtlich übernommen, kein widersprüchliches "STRENG"
    assert "NIEMALS in Richtung des erwarteten Begriffs" in CLOZE_EVALUATION_SYSTEM_PROMPT
    assert "großzügig" not in CLOZE_EVALUATION_SYSTEM_PROMPT
    # Tutor behauptet keinen Vollzugriff auf Unterlagen
    assert "VOLLEN Zugriff" not in TUTOR_SYSTEM_PROMPT


def test_tutor_highlight_box_is_clamped_to_image():
    mock_client = _mock_openai({
        "tutor_speech": "Schau dir das Vorzeichen an.",
        "highlight_box": {"x_pct": 90, "y_pct": -5, "w_pct": 40, "h_pct": 150}
    })
    with patch("backend.app.services.tutor_service.OPENAI_API_KEY", "sk-fake"), \
         patch("openai.OpenAI", return_value=mock_client):
        from backend.app.services.tutor_service import analyze_whiteboard_and_speak
        res = analyze_whiteboard_and_speak("data:image/jpeg;base64,AAAA", audio_enabled=False)

    coords = res["actions"][0]["coords"]
    assert coords == {"x_pct": 90.0, "y_pct": 0.0, "w_pct": 10.0, "h_pct": 100.0}
