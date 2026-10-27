"""Nächtliche Sicherung beider Umgebungen auf die Synology (Tagesstände per rsync --link-dest).

Läuft auf dem Pi aus ~/GoThea (Crontab des Benutzers pi, 02:30, vor dem Neustart um 03:22):
    .venv/bin/python scripts/backup_to_nas.py                 # sichern + aufräumen
    .venv/bin/python scripts/backup_to_nas.py --list          # Stände auf dem NAS
    .venv/bin/python scripts/backup_to_nas.py --restore 2026-10-27 staging ~/restore-test
                                                              # Stand herunterladen (Ziel muss neu sein)

Auf dem NAS (Ordner goThea-Backup, Benutzer gothea-backup, nur rsync, Schlüssel ~/.ssh/gothea_backup):
    snapshots/<Datum>/prod/      DATA_DIR Produktion ohne Datenbank, Seitenbilder-Cache, temp_uploads
    snapshots/<Datum>/staging/   ebenso für Staging
    snapshots/<Datum>/shared/    Cache der Seiten-Erschließung (neu erzeugen kostet Tokens)
    snapshots/<Datum>/db/        prod.db.gz, staging.db.gz (konsistent per SQLite-Backup)
Unveränderte Dateien sind feste Verknüpfungen auf den Vortag und kosten keinen Platz.
Aufbewahrt werden die letzten KEEP_DAILY Tage und je Woche der jüngste Stand für KEEP_WEEKLY Wochen.

Das Ergebnis jedes Laufs steht in data/shared/backup_status.json; der Eltern-Modus warnt,
wenn der letzte erfolgreiche Lauf zu alt ist oder der letzte Lauf scheiterte.
"""
import argparse
import gzip
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Set

KEEP_DAILY = 14
KEEP_WEEKLY = 8

HOME = Path.home()
DATA_ROOT = HOME / "GoThea" / "data"
ENVIRONMENTS = ["prod", "staging"]
STATUS_FILE = DATA_ROOT / "shared" / "backup_status.json"

NAS = "gothea-backup@192.168.1.2"
NAS_ROOT = "/volume1/goThea-Backup"
SNAPSHOTS = f"{NAS_ROOT}/snapshots"
SSH = f"ssh -i {HOME / '.ssh' / 'gothea_backup'} -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15"

# Neu erzeugbar oder ersetzt durch die gesicherte Kopie
EXCLUDES = ["/*/app_data.db", "/*/app_data.db-*", "/*/cache/", "/*/temp_uploads/"]


def keep_set(names: Iterable[str], today: date) -> Set[str]:
    """Welche Stände (Namen JJJJ-MM-TT) bleiben: die letzten KEEP_DAILY Tage, dazu je Woche der jüngste."""
    dated = sorted((date.fromisoformat(n), n) for n in names if _is_date(n))
    keep = {n for d, n in dated if (today - d).days < KEEP_DAILY}
    newest_per_week = {}
    for d, n in dated:
        if (today - d).days < KEEP_WEEKLY * 7:
            newest_per_week[d.isocalendar()[:2]] = n
    return keep | set(newest_per_week.values())


def _is_date(name: str) -> bool:
    try:
        date.fromisoformat(name)
        return True
    except ValueError:
        return False


def rsync(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["rsync", "-e", SSH, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"rsync {' '.join(args[-2:])}: {result.stderr.strip()[-500:]}")
    return result.stdout if capture else ""


def remote_snapshots() -> List[str]:
    out = rsync("--list-only", f"{NAS}:{SNAPSHOTS}/", capture=True)
    names = [line.split()[-1] for line in out.splitlines() if line.startswith("d")]
    return sorted(n for n in names if _is_date(n))


def dump_databases(target: Path) -> None:
    """SQLite-Backup der laufenden Datenbanken (konsistent trotz WAL), gepackt."""
    for env in ENVIRONMENTS:
        src = sqlite3.connect(f"file:{DATA_ROOT / env / 'app_data.db'}?mode=ro", uri=True)
        raw = target / f"{env}.db"
        dst = sqlite3.connect(raw)
        src.backup(dst)
        src.close()
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"Datenbank {env}: integrity_check schlägt fehl")
        dst.close()
        with raw.open("rb") as fin, gzip.open(f"{raw}.gz", "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout)
        raw.unlink()


def backup() -> dict:
    today = date.today().isoformat()
    with tempfile.TemporaryDirectory(prefix="gothea-backup-") as tmp:
        work = Path(tmp)
        # rsync legt auf dem NAS nur eine Ordnerebene je Lauf an
        (work / "empty").mkdir()
        rsync("-a", f"{work / 'empty'}/", f"{NAS}:{SNAPSHOTS}/")
        previous = [n for n in remote_snapshots() if n != today]

        db_dir = work / "db"
        db_dir.mkdir()
        dump_databases(db_dir)

        sources = [str(DATA_ROOT / env) for env in ENVIRONMENTS] + [str(DATA_ROOT / "shared"), str(db_dir)]
        args = ["-a", "--delete", "--stats"] + [f"--exclude={e}" for e in EXCLUDES]
        if previous:
            args.append(f"--link-dest={SNAPSHOTS}/{previous[-1]}/")
        stats = rsync(*args, *sources, f"{NAS}:{SNAPSHOTS}/{today}/", capture=True)

    removed = prune(today)
    sent = next((line.split(":", 1)[1].strip() for line in stats.splitlines()
                 if line.startswith("Total transferred file size")), "?")
    return {"snapshot": today, "transferred": sent, "removed": removed}


def prune(today_name: str) -> List[str]:
    names = remote_snapshots()
    keep = keep_set(names, date.fromisoformat(today_name)) | {today_name}
    drop = [n for n in names if n not in keep]
    if drop:
        with tempfile.TemporaryDirectory() as empty:
            rsync("-a", "--delete", *[f"--include=/{n}/***" for n in drop], "--exclude=*",
                  f"{empty}/", f"{NAS}:{SNAPSHOTS}/")
    return drop


def restore(snapshot: str, env: str, target: Path) -> None:
    """Lädt DATA_DIR einer Umgebung aus einem Stand nach target (ohne Seitenbilder-Cache) samt Datenbank."""
    if env not in ENVIRONMENTS:
        sys.exit(f"Umgebung muss eine von {ENVIRONMENTS} sein")
    if target.exists():
        sys.exit(f"{target} existiert schon – Ziel muss neu sein")
    target.mkdir(parents=True)
    rsync("-a", f"{NAS}:{SNAPSHOTS}/{snapshot}/{env}/", f"{target}/")
    packed = target / f"{env}.db.gz"
    rsync("-a", f"{NAS}:{SNAPSHOTS}/{snapshot}/db/{env}.db.gz", str(packed))
    with gzip.open(packed, "rb") as fin, (target / "app_data.db").open("wb") as fout:
        shutil.copyfileobj(fin, fout)
    packed.unlink()
    db = sqlite3.connect(target / "app_data.db")
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        sys.exit("Wiederhergestellte Datenbank: integrity_check schlägt fehl")
    materials = db.execute("SELECT count(*) FROM materials").fetchone()[0]
    print(f"{target}: Stand {snapshot} ({env}), {materials} Materialien. "
          f"Einsetzen: Dienst stoppen, DATA_DIR wegschieben, {target} an seine Stelle, Dienst starten.")


def write_status(ok: bool, **details) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = {}
    if STATUS_FILE.exists():
        try:
            old = json.loads(STATUS_FILE.read_text())
        except ValueError:
            pass
    status = {"last_run": now, "ok": ok, "last_success": now if ok else old.get("last_success"), **details}
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="Stände auf dem NAS auflisten")
    parser.add_argument("--restore", nargs=3, metavar=("DATUM", "UMGEBUNG", "ZIEL"))
    args = parser.parse_args()

    if args.list:
        print("\n".join(remote_snapshots()) or "(keine Stände)")
        return
    if args.restore:
        snapshot, env, target = args.restore
        restore(snapshot, env, Path(target).expanduser())
        return

    started = datetime.now()
    try:
        result = backup()
    except Exception as exc:
        write_status(False, error=str(exc))
        print(f"{started:%Y-%m-%d %H:%M} Sicherung fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)
    seconds = round((datetime.now() - started).total_seconds())
    write_status(True, seconds=seconds, **result)
    print(f"{started:%Y-%m-%d %H:%M} Sicherung {result['snapshot']} ok in {seconds} s, "
          f"übertragen {result['transferred']}, entfernt {result['removed'] or '–'}")


if __name__ == "__main__":
    main()
