"""
Prüft alle Übungen (backend/app/exercise_sets/*.json), auch Entwürfe: eindeutige IDs und Zwillingsbezüge, Kopf
und Daten nach den Regeln ihres Typs, dann gegen die Datenbank – gibt es Fach, Thema und die Materialien in Quelle und Nachschlagen, liegt die
Seite im Material, passt die Buchseite?
Vor dem Einspielen neuer Übungen ausführen; Exit-Code 1, sobald eine Übung nicht passt. Am Ende der wirksame Stand:
freigegeben / wartend – mit den Freigaben der Eltern aus der App (Datenbank), die vor dem Status der Datei gelten.

Auf dem Pi (Staging):
    cd ~/GoThea-staging && .venv/bin/python scripts/check_exercises.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.config import DATA_DIR  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.services import practice_exercises as pe  # noqa: E402


def main() -> int:
    print(f"Datenverzeichnis: {DATA_DIR}")
    db = SessionLocal()
    pe.sync_releases(db)
    exercises = [pe.get_exercise(i, include_drafts=True) for i in pe.all_ids()]
    collection = pe.check_collection()
    for e in collection:
        print(f"   {e}")
    failed = len(collection)
    try:
        for ex in exercises:
            errors = pe.validate(ex) or pe.check_references(db, ex)
            if errors:
                failed += 1
                print(f"\n{ex['id']} ({ex['status']})")
                for e in errors:
                    print(f"   {e}")
    finally:
        db.close()
    waiting = [ex["id"] for ex in exercises if pe.is_draft(ex)]
    in_app = [ex["id"] for ex in exercises if ex.get("freigabe_in_app")]
    print(f"\nWartend ({len(waiting)}): {', '.join(waiting) or '–'}")
    print(f"In der App entschieden ({len(in_app)}): {', '.join(in_app) or '–'}")
    print(f"\n{len(exercises)} Übungen geprüft, {failed} mit Fehlern.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
