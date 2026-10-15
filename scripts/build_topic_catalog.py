"""
Baut den Themenkatalog je Fach aus den Inhaltsverzeichnissen der Schulbücher auf
und verknüpft Themen mit Buchseiten. Bestehende Themen aus Theas Unterlagen werden darauf abgebildet.

Auf dem Pi (Staging), erst ansehen, dann anwenden:
    cd ~/GoThea && APP_ENV=staging .venv/bin/python scripts/build_topic_catalog.py [--subject sub_physics]
    cd ~/GoThea && APP_ENV=staging .venv/bin/python scripts/build_topic_catalog.py --apply
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.config import DATA_DIR  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.material import Material  # noqa: E402
from backend.app.models.taxonomy import Subject, Topic  # noqa: E402
from backend.app.services.book_topic_catalog import apply_catalog, plan_catalog  # noqa: E402
from backend.app.services.document_kinds import BUCH  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--subject")
    args = parser.parse_args()
    print(f"Datenverzeichnis: {DATA_DIR} | {'ANWENDEN' if args.apply else 'nur Vorschau'}")

    db = SessionLocal()
    try:
        subject_ids = [args.subject] if args.subject else [
            sid for (sid,) in db.query(Material.subject_id).filter_by(kind=BUCH, parent_id=None).distinct()]
        for subject in db.query(Subject).filter(Subject.id.in_(subject_ids)).order_by(Subject.name):
            plan = plan_catalog(db, subject)
            print(f"\n=== {subject.name}: {len(plan.sections)} Buchabschnitte -> {len(plan.groups)} Themen")
            if plan.error:
                print(f"   ÜBERSPRUNGEN: {plan.error}")
                continue
            for g in sorted(plan.groups, key=lambda g: (g.area or "", g.name)):
                secs = [plan.sections[s] for s in g.section_ids]
                pages = ", ".join(f"S.{s.book_page}" for s in secs if s.book_page)
                mapped = [db.get(Topic, t).name for t in g.topic_ids]
                info = f"  <= Thea: {'; '.join(mapped)}" if mapped else ""
                print(f"   [{g.area or '-'}] {g.name} ({len(secs)} Abschn. {pages}){info}")
            omitted = plan.omitted_sections
            if omitted:
                print(f"   weggelassen: {'; '.join(s.title for s in omitted[:12])}{' …' if len(omitted) > 12 else ''}")
            if args.apply:
                apply_catalog(db, plan)
                print(f"   angewendet: jetzt {db.query(Topic).filter_by(subject_id=subject.id).count()} Themen")
    finally:
        db.close()


if __name__ == "__main__":
    main()
