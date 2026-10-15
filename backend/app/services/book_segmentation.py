import json
import logging
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import pypdf
from sqlalchemy.orm import Session

from backend.app.services.document_kinds import NEVER_BOOK_KINDS, normalize_kind
from backend.app.prompts.book_toc import BOOK_TOC_SYSTEM_PROMPT
from backend.app.services import llm
from backend.app.models.material import Material
from backend.app.models.taxonomy import Topic

logger = logging.getLogger(__name__)

# Pro Buch darf nur eine Segmentierung gleichzeitig laufen (Upload-Hintergrund vs. Bücher-Tab)
_segmentation_locks: Dict[str, threading.Lock] = {}
_segmentation_locks_guard = threading.Lock()
_segmentations_running: Set[str] = set()


def _get_book_lock(book_id: str) -> threading.Lock:
    with _segmentation_locks_guard:
        return _segmentation_locks.setdefault(book_id, threading.Lock())


def is_segmentation_running(book_id: str) -> bool:
    with _segmentation_locks_guard:
        return book_id in _segmentations_running

# Bekannte Inhaltsverzeichnisse (aus Vision-Analysen der Original-Inhaltsverzeichnisse) liegen als
# Daten in backend/app/book_tables/: je Kapitel PDF-Seiten, Buchseiten, Art, Thema, Schwerpunkt, Abschnitte.
BOOK_TABLES_DIR = Path(__file__).resolve().parent.parent / "book_tables"


def _load_book_table(filename: str) -> List[Dict[str, Any]]:
    return json.loads((BOOK_TABLES_DIR / filename).read_text(encoding="utf-8"))


FUNDAMENTE_MATHE_7_CHAPTERS = _load_book_table("fundamente_mathe_7.json")
FRANZ_VORKURS_SECTIONS = _load_book_table("franz_vorkurs_sections.json")
PHYSIK_PLUS_7_CHAPTERS = _load_book_table("physik_plus_7.json")
DEUTSCHBUCH_7_CHAPTERS = _load_book_table("deutschbuch_7.json")
APLUS_1_CHAPTERS = _load_book_table("aplus_1.json")


def segment_book_material(
    db: Session,
    book: Material,
    chapters_spec: List[Dict[str, Any]],
    target_dir: Optional[Path] = None,
    force: bool = False
) -> List[Material]:
    """
    Teilt ein Schulbuch-Material anhand einer Kapitelspezifikation in
    einzelne Kapitel-PDFs und Child-Material-Einträge auf.
    """
    if not book.file_path or not os.path.exists(book.file_path):
        raise FileNotFoundError(f"PDF-Datei für Buch {book.id} nicht gefunden: {book.file_path}")

    dest_folder = target_dir or Path(book.file_path).parent
    dest_folder.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(book.file_path)
    total_pages = len(reader.pages)

    if book.kind != "Buch":
        book.kind = "Buch"

    # Vorhandene Topics des Fachs cachen
    topics_by_name = {
        t.name.lower(): t for t in db.query(Topic).filter_by(subject_id=book.subject_id).all()
    }

    # Bereits existierende Kapitel für dieses Buch prüfen
    existing_children = {
        m.dossier_order: m for m in db.query(Material).filter_by(parent_id=book.id).all()
    }

    created_or_updated: List[Material] = []
    rewritten_ids: List[str] = []

    for idx, spec in enumerate(chapters_spec):
        unit_num = spec.get("unit_number", idx)
        start_pdf = max(1, spec.get("start_pdf_page", spec.get("book_start_page", 1)))
        end_pdf = min(total_pages, spec.get("end_pdf_page", spec.get("book_end_page", total_pages)))

        if start_pdf > total_pages:
            continue

        page_count = end_pdf - start_pdf + 1
        chap_id = f"{book.id}_ch{unit_num:02d}"
        chap_filename = f"{book.id}_Kapitel_{unit_num:02d}.pdf"
        chap_path = dest_folder / chap_filename

        # 1. Kapitel-PDF via pypdf extrahieren
        if force or not chap_path.exists() or chap_path.stat().st_size == 0:
            rewritten_ids.append(chap_id)
            writer = pypdf.PdfWriter()
            for p_idx in range(start_pdf - 1, end_pdf):
                writer.add_page(reader.pages[p_idx])
            with open(chap_path, "wb") as f_out:
                writer.write(f_out)
            logger.info(f"📄 Kapitel {unit_num} extrahiert: {chap_path.name} ({page_count} Seiten, PDF {start_pdf}-{end_pdf})")

        file_size = chap_path.stat().st_size if chap_path.exists() else 0

        # 2. Thema verknüpfen: nur ein vorhandenes Thema übernehmen. Kapitel umfassen meist mehrere
        #    Unterrichtseinheiten; eigene Kapitel-Themen würden den Themenkatalog verwässern.
        topic_name = spec.get("topic_name")
        matched_topic = topics_by_name.get(topic_name.lower()) if topic_name else None

        # 3. Material-Eintrag erstellen oder aktualisieren
        order = unit_num + 2  # Master ist meist Order 1
        child = existing_children.get(order)
        if not child:
            child = db.query(Material).filter_by(id=chap_id).first()

        sec_list = spec.get("sections", [])
        sec_json = json.dumps(sec_list, ensure_ascii=False) if sec_list else None

        if not child:
            child = Material(
                id=chap_id,
                user_id=book.user_id,
                subject_id=book.subject_id,
                topic_id=matched_topic.id if matched_topic else None,
                dossier_id=book.dossier_id,
                dossier_order=order,
                parent_id=book.id,
                title=spec.get("title", f"Kapitel {unit_num}"),
                kind=spec.get("kind", "Buchauszug"),
                filename=chap_filename,
                file_path=str(chap_path),
                file_size=file_size,
                mime_type="application/pdf",
                page_count=page_count,
                start_page=spec.get("book_start_page", start_pdf),
                end_page=spec.get("book_end_page", end_pdf),
                summary=spec.get("focus"),
                toc_json=sec_json,
            )
            db.add(child)
        else:
            child.title = spec.get("title", child.title)
            child.parent_id = book.id
            child.topic_id = matched_topic.id if matched_topic else child.topic_id
            child.file_path = str(chap_path)
            child.file_size = file_size
            child.page_count = page_count
            child.start_page = spec.get("book_start_page", start_pdf)
            child.end_page = spec.get("book_end_page", end_pdf)
            child.summary = spec.get("focus")
            if sec_json:
                child.toc_json = sec_json

        created_or_updated.append(child)

    # Kapitel aus einer früheren Segmentierung, die es nicht mehr gibt, entfernen
    kept_ids = {c.id for c in created_or_updated}
    kept_paths = {c.file_path for c in created_or_updated} | {book.file_path}
    stale_paths: List[Path] = []
    stale_ids: List[str] = []
    for stale in db.query(Material).filter_by(parent_id=book.id).all():
        if stale.id not in kept_ids:
            stale_ids.append(stale.id)
            logger.info(f"🗑️ Veraltetes Kapitel entfernt: {stale.title} ({stale.id})")
            if stale.file_path and stale.file_path not in kept_paths:
                stale_paths.append(Path(stale.file_path))
            db.delete(stale)

    try:
        if book.kind != "Buch":
            book.kind = "Buch"
        db.commit()
        for stale_path in stale_paths:
            stale_path.unlink(missing_ok=True)
        _refresh_rendered_pages(created_or_updated, rewritten_ids + stale_ids)
        logger.info(f"✅ Schulbuch {book.title} ({book.id}) erfolgreich in {len(created_or_updated)} Kapitel segmentiert.")
        return created_or_updated
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Fehler bei der Buchsegmentierung für {book.id}: {e}", exc_info=True)
        raise


def _refresh_rendered_pages(chapters: List[Material], outdated_ids: List[str]) -> None:
    """Verwirft veraltete Seitenbilder und rendert die Kapitel im Hintergrund vor."""
    try:
        from backend.app.services.page_renderer import page_renderer
        if outdated_ids:
            page_renderer.purge_material_cache(outdated_ids)
        from backend.app.services.page_extraction import PRIORITY_BOOK_BACKFILL, page_extraction_service
        for chap in chapters:
            page_renderer.queue_material(chap.id, chap.file_path, chap.mime_type, chap.page_count)
            page_extraction_service.queue_material(chap.id, PRIORITY_BOOK_BACKFILL)
    except Exception as e:
        logger.warning(f"Kapitel konnten nicht zum Vorrendern eingereiht werden: {e}")


def is_candidate_book(material: Material) -> bool:
    """
    Prüft, ob ein Material ein Schulbuch ist, das in Kapitel segmentiert werden sollte.
    """
    if material.parent_id is not None:
        return False
    if material.mime_type != "application/pdf":
        return False
    # Ausdrücklich als etwas anderes erkannte Dokumente (Vokabelliste, Test, Mitschrift ...) nie zerlegen
    if normalize_kind(material.kind, default="") in NEVER_BOOK_KINDS:
        return False

    kind_lower = (material.kind or "").lower()
    if kind_lower in ("buch", "lehrbuch"):
        return True

    title_lower = (material.title or "").lower()
    book_keywords = [
        "buch", "lehrbuch", "schulbuch", "arbeitsbuch", "arbeitsheft", "workbook", "vorkurs",
        "fundamente", "cornelsen", "klett", "duden", "westermann",
        "mathematik", "englisch", "französisch", "franzoesisch", "biologie", "physik", "klasse 7"
    ]
    if material.page_count and material.page_count >= 20:
        if any(kw in title_lower for kw in book_keywords):
            return True
        if material.page_count >= 25:
            return True

    return False


def extract_chapters_from_pdf_outline(pdf_path: Path, total_pages: int) -> List[Dict[str, Any]]:
    """
    Extrahiert Kapitelgrenzen und Unterabschnitte aus den PDF-Lesezeichen (Document Outline),
    falls vorhanden. Sehr schnell und 100 % präzise für digitale Schulbuch-PDFs.
    """
    if not pdf_path.exists():
        return []

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        raw_outline = reader.outline
        if not raw_outline:
            return []

        def _flatten_outline(items, level=1) -> List[tuple]:
            res = []
            for item in items:
                if isinstance(item, list):
                    res.extend(_flatten_outline(item, level=level + 1))
                else:
                    try:
                        title = str(getattr(item, "title", item)).strip()
                        page_num = reader.get_destination_page_number(item)
                        if page_num is not None and 0 <= page_num < total_pages:
                            res.append((title, page_num + 1, level))
                    except Exception:
                        pass
            return res

        extracted = _flatten_outline(raw_outline)
        if len(extracted) < 2:
            return []

        # Sortieren nach Startseite
        extracted.sort(key=lambda x: x[1])

        # Prüfen, ob Level-1-Einträge existieren
        level1_items = [x for x in extracted if x[2] == 1]
        if len(level1_items) >= 2:
            chapter_entries = level1_items
            sub_entries = [x for x in extracted if x[2] > 1]
        else:
            unique_items = []
            for title, p_num, lvl in extracted:
                if not unique_items or p_num > unique_items[-1][1]:
                    unique_items.append((title, p_num, lvl))
            chapter_entries = unique_items
            sub_entries = []

        if len(chapter_entries) < 2:
            return []

        chapters: List[Dict[str, Any]] = []
        for idx, (title, start_p, lvl) in enumerate(chapter_entries):
            end_p = chapter_entries[idx + 1][1] - 1 if idx + 1 < len(chapter_entries) else total_pages
            if end_p < start_p:
                end_p = start_p

            chapter_sections = []
            for sub_title, sub_p, sub_lvl in sub_entries:
                if start_p <= sub_p <= end_p:
                    chapter_sections.append({
                        "title": sub_title,
                        "book_page": sub_p,
                        "relative_page": max(1, sub_p - start_p + 1),
                        "level": sub_lvl
                    })

            chapters.append({
                "unit_number": idx + 1,
                "title": title,
                "start_pdf_page": start_p,
                "end_pdf_page": end_p,
                "book_start_page": start_p,
                "book_end_page": end_p,
                "kind": "Buchauszug",
                "topic_name": title,
                "focus": f"Kapitel: {title}",
                "sections": chapter_sections
            })
        logger.info(f"📑 {len(chapters)} Kapitel mit Unterabschnitten direkt aus PDF-Bookmarks erkannt.")
        return chapters
    except Exception as e:
        logger.warning(f"Konnte PDF-Outline nicht parsen: {e}")
        return []


# Inhaltsverzeichnisse stehen in den ersten Seiten; lange TOCs (z. B. Deutschbuch) brauchen viel Text
TOC_SCAN_PAGES = 20
TOC_MAX_TEXT_CHARS = 15000


def extract_chapters_with_ai(file_path: Path, total_pages: int, title_hint: str = "") -> List[Dict[str, Any]]:
    """
    Analysiert die ersten Seiten eines Schulbuchs (Inhaltsverzeichnis) via OpenAI.
    Unterstützt sowohl digitale Texte als auch eingescannte Bildseiten (Vision).
    """
    from backend.app.config import OPENAI_MODEL
    if not llm.is_available() or not file_path.exists():
        return []

    try:
        from backend.app.services.material_ingestion import render_material_page_as_image, prepare_image_base64_for_vision

        reader = pypdf.PdfReader(str(file_path))
        toc_text = ""
        max_scan_pages = min(TOC_SCAN_PAGES, len(reader.pages))
        for p_idx in range(max_scan_pages):
            t = (reader.pages[p_idx].extract_text() or "").strip()
            if t:
                toc_text += f"\n--- Dokumentseite im PDF: Seite {p_idx + 1} ---\n" + t


        # Wenn digitaler Text vorhanden ist:
        if len(toc_text.strip()) > 150 and any(k in toc_text.lower() for k in ["inhalt", "kapitel", "unit", "inhaltsverzeichnis"]):
            messages = [
                {"role": "system", "content": BOOK_TOC_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Buchtitel: {title_hint}\nGesamtseitenzahl: {total_pages}\nAchte genau auf die PDF-Seitenzahlen in den Trennzeilen und berechne den Offset zu den gedruckten Buchseiten.\n\nInhaltsverzeichnis-Text:\n{toc_text[:TOC_MAX_TEXT_CHARS]}"
                }
            ]
        else:
            # Gescannte PDF: Seiten als Bilder rendern und an Vision übergeben (bis zu Seite 20)
            user_content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": f"Buchtitel: {title_hint}\nGesamtseiten: {total_pages}\nHier sind die Inhaltsverzeichnis-Seiten des gescannten Buchs. Achte genau auf die PDF-Seitenzahlen in den Trennzeilen und berechne den Offset zu den gedruckten Buchseiten."
                }
            ]
            for p_num in range(2, min(TOC_SCAN_PAGES, total_pages) + 1):
                try:
                    img_bytes, mime = render_material_page_as_image(str(file_path), "application/pdf", page_num=p_num)
                    b64 = prepare_image_base64_for_vision(img_bytes, mime)
                    user_content.append({
                        "type": "text",
                        "text": f"--- Dokumentseite im PDF: Seite {p_num} ---"
                    })
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}
                    })
                except Exception as e:
                    logger.warning(f"Inhaltsverzeichnis: Seite {p_num} nicht gerendert: {e}")

            if len(user_content) <= 1:
                return []

            messages = [
                {"role": "system", "content": BOOK_TOC_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ]

        data = llm.chat_json(messages, purpose="Buch-Inhaltsverzeichnis", model=OPENAI_MODEL, temperature=0.1)
        raw_chaps = data.get("chapters", [])
        if not isinstance(raw_chaps, list) or len(raw_chaps) < 1:
            return []

        valid_chaps = []
        for c in raw_chaps:
            sp = int(c.get("start_pdf_page", 1))
            ep = int(c.get("end_pdf_page", sp))
            b_sp = int(c.get("book_start_page", sp))
            if 1 <= sp <= total_pages:
                ep = min(total_pages, max(sp, ep))
                sections = []
                for s in c.get("sections", []):
                    if isinstance(s, dict) and "title" in s:
                        bp = int(s.get("book_page", b_sp))
                        rp = int(s.get("relative_page", max(1, bp - b_sp + 1)))
                        sections.append({
                            "title": str(s.get("title")),
                            "book_page": bp,
                            "relative_page": rp,
                            "level": int(s.get("level", 2))
                        })

                valid_chaps.append({
                    "unit_number": len(valid_chaps) + 1,
                    "title": str(c.get("title", f"Kapitel {len(valid_chaps) + 1}")),
                    "start_pdf_page": sp,
                    "end_pdf_page": ep,
                    "book_start_page": b_sp,
                    "book_end_page": int(c.get("book_end_page", ep)),
                    "kind": "Buchauszug",
                    "topic_name": str(c.get("topic_name") or c.get("title")),
                    "focus": str(c.get("focus") or ""),
                    "sections": sections
                })

        logger.info(f"🤖 {len(valid_chaps)} Kapitel via OpenAI Inhaltsanalyse extrahiert.")
        return valid_chaps
    except Exception as e:
        logger.warning(f"Konnte Kapitel nicht via KI extrahieren: {e}")
        return []


def auto_segment_if_known(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """
    Prüft, ob für das gegebene Buch eine bekannte Kapiteltabelle vorliegt
    (z. B. Fundamente der Mathematik, À plus! 1, Physik Plus, Deutschbuch 7), und segmentiert es automatisch.
    """
    title_lower = (book.title or "").lower()
    if "fundamente" in title_lower and "mathematik" in title_lower:
        return segment_book_material(db, book, FUNDAMENTE_MATHE_7_CHAPTERS, force=force)
    if any(k in title_lower for k in ["aplus", "a plus", "à plus"]):
        return segment_book_material(db, book, APLUS_1_CHAPTERS, force=force)
    if "physik" in title_lower and "plus" in title_lower:
        return segment_book_material(db, book, PHYSIK_PLUS_7_CHAPTERS, force=force)
    if "deutschbuch" in title_lower:
        return segment_book_material(db, book, DEUTSCHBUCH_7_CHAPTERS, force=force)
    return None


def auto_detect_and_segment_book(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """Segmentiert ein Buch; parallele Aufrufe für dasselbe Buch warten aufeinander."""
    with _get_book_lock(book.id):
        with _segmentation_locks_guard:
            _segmentations_running.add(book.id)
        try:
            return _auto_detect_and_segment_book_unlocked(db, book, force=force)
        finally:
            with _segmentation_locks_guard:
                _segmentations_running.discard(book.id)


def _auto_detect_and_segment_book_unlocked(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """
    Vollautomatische Pipeline zur Erkennung und Segmentierung von Schulbüchern:
    1. Prüft, ob bereits Kapitel existieren.
    2. Prüft bekannte Lehrbücher (Fundamente der Mathematik, Deutschbuch 7, Physik Plus 7 etc.).
    3. Liest PDF-Outline / Bookmarks aus (für digitale Lehrbücher).
    4. Nutzt OpenAI Inhaltsverzeichnis-Analyse (Text oder Vision für Scans).
    """
    if not book.file_path or not os.path.exists(book.file_path):
        return None

    # Bereits segmentiert?
    if not force:
        existing_children = db.query(Material).filter_by(parent_id=book.id).count()
        if existing_children > 0:
            return db.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()

    # 1. Bekannte Vorlagen prüfen
    known = auto_segment_if_known(db, book, force=force)
    if known:
        return known

    pdf_path = Path(book.file_path)

    # 2. PDF Outline / Lesezeichen prüfen
    outline_chapters = extract_chapters_from_pdf_outline(pdf_path, book.page_count)
    if outline_chapters:
        return segment_book_material(db, book, outline_chapters, force=force)

    # 3. KI Inhaltsverzeichnis-Erkennung (Vision/Text)
    ai_chapters = extract_chapters_with_ai(pdf_path, book.page_count, title_hint=book.title)
    if ai_chapters:
        return segment_book_material(db, book, ai_chapters, force=force)

    return None


def trigger_background_book_segmentation(material_id: str):
    """
    Startet die automatische Buchsegmentierung asynchron in einem Hintergrund-Thread,
    damit Web-Uploads und Inbox-Verarbeitung blitzschnell antworten.
    """
    with _segmentation_locks_guard:
        if material_id in _segmentations_running:
            logger.info(f"📚 Segmentierung für {material_id} läuft bereits.")
            return
        # Sofort als laufend markieren, damit die Bücherliste es direkt anzeigen kann
        _segmentations_running.add(material_id)

    def _worker():
        from backend.app.database import SessionLocal
        db = SessionLocal()
        try:
            book = db.query(Material).filter_by(id=material_id).first()
            if not book:
                return
            logger.info(f"📚 Hintergrund-Segmentierung für Buch '{book.title}' ({book.id}) gestartet...")
            result = auto_detect_and_segment_book(db, book)
            if result:
                logger.info(f"✅ Hintergrund-Segmentierung für Buch '{book.title}' erfolgreich abgeschlossen: {len(result)} Kapitel.")
                try:
                    from backend.app.services.book_topic_catalog import extend_catalog_for_subject
                    extend_catalog_for_subject(db, book.subject_id)
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Themenkatalog nach Segmentierung von {book.id} nicht erweitert: {e}")
            else:
                logger.info(f"ℹ️ Für Buch '{book.title}' wurden keine separaten Kapitel extrahiert (bleibt Gesamtbuch).")
                from backend.app.services.page_renderer import page_renderer
                page_renderer.queue_material(book.id, book.file_path, book.mime_type, book.page_count)
        except Exception as e:
            logger.error(f"❌ Fehler bei Hintergrund-Segmentierung für {material_id}: {e}", exc_info=True)
        finally:
            db.close()
            with _segmentation_locks_guard:
                _segmentations_running.discard(material_id)

    thread = threading.Thread(target=_worker, daemon=True, name=f"BookSegmenter-{material_id}")
    thread.start()


def get_chapter_sections(material: Material, parent_book: Optional[Material] = None) -> List[Dict[str, Any]]:
    """
    Liefert die Unterabschnitte (Inhaltsverzeichnis-Einträge) für ein Kapitel-Material.
    Priorität:
    1. Gespeicherter `material.toc_json` im Material.
    2. Fallback für bekannte Bücher (z. B. Fundamente der Mathematik 7 nach Kapitelnummer / Titel).
    3. Leere Liste, falls keine Unterabschnitte bekannt sind.
    """
    if material.toc_json:
        try:
            parsed = json.loads(material.toc_json)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass

    # Fallback-Ermittlung anhand Titel oder Kapitelnummer
    title_search = f"{(parent_book.title if parent_book else '')} {material.title or ''} {material.filename or ''}".lower()

    if "fundamente" in title_search or "mathematik 7" in title_search or "mathe7" in title_search or "lehrbuch" in title_search:
        # Finde unit_number aus material.title oder dossier_order oder id
        for spec in FUNDAMENTE_MATHE_7_CHAPTERS:
            unit_num = spec.get("unit_number")
            matches = False
            if f"kapitel {unit_num}:" in (material.title or "").lower() or f"kapitel {unit_num} " in (material.title or "").lower():
                matches = True
            elif unit_num == 0 and ("titelei" in (material.title or "").lower() or "lernausgangslage" in (material.title or "").lower()):
                matches = True
            elif f"_ch{unit_num:02d}" in (material.id or "") or f"kapitel_{unit_num:02d}" in (material.filename or "").lower():
                matches = True
            elif material.dossier_order is not None and material.dossier_order == unit_num + 2:
                matches = True
            elif material.start_page == spec.get("book_start_page"):
                matches = True

            if matches:
                return spec.get("sections", [])

    if "à plus" in title_search or "vorkurs" in title_search or "franz" in title_search:
        return FRANZ_VORKURS_SECTIONS

    if "physik" in title_search:
        for p_chap in PHYSIK_PLUS_7_CHAPTERS:
            if (p_chap["title"].lower() in (material.title or "").lower()) or \
               (material.dossier_order is not None and material.dossier_order == p_chap["unit_number"] + 2) or \
               (material.start_page == p_chap["book_start_page"]):
                return p_chap.get("sections", [])

    if "deutschbuch" in title_search:
        for d_chap in DEUTSCHBUCH_7_CHAPTERS:
            if (d_chap["title"].lower() in (material.title or "").lower()) or \
               (material.dossier_order is not None and material.dossier_order == d_chap["unit_number"] + 2) or \
               (material.start_page == d_chap["book_start_page"]):
                return d_chap.get("sections", [])

    return []


def get_all_book_sections(book: Material) -> List[Dict[str, Any]]:
    """
    Liefert alle Abschnitte für ein gesamtes Buch (z. B. wenn das Buch nicht segmentiert ist
    oder als Gesamtwerk geöffnet wird), bezogen auf die absoluten PDF-Seiten des Gesamtbuchs.
    """
    title_lower = f"{(book.title or '')} {(book.filename or '')}".lower()
    all_sections: List[Dict[str, Any]] = []

    if "fundamente" in title_lower or "mathematik" in title_lower or "mathe7" in title_lower:
        for chap in FUNDAMENTE_MATHE_7_CHAPTERS:
            chap_title = chap.get("title", "")
            chap_start_pdf = chap.get("start_pdf_page", 1)
            chap_book_start = chap.get("book_start_page", chap_start_pdf)

            all_sections.append({
                "title": chap_title,
                "book_page": chap_book_start,
                "relative_page": chap_start_pdf,
                "level": 1
            })

            for sec in chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", chap_book_start),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    if "à plus" in title_lower or "vorkurs" in title_lower or "franz" in title_lower:
        return FRANZ_VORKURS_SECTIONS

    if "physik" in title_lower:
        for p_chap in PHYSIK_PLUS_7_CHAPTERS:
            chap_start_pdf = p_chap.get("start_pdf_page", p_chap["book_start_page"])
            all_sections.append({
                "title": p_chap["title"],
                "book_page": p_chap["book_start_page"],
                "relative_page": chap_start_pdf,
                "level": 1
            })
            for sec in p_chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", p_chap["book_start_page"]),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    if "deutschbuch" in title_lower:
        for d_chap in DEUTSCHBUCH_7_CHAPTERS:
            chap_start_pdf = d_chap.get("start_pdf_page", d_chap["book_start_page"])
            all_sections.append({
                "title": d_chap["title"],
                "book_page": d_chap["book_start_page"],
                "relative_page": chap_start_pdf,
                "level": 1
            })
            for sec in d_chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", d_chap["book_start_page"]),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    return []


