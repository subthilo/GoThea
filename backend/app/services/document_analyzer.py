import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_ANALYSIS_MODEL
from backend.app.services import llm
from backend.app.services.document_kinds import dossier_for_kind, normalize_kind
from backend.app.services.topic_catalog import build_catalog_text, resolve_topic
from backend.app.models import Subject, Topic
from backend.app.services.material_ingestion import (
    prepare_image_base64_for_vision,
    render_material_page_as_image,
)
from backend.app.services.document_heuristics import (
    SUBJECT_NAME_TO_ID,
    clean_title_from_filename,
    detect_kind_from_filename_and_text,
    predict_subject_and_topic,
    sanitize_filename_part,
)
from backend.app.services.timetable_analyzer import (
    sync_subjects_to_database,
    heuristic_timetable_analyzer,
    get_or_create_organisation_subject,
    is_timetable_document,
    ORGANISATION_DOSSIER_TITLE,
)

logger = logging.getLogger(__name__)

@dataclass
class DocumentAnalysisResult:
    subject_id: str
    subject_name: str
    topic_id: Optional[str]
    topic_name: Optional[str]
    kind: str
    title: str
    normalized_filename: str
    dossier_title: str
    dossier_kind: str
    summary: Optional[str] = None
    solution_pages: List[int] = field(default_factory=list)
    worked_on_paper: Optional[bool] = None
    teacher_graded: Optional[bool] = None


from backend.app.prompts.document_analysis import (
    DOCUMENT_ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_prompt,
)


def get_pdf_page_count(file_path: Path, mime_type: str) -> Optional[int]:
    if mime_type != "application/pdf":
        return None
    try:
        import pypdf
        return len(pypdf.PdfReader(str(file_path)).pages)
    except Exception as e:
        logger.warning(f"Seitenzahl von {file_path.name} nicht lesbar: {e}")
        return None


# Kleine Dokumente vollständig ansehen (Lösungsseiten, Antworten auf Folgeseiten),
# bei größeren reichen Cover, Impressum und Inhaltsverzeichnis
ANALYZE_ALL_PAGES_UP_TO = 6
ANALYZE_FIRST_PAGES_OF_LARGE_DOCS = 3


def parse_page_list(value: Any) -> List[int]:
    """KI-Angabe der Lösungsseiten robust in eine sortierte Liste von Seitenzahlen wandeln."""
    if not isinstance(value, list):
        return []
    pages = set()
    for v in value:
        try:
            pages.add(int(v))
        except (TypeError, ValueError):
            continue
    return sorted(p for p in pages if p > 0)


def _as_bool(value: Any) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def pages_to_analyze(page_count: Optional[int], mime_type: str) -> List[int]:
    if mime_type != "application/pdf" or not page_count:
        return [1]
    if page_count <= ANALYZE_ALL_PAGES_UP_TO:
        return list(range(1, page_count + 1))
    return list(range(1, ANALYZE_FIRST_PAGES_OF_LARGE_DOCS + 1))


def query_openai_analyzer(
    file_path: Path,
    extracted_text: str,
    mime_type: str,
    model_name: str,
    original_filename: Optional[str] = None,
    topic_catalog: str = ""
) -> Optional[Dict[str, Any]]:
    """Fragt OpenAI nach Fach, Thema, Dokumentart, Titel und Zusammenfassung."""
    try:
        effective_name = original_filename or file_path.name
        page_count = get_pdf_page_count(file_path, mime_type)
        clean_text = (extracted_text or "").strip()

        # Seitenbilder sind immer dabei: Handschrift, Korrekturen und Lösungsseiten sieht man nur dort
        user_content = [{"type": "text", "text": build_analysis_user_prompt(effective_name, clean_text, page_count, topic_catalog)}]
        for page_num in pages_to_analyze(page_count, mime_type):
            try:
                img_bytes, img_mime = render_material_page_as_image(str(file_path), mime_type, page_num=page_num)
            except Exception as e:
                logger.warning(f"Analyse ohne Bild von Seite {page_num} ({file_path.name}): {e}")
                continue
            user_content.append({"type": "text", "text": f"--- Seite {page_num} ---"})
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{prepare_image_base64_for_vision(img_bytes, img_mime)}", "detail": "high"}
            })
        messages = [
            {"role": "system", "content": DOCUMENT_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        reply = llm.chat(messages, purpose="Dokumentanalyse", model=model_name, temperature=0.1, json_mode=True)
        parsed = reply.json()
        if reply.prompt_tokens is not None:
            parsed["_usage"] = {"prompt_tokens": reply.prompt_tokens, "completion_tokens": reply.completion_tokens}
        return parsed
    except Exception as e:
        logger.warning(f"KI-Inhaltsanalyse fehlgeschlagen ({e}), verwende Heuristik-Fallback.")
        return None



def analyze_document_content(
    db: Session,
    file_path: Path,
    extracted_text: str = "",
    mime_type: str = "application/pdf",
    original_filename: Optional[str] = None
) -> DocumentAnalysisResult:
    """
    Zentrale Analysefunktion für Dokumente aus der Inbox oder dem Upload.
    Verwendet KI-Inhaltsanalyse falls ein OpenAI-Schlüssel konfiguriert ist,
    sonst robusten Heuristik-Fallback.
    """
    effective_name = original_filename or file_path.name
    raw_ai_data = None
    if llm.is_available():
        raw_ai_data = query_openai_analyzer(
            file_path=file_path,
            extracted_text=extracted_text,
            mime_type=mime_type,
            model_name=OPENAI_ANALYSIS_MODEL,
            original_filename=effective_name,
            topic_catalog=build_catalog_text(db)
        )

    if raw_ai_data and isinstance(raw_ai_data, dict):
        return _result_from_ai(db, raw_ai_data, file_path, effective_name, extracted_text)
    return _result_from_heuristics(db, file_path, effective_name, extracted_text)


def _extension(effective_name: str, file_path: Path) -> str:
    return Path(effective_name).suffix.lower() or file_path.suffix.lower() or ".pdf"


def _timetable_result(
    db: Session,
    title: str,
    recognised_subjects: List[str],
    ext: str,
    normalized_filename: Optional[str] = None,
    summary: Optional[str] = None,
) -> DocumentAnalysisResult:
    """Stundenpläne gehören immer zum Fach Organisation; erkannte Fächer werden angelegt."""
    if recognised_subjects:
        sync_subjects_to_database(db, recognised_subjects)
    orga_sub = get_or_create_organisation_subject(db)
    if "stundenplan" not in title.lower():
        title = f"Stundenplan: {title}"
    return DocumentAnalysisResult(
        subject_id=orga_sub.id,
        subject_name=orga_sub.name,
        topic_id=None,
        topic_name="Stundenplan",
        kind="Stundenplan",
        title=title,
        normalized_filename=normalized_filename or f"Organisation_Stundenplan_{sanitize_filename_part(title)}{ext}",
        dossier_title=ORGANISATION_DOSSIER_TITLE,
        dossier_kind="organisation",
        summary=summary or f"Stundenplan mit {len(recognised_subjects)} erkannten Schulfächern.",
    )


def _subject_from_ai_name(db: Session, fach: str, effective_name: str, extracted_text: str) -> Optional[Subject]:
    """Fach zum Namen, den die KI nennt: Fachname in der DB, dann Kurz-/Altnamen, dann Heuristik."""
    fach = fach.strip().lower()
    for s in db.query(Subject).all():
        if s.name.lower() in fach or (fach and fach in s.name.lower()):
            return s
    subject_id = SUBJECT_NAME_TO_ID.get(fach) or next(
        (sid for key, sid in SUBJECT_NAME_TO_ID.items() if key in fach), None)
    subject = db.query(Subject).filter_by(id=subject_id).first() if subject_id else None
    if not subject:
        pred_sub_id, _ = predict_subject_and_topic(db, effective_name, extracted_text)
        subject = db.query(Subject).filter_by(id=pred_sub_id).first()
    return subject or db.query(Subject).first()


def _result_from_ai(
    db: Session,
    raw_ai_data: Dict[str, Any],
    file_path: Path,
    effective_name: str,
    extracted_text: str,
) -> DocumentAnalysisResult:
    ext = _extension(effective_name, file_path)
    title = raw_ai_data.get("inhaltlicher_titel") or clean_title_from_filename(effective_name)

    if is_timetable_document(effective_name, extracted_text, raw_ai_data):
        recognised = raw_ai_data.get("erkannte_faecher") or \
            heuristic_timetable_analyzer(file_path, extracted_text).get("erkannte_faecher", [])
        return _timetable_result(db, title, recognised, ext,
                                 normalized_filename=raw_ai_data.get("normierter_dateiname"),
                                 summary=raw_ai_data.get("zusammenfassung"))

    subject = _subject_from_ai_name(db, raw_ai_data.get("fach") or "", effective_name, extracted_text)
    subject_id = subject.id if subject else "sub_math"

    # Thema aus dem Katalog übernehmen oder (mittlere Ebene) neu anlegen
    oberthema = (raw_ai_data.get("oberthema") or "").strip()
    topic = resolve_topic(db, subject_id, oberthema, raw_ai_data.get("themenbereich"))
    topic_id = topic.id if topic else None
    topic_name = topic.name if topic else (oberthema or None)

    kind = normalize_kind(raw_ai_data.get("dokumentart"))
    if kind == "Stundenplan" and raw_ai_data.get("erkannte_faecher"):
        sync_subjects_to_database(db, raw_ai_data["erkannte_faecher"])

    norm_name = raw_ai_data.get("normierter_dateiname") or ""
    if not norm_name.endswith(".pdf"):
        norm_name = "_".join(sanitize_filename_part(part) for part in (
            subject.name if subject else "Fach", topic_name or "Allgemein", kind, title)) + ext

    dossier_title, dossier_kind = dossier_for_kind(kind, title, topic_name or subject.name, subject.name)
    return DocumentAnalysisResult(
        subject_id=subject_id,
        subject_name=subject.name if subject else "Allgemein",
        topic_id=topic_id,
        topic_name=topic_name,
        kind=kind,
        title=title,
        normalized_filename=norm_name,
        dossier_title=dossier_title,
        dossier_kind=dossier_kind,
        summary=raw_ai_data.get("zusammenfassung"),
        solution_pages=parse_page_list(raw_ai_data.get("loesungsseiten")),
        worked_on_paper=_as_bool(raw_ai_data.get("von_schuelerin_bearbeitet")),
        teacher_graded=_as_bool(raw_ai_data.get("von_lehrkraft_bewertet")),
    )


def _result_from_heuristics(
    db: Session,
    file_path: Path,
    effective_name: str,
    extracted_text: str,
) -> DocumentAnalysisResult:
    ext = _extension(effective_name, file_path)
    if is_timetable_document(effective_name, extracted_text):
        tt_info = heuristic_timetable_analyzer(file_path, extracted_text)
        title = tt_info.get("titel") or clean_title_from_filename(effective_name)
        return _timetable_result(db, title, tt_info.get("erkannte_faecher", []), ext)

    subject_id, topic_id = predict_subject_and_topic(db, effective_name, extracted_text)
    subject = db.query(Subject).filter_by(id=subject_id).first()
    topic = db.query(Topic).filter_by(id=topic_id).first() if topic_id else None

    kind = normalize_kind(detect_kind_from_filename_and_text(effective_name, extracted_text))
    title = clean_title_from_filename(effective_name)
    norm_name = f"{sanitize_filename_part(subject.name if subject else 'Fach')}_{sanitize_filename_part(title)}{ext}"

    subject_label = subject.name if subject else "Schule"
    dossier_title, dossier_kind = dossier_for_kind(kind, title, topic.name if topic else subject_label, subject_label)
    return DocumentAnalysisResult(
        subject_id=subject_id,
        subject_name=subject.name if subject else "Allgemein",
        topic_id=topic_id,
        topic_name=topic.name if topic else None,
        kind=kind,
        title=title,
        normalized_filename=norm_name,
        dossier_title=dossier_title,
        dossier_kind=dossier_kind,
        summary=f"{kind} zu {subject.name if subject else 'Lernstoff'}"
    )
