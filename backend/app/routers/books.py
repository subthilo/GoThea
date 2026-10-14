import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.book import BookOverviewRead, BookDetailRead, BookChapterRead
from backend.app.services.book_seeder import seed_textbooks_if_empty
from backend.app.services.book_segmentation import (
    auto_detect_and_segment_book,
    auto_segment_if_known,
    trigger_background_book_segmentation,
    segment_book_material,
    get_chapter_sections,
    get_all_book_sections,
)
from backend.app.services.parent_auth import require_parent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["Schulbücher"])

@router.get("", response_model=List[BookOverviewRead])
def list_books(
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert alle verfügbaren Schulbücher der Schülerin.
    """
    books = db.query(Material).filter(
        Material.kind.in_(["Buch", "Lehrbuch"]),
        Material.parent_id.is_(None),
        Material.user_id == user_id
    ).all()

    subjects_map = {s.id: s for s in db.query(Subject).all()}
    result: List[BookOverviewRead] = []

    for book in books:
        sub = subjects_map.get(book.subject_id)
        children = db.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()
        if not children:
            # Noch unsegmentiert: Segmentierung im Hintergrund anstoßen (KI-Analyse kann über eine Minute dauern)
            trigger_background_book_segmentation(book.id)

        first_chap = children[0] if children else None
        cover_preview = f"/api/v1/materials/{first_chap.id}/preview?page=1" if first_chap else f"/api/v1/materials/{book.id}/preview?page=1"

        author = "Cornelsen Verlag"
        if "Mathematik – Lehrbuch" in (book.title or ""):
            author = "Mihaela Singer, Sorin Borodi et al."
        elif "plus" in (book.title or "").lower() or "franz" in (book.title or "").lower():
            author = "Cornelsen Verlag (À plus!)"

        result.append(
            BookOverviewRead(
                id=book.id,
                title=book.title,
                authors=author,
                grade_level=7,
                subject_id=book.subject_id,
                subject_name=sub.name if sub else "Mathematik",
                subject_icon=sub.icon if sub else "📐",
                subject_color=sub.color_code if sub else "#0284c7",
                total_pages=book.page_count,
                chapters_count=len(children) if children else 1,
                summary=book.summary,
                cover_preview_url=cover_preview
            )
        )

    return result

@router.get("/{book_id}", response_model=BookDetailRead)
def get_book_detail(
    book_id: str,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert die Detailansicht eines Schulbuchs inklusive aller extrahierten
    Kapitel, Unterabschnitte, Seitenzahlen, Themen und Lerninhalte für den Bücher-Browser.
    """
    book = db.query(Material).filter_by(id=book_id, user_id=user_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Schulbuch nicht gefunden.")

    sub = db.query(Subject).filter_by(id=book.subject_id).first()
    topics_map = {t.id: t.name for t in db.query(Topic).all()}

    children = (
        db.query(Material)
        .filter_by(parent_id=book.id, user_id=user_id)
        .order_by(Material.dossier_order, Material.start_page)
        .all()
    )

    if not children:
        # Noch unsegmentiert: Segmentierung im Hintergrund anstoßen, bis dahin Gesamtbuch anzeigen
        trigger_background_book_segmentation(book.id)

    chapters_out: List[BookChapterRead] = []
    if children:
        for idx, chap in enumerate(children):
            t_name = topics_map.get(chap.topic_id) if chap.topic_id else None
            sec_list = get_chapter_sections(chap, parent_book=book)
            chapters_out.append(
                BookChapterRead(
                    id=chap.id,
                    chapter_number=idx,
                    title=chap.title,
                    kind=chap.kind,
                    topic_id=chap.topic_id,
                    topic_name=t_name,
                    start_page=chap.start_page or 1,
                    end_page=chap.end_page or (chap.start_page or 1) + chap.page_count - 1,
                    page_count=chap.page_count,
                    focus=chap.summary,
                    filename=chap.filename,
                    file_size=chap.file_size,
                    file_url=f"/api/v1/materials/{chap.id}/file",
                    preview_url=f"/api/v1/materials/{chap.id}/preview",
                    sections=sec_list
                )
            )
    else:
        # Fallback: Das gesamte Buch als eine Einheit anbieten, damit Thea es sofort öffnen kann!
        sec_list = get_all_book_sections(book)
        chapters_out.append(
            BookChapterRead(
                id=book.id,
                chapter_number=0,
                title="Gesamtlehrbuch (Vollständige Ausgabe)",
                kind="Buch",
                topic_id=None,
                topic_name=None,
                start_page=1,
                end_page=book.page_count,
                page_count=book.page_count,
                focus=book.summary or "Vollständiges Schulbuch",
                filename=book.filename,
                file_size=book.file_size,
                file_url=f"/api/v1/materials/{book.id}/file",
                preview_url=f"/api/v1/materials/{book.id}/preview",
                sections=sec_list
            )
        )

    first_chap = children[0] if children else None
    cover_preview = f"/api/v1/materials/{first_chap.id}/preview?page=1" if first_chap else f"/api/v1/materials/{book.id}/preview?page=1"

    author = "Cornelsen Verlag"
    if "Mathematik – Lehrbuch" in (book.title or ""):
        author = "Mihaela Singer, Sorin Borodi et al."

    return BookDetailRead(
        id=book.id,
        title=book.title,
        authors=author,
        grade_level=7,
        subject_id=book.subject_id,
        subject_name=sub.name if sub else "Mathematik",
        subject_icon=sub.icon if sub else "📐",
        subject_color=sub.color_code if sub else "#0284c7",
        total_pages=book.page_count,
        chapters_count=len(children) if children else 1,
        summary=book.summary,
        cover_preview_url=cover_preview,
        dossier_id=book.dossier_id,
        chapters=chapters_out
    )

@router.get("/{book_id}/chapters/{chapter_id}", response_model=BookChapterRead)
def get_book_chapter(
    book_id: str,
    chapter_id: str,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert ein einzelnes Kapitel eines Buches mit Metadaten und Unterabschnitten.
    """
    chap = db.query(Material).filter_by(id=chapter_id, parent_id=book_id, user_id=user_id).first()
    if not chap:
        raise HTTPException(status_code=404, detail="Kapitel im angegebenen Buch nicht gefunden.")

    book = db.query(Material).filter_by(id=book_id, user_id=user_id).first()
    topic = db.query(Topic).filter_by(id=chap.topic_id).first() if chap.topic_id else None

    # Kapitelnummer anhand von dossier_order ermitteln
    num = max(0, chap.dossier_order - 2) if chap.dossier_order else 0
    sec_list = get_chapter_sections(chap, parent_book=book)

    return BookChapterRead(
        id=chap.id,
        chapter_number=num,
        title=chap.title,
        kind=chap.kind,
        topic_id=chap.topic_id,
        topic_name=topic.name if topic else None,
        start_page=chap.start_page or 1,
        end_page=chap.end_page or (chap.start_page or 1) + chap.page_count - 1,
        page_count=chap.page_count,
        focus=chap.summary,
        filename=chap.filename,
        file_size=chap.file_size,
        file_url=f"/api/v1/materials/{chap.id}/file",
        preview_url=f"/api/v1/materials/{chap.id}/preview",
        sections=sec_list
    )

@router.post("/{book_id}/resegment", dependencies=[Depends(require_parent)])
def resegment_book(
    book_id: str,
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Segmentiert ein Schulbuch erneut und überschreibt vorhandene Kapitel-PDFs,
    z. B. nachdem eine bekannte Kapiteltabelle korrigiert wurde.
    """
    book = db.query(Material).filter_by(id=book_id, user_id=user_id, parent_id=None).first()
    if not book:
        raise HTTPException(status_code=404, detail="Schulbuch nicht gefunden.")

    try:
        chapters = auto_detect_and_segment_book(db, book, force=True)
    except Exception as e:
        db.rollback()
        logger.error(f"Neu-Segmentierung für {book.id} fehlgeschlagen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Neu-Segmentierung fehlgeschlagen.")

    if not chapters:
        raise HTTPException(status_code=422, detail="Für dieses Buch konnte keine Kapitelstruktur ermittelt werden.")

    return {"status": "success", "book_id": book.id, "chapters_count": len(chapters)}

@router.post("/seed", dependencies=[Depends(require_parent)])
def seed_default_textbook(
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Importiert das vorinstallierte Mathematik-7 Lehrbuch auf Wunsch des Nutzers.
    """
    book_id = seed_textbooks_if_empty(db, user_id=user_id)
    return {"status": "success", "book_id": book_id}
