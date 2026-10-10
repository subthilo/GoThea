import io
import re
import uuid
import shutil
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from pypdf import PdfReader
from sqlalchemy.orm import Session

from backend.app.config import MATERIALS_DIR, TEMP_UPLOADS_DIR
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.material import Material, MaterialChunk
from backend.app.schemas.material import PreAnalysisResponse, MaterialConfirmRequest

SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "sub_math": ["mathe", "mathematik", "bruch", "brüche", "rational", "zahlen", "gleichung", "geometrie", "dreieck", "rechnen", "term"],
    "sub_bio": ["bio", "biologie", "zelle", "mikroskop", "pflanze", "tier", "organell", "ökosystem", "chloroplast", "vakuole"],
    "sub_de": ["deutsch", "gedicht", "lyrik", "grammatik", "aufsatz", "inhaltsangabe", "satzbau", "ballade", "rechtschreibung"],
    "sub_en": ["englisch", "english", "vocabulary", "grammar", "tense", "present", "past", "words", "unit"],
    "sub_geo": ["geografie", "erdkunde", "karte", "kontinent", "klima", "ozean", "vulkan", "erde", "landschaft"],
    "sub_hist": ["geschichte", "antike", "mittelalter", "rom", "griechenland", "ägypten", "ritter", "kaiser", "quelle"],
    "sub_phys": ["physik", "kraft", "optik", "licht", "spiegel", "geschwindigkeit", "energie", "magnet"],
}

def clean_title_from_filename(filename: str) -> str:
    base = Path(filename).stem
    cleaned = re.sub(r"[_\-\.]+", " ", base)
    words = cleaned.strip().split()
    return " ".join(w.capitalize() for w in words) if words else "Unbenanntes Material"

def detect_kind_from_filename_and_text(filename: str, text: str) -> str:
    lower_f = filename.lower()
    lower_t = text.lower()
    if any(k in lower_f or k in lower_t for k in ["heft", "notiz", "mitschrift", "hefter"]):
        return "Hefterseite"
    if any(k in lower_f or k in lower_t for k in ["buch", "lehrbuch", "seite", "kapitel"]):
        return "Buchauszug"
    if any(k in lower_f or k in lower_t for k in ["test", "probe", "klassenarbeit", "kontrolle", "klausur"]):
        return "Übungszettel"
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

    material = Material(
        id=mat_id,
        user_id="usr_thea",
        subject_id=request.subject_id,
        topic_id=request.topic_id,
        title=request.title,
        kind=request.kind,
        filename=perm_filename,
        file_path=str(perm_path),
        file_size=file_size,
        mime_type=mime_type,
        page_count=page_count,
        extracted_text=extracted_text or None,
        summary=request.summary
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
    return material

def render_material_page_as_image(file_path: str, mime_type: str, page_num: int = 1) -> Tuple[bytes, str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("Materialdatei nicht gefunden.")

    if "pdf" in mime_type.lower():
        try:
            import fitz
            doc = fitz.open(str(path))
            total_pages = len(doc)
            target_page = max(0, min(page_num - 1, total_pages - 1))
            page = doc.load_page(target_page)
            # 150 DPI für scharfe Retina-Darstellung
            pix = page.get_pixmap(dpi=150)
            return pix.tobytes("png"), "image/png"
        except Exception:
            return path.read_bytes(), mime_type
    else:
        return path.read_bytes(), mime_type
