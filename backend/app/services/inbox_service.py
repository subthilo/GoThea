import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.app.config import INBOX_DIR, INBOX_ERRORS_DIR, MATERIALS_DIR
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material, MaterialChunk
from backend.app.schemas.inbox import (
    InboxFileItem,
    InboxStatusResponse,
    ProcessedItemDetail,
    QuarantinedItemDetail,
    InboxProcessResult,
)
from backend.app.services.material_ingestion import (
    clean_title_from_filename,
    detect_kind_from_filename_and_text,
    extract_pdf_data,
    chunk_text,
    SUBJECT_KEYWORDS,
)
from backend.app.services.document_analyzer import analyze_document_content, predict_subject_and_topic

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
IGNORED_PATTERNS = {".ds_store", ".localized", "thumbs.db"}
IGNORED_EXTENSIONS = {".tmp", ".part", ".crdownload", ".download"}

def is_valid_inbox_file(path: Path) -> bool:
    """Prüft, ob eine Datei verarbeitbar ist (keine Temp-, Hidden- oder Systemdatei)."""
    if not path.is_file():
        return False
    name_lower = path.name.lower()
    if name_lower.startswith("."):
        return False
    if name_lower in IGNORED_PATTERNS:
        return False
    ext = path.suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return False
    return ext in SUPPORTED_EXTENSIONS

def get_inbox_files(inbox_dir: Optional[Path] = None) -> List[Path]:
    """Liefert alle verarbeitbaren Dateien im Inbox-Ordner, sortiert nach Name."""
    target_dir = inbox_dir or INBOX_DIR
    if not target_dir.exists():
        return []

    files = []
    for entry in target_dir.iterdir():
        if entry.is_file() and is_valid_inbox_file(entry):
            files.append(entry)
    return sorted(files, key=lambda f: f.name.lower())

def get_inbox_status(inbox_dir: Optional[Path] = None) -> InboxStatusResponse:
    """Ermittelt den aktuellen Füllstand des Inbox-Netzwerkordners."""
    target_dir = inbox_dir or INBOX_DIR
    files = get_inbox_files(target_dir)

    items = []
    for f in files:
        try:
            stat = f.stat()
            mime = "application/pdf" if f.suffix.lower() == ".pdf" else f"image/{f.suffix.lower().replace('.', '')}"
            items.append(
                InboxFileItem(
                    filename=f.name,
                    file_size=stat.st_size,
                    mime_type=mime,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                )
            )
        except Exception:
            pass

    errors_dir = target_dir / "_errors"
    errors_count = 0
    if errors_dir.exists():
        errors_count = len([e for e in errors_dir.iterdir() if e.is_file() and not e.name.endswith(".error.txt")])

    return InboxStatusResponse(
        inbox_dir=str(target_dir),
        pending_count=len(items),
        files=items,
        errors_count=errors_count,
    )

def quarantine_file(file_path: Path, error_message: str, inbox_dir: Optional[Path] = None) -> Path:
    """Verschiebt eine fehlerhafte Datei in den Quarantäne-Ordner _errors/ mit Fehler-Log."""
    target_dir = inbox_dir or INBOX_DIR
    errors_dir = target_dir / "_errors"
    errors_dir.mkdir(parents=True, exist_ok=True)

    dest_file = errors_dir / file_path.name
    # Falls Datei bereits in Quarantäne existiert, Zeitstempel anfügen
    if dest_file.exists():
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest_file = errors_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

    shutil.move(str(file_path), str(dest_file))

    # Sidecar Fehlerprotokoll schreiben
    log_file = dest_file.with_suffix(dest_file.suffix + ".error.txt")
    log_content = (
        f"GoThea Inbox Quarantäne-Protokoll\n"
        f"Zeitstempel: {datetime.utcnow().isoformat()}\n"
        f"Datei: {file_path.name}\n"
        f"Fehler: {error_message}\n"
    )
    log_file.write_text(log_content, encoding="utf-8")
    return dest_file

def find_or_create_dossier(
    db: Session,
    user_id: str,
    subject_id: str,
    topic_id: Optional[str],
    dossier_title: str,
    kind: str = "hefter"
) -> Dossier:
    """Findet eine bestehende Mappe oder erstellt eine neue."""
    existing = (
        db.query(Dossier)
        .filter_by(user_id=user_id, subject_id=subject_id, title=dossier_title)
        .first()
    )
    if existing:
        return existing

    subject = db.query(Subject).filter_by(id=subject_id).first()
    color = subject.color_code if subject else "#2563eb"
    icon = "📖" if kind == "lehrbuch" else ("📁" if kind == "hefter" else "📑")

    new_dossier = Dossier(
        id=f"dos_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        subject_id=subject_id,
        topic_id=topic_id,
        title=dossier_title,
        kind=kind,
        color_code=color,
        icon=icon,
        description=f"Automatisch aus Inbox erstellte Mappe für {subject.name if subject else 'Schulfach'}"
    )
    db.add(new_dossier)
    db.flush()
    return new_dossier

def process_single_inbox_file(
    db: Session,
    file_path: Path,
    materials_dir: Optional[Path] = None,
    user_id: str = "usr_thea"
) -> ProcessedItemDetail:
    """
    Verarbeitet eine einzelne Datei aus dem Inbox-Ordner atomar:
    1. Validiert & liest Datei
    2. Extrahiert Metadaten (PDF/Bild)
    3. Weist Fach, Thema und Dossier zu
    4. Verschiebt Datei nach materials/
    5. Erstellt DB-Einträge
    6. Gibt Zusammenfassung zurück
    """
    target_mat_dir = materials_dir or MATERIALS_DIR
    target_mat_dir.mkdir(parents=True, exist_ok=True)

    if not file_path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

    file_bytes = file_path.read_bytes()
    file_size = len(file_bytes)
    if file_size == 0:
        raise ValueError("Datei ist leer (0 Bytes).")

    ext = file_path.suffix.lower()
    is_pdf = ext == ".pdf"
    filename = file_path.name

    if is_pdf:
        page_count, extracted_text = extract_pdf_data(file_bytes)
        mime_type = "application/pdf"
    else:
        page_count = 1
        extracted_text = ""
        mime_type = "image/png" if ext == ".png" else "image/jpeg"

    # KI-Inhaltsanalyse & automatische Umbenennung
    analysis = analyze_document_content(
        db=db,
        file_path=file_path,
        extracted_text=extracted_text,
        mime_type=mime_type
    )

    title = analysis.title
    kind = analysis.kind
    subject_id = analysis.subject_id
    topic_id = analysis.topic_id
    dossier_title = analysis.dossier_title
    dossier_kind = analysis.dossier_kind

    subject = db.query(Subject).filter_by(id=subject_id).first()
    topic = db.query(Topic).filter_by(id=topic_id).first() if topic_id else None

    dossier = find_or_create_dossier(
        db=db,
        user_id=user_id,
        subject_id=subject_id,
        topic_id=topic_id,
        dossier_title=dossier_title,
        kind=dossier_kind
    )

    # Nächste dossier_order ermitteln
    existing_count = db.query(Material).filter_by(dossier_id=dossier.id).count()
    dossier_order = existing_count + 1

    # Physische Datei atomar nach materials/ verschieben
    mat_id = f"mat_{uuid.uuid4().hex[:8]}"
    perm_filename = f"{mat_id}{ext}"
    perm_path = target_mat_dir / perm_filename
    shutil.move(str(file_path), str(perm_path))

    # Material-Datensatz in DB anlegen
    material = Material(
        id=mat_id,
        user_id=user_id,
        subject_id=subject_id,
        topic_id=topic_id,
        dossier_id=dossier.id,
        dossier_order=dossier_order,
        title=title,
        kind=kind,
        filename=analysis.normalized_filename,
        file_path=str(perm_path),
        file_size=file_size,
        mime_type=mime_type,
        page_count=page_count,
        extracted_text=extracted_text or None,
        summary=analysis.summary or f"Automatisch aus Inbox verarbeitet in Mappe '{dossier.title}'"
    )
    db.add(material)
    db.flush()

    # Text-Chunking für RAG / Volltextsuche
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

    # Erste Seiten vorab rendern für Sofort-Anzeige im Web-Viewer
    try:
        from backend.app.services.material_ingestion import pre_cache_material_pages
        pre_cache_material_pages(material.id, material.file_path, material.mime_type, max_pages=3)
    except Exception:
        pass

    return ProcessedItemDetail(
        material_id=material.id,
        title=material.title,
        filename=material.filename,
        kind=material.kind,
        subject_id=material.subject_id,
        subject_name=subject.name if subject else None,
        topic_id=material.topic_id,
        topic_name=topic.name if topic else None,
        dossier_id=dossier.id,
        dossier_title=dossier.title,
        page_count=material.page_count
    )

def process_all_inbox_files(
    db: Session,
    inbox_dir: Optional[Path] = None,
    materials_dir: Optional[Path] = None,
    user_id: str = "usr_thea"
) -> InboxProcessResult:
    """
    Verarbeitet alle wartenden Dateien im Inbox-Ordner.
    Erfolgreiche Dateien werden nach materials/ verschoben.
    Fehlerhafte Dateien landen in _errors/ mit Sidecar-Protokoll.
    """
    target_inbox = inbox_dir or INBOX_DIR
    target_materials = materials_dir or MATERIALS_DIR

    files = get_inbox_files(target_inbox)
    processed_items: List[ProcessedItemDetail] = []
    quarantined_items: List[QuarantinedItemDetail] = []

    for f in files:
        try:
            item = process_single_inbox_file(
                db=db,
                file_path=f,
                materials_dir=target_materials,
                user_id=user_id
            )
            processed_items.append(item)
        except Exception as e:
            err_msg = str(e)
            try:
                quarantine_file(f, err_msg, inbox_dir=target_inbox)
            except Exception:
                pass
            quarantined_items.append(QuarantinedItemDetail(filename=f.name, error_message=err_msg))

    return InboxProcessResult(
        total_detected=len(files),
        processed_count=len(processed_items),
        errors_count=len(quarantined_items),
        processed_items=processed_items,
        quarantined_items=quarantined_items
    )
