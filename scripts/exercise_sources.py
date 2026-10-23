"""
Bestand zu einem Thema für Übungs-Sessions (Skill /uebungen): Buchabschnitte mit Seiten, Theas eigene Unterlagen,
Seiten mit ihrer Handschrift und die Übungen, die es schon gibt – mit allen IDs für den Kopf neuer Übungen.

Auf dem Pi (Staging):
    cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py Chemie                 # Themen des Fachs
    cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py Chemie "Sicherheit"    # Bestand zum Thema
    cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py text mat_3a98b56c_ch01 1-2   # Seitentext
Seiten sind immer Seiten in der Datei (material_seite); bei Buchkapiteln steht die gedruckte Buchseite dabei.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.material import Material  # noqa: E402
from backend.app.models.material_page import MaterialPage  # noqa: E402
from backend.app.models.taxonomy import Subject, Topic, TopicBookRef  # noqa: E402
from backend.app.services import practice_exercises  # noqa: E402
from backend.app.services.document_kinds import BUCH, BUCHAUSZUG  # noqa: E402


def printed(material: Material, page: int) -> str:
    return f" (Buch S. {material.start_page + page - 1})" if material.start_page else ""


def find_subject(db, query: str) -> Subject:
    q = query.lower()
    subjects = db.query(Subject).all()
    hits = [s for s in subjects if s.id == query or s.name.lower() == q] or \
           [s for s in subjects if s.name.lower().startswith(q)]
    if len(hits) != 1:
        sys.exit(f"Fach „{query}“ nicht eindeutig. Fächer: " + ", ".join(sorted(s.name for s in subjects)))
    return hits[0]


def list_topics(db, subject: Subject) -> None:
    print(f"# {subject.name} ({subject.id}) – Themen\n")
    for t in db.query(Topic).filter_by(subject_id=subject.id).order_by(Topic.area, Topic.name):
        refs = db.query(TopicBookRef).filter_by(topic_id=t.id).count()
        docs = db.query(Material).filter_by(topic_id=t.id).count()
        print(f"- {t.area + ' › ' if t.area else ''}{t.name} ({t.id}): {refs} Buchabschnitte, {docs} Unterlagen")


def find_topic(db, subject: Subject, query: str) -> Topic:
    topics = db.query(Topic).filter_by(subject_id=subject.id).all()
    hits = [t for t in topics if t.id == query] or [t for t in topics if query.lower() in t.name.lower()]
    if len(hits) != 1:
        print(f"Thema „{query}“ nicht eindeutig ({len(hits)} Treffer).\n")
        list_topics(db, subject)
        sys.exit(1)
    return hits[0]


def handwriting_pages(db, material_id: str, first: int = 1, last: int = 10_000) -> list:
    rows = db.query(MaterialPage.page_number).filter(
        MaterialPage.material_id == material_id, MaterialPage.has_handwriting.is_(True),
        MaterialPage.page_number >= first, MaterialPage.page_number <= last)
    return sorted(n for (n,) in rows)


def report(db, subject: Subject, topic: Topic) -> None:
    print(f"# {subject.name} › {topic.area + ' › ' if topic.area else ''}{topic.name}")
    print(f"fach: {subject.id}   thema: {topic.id}\n")

    print("## Buchabschnitte (Themenkatalog)")
    refs = db.query(TopicBookRef).filter_by(topic_id=topic.id).all()
    for ref in sorted(refs, key=lambda r: (r.material_id, r.start_page)):
        chapter = db.get(Material, ref.material_id)
        book = chapter.parent if chapter else None
        if chapter is None:
            continue
        pages = f"S. {ref.start_page}–{ref.end_page}" if ref.end_page != ref.start_page else f"S. {ref.start_page}"
        span = f"Buch S. {ref.book_page}" if ref.book_page else ""
        print(f"- {book.title if book else chapter.title} › {ref.section_title}: {chapter.id} {pages} ({span})")
        hand = handwriting_pages(db, chapter.id, ref.start_page, ref.end_page)
        if hand:
            print(f"    Theas Handschrift auf S. {', '.join(f'{p}{printed(chapter, p)}' for p in hand)}")
    if not refs:
        print("- keine")

    print("\n## Theas Unterlagen zum Thema")
    docs = db.query(Material).filter(Material.topic_id == topic.id, Material.kind.notin_([BUCH, BUCHAUSZUG])).all()
    for m in sorted(docs, key=lambda m: m.created_at):
        flags = [f for f, on in (("auf Papier bearbeitet", m.worked_on_paper), ("bewertet", m.teacher_graded)) if on]
        hand = handwriting_pages(db, m.id)
        print(f"- {m.kind} „{m.title}“: {m.id}, {m.page_count} S.{', ' + ', '.join(flags) if flags else ''}"
              f"{f', Handschrift S. {hand}' if hand else ''}")
    if not docs:
        print("- keine")

    print("\n## Vorhandene Übungen")
    existing = [ex for ex in practice_exercises._load_all().values() if ex.get("thema") == topic.id]
    for ex in existing:
        q = ex["quelle"]
        print(f"- {ex['id']} ({ex['typ']}, {ex['ableitung']}, {ex['status']}): {q.get('material')} S. {q.get('seite')} "
              f"Nr. {q.get('nummer')}")
    if not existing:
        print("- keine")


def page_text(db, material_id: str, pages: str) -> None:
    material = db.get(Material, material_id)
    if material is None:
        sys.exit(f"Material {material_id} gibt es nicht")
    first, _, last = pages.partition("-")
    first, last = int(first), int(last or first)
    book = material.parent.title if material.parent else material.title
    for row in db.query(MaterialPage).filter(MaterialPage.material_id == material_id, MaterialPage.page_number >= first,
                                             MaterialPage.page_number <= last).order_by(MaterialPage.page_number):
        marks = [f for f, on in (("Handschrift", row.has_handwriting), ("Lehrkraft", row.has_teacher_marks),
                                 ("Lösungsseite", row.is_solution_page)) if on]
        print(f"===== {book} › {material.title}, S. {row.page_number}{printed(material, row.page_number)}"
              f"{' [' + ', '.join(marks) + ']' if marks else ''}")
        print(row.text)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    db = SessionLocal()
    try:
        if args[0] == "text" and len(args) == 3:
            page_text(db, args[1], args[2])
        elif len(args) == 1:
            list_topics(db, find_subject(db, args[0]))
        else:
            subject = find_subject(db, args[0])
            report(db, subject, find_topic(db, subject, args[1]))
    finally:
        db.close()


if __name__ == "__main__":
    main()
