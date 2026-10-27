"""Nächtliche Sicherung: Aufbewahrungsregel (scripts/backup_to_nas.py) und Warnung im Eltern-Modus."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app import config
from backend.app.services.backup_status import backup_status
from backend.app.services.parent_auth import issue_token
from scripts.backup_to_nas import KEEP_DAILY, KEEP_WEEKLY, keep_set

NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def own_shared_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SHARED_DATA_DIR", tmp_path)


def test_keeps_recent_days_and_newest_per_week():
    today = date(2026, 10, 27)
    names = [(today - timedelta(days=i)).isoformat() for i in range(120)] + ["@eaDir"]
    keep = keep_set(names, today)
    for i in range(KEEP_DAILY):
        assert (today - timedelta(days=i)).isoformat() in keep
    older = [date.fromisoformat(n) for n in keep if (today - date.fromisoformat(n)).days >= KEEP_DAILY]
    # je Kalenderwoche höchstens einer, und zwar der Sonntag (jüngster Tag der Woche)
    assert len({d.isocalendar()[:2] for d in older}) == len(older)
    assert all(d.isoweekday() == 7 for d in older)
    assert all((today - d).days < KEEP_WEEKLY * 7 for d in older)
    assert "@eaDir" not in keep


def _write_status(**data):
    (config.SHARED_DATA_DIR / "backup_status.json").write_text(json.dumps(data))


def test_status_without_file_does_not_warn():
    assert backup_status(NOW)["state"] == "none"


def test_status_ok_stale_and_error():
    _write_status(ok=True, last_success=(NOW - timedelta(hours=20)).isoformat())
    assert backup_status(NOW)["state"] == "ok"
    _write_status(ok=True, last_success=(NOW - timedelta(days=3)).isoformat())
    assert backup_status(NOW)["state"] == "stale"
    _write_status(ok=False, last_success=(NOW - timedelta(hours=20)).isoformat(), error="rsync: Zeitüberschreitung")
    status = backup_status(NOW)
    assert status["state"] == "error" and "rsync" in status["error"]


def test_endpoint_only_for_parents(strict_client):
    assert strict_client.get("/api/v1/backup/status").status_code == 403
    res = strict_client.get("/api/v1/backup/status", headers={"X-Parent-Token": issue_token()[0]})
    assert res.status_code == 200 and res.json()["state"] == "none"
