import io
import os
import re
import uuid
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import base64
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session

import logging

from backend.app.config import MATERIALS_DIR, TEMP_UPLOADS_DIR, PAGE_CACHE_DIR
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.material import Material, MaterialChunk
from backend.app.schemas.material import PreAnalysisResponse, MaterialConfirmRequest

logger = logging.getLogger(__name__)

def prepare_image_base64_for_vision(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Skaliert ein Bild auf max. 1600x1600 Pixel und liefert Base64-JPEG."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        max_size = (1600, 1600)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=85)
        return base64.b64encode(out_buf.getvalue()).decode("utf-8")
    except Exception:
        return base64.b64encode(image_bytes).decode("utf-8")


SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "sub_math": ["mathe", "mathematik", "bruch", "brüche", "rational", "zahlen", "gleichung", "geometrie", "dreieck", "rechnen", "term"],
    "sub_bio": ["bio", "biologie", "zelle", "mikroskop", "pflanze", "tier", "organell", "ökosystem", "chloroplast", "vakuole"],
    "sub_de": ["deutsch", "gedicht", "lyrik", "grammatik", "aufsatz", "inhaltsangabe", "satzbau", "ballade", "rechtschreibung"],
    "sub_en": ["englisch", "english", "vocabulary", "grammar", "tense", "present", "past", "words", "unit"],
    "sub_geo": ["geografie", "erdkunde", "karte", "kontinent", "klima", "ozean", "vulkan", "erde", "landschaft"],
    "sub_hist": ["geschichte", "antike", "mittelalter", "rom", "griechenland", "ägypten", "ritter", "kaiser", "quelle"],
    "sub_phys": ["physik", "kraft", "optik", "licht", "spiegel", "geschwindigkeit", "energie", "magnet"],
    "sub_orga": ["stundenplan", "wochenplan", "timetable", "organisation", "termine", "schulwoche"],
}

def clean_title_from_filename(filename: str) -> str:
    base = Path(filename).stem
    cleaned = re.sub(r"[_\-\.]+", " ", base)
    words = cleaned.strip().split()
    return " ".join(w.capitalize() for w in words) if words else "Unbenanntes Material"

def sanitize_filename_part(text: str) -> str:
    """Wandelt Umlaute und Sonderzeichen für saubere Dateinamen um."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    return cleaned.strip("_")



def detect_kind_from_filename_and_text(filename: str, text: str) -> str:
    lower_f = filename.lower()
    lower_t = text.lower()
    if any(k in lower_f or k in lower_t for k in ["stundenplan", "wochenplan", "timetable"]):
        return "Stundenplan"
    if any(k in lower_f or k in lower_t for k in ["heft", "notiz", "mitschrift", "hefter"]):
        return "Hefterseite"
    if any(k in lower_f or k in lower_t for k in ["buch", "lehrbuch", "seite", "kapitel"]):
        return "Buchauszug"
    if any(k in lower_f or k in lower_t for k in ["klassenarbeit", "klausur"]):
        return "Klassenarbeit"
    if any(k in lower_f or k in lower_t for k in ["test", "probe", "kontrolle", "uebungszettel"]):
        return "Test"
    return "Arbeitsblatt"

def extract_pdf_data(file_bytes: bytes) -> Tuple[int, str]:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        texts = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                texts.append(t.strip())
        full_text = "\n\n".join(texts)
        return max(1, page_count), full_text
    except Exception:
        return 1, ""

def pre_analyze_upload(
    db: Session,
    filename: str,
    file_bytes: bytes,
    content_type: str
) -> PreAnalysisResponse:
    TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_token = f"upl_{uuid.uuid4().hex[:12]}"
    ext = Path(filename).suffix or (".pdf" if "pdf" in content_type else ".png")
    temp_filename = f"{upload_token}{ext}"
    temp_path = TEMP_UPLOADS_DIR / temp_filename
    temp_path.write_bytes(file_bytes)

    is_pdf = "pdf" in content_type.lower() or ext.lower() == ".pdf"
    if is_pdf:
        page_count, extracted_text = extract_pdf_data(file_bytes)
    else:
        page_count = 1
        extracted_text = ""

    corpus = f"{filename} {extracted_text}".lower()
    predicted_subject_id: Optional[str] = None
    best_score = 0

    all_subjects = db.query(Subject).all()
    subject_map = {s.id: s for s in all_subjects}

    for sub_id, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in corpus)
        if sub_id in subject_map and subject_map[sub_id].name.lower() in corpus:
            score += 3
        if score > best_score:
            best_score = score
            predicted_subject_id = sub_id

    if not predicted_subject_id and all_subjects:
        predicted_subject_id = all_subjects[0].id

    predicted_topic_id: Optional[str] = None
    if predicted_subject_id:
        topics = db.query(Topic).filter_by(subject_id=predicted_subject_id).all()
        best_t_score = 0
        for top in topics:
            t_words = [w.lower() for w in top.name.split() if len(w) > 3]
            t_score = sum(1 for w in t_words if w in corpus)
            if t_score > best_t_score:
                best_t_score = t_score
                predicted_topic_id = top.id

    predicted_title = clean_title_from_filename(filename)
    predicted_kind = detect_kind_from_filename_and_text(filename, extracted_text)
    from backend.app.services.timetable_analyzer import is_timetable_document, get_or_create_organisation_subject
    if predicted_kind == "Stundenplan" or is_timetable_document(filename, extracted_text):
        predicted_kind = "Stundenplan"
        orga_sub = get_or_create_organisation_subject(db)
        predicted_subject_id = orga_sub.id
        predicted_topic_id = None
        if "stundenplan" not in predicted_title.lower():
            predicted_title = f"Stundenplan: {predicted_title}"

    preview_snippet = (extracted_text[:280] + "...") if len(extracted_text) > 280 else (extracted_text or None)

    return PreAnalysisResponse(
        upload_token=upload_token,
        filename=filename,
        file_size=len(file_bytes),
        mime_type=content_type,
        page_count=page_count,
        predicted_subject_id=predicted_subject_id,
        predicted_topic_id=predicted_topic_id,
        predicted_title=predicted_title,
        predicted_kind=predicted_kind,
        preview_snippet=preview_snippet,
        extracted_text=extracted_text or None
    )

def chunk_text(text: str) -> List[Dict[str, Any]]:
    if not text or not text.strip():
        return []
    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    chunk_idx = 0
    buffer = ""

    for para in raw_paras:
        is_section_header = any(
            para.lower().startswith(k)
            for k in ["merke", "definition", "aufgabe", "übung", "vokabel", "frage", "beispiel"]
        )
        if buffer and (is_section_header or len(buffer) + len(para) > 500):
            chunks.append(classify_chunk(buffer, chunk_idx))
            chunk_idx += 1
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}".strip()

    if buffer:
        chunks.append(classify_chunk(buffer, chunk_idx))

    return chunks

def classify_chunk(content: str, idx: int) -> Dict[str, Any]:
    c_lower = content.lower()
    if any(k in c_lower for k in ["merke", "definition", "regel", "satz"]):
        ctype = "rule"
    elif any(k in c_lower for k in ["aufgabe", "übung", "berechne", "frage", "?"]):
        ctype = "exercise"
    elif any(k in c_lower for k in ["vokabel", "vocabulary", ":"]):
        ctype = "vocabulary"
    else:
        ctype = "general"
    return {"chunk_index": idx, "content": content, "chunk_type": ctype, "page_number": 1}

def confirm_and_save_material(
    db: Session,
    request: MaterialConfirmRequest
) -> Material:
    MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
    matching_files = list(TEMP_UPLOADS_DIR.glob(f"{request.upload_token}.*"))
    if not matching_files:
        raise ValueError(f"Upload-Token '{request.upload_token}' nicht gefunden oder abgelaufen.")

    temp_path = matching_files[0]
    ext = temp_path.suffix
    file_bytes = temp_path.read_bytes()
    file_size = len(file_bytes)

    if ext.lower() == ".pdf":
        page_count, extracted_text = extract_pdf_data(file_bytes)
        mime_type = "application/pdf"
    else:
        page_count = 1
        extracted_text = ""
        mime_type = "image/png" if ext.lower() == ".png" else "image/jpeg"

    mat_id = f"mat_{uuid.uuid4().hex[:8]}"
    perm_filename = f"{mat_id}{ext}"
    perm_path = MATERIALS_DIR / perm_filename
    shutil.move(str(temp_path), str(perm_path))

    from backend.app.services.timetable_analyzer import (
        is_timetable_document,
        get_or_create_organisation_subject,
        heuristic_timetable_analyzer,
        sync_subjects_to_database,
    )
    from backend.app.models.dossier import Dossier

    is_tt = (
        request.kind == "Stundenplan"
        or is_timetable_document(temp_path.name, extracted_text)
        or is_timetable_document(request.title or "", extracted_text)
        or ("stundenplan" in (request.title or "").lower())
    )

    save_subject_id = request.subject_id
    save_topic_id = request.topic_id
    save_kind = request.kind
    save_title = request.title
    save_dossier_id = request.dossier_id
    save_summary = request.summary

    if is_tt:
        save_kind = "Stundenplan"
        orga_sub = get_or_create_organisation_subject(db)
        save_subject_id = orga_sub.id
        save_topic_id = None
        if "stundenplan" not in (save_title or "").lower():
            save_title = f"Stundenplan: {save_title}"

        # Erkannte Fächer auslesen und in DB synchronisieren
        tt_info = heuristic_timetable_analyzer(perm_path, extracted_text)
        erkannte = tt_info.get("erkannte_faecher", [])
        if erkannte:
            sync_subjects_to_database(db, erkannte)

        if not save_summary:
            save_summary = f"Stundenplan mit {len(erkannte)} erkannten Schulfächern."

        # Dossier 'Stundenplan & Organisation' zuordnen oder erstellen
        if not save_dossier_id:
            dossier = (
                db.query(Dossier)
                .filter(
                    (Dossier.subject_id == orga_sub.id) | (Dossier.title == "Stundenplan & Organisation")
                )
                .first()
            )
            if not dossier:
                dossier = Dossier(
                    id=f"dos_{uuid.uuid4().hex[:8]}",
                    user_id="usr_thea",
                    subject_id=orga_sub.id,
                    title="Stundenplan & Organisation",
                    kind="organisation",
                    color_code=orga_sub.color_code,
                    icon="📁",
                    description="Organisatorische Dokumente und Stundenpläne"
                )
                db.add(dossier)
                db.flush()
            else:
                if dossier.subject_id != orga_sub.id:
                    dossier.subject_id = orga_sub.id
            save_dossier_id = dossier.id

    # Nächste dossier_order ermitteln
    dossier_order = request.dossier_order or 1
    if save_dossier_id and not request.dossier_order:
        existing_count = db.query(Material).filter_by(dossier_id=save_dossier_id).count()
        dossier_order = existing_count + 1

    material = Material(
        id=mat_id,
        user_id="usr_thea",
        subject_id=save_subject_id,
        topic_id=save_topic_id,
        title=save_title,
        kind=save_kind,
        filename=perm_filename,
        file_path=str(perm_path),
        file_size=file_size,
        mime_type=mime_type,
        page_count=page_count,
        extracted_text=extracted_text or None,
        summary=save_summary,
        dossier_id=save_dossier_id,
        dossier_order=dossier_order,
        parent_id=request.parent_id
    )
    db.add(material)
    db.flush()

    if extracted_text:
        chunks_data = chunk_text(extracted_text)
        for cd in chunks_data:
            chunk = MaterialChunk(
                material_id=material.id,
                chunk_index=cd["chunk_index"],
                content=cd["content"],
                chunk_type=cd["chunk_type"],
                page_number=cd["page_number"]
            )
            db.add(chunk)

    db.commit()
    db.refresh(material)

    # Hintergrund-Rendering für alle Seiten des Dokuments anstoßen
    try:
        from backend.app.services.page_renderer import page_renderer
        page_renderer.queue_material(material.id, material.file_path, material.mime_type, material.page_count)
    except Exception:
        pass

    return material

def render_material_page_as_image(
    file_path: str,
    mime_type: str,
    page_num: int = 1,
    material_id: Optional[str] = None
) -> Tuple[bytes, str]:
    """
    Rendert eine Dokumentenseite extrem schnell als JPEG-Bild.
    Delegiert an den priorisierten PageRenderingService.
    """
    from backend.app.services.page_renderer import page_renderer, PRIORITY_LIVE
    return page_renderer.render_page(
        file_path=file_path,
        mime_type=mime_type,
        page_num=page_num,
        material_id=material_id,
        priority=PRIORITY_LIVE
    )

def pre_cache_material_pages(
    material_id: str,
    file_path: str,
    mime_type: str,
    max_pages: int = 3
):
    """
    Rendert die ersten Seiten eines PDFs asynchron/beim Upload vor.
    """
    from backend.app.services.page_renderer import page_renderer
    page_renderer.queue_material(material_id, file_path, mime_type, max_pages)


