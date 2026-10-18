"""Lunas Vorschlag und „Wiederholen“ aus den Versuchen (services/practice_plan.py)."""
from datetime import datetime, timedelta

from backend.app.models.practice_attempt import PracticeAttempt
from backend.app.services.practice_plan import plan

NOW = datetime(2026, 10, 17, 16, 0)
FAMILIES = [
    {"id": "a", "zwillinge": ["a2"]},
    {"id": "b", "zwillinge": ["b2"]},
    {"id": "c", "zwillinge": []},
]


def att(ex, stage, hours_ago, solved=False, first_try=None, failed=0, hints=0, solution=False, checks=None, board=None):
    at = NOW - timedelta(hours=hours_ago)
    if first_try is None:
        first_try = solved and not failed and not hints and not solution
    return PracticeAttempt(exercise_id=ex, stage=stage, board_id=board, started_at=at, last_activity_at=at,
                           solved_at=at if solved else None, solved_first_try=first_try if solved else None,
                           checks=checks if checks is not None else (failed + (1 if solved else 0)),
                           failed_checks=failed, hints_used=hints, solution_shown=solution)


def test_nothing_done_suggests_first_new_task():
    out = plan(FAMILIES, [], NOW)
    # Neu beginnt auf der leichtesten Stufe: Gedankengang (-1)
    assert out["vorschlag"] == {"art": "neu", "familie": "a", "exercise_id": "a", "stufe": -1, "board_id": None}
    assert out["stand"]["a"] == {"geschafft": [], "naechste_stufe": -1, "zuletzt": None}
    assert out["wiederholen"] == []


def test_stages_count_for_the_whole_family_and_go_on_with_the_last_one():
    attempts = [att("a", 0, 30, solved=True), att("b", 0, 5, solved=True), att("b2", 1, 4, solved=True)]
    out = plan(FAMILIES, attempts, NOW)
    assert out["stand"]["b"]["geschafft"] == [0, 1] and out["stand"]["b"]["naechste_stufe"] == 2
    assert out["vorschlag"]["art"] == "weiter" and out["vorschlag"]["familie"] == "b" and out["vorschlag"]["stufe"] == 2


def test_unfinished_attempt_is_resumed_on_its_board():
    attempts = [att("a", 0, 30, solved=True), att("a", 2, 2, failed=1, board="ses_1")]
    out = plan(FAMILIES, attempts, NOW, open_boards={"ses_1"})
    assert out["vorschlag"] == {"art": "weiter", "familie": "a", "exercise_id": "a", "stufe": 2, "board_id": "ses_1"}
    # Tafel inzwischen gelöscht: neu anfangen statt auf eine fehlende Tafel zu verweisen
    assert plan(FAMILIES, attempts, NOW)["vorschlag"]["board_id"] is None


def test_struggle_comes_back_next_day_with_a_twin():
    attempts = [att("a", 1, 26, solved=True, failed=2), att("b", 0, 1, solved=True)]
    out = plan(FAMILIES, attempts, NOW)
    assert out["wiederholen"] == [{"familie": "a", "exercise_id": "a2", "stufe": 1,
                                   "seit": (NOW - timedelta(hours=26)).isoformat()}]
    assert out["vorschlag"]["art"] == "wiederholen" and out["vorschlag"]["exercise_id"] == "a2"


def test_fresh_struggle_waits_but_stays_in_the_list():
    attempts = [att("a", 1, 1, solved=True, hints=1)]
    out = plan(FAMILIES, attempts, NOW)
    assert [r["familie"] for r in out["wiederholen"]] == ["a"]
    assert out["vorschlag"]["art"] == "weiter" and out["vorschlag"]["stufe"] == 2


def test_struggle_is_resolved_by_a_clean_solve_on_that_stage_or_higher():
    attempts = [att("a", 1, 40, solved=True, failed=1), att("a2", 1, 30, solved=True)]
    assert plan(FAMILIES, attempts, NOW)["wiederholen"] == []
    # Eine niedrigere Stufe auf Anhieb reicht nicht
    attempts = [att("a", 2, 40, solved=True, failed=1), att("a2", 1, 30, solved=True)]
    assert plan(FAMILIES, attempts, NOW)["wiederholen"][0]["stufe"] == 2


def test_only_opened_attempts_are_ignored():
    attempts = [att("a", 0, 1, checks=0)]
    out = plan(FAMILIES, attempts, NOW)
    assert out["stand"]["a"]["zuletzt"] is None and out["vorschlag"]["art"] == "neu"


def test_all_done_offers_repeat_even_if_fresh():
    families = [{"id": "c", "zwillinge": []}]
    attempts = [att("c", s, 5 - s, solved=True) for s in range(4)] + [att("c", 4, 0.5, solved=True, failed=1)]
    out = plan(families, attempts, NOW)
    assert out["stand"]["c"]["naechste_stufe"] is None
    assert out["vorschlag"] == {"art": "wiederholen", "familie": "c", "exercise_id": "c", "stufe": 4, "board_id": None}


def test_reasoning_stage_counts_like_any_other():
    out = plan(FAMILIES, [att("a", -1, 2, solved=True)], NOW)
    assert out["stand"]["a"]["geschafft"] == [-1] and out["stand"]["a"]["naechste_stufe"] == 0
    assert out["vorschlag"] == {"art": "weiter", "familie": "a", "exercise_id": "a", "stufe": 0, "board_id": None}
