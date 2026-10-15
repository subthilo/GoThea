"""
Baut den Themenkatalog eines Fachs aus den Inhaltsverzeichnissen seiner Schulbücher auf und
verknüpft jedes Thema mit den Buchseiten, auf denen es steht (TopicBookRef).
"""
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.config import OPENAI_MODEL
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic, TopicBookRef
from backend.app.prompts.book_topic_catalog import BOOK_TOPIC_CATALOG_SYSTEM_PROMPT
from backend.app.services.document_kinds import BUCH
from backend.app.services import llm
from backend.app.services.topic_consolidation import IS_BOOK_OR_CHAPTER, merge_topics
from backend.app.services.topic_plans import fingerprint

logger = logging.getLogger(__name__)


@dataclass
class BookSection:
    material_id: str      # Buchkapitel
    book_title: str
    chapter_title: str
    title: str
    start_page: int       # Seite im Kapitel-PDF
    end_page: int
    book_page: Optional[int]


@dataclass
class CatalogGroup:
    name: str
    area: Optional[str]
    section_ids: List[str]
    topic_ids: List[str]


@dataclass
class CatalogPlan:
    subject_id: str
    subject_name: str
    sections: Dict[str, BookSection] = field(default_factory=dict)
    groups: List[CatalogGroup] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def omitted_sections(self) -> List[BookSection]:
        used = {sid for g in self.groups for sid in g.section_ids}
        return [s for sid, s in self.sections.items() if sid not in used]


def collect_book_sections(db: Session, subject_id: str) -> Dict[str, BookSection]:
    """Alle Abschnitte aller Bücher eines Fachs mit Seitenbereich im jeweiligen Kapitel-PDF."""
    sections: Dict[str, BookSection] = {}
    books = db.query(Material).filter_by(subject_id=subject_id, kind=BUCH, parent_id=None).order_by(Material.title).all()
    for book in books:
        chapters = db.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()
        for chapter in chapters:
            try:
                raw = json.loads(chapter.toc_json) if chapter.toc_json else []
            except ValueError:
                raw = []
            entries = sorted(
                (e for e in raw if isinstance(e, dict) and e.get("title")),
                key=lambda e: int(e.get("relative_page") or 1),
            )
            last_page = max(1, chapter.page_count or 1)
            for i, entry in enumerate(entries):
                start = min(max(1, int(entry.get("relative_page") or 1)), last_page)
                next_start = int(entries[i + 1].get("relative_page") or start) if i + 1 < len(entries) else last_page + 1
                end = min(last_page, max(start, next_start - 1))
                sections[f"s{len(sections) + 1}"] = BookSection(
                    material_id=chapter.id, book_title=book.title, chapter_title=chapter.title,
                    title=str(entry["title"]), start_page=start, end_page=end,
                    book_page=entry.get("book_page"),
                )
    return sections


def _existing_topics(db: Session, subject_id: str) -> Dict[str, Topic]:
    return {t.id: t for t in db.query(Topic).filter_by(subject_id=subject_id).all()}


def validate_catalog(groups: List[CatalogGroup], sections: Dict[str, BookSection], topics: Dict[str, Topic]) -> Optional[str]:
    section_ids = [sid for g in groups for sid in g.section_ids]
    unknown = [sid for sid in section_ids if sid not in sections]
    if unknown:
        return f"Unbekannte Abschnitte: {unknown[:5]}"
    if len(section_ids) != len(set(section_ids)):
        return "Abschnitte mehrfach vergeben"
    topic_ids = [tid for g in groups for tid in g.topic_ids]
    if sorted(topic_ids) != sorted(topics):
        return f"Bestehende Themen fehlen oder doppelt: fehlend={sorted(set(topics) - set(topic_ids))}"
    names = [g.name.strip().lower() for g in groups]
    if not all(names) or len(names) != len(set(names)):
        return "Themennamen leer oder nicht eindeutig"
    if any(not g.section_ids and not g.topic_ids for g in groups):
        return "Thema ohne Abschnitte und ohne bestehendes Thema"
    merged = [g.name for g in groups if len(g.topic_ids) > 1]
    if merged:
        return f"Bestehende Themen zusammengelegt in: {merged}"
    return None


def _ask_model(payload: dict) -> dict:
    return llm.chat_json(
        purpose="Buch-Themenkatalog",
        model=OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": BOOK_TOPIC_CATALOG_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )


def plan_catalog(db: Session, subject: Subject, ask: Optional[Callable[[dict], dict]] = None) -> CatalogPlan:
    ask = ask or _ask_model
    plan = CatalogPlan(subject_id=subject.id, subject_name=subject.name)
    plan.sections = collect_book_sections(db, subject.id)
    topics = _existing_topics(db, subject.id)
    if not plan.sections:
        plan.error = "Keine Buchabschnitte für dieses Fach"
        return plan

    books: Dict[str, Dict[str, list]] = {}
    for sid, sec in plan.sections.items():
        books.setdefault(sec.book_title, {}).setdefault(sec.chapter_title, []).append(
            {"id": sid, "titel": sec.title, "buchseite": sec.book_page})
    payload = {
        "fach": subject.name,
        "buecher": [
            {"titel": title, "kapitel": [{"kapitel": ch, "abschnitte": secs} for ch, secs in chapters.items()]}
            for title, chapters in books.items()
        ],
        "bestehende_themen": [
            {"id": t.id, "name": t.name, "bereich": t.area,
             "dokumente": [m.title for m in db.query(Material).filter(Material.topic_id == t.id).limit(6)]}
            for t in topics.values()
        ],
    }
    raw = ask(payload)
    groups = [
        CatalogGroup(
            name=str(g.get("name", "")).strip(),
            area=(g.get("bereich") or "").strip() or None,
            section_ids=[str(s) for s in g.get("abschnitte", [])],
            topic_ids=[str(t) for t in g.get("bestehende_themen", [])],
        )
        for g in raw.get("themen", []) if isinstance(g, dict)
    ]
    plan.error = validate_catalog(groups, plan.sections, topics)
    if not plan.error:
        plan.groups = groups
    return plan


def catalog_fingerprint(db: Session, subject_id: str) -> str:
    """Ändert sich, sobald Buchabschnitte oder Themen des Fachs sich ändern."""
    sections = [asdict(s) for s in collect_book_sections(db, subject_id).values()]
    topics = sorted((t.id, t.name) for t in db.query(Topic).filter_by(subject_id=subject_id))
    return fingerprint({"sections": sections, "topics": topics})


def catalog_plan_from_dict(data: dict) -> CatalogPlan:
    plan = CatalogPlan(subject_id=data["subject_id"], subject_name=data["subject_name"], error=data.get("error"))
    plan.sections = {sid: BookSection(**s) for sid, s in data["sections"].items()}
    plan.groups = [CatalogGroup(**g) for g in data["groups"]]
    return plan


def extend_catalog_for_subject(db: Session, subject_id: str) -> Optional[CatalogPlan]:
    """Nach dem Segmentieren eines neuen Buchs: Katalog des Fachs neu aufbauen, ohne bestehende
    Themen umzubenennen (Thea soll ihre Themen wiederfinden)."""
    if not llm.is_available():
        return None
    subject = db.get(Subject, subject_id)
    if subject is None:
        return None
    plan = plan_catalog(db, subject)
    if plan.error:
        logger.warning(f"Themenkatalog für {subject.name} nicht erweitert: {plan.error}")
        return plan
    apply_catalog(db, plan, rename_existing=False)
    logger.info(f"📚 Themenkatalog für {subject.name} aus den Büchern aktualisiert: {len(plan.groups)} Themen.")
    return plan


def apply_catalog(db: Session, plan: CatalogPlan, rename_existing: bool = True) -> None:
    if plan.error:
        raise ValueError(plan.error)
    # Buchverweise dieses Fachs neu aufbauen; Bücher/Kapitel selbst tragen kein Thema
    chapter_ids = {s.material_id for s in plan.sections.values()}
    db.query(TopicBookRef).filter(TopicBookRef.material_id.in_(chapter_ids)).delete(synchronize_session=False)
    db.query(Material).filter(Material.subject_id == plan.subject_id, IS_BOOK_OR_CHAPTER) \
        .update({"topic_id": None}, synchronize_session=False)

    for group in plan.groups:
        existing = [db.get(Topic, tid) for tid in group.topic_ids]
        target = next((t for t in existing if t.name.strip().lower() == group.name.lower()), None) \
            or (existing[0] if existing else None)
        if target is None:
            target = Topic(id=f"top_{uuid.uuid4().hex[:8]}", subject_id=plan.subject_id, name=group.name,
                           grade_level=7, rlp_level_code="E", standard_competencies="Aus Schulbuch-Inhaltsverzeichnis")
            db.add(target)
            db.flush()
        merge_topics(db, target, [t for t in existing if t.id != target.id])
        if rename_existing or not existing:
            target.name = group.name
        if rename_existing or not target.area:
            target.area = group.area or target.area
        for sid in group.section_ids:
            sec = plan.sections[sid]
            db.add(TopicBookRef(topic_id=target.id, material_id=sec.material_id, section_title=sec.title,
                                start_page=sec.start_page, end_page=sec.end_page, book_page=sec.book_page))
        db.flush()
    db.commit()
