from datetime import date, timedelta
from backend.app.models.test import Test
from backend.app.services.planner import (
    get_preparation_window,
    get_daily_budget_minutes,
    calculate_task_for_date
)

def test_preparation_window_formulas():
    # 1. Grundschule (<= 4)
    assert get_preparation_window("Test", 3) == 4
    assert get_preparation_window("Klassenarbeit", 4) == 7

    # 2. Sekundarstufe I (5..9, wie Thea Klasse 7)
    assert get_preparation_window("Test", 7) == 5
    assert get_preparation_window("Klassenarbeit", 7) == 10

    # 3. Oberstufe (>= 10)
    assert get_preparation_window("Test", 11) == 7
    assert get_preparation_window("Klausur", 12) == 14


def test_daily_budget_formulas():
    # Grundschule
    assert get_daily_budget_minutes("Test", 3) == 15
    # Sek I
    assert get_daily_budget_minutes("Test", 7) == 20
    assert get_daily_budget_minutes("Klassenarbeit", 7) == 25
    # Oberstufe
    assert get_daily_budget_minutes("Klausur", 11) == 35


def test_phases_and_countdown_workflow():
    today = date(2026, 10, 10)
    exam_date = today + timedelta(days=6)

    test = Test(
        id="tst_unit_math",
        subject_id="sub_math",
        kind="Klassenarbeit",
        date=exam_date.isoformat(),
        note="Terme & Gleichungen"
    )

    # 1. Berechnung für heute (6 Tage vor Prüfung)
    task_today = calculate_task_for_date(
        test=test,
        target_date=today,
        grade_level=7,
        blocked_dates_all=set(),
        blocked_dates_subject={},
        completed_task_ids=set()
    )
    assert task_today is not None
    assert task_today.days_until_test == 6
    assert task_today.target_minutes == 25
    assert not task_today.is_exam_day
    # Bei 6 Tagen vor Prüfung und N=10 Tagen Fenster ist man in Phase 1 oder 2
    assert task_today.phase_number in (1, 2)

    # 2. Berechnung für den Tag vor der Prüfung (1 Tag vor Prüfung = Phase 3 Generalprobe)
    day_before_exam = exam_date - timedelta(days=1)
    task_p3 = calculate_task_for_date(
        test=test,
        target_date=day_before_exam,
        grade_level=7,
        blocked_dates_all=set(),
        blocked_dates_subject={},
        completed_task_ids=set()
    )
    assert task_p3 is not None
    assert task_p3.phase_number == 3
    assert "Generalprobe" in task_p3.phase_name

    # 3. Berechnung für den Prüfungstag selbst (Ruhemodus)
    task_exam_day = calculate_task_for_date(
        test=test,
        target_date=exam_date,
        grade_level=7,
        blocked_dates_all=set(),
        blocked_dates_subject={},
        completed_task_ids=set()
    )
    assert task_exam_day is not None
    assert task_exam_day.is_exam_day is True
    assert task_exam_day.target_minutes == 0
    assert task_exam_day.phase_number == 0
    assert "Ruhemodus" in task_exam_day.phase_name


def test_blocked_days_are_excluded():
    today = date(2026, 10, 10)
    exam_date = today + timedelta(days=4)

    test = Test(
        id="tst_blocked_test",
        subject_id="sub_bio",
        kind="Test",
        date=exam_date.isoformat()
    )

    # Heute als gesperrt markieren
    blocked_all = {today}
    task = calculate_task_for_date(
        test=test,
        target_date=today,
        grade_level=7,
        blocked_dates_all=blocked_all,
        blocked_dates_subject={},
        completed_task_ids=set()
    )
    assert task is None  # Kein Task an einem gesperrten Tag!
