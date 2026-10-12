from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.book import BookOverviewRead, BookDetailRead, BookChapterRead
from backend.app.services.book_seeder import seed_textbooks_if_empty

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
        Material.kind == "Buch",
        Material.user_id == user_id
    ).all()

    subjects_map = {s.id: s for s in db.query(Subject).all()}
    result: List[BookOverviewRead] = []

    for book in books:
        sub = subjects_map.get(book.subject_id)
        children = db.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()
        first_chap = children[0] if children else None

        cover_preview = f"/api/v1/materials/{first_chap.id}/preview?page=1" if first_chap else f"/api/v1/materials/{book.id}/preview?page=1"

        result.append(
            BookOverviewRead(
                id=book.id,
                title=book.title,
                authors="Mihaela Singer, Sorin Borodi et al." if "Mathematik" in book.title else None,
                grade_level=7,
                subject_id=book.subject_id,
                subject_name=sub.name if sub else "Mathematik",
                subject_icon=sub.icon if sub else "📐",
                subject_color=sub.color_code if sub else "#0284c7",
                total_pages=book.page_count,
                chapters_count=len(children),
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
    Kapitel, Seitenzahlen, Themen und Lerninhalte für den Bücher-Browser.
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

    chapters_out: List[BookChapterRead] = []
    for idx, chap in enumerate(children):
        t_name = topics_map.get(chap.topic_id) if chap.topic_id else None
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
                preview_url=f"/api/v1/materials/{chap.id}/preview"
            )
        )

    first_chap = children[0] if children else None
    cover_preview = f"/api/v1/materials/{first_chap.id}/preview?page=1" if first_chap else f"/api/v1/materials/{book.id}/preview?page=1"

    return BookDetailRead(
        id=book.id,
        title=book.title,
        authors="Mihaela Singer, Sorin Borodi et al." if "Mathematik" in book.title else None,
        grade_level=7,
        subject_id=book.subject_id,
        subject_name=sub.name if sub else "Mathematik",
        subject_icon=sub.icon if sub else "📐",
        subject_color=sub.color_code if sub else "#0284c7",
        total_pages=book.page_count,
        chapters_count=len(children),
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
    Liefert ein einzelnes Kapitel eines Buches mit Metadaten.
    """
    chap = db.query(Material).filter_by(id=chapter_id, parent_id=book_id, user_id=user_id).first()
    if not chap:
        raise HTTPException(status_code=404, detail="Kapitel im angegebenen Buch nicht gefunden.")

    topic = db.query(Topic).filter_by(id=chap.topic_id).first() if chap.topic_id else None

    # Kapitelnummer anhand von dossier_order ermitteln
    num = max(0, chap.dossier_order - 2) if chap.dossier_order else 0

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
        preview_url=f"/api/v1/materials/{chap.id}/preview"
    )

@router.post("/seed")
def seed_default_textbook(
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Importiert das vorinstallierte Mathematik-7 Lehrbuch auf Wunsch des Nutzers.
    """
    book_id = seed_textbooks_if_empty(db, user_id=user_id)
    return {"status": "success", "book_id": book_id}
