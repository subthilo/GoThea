import re
import io
import json
import base64
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_API_KEY, OPENAI_ANALYSIS_MODEL
from backend.app.services.llm import chat_params
from backend.app.services.document_kinds import dossier_for_kind, normalize_kind
from backend.app.services.topic_catalog import build_catalog_text, resolve_topic
from backend.app.models import Subject, Topic
from backend.app.services.material_ingestion import (
    render_material_page_as_image,
    clean_title_from_filename,
    detect_kind_from_filename_and_text,
    SUBJECT_KEYWORDS,
)
from backend.app.services.timetable_analyzer import (
    sync_subjects_to_database,
    heuristic_timetable_analyzer,
    get_or_create_organisation_subject,
    is_timetable_document
)

def predict_subject_and_topic(
    db: Session,
    filename: str,
    text: str
) -> Tuple[str, Optional[str]]:
    """Heuristische Fach- und Themenprognose anhand von Dateinamen und extrahiertem Text."""
    corpus = f"{filename} {text}".lower()
    all_subjects = db.query(Subject).filter_by(is_active=True).all()
    subject_map = {s.id: s for s in all_subjects}

    best_subject_id = None
    best_score = 0

    for sub_id, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in corpus)
        if sub_id in subject_map and subject_map[sub_id].name.lower() in corpus:
            score += 3
        if score > best_score:
            best_score = score
            best_subject_id = sub_id

    if not best_subject_id and all_subjects:
        best_subject_id = all_subjects[0].id

    predicted_topic_id = None
    if best_subject_id:
        topics = db.query(Topic).filter_by(subject_id=best_subject_id).all()
        best_t_score = 0
        for top in topics:
            t_words = top.name.lower().split()
            t_score = sum(2 for w in t_words if len(w) > 3 and w in corpus)
            if t_score > best_t_score:
                best_t_score = t_score
                predicted_topic_id = top.id

    return best_subject_id or "sub_math", predicted_topic_id

SUBJECT_NAME_TO_ID: Dict[str, str] = {
    "mathematik": "sub_math",
    "mathe": "sub_math",
    "biologie": "sub_bio",
    "bio": "sub_bio",
    "deutsch": "sub_german",
    "german": "sub_german",
    "englisch": "sub_english",
    "english": "sub_english",
    "geschichte": "sub_history",
    "history": "sub_history",
    "geografie": "sub_geo",
    "geographie": "sub_geo",
    "erdkunde": "sub_geo",
    "geo": "sub_geo",
    "physik": "sub_physics",
    "physics": "sub_physics",
    "chemie": "sub_chemie",
    "informatik": "sub_informatik",
    "politische bildung": "sub_pb",
    "pb": "sub_pb",
    "kunst": "sub_kunst",
    "musik": "sub_musik",
    "sport": "sub_sport",
    "ler": "sub_ler",
    "wat": "sub_wat",
    "französisch": "sub_franzoesisch",
    "franzoesisch": "sub_franzoesisch",
    "spanisch": "sub_spanisch",
    "latein": "sub_latein",
    "russisch": "sub_russisch",
    "astronomie": "sub_astronomie",
    "organisation": "sub_orga",
    "stundenplan": "sub_orga",
    "stundenplan & organisation": "sub_orga",
}

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


def sanitize_filename_part(text: str) -> str:
    """Wandelt Umlaute und Sonderzeichen für saubere Dateinamen um."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    # Nur alphanumerische Zeichen und Unterstriche
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    return cleaned.strip("_")


def prepare_image_base64_for_vision(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Skaliert ein Bild auf max. 1600x1600 Pixel und liefert Base64-JPEG."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return base64.b64encode(image_bytes).decode("utf-8")


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
    except Exception:
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
    api_key: str,
    model_name: str,
    original_filename: Optional[str] = None,
    topic_catalog: str = ""
) -> Optional[Dict[str, Any]]:
    """Fragt OpenAI nach Fach, Thema, Dokumentart, Titel und Zusammenfassung."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        effective_name = original_filename or file_path.name
        page_count = get_pdf_page_count(file_path, mime_type)
        clean_text = (extracted_text or "").strip()

        # Seitenbilder sind immer dabei: Handschrift, Korrekturen und Lösungsseiten sieht man nur dort
        user_content = [{"type": "text", "text": build_analysis_user_prompt(effective_name, clean_text, page_count, topic_catalog)}]
        for page_num in pages_to_analyze(page_count, mime_type):
            try:
                img_bytes, img_mime = render_material_page_as_image(str(file_path), mime_type, page_num=page_num)
            except Exception:
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

        response = client.chat.completions.create(**chat_params(
            model_name,
            temperature=0.1,
            messages=messages,
            response_format={"type": "json_object"}
        ))

        parsed = json.loads(response.choices[0].message.content or "{}")
        usage = getattr(response, "usage", None)
        if usage is not None and isinstance(getattr(usage, "prompt_tokens", None), int):
            parsed["_usage"] = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}
        return parsed
    except Exception as e:
        print(f"Warnung: OpenAI Inhaltsanalyse fehlgeschlagen ({e}), verwende Heuristik-Fallback.")
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
    Verwendet KI-Inhaltsanalyse falls OPENAI_API_KEY konfiguriert ist,
    sonst robusten Heuristik-Fallback.
    """
    effective_name = original_filename or file_path.name
    raw_ai_data = None
    if OPENAI_API_KEY:
        raw_ai_data = query_openai_analyzer(
            file_path=file_path,
            extracted_text=extracted_text,
            mime_type=mime_type,
            api_key=OPENAI_API_KEY,
            model_name=OPENAI_ANALYSIS_MODEL,
            original_filename=effective_name,
            topic_catalog=build_catalog_text(db)
        )

    if raw_ai_data and isinstance(raw_ai_data, dict):
        # 0. Zuerst prüfen, ob es sich um einen Stundenplan handelt
        if is_timetable_document(effective_name, extracted_text, raw_ai_data):
            orga_sub = get_or_create_organisation_subject(db)
            kind = "Stundenplan"
            title = raw_ai_data.get("inhaltlicher_titel") or clean_title_from_filename(effective_name)
            if "stundenplan" not in title.lower():
                title = f"Stundenplan: {title}"

            erkannte = raw_ai_data.get("erkannte_faecher") or []
            if not erkannte:
                tt_info = heuristic_timetable_analyzer(file_path, extracted_text)
                erkannte = tt_info.get("erkannte_faecher", [])
            if erkannte:
                sync_subjects_to_database(db, erkannte)

            safe_title = sanitize_filename_part(title)
            ext = file_path.suffix.lower() or ".pdf"
            norm_name = raw_ai_data.get("normierter_dateiname") or f"Organisation_Stundenplan_{safe_title}{ext}"
            summary = raw_ai_data.get("zusammenfassung") or f"Stundenplan mit {len(erkannte)} erkannten Schulfächern."

            return DocumentAnalysisResult(
                subject_id=orga_sub.id,
                subject_name=orga_sub.name,
                topic_id=None,
                topic_name="Stundenplan",
                kind=kind,
                title=title,
                normalized_filename=norm_name,
                dossier_title="Stundenplan & Organisation",
                dossier_kind="organisation",
                summary=summary
            )


        # 1. Fach zuordnen
        fach_str = (raw_ai_data.get("fach") or "").strip().lower()
        subject = None
        # Direkt in DB nach Fachname suchen (z.B. "Mathematik", "Biologie", "Physik")
        for s in db.query(Subject).all():
            if s.name.lower() in fach_str or (fach_str and fach_str in s.name.lower()):
                subject = s
                break
        if not subject:
            subject_id = SUBJECT_NAME_TO_ID.get(fach_str)
            if not subject_id:
                for key, sid in SUBJECT_NAME_TO_ID.items():
                    if key in fach_str:
                        subject_id = sid
                        break
            if subject_id:
                subject = db.query(Subject).filter_by(id=subject_id).first()
        if not subject:
            # Fallback über Vorhersage
            pred_sub_id, _ = predict_subject_and_topic(db, effective_name, extracted_text)
            subject = db.query(Subject).filter_by(id=pred_sub_id).first()
        if not subject:
            subject = db.query(Subject).first()

        subject_id = subject.id if subject else "sub_math"

        # 2. Thema aus dem Katalog übernehmen oder (mittlere Ebene) neu anlegen
        oberthema = (raw_ai_data.get("oberthema") or "").strip()
        topic = resolve_topic(db, subject_id, oberthema, raw_ai_data.get("themenbereich"))

        topic_id = topic.id if topic else None
        topic_name = topic.name if topic else (oberthema or None)

        # 3. Dokumentart
        kind = normalize_kind(raw_ai_data.get("dokumentart"))

        # Falls Stundenplan: Fächer in DB synchronisieren
        if kind == "Stundenplan":
            erkannte = raw_ai_data.get("erkannte_faecher") or []
            if erkannte:
                sync_subjects_to_database(db, erkannte)

        # 4. Titel & normierter Dateiname
        title = raw_ai_data.get("inhaltlicher_titel") or clean_title_from_filename(effective_name)
        norm_name = raw_ai_data.get("normierter_dateiname") or ""
        if not norm_name or not norm_name.endswith(".pdf"):
            ext = Path(effective_name).suffix.lower() or file_path.suffix.lower() or ".pdf"
            safe_fach = sanitize_filename_part(subject.name if subject else "Fach")
            safe_thema = sanitize_filename_part(topic_name or "Allgemein")
            safe_kind = sanitize_filename_part(kind)
            safe_title = sanitize_filename_part(title)
            norm_name = f"{safe_fach}_{safe_thema}_{safe_kind}_{safe_title}{ext}"

        # 5. Mappe bestimmen
        dossier_title, dossier_kind = dossier_for_kind(kind, title, topic_name or subject.name, subject.name)

        summary = raw_ai_data.get("zusammenfassung")

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
            summary=summary,
            solution_pages=parse_page_list(raw_ai_data.get("loesungsseiten")),
            worked_on_paper=_as_bool(raw_ai_data.get("von_schuelerin_bearbeitet")),
            teacher_graded=_as_bool(raw_ai_data.get("von_lehrkraft_bewertet")),
        )

    # Heuristik-Fallback wenn keine KI verfügbar ist
    if is_timetable_document(effective_name, extracted_text):
        kind = "Stundenplan"
        tt_info = heuristic_timetable_analyzer(file_path, extracted_text)
        if tt_info.get("erkannte_faecher"):
            sync_subjects_to_database(db, tt_info["erkannte_faecher"])
        title = tt_info.get("titel") or clean_title_from_filename(effective_name)
        if "stundenplan" not in title.lower():
            title = f"Stundenplan: {title}"
        orga_sub = get_or_create_organisation_subject(db)
        safe_title = sanitize_filename_part(title)
        ext = Path(effective_name).suffix.lower() or file_path.suffix.lower() or ".pdf"
        norm_name = f"Organisation_Stundenplan_{safe_title}{ext}"
        return DocumentAnalysisResult(
            subject_id=orga_sub.id,
            subject_name=orga_sub.name,
            topic_id=None,
            topic_name="Stundenplan",
            kind=kind,
            title=title,
            normalized_filename=norm_name,
            dossier_title="Stundenplan & Organisation",
            dossier_kind="organisation",
            summary=f"Stundenplan mit {len(tt_info.get('erkannte_faecher', []))} erkannten Schulfächern."
        )
    else:
        subject_id, topic_id = predict_subject_and_topic(db, effective_name, extracted_text)
        subject = db.query(Subject).filter_by(id=subject_id).first()
        topic = db.query(Topic).filter_by(id=topic_id).first() if topic_id else None

        kind = normalize_kind(detect_kind_from_filename_and_text(effective_name, extracted_text))
        title = clean_title_from_filename(effective_name)

        safe_fach = sanitize_filename_part(subject.name if subject else "Fach")
        safe_title = sanitize_filename_part(title)
        ext = Path(effective_name).suffix.lower() or file_path.suffix.lower() or ".pdf"
        norm_name = f"{safe_fach}_{safe_title}{ext}"

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
