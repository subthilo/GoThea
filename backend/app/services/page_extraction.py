"""
Seiteninhalt-Erschließung: Jede Dokumentseite wird einmalig per KI transkribiert (gedruckter Text, Aufgaben,
Handschrift der Schülerin, Korrekturen der Lehrkraft) und als MaterialPage gespeichert.

Ergebnisse liegen zusätzlich inhaltsadressiert (Prüfsumme der Datei + Seite) im gemeinsamen Ordner beider
Umgebungen: Dieselbe Datei wird in Staging und Produktion nur einmal per KI verarbeitet.
"""
import hashlib
import itertools
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from queue import Empty, PriorityQueue
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.config import BOOK_EXTRACTION_INTERVAL_SECONDS, OPENAI_MODEL, SHARED_DATA_DIR
from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
from backend.app.prompts.page_extraction import PAGE_EXTRACTION_SYSTEM_PROMPT
from backend.app.services.document_kinds import BUCH, STUNDENPLAN
from backend.app.services import llm

logger = logging.getLogger(__name__)

CACHE_DIR = SHARED_DATA_DIR / "page_extractions"

PRIORITY_DOCUMENT = 1       # Neu hochgeladene Dokumente: sofort
PRIORITY_BOOK_BACKFILL = 3  # Buchkapitel: langsam im Hintergrund

_sha_cache: Dict[Tuple[str, int], str] = {}
_sha_lock = threading.Lock()


def file_sha256(path: Path) -> str:
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)  # neu geschriebene Dateien sicher erkennen
    with _sha_lock:
        if key in _sha_cache:
            return _sha_cache[key]
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    with _sha_lock:
        _sha_cache[key] = digest.hexdigest()
    return _sha_cache[key]


def content_key(path: Path, page: int) -> str:
    return f"{file_sha256(path)}_p{page}"


def _cache_file(key: str) -> Path:
    return CACHE_DIR / key[:2] / f"{key}.json"


def load_cached(key: str) -> Optional[dict]:
    f = _cache_file(key)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None


def save_cached(key: str, data: dict) -> None:
    target = _cache_file(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomar schreiben: beide Umgebungen greifen auf denselben Ordner zu
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, target)


def _normalize(raw: dict) -> dict:
    tasks = raw.get("aufgaben")
    return {
        "text": str(raw.get("text") or ""),
        "aufgaben": tasks if isinstance(tasks, list) else [],
        "hat_handschrift": raw.get("hat_handschrift") is True,
        "hat_korrekturen_lehrkraft": raw.get("hat_korrekturen_lehrkraft") is True,
        "ist_loesungsseite": raw.get("ist_loesungsseite") is True,
        "lesbarkeit": raw.get("lesbarkeit") if raw.get("lesbarkeit") in ("gut", "mittel", "schlecht") else None,
    }


def _ask_model(image_b64: str) -> dict:
    return llm.chat_json(
        purpose="Seiten-Erschließung",
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": PAGE_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Erschließe diese Seite."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}},
            ]},
        ],
    )


def extract_page_content(path: Path, mime_type: str, page: int, material_id: Optional[str] = None,
                         background: bool = False, ask=None) -> Optional[dict]:
    """Inhalt einer Seite: aus dem gemeinsamen Cache oder per KI (None ohne API-Key)."""
    key = content_key(path, page)
    cached = load_cached(key)
    if cached is not None:
        return cached
    if not llm.is_available() and ask is None:
        return None

    from backend.app.services.material_ingestion import prepare_image_base64_for_vision
    from backend.app.services.page_renderer import PRIORITY_BACKGROUND, PRIORITY_LIVE, page_renderer
    img_bytes, img_mime = page_renderer.render_page(str(path), mime_type, page_num=page, material_id=material_id,
                                                    priority=PRIORITY_BACKGROUND if background else PRIORITY_LIVE)
    data = _normalize((ask or _ask_model)(prepare_image_base64_for_vision(img_bytes, img_mime)))
    data["model"] = OPENAI_MODEL
    save_cached(key, data)
    return data


def store_page(db: Session, material: Material, page: int, key: str, data: dict) -> MaterialPage:
    row = db.query(MaterialPage).filter_by(material_id=material.id, page_number=page).first()
    if row is None:
        row = MaterialPage(material_id=material.id, page_number=page)
        db.add(row)
    row.content_key = key
    row.text = data["text"]
    row.tasks_json = json.dumps(data["aufgaben"], ensure_ascii=False) if data["aufgaben"] else None
    row.has_handwriting = data["hat_handschrift"]
    row.has_teacher_marks = data["hat_korrekturen_lehrkraft"]
    row.is_solution_page = data["ist_loesungsseite"]
    row.legibility = data["lesbarkeit"]
    row.model = data.get("model")
    return row


def refresh_material_text(db: Session, material: Material) -> None:
    """Gesamttext des Dokuments aus den erschlossenen Seiten (Grundlage für Tutor und Suche)."""
    pages = db.query(MaterialPage).filter_by(material_id=material.id).order_by(MaterialPage.page_number).all()
    if pages:
        material.extracted_text = "\n\n".join(f"--- Seite {p.page_number} ---\n{p.text}" for p in pages)


def missing_pages(db: Session, material: Material) -> List[int]:
    done = {n for (n,) in db.query(MaterialPage.page_number).filter_by(material_id=material.id)}
    return [p for p in range(1, max(1, material.page_count or 1) + 1) if p not in done]


def extract_material(db: Session, material: Material, pages: Optional[List[int]] = None,
                     background: bool = False, ask=None) -> int:
    """Erschließt die angegebenen (sonst alle fehlenden) Seiten eines Dokuments synchron."""
    path = Path(material.file_path or "")
    if not path.exists():
        return 0
    done = 0
    for page in pages or missing_pages(db, material):
        data = extract_page_content(path, material.mime_type, page, material.id, background=background, ask=ask)
        if data is None:
            break
        store_page(db, material, page, content_key(path, page), data)
        done += 1
    if done:
        db.flush()  # Sessions laufen ohne autoflush: neue Seiten erst schreiben, dann den Gesamttext bilden
        refresh_material_text(db, material)
        db.commit()
    return done


def needs_extraction(material: Material) -> bool:
    """Bücher werden über ihre Kapitel erschlossen, Stundenpläne gar nicht."""
    return material.kind not in (STUNDENPLAN,) and not (material.kind == BUCH and material.parent_id is None)


class PageExtractionService:
    """Arbeitet Erschließungs-Aufträge im Hintergrund ab: Dokumente sofort, Buchkapitel gedrosselt."""

    def __init__(self):
        self._queue: PriorityQueue = PriorityQueue()
        self._counter = itertools.count()
        self._queued: Set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._session_factory = None

    def queue_material(self, material_id: str, priority: int = PRIORITY_DOCUMENT) -> None:
        if not llm.is_available():
            return
        if priority == PRIORITY_BOOK_BACKFILL and BOOK_EXTRACTION_INTERVAL_SECONDS <= 0:
            return
        with self._lock:
            if material_id in self._queued:
                return
            self._queued.add(material_id)
        self._queue.put((priority, next(self._counter), material_id))

    def start(self, session_factory) -> None:
        if not llm.is_available() or (self._thread and self._thread.is_alive()):
            return
        self._session_factory = session_factory
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="PageExtractionWorker", daemon=True)
        self._thread.start()
        logger.info("🔎 Seiten-Erschließung gestartet.")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _queue_missing(self) -> None:
        db = self._session_factory()
        try:
            docs = books = 0
            for material in db.query(Material).all():
                if not needs_extraction(material) or not missing_pages(db, material):
                    continue
                if material.parent_id or material.kind == BUCH:
                    self.queue_material(material.id, PRIORITY_BOOK_BACKFILL)
                    books += 1
                else:
                    self.queue_material(material.id, PRIORITY_DOCUMENT)
                    docs += 1
            logger.info(f"🔎 Seiten-Erschließung eingereiht: {docs} Dokumente, {books} Buchkapitel.")
        finally:
            db.close()

    def _run(self) -> None:
        self._queue_missing()
        while not self._stop.is_set():
            try:
                priority, _, material_id = self._queue.get(timeout=1.0)
            except Empty:
                continue
            with self._lock:
                self._queued.discard(material_id)
            self._process(material_id, priority)

    def _process(self, material_id: str, priority: int) -> None:
        background = priority == PRIORITY_BOOK_BACKFILL
        db = self._session_factory()
        try:
            material = db.get(Material, material_id)
            if material is None or not needs_extraction(material):
                return
            pending = missing_pages(db, material)
            # Dokumente am Stück; Buchkapitel seitenweise und danach wieder einreihen,
            # damit neu hochgeladene Dokumente nie hinter einem langen Kapitel warten
            for page in (pending[:1] if background else pending):
                if self._stop.is_set() or not extract_material(db, material, [page], background=background):
                    return
            if background and len(pending) > 1:
                if not self._stop.wait(BOOK_EXTRACTION_INTERVAL_SECONDS):
                    self.queue_material(material_id, priority)
                return
            logger.info(f"🔎 Erschlossen: {material.title} ({material.page_count} S.)")
        except Exception as e:
            db.rollback()
            logger.warning(f"Seiten-Erschließung für {material_id} fehlgeschlagen: {e}")
        finally:
            db.close()


page_extraction_service = PageExtractionService()
