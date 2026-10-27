"""Übernahme Staging → Produktion: Datenbank und Dateien als Ganzes, Theas Spuren geleert.

Läuft auf dem Pi (der Code muss vorher per ./deploy.sh prod auf Produktion sein):
    cd ~/GoThea && .venv/bin/python scripts/promote_staging_to_prod.py            # Vorschau
    cd ~/GoThea && .venv/bin/python scripts/promote_staging_to_prod.py --apply    # ausführen

Übernommen: Datenbank (Bücher, Dokumente, Erschließung, Themen, Tests, Stundenplan, Lernplan,
Ausmalbilder, Übungs-Freigaben), Materialdateien, Ausmalbild-Felder, Seitenbilder-Cache.
Geleert: Übungsversuche, Tafeln + Tutor-Verlauf, Seiten-Notizen, Bilder; nicht übernommen:
Design-Wahl, Handschrift-Ziffern, gespeicherte Tafel-Prüfungen, Logs.
Bleibt von Produktion: die Eltern-PIN (parent_auth.json).

Mit --apply: Produktion wird gestoppt, ihr ganzer Datenordner wandert nach ~/GoThea-backups/,
die neue Datenbank entsteht per SQLite-Backup aus der laufenden Staging-DB (Staging läuft weiter).
"""
import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STAGING_DATA = HOME / "GoThea" / "data" / "staging"
PROD_DATA = HOME / "GoThea" / "data" / "prod"
BACKUPS = HOME / "GoThea-backups"

# Theas Spuren – Reihenfolge: abhängige Tabellen zuerst (das Skript läuft ohne Fremdschlüssel-Kaskade)
CLEARED_TABLES = [
    "practice_events", "practice_attempts", "exercise_scores", "completed_tasks",
    "tutor_messages", "tutor_exercises", "tutor_sessions",
    "page_annotations",
    "painting_slots", "paintings",
]
COPIED_DIRS = ["materials", "coloring", "cache"]
KEPT_FROM_PROD = ["parent_auth.json"]


def counts(db: sqlite3.Connection) -> dict:
    return {t: db.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in CLEARED_TABLES}


def staged_paths(db: sqlite3.Connection) -> int:
    return db.execute(
        "SELECT count(*) FROM materials WHERE file_path LIKE ?", (f"{STAGING_DATA}/%",)
    ).fetchone()[0]


def dir_size(path: Path) -> str:
    out = subprocess.run(["du", "-sh", str(path)], capture_output=True, text=True).stdout
    return out.split()[0] if out else "?"


def preview() -> None:
    db = sqlite3.connect(f"file:{STAGING_DATA / 'app_data.db'}?mode=ro", uri=True)
    print("Staging → Produktion (Vorschau)\n")
    print("Wird geleert:")
    for table, n in counts(db).items():
        print(f"  {table:20} {n}")
    print(f"\nPfade umschreiben: {staged_paths(db)} Materialien ({STAGING_DATA} → {PROD_DATA})")
    print("\nOrdner kopieren:")
    for name in COPIED_DIRS:
        print(f"  {name:12} {dir_size(STAGING_DATA / name)}")
    print(f"\nProduktion jetzt ({dir_size(PROD_DATA)}) wandert nach {BACKUPS}/; PIN bleibt.")
    print("\nAusführen mit --apply")


def wait_for_health(port: int) -> bool:
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/api/health", timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


def apply() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    new_dir = PROD_DATA.with_name(f"prod-neu-{stamp}")
    old_backup = BACKUPS / f"prod-data-{stamp}-vor-uebernahme"
    new_dir.mkdir()

    # 1. Datenbank: konsistente Kopie aus der laufenden Staging-DB, dann zurücksetzen
    print("Datenbank kopieren …")
    src = sqlite3.connect(f"file:{STAGING_DATA / 'app_data.db'}?mode=ro", uri=True)
    dst = sqlite3.connect(new_dir / "app_data.db")
    src.backup(dst)
    src.close()
    before = counts(dst)
    for table in CLEARED_TABLES:
        dst.execute(f'DELETE FROM "{table}"')
    dst.execute(
        "UPDATE materials SET file_path = replace(file_path, ?, ?) WHERE file_path LIKE ?",
        (f"{STAGING_DATA}/", f"{PROD_DATA}/", f"{STAGING_DATA}/%"),
    )
    dst.commit()
    left = staged_paths(dst)
    if left or any(counts(dst).values()):
        sys.exit(f"Abbruch: Reste in der neuen DB (Pfade {left}, {counts(dst)}); Produktion unverändert.")
    dst.execute("VACUUM")
    dst.close()
    print("  geleert:", ", ".join(f"{t} {n}" for t, n in before.items() if n))

    # 2. Dateien (cp -a: Zeitstempel bleiben, der Seiten-Cache bleibt gültig)
    for name in COPIED_DIRS:
        print(f"{name} kopieren ({dir_size(STAGING_DATA / name)}) …")
        subprocess.run(["cp", "-a", str(STAGING_DATA / name), str(new_dir / name)], check=True)
    for name in KEPT_FROM_PROD:
        if (PROD_DATA / name).exists():
            shutil.copy2(PROD_DATA / name, new_dir / name)

    # 3. Umschalten: Produktion stoppen, alten Ordner sichern, neuen einsetzen, starten
    print("Produktion stoppen und umschalten …")
    subprocess.run(["sudo", "systemctl", "stop", "gothea"], check=True)
    BACKUPS.mkdir(exist_ok=True)
    shutil.move(str(PROD_DATA), str(old_backup))
    new_dir.rename(PROD_DATA)
    subprocess.run(["sudo", "systemctl", "start", "gothea"], check=True)
    if not wait_for_health(8000):
        sys.exit(f"Produktion antwortet nicht. Logs: sudo journalctl -u gothea -n 50; alter Stand: {old_backup}")
    print(f"Fertig. Produktion läuft mit den Staging-Daten; alter Stand: {old_backup}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="wirklich übernehmen")
    args = parser.parse_args()
    apply() if args.apply else preview()
