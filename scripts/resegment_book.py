"""
Teilt ein Buch nach seiner (korrigierten) Kapiteltabelle neu ein und nimmt erschlossene Seiten und Notizen mit
(book_segmentation.resegment_keeping_pages). Die alte Tabelle sagt, wo die bisherigen Kapitel im Buch lagen.

Anlass: Das Deutsch-Arbeitsheft war nach der Tabelle des Schülerbuchs eingeteilt (24.10.2026).

Auf dem Pi (Staging), erst ansehen, dann anwenden (legt vorher eine Sicherung der Datenbank an):
    cd ~/GoThea-staging && .venv/bin/python scripts/resegment_book.py mat_5af366e1 --old-table deutschbuch_7.json
    cd ~/GoThea-staging && .venv/bin/python scripts/resegment_book.py mat_5af366e1 --old-table deutschbuch_7.json --apply
Danach den Dienst neu starten: der Hintergrund-Worker erschließt die Seiten, die vorher in keinem Kapitel lagen.
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.config import APP_ENV, DATA_DIR, DB_PATH  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.material import Material  # noqa: E402
from backend.app.services.book_segmentation import (  # noqa: E402
    _load_book_table, known_table, resegment_keeping_pages)


def backup_database() -> Path:
    target_dir = Path.home() / "GoThea-backups"
    target_dir.mkdir(exist_ok=True)
    target = target_dir / f"{APP_ENV}-app_data-{datetime.now():%Y%m%d-%H%M}-vor-neueinteilung.db"
    with sqlite3.connect(DB_PATH) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("book_id")
    parser.add_argument("--old-table", required=True, help="Tabelle in backend/app/book_tables/, nach der bisher eingeteilt war")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(f"Datenverzeichnis: {DATA_DIR} | {'ANWENDEN' if args.apply else 'nur Vorschau'}")

    db = SessionLocal()
    try:
        book = db.get(Material, args.book_id)
        if book is None or book.parent_id is not None:
            sys.exit(f"Kein Buch: {args.book_id}")
        new_spec = known_table(book.title)
        if not new_spec:
            sys.exit(f"Keine Kapiteltabelle für „{book.title}“")
        old_spec = _load_book_table(args.old_table)

        report = resegment_keeping_pages(db, book, old_spec, new_spec, dry_run=True)
        print(f"„{book.title}“: {book.page_count} Seiten")
        print("Neue Kapitel (PDF-Seiten):")
        for spec in new_spec:
            print(f"   {spec['unit_number']}: {spec['title']} – PDF {spec['start_pdf_page']}–{spec['end_pdf_page']}")
        print(f"Erschlossene Seiten zum Umziehen: {report['seiten']}, Notizen: {report['notizen']}")
        for abs_page, (order, page) in report["notizen_ziel"]:
            print(f"   Notiz auf Buch-PDF-Seite {abs_page} → {new_spec[order - 2]['title']}, Seite {page}")
        if report["ohne_ziel"]:
            sys.exit(f"Abbruch: Buch-PDF-Seiten ohne neues Kapitel: {report['ohne_ziel']}")

        if args.apply:
            print(f"Sicherung: {backup_database()}")
            report = resegment_keeping_pages(db, book, old_spec, new_spec)
            print("Fertig:", ", ".join(f"{title} ({n} S.)" for title, n in report["kapitel"]))
            print("Jetzt den Dienst neu starten, damit fehlende Seiten erschlossen werden.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
