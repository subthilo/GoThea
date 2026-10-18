"""XP nur für Einsatz (services/effort_xp.py): wofür es Punkte gibt und wofür nicht."""
import json
from datetime import date, datetime, timedelta

from backend.app.models.practice_attempt import PracticeAttempt, PracticeEvent
from backend.app.services.effort_xp import awards, local_day, streak_days

T0 = datetime(2026, 10, 18, 8, 0)  # UTC, 10:00 in Berlin
FAMILY = {"a": "a", "a2": "a", "b": "b"}


def att(ex, stage, statuses, minutes=0, hints=0, solution=False, day=0):
    """Versuch mit Prüfungen in der gegebenen Reihenfolge; gelöst, wenn die letzte „richtig“ ist."""
    start = T0 + timedelta(days=day, minutes=minutes)
    a = PracticeAttempt(id=f"pat_{ex}_{stage}_{day}_{minutes}", exercise_id=ex, stage=stage, started_at=start,
                        last_activity_at=start, hints_used=hints, solution_shown=solution,
                        checks=len(statuses), failed_checks=statuses.count("noch_nicht"))
    a.events = [PracticeEvent(kind="check", created_at=start + timedelta(seconds=i),
                              data_json=json.dumps({"status": s})) for i, s in enumerate(statuses)]
    if statuses and statuses[-1] == "richtig":
        a.solved_at = start + timedelta(seconds=len(statuses))
        a.solved_first_try = statuses.count("noch_nicht") == 0 and not hints and not solution
    return a


def by_id(rows):
    return {r["attempt_id"]: r for r in rows}


def test_first_try_earns_no_more_than_a_struggle():
    clean = awards([att("a", 0, ["richtig"])], FAMILY)[0]
    struggle = awards([att("b", 0, ["noch_nicht", "noch_nicht", "richtig"], hints=1)], FAMILY)[0]
    assert clean["teile"] == {"versucht": 10, "neue_stufe": 5, "zu_ende": 5, "erster_des_tages": 10}
    assert struggle["teile"]["dranbleiben"] == 10 and struggle["teile"]["hilfe"] == 2
    assert struggle["xp"] > clean["xp"]


def test_unfinished_attempt_still_counts_and_opened_only_does_not():
    rows = awards([att("a", 1, ["noch_nicht"]), att("b", 0, [])], FAMILY)
    assert len(rows) == 1 and rows[0]["xp"] == 10 + 5 + 10 and not rows[0]["geloest"]


def test_caps_on_rechecks_and_help():
    row = awards([att("a", 0, ["noch_nicht"] * 6 + ["richtig"], hints=3, solution=True)], FAMILY)[0]
    assert row["teile"]["dranbleiben"] == 15 and row["teile"]["hilfe"] == 4


def test_same_task_and_stage_counts_only_twice_a_day():
    rows = awards([att("a", 0, ["richtig"], minutes=m) for m in (0, 5, 10)], FAMILY)
    assert [r["xp"] for r in rows] == [30, 15, 0]
    # Am nächsten Tag zählt es wieder (aber die Stufe ist nicht mehr neu)
    tomorrow = awards([att("a", 0, ["richtig"], minutes=m) for m in (0, 5, 10)] + [att("a", 0, ["richtig"], day=1)], FAMILY)
    assert tomorrow[-1]["teile"] == {"versucht": 10, "zu_ende": 5, "erster_des_tages": 10}


def test_repeat_bonus_after_struggle_on_the_same_stage_with_a_twin():
    rows = awards([att("a", 1, ["noch_nicht", "richtig"]), att("a2", 1, ["richtig"], day=1),
                   att("a2", 1, ["richtig"], day=2)], FAMILY)
    assert "wiederholt" not in rows[0]["teile"]
    assert rows[1]["teile"]["wiederholt"] == 5 and "neue_stufe" not in rows[1]["teile"]
    assert "wiederholt" not in rows[2]["teile"]  # auf Anhieb geschafft → nichts mehr offen


def test_day_is_berlin_time():
    late = datetime(2026, 10, 18, 22, 30)  # UTC → 00:30 am 19.10. in Berlin
    assert local_day(late) == date(2026, 10, 19)


def test_streak_forgives_one_missed_day():
    today = date(2026, 10, 18)
    d = lambda n: today - timedelta(days=n)  # noqa: E731
    assert streak_days([d(0), d(1), d(3), d(4)], today) == 4   # 16.10. fehlt: Serie hält
    assert streak_days([d(0), d(3)], today) == 1               # zwei Tage Pause: neu
    assert streak_days([d(2)], today) == 1                     # vorgestern geübt: noch aktiv
    assert streak_days([d(3)], today) == 0
