"""
Ordnet alle gespeicherten Dokumente mit der aktuellen Dokumentanalyse neu ein.

Auf dem Pi (Staging):
    cd ~/GoThea && APP_ENV=staging .venv/bin/python scripts/reanalyze_materials.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main  # noqa: E402,F401  (registriert alle Modelle)
from backend.app.config import DATA_DIR  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.material import Material  # noqa: E402
from backend.app.services.page_renderer import page_renderer  # noqa: E402
from backend.app.services.reanalysis import reanalyze_all  # noqa: E402


def main():
    print(f"Datenverzeichnis: {DATA_DIR}")
    page_renderer.start()
    db = SessionLocal()
    try:
        reports = reanalyze_all(db)
        for r in reports:
            title = db.query(Material.title).filter_by(id=r.material_id).scalar()
            print(f"\n{r.material_id}  {title}")
            for c in r.changes or ["(unverändert)"]:
                print(f"   {c}")
            if r.removed_chapters:
                print(f"   {r.removed_chapters} Kapitel entfernt (kein Buch mehr)")
            if r.segmentation_triggered:
                print("   Segmentierung als Buch angestoßen")
        print(f"\n{len(reports)} Dokumente neu analysiert, {sum(1 for r in reports if r.changes)} geändert.")
    finally:
        db.close()
        page_renderer.stop()


if __name__ == "__main__":
    main()
