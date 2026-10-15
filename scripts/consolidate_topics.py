"""
Führt doppelte / zu feine Themen auf mittlere Ebene zusammen (KI-Vorschlag pro Fach, streng geprüft).

Auf dem Pi (Staging), erst ansehen, dann anwenden:
    cd ~/GoThea && APP_ENV=staging .venv/bin/python scripts/consolidate_topics.py
    cd ~/GoThea && APP_ENV=staging .venv/bin/python scripts/consolidate_topics.py --apply
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.config import DATA_DIR  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.taxonomy import Subject, Topic  # noqa: E402
from backend.app.services.topic_consolidation import apply_plan, plan_for_subject  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Plan anwenden (sonst nur anzeigen)")
    parser.add_argument("--subject", help="Nur dieses Fach (ID, z. B. sub_physics)")
    args = parser.parse_args()

    print(f"Datenverzeichnis: {DATA_DIR} | {'ANWENDEN' if args.apply else 'nur Vorschau'}")
    db = SessionLocal()
    try:
        query = db.query(Subject).filter_by(is_active=True)
        if args.subject:
            query = query.filter_by(id=args.subject)
        for subject in query.order_by(Subject.name).all():
            before = db.query(Topic).filter_by(subject_id=subject.id).count()
            if before == 0:
                continue
            plan = plan_for_subject(db, subject)
            print(f"\n=== {subject.name}: {before} Themen -> {len(plan.groups)} (+{len(plan.delete_unused)} ungenutzte entfernt)")
            if plan.error:
                print(f"   ÜBERSPRUNGEN, Vorschlag ungültig: {plan.error}")
                continue
            for g in sorted(plan.groups, key=lambda g: (g.area or "", g.name)):
                merged = [db.get(Topic, t).name for t in g.topic_ids if db.get(Topic, t).name != g.name]
                suffix = f"  <- {', '.join(merged)}" if merged else ""
                print(f"   [{g.area or '-'}] {g.name}{suffix}")
            if args.apply:
                apply_plan(db, plan)
                print(f"   angewendet: jetzt {db.query(Topic).filter_by(subject_id=subject.id).count()} Themen")
    finally:
        db.close()


if __name__ == "__main__":
    main()
