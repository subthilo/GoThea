import math
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.test import Test
from backend.app.models.study_block import StudyBlock
from backend.app.models.completed_task import CompletedTask
from backend.app.models.user import User
from backend.app.schemas.planner import (
    PlanTaskItem,
    DayPlan,
    PlanOverviewResponse,
    TestRead
)

def get_preparation_window(kind: str, grade_level: int) -> int:
    """
    Berechnet das Vorbereitungsfenster N(k, g) in Tagen.
    Formel aus docs/02_modules/planner_and_countdown.md
    """
    k = kind.strip()
    if k == "Test":
        if grade_level <= 4:
            return 4
        elif 5 <= grade_level <= 9:
            return 5
        else:
            return 7
    elif k in ("Klassenarbeit", "Klausur"):
        if grade_level <= 4:
            return 7
        elif 5 <= grade_level <= 9:
            return 10
        else:
            return 14
    return 7


def get_daily_budget_minutes(kind: str, grade_level: int) -> int:
    """
    Berechnet das tägliche Richt-Zeitbudget B(k, g) in Minuten.
    """
    k = kind.strip()
    if grade_level <= 4:
        return 15
    elif 5 <= grade_level <= 9:
        if k == "Test":
            return 20
        else:
            return 25
    else:
        return 35


def calculate_task_for_date(
    test: Test,
    target_date: date,
    grade_level: int,
    blocked_dates_all: set,
    blocked_dates_subject: Dict[date, set],
    completed_task_ids: set
) -> Optional[PlanTaskItem]:
    """
    Prüft, ob für 'test' am 'target_date' gelernt werden muss und welche Phase aktiv ist.
    """
    try:
        exam_date = datetime.strptime(test.date, "%Y-%m-%d").date()
    except ValueError:
        return None

    # Prüfung liegt in der Vergangenheit
    if target_date > exam_date:
        return None

    days_until_exam = (exam_date - target_date).days

    # Fall A: Heute ist Prüfungstag!
    if days_until_exam == 0:
        task_id = f"{test.id}_{target_date.isoformat()}"
        return PlanTaskItem(
            task_identifier=task_id,
            test_id=test.id,
            subject_id=test.subject_id,
            subject_name=test.subject.name if test.subject else "Fach",
            subject_icon=test.subject.icon if test.subject else "📚",
            subject_color=test.subject.color_code if test.subject else "#2563eb",
            test_kind=test.kind,
            test_date=test.date,
            test_note=test.note,
            days_until_test=0,
            phase_number=0,
            phase_name="Prüfungstag (Ruhemodus)",
            phase_description="Heute musst du nicht mehr lernen. Du bist vorbereitet. Viel Erfolg!",
            target_minutes=0,
            is_completed=True,
            is_exam_day=True
        )

    # Fall B: Vorbereitungstage ermitteln
    window_days = get_preparation_window(test.kind, grade_level)
    earliest_prep_date = exam_date - timedelta(days=window_days)

    # Liegt target_date noch vor Beginn des Lernfensters?
    if target_date < earliest_prep_date:
        return None

    # Ist der Tag für das Fach oder generell gesperrt?
    if target_date in blocked_dates_all or test.subject_id in blocked_dates_subject.get(target_date, set()):
        return None

    # 1. Alle verfügbaren Lerntage vor der Prüfung berechnen (Menge C = {c_1, ..., c_m})
    available_study_days: List[date] = []
    curr = earliest_prep_date
    while curr < exam_date:
        if curr not in blocked_dates_all and test.subject_id not in blocked_dates_subject.get(curr, set()):
            available_study_days.append(curr)
        curr += timedelta(days=1)

    m = len(available_study_days)
    if m == 0 or target_date not in available_study_days:
        return None

    # 1-basierter Index des Ziel-Tages
    i = available_study_days.index(target_date) + 1
    budget = get_daily_budget_minutes(test.kind, grade_level)
    task_id = f"{test.id}_{target_date.isoformat()}"
    is_completed = task_id in completed_task_ids

    # 2. Phasenallokation gemäß Kapitel 6.2
    # Phase 1: i <= floor(0.4 * m)
    # Phase 2: floor(0.4 * m) < i < m
    # Phase 3: i == m (letzter Tag vor Prüfung)
    cutoff_p1 = math.floor(0.4 * m)

    if m > 1 and i == m:
        phase_num = 3
        phase_name = "Phase 3: Letzte Runde (Generalprobe)"
        phase_desc = "Kurze Probeklausur unter realistischen Bedingungen, Formeln überfliegen und entspannen."
    elif i <= cutoff_p1:
        phase_num = 1
        phase_name = "Phase 1: Grundlagen & Verstehen"
        phase_desc = "Zusammenfassungen und Regeln studieren, Verständnisfragen klären."
    else:
        phase_num = 2
        phase_name = "Phase 2: Aktives Üben & Vertiefen"
        phase_desc = "Typische Rechen- und Textaufgaben auf der Tafel eigenständig lösen."

    return PlanTaskItem(
        task_identifier=task_id,
        test_id=test.id,
        subject_id=test.subject_id,
        subject_name=test.subject.name if test.subject else "Fach",
        subject_icon=test.subject.icon if test.subject else "📚",
        subject_color=test.subject.color_code if test.subject else "#2563eb",
        test_kind=test.kind,
        test_date=test.date,
        test_note=test.note,
        days_until_test=days_until_exam,
        phase_number=phase_num,
        phase_name=phase_name,
        phase_description=phase_desc,
        target_minutes=budget,
        is_completed=is_completed,
        is_exam_day=False
    )


def compute_plan_overview(db: Session, ref_date: Optional[date] = None) -> PlanOverviewResponse:
    if ref_date is None:
        ref_date = date.today()

    user = db.query(User).first()
    grade_level = user.grade_level if user else 7

    # Alle anstehenden Tests abrufen
    active_tests = db.query(Test).filter(Test.date >= ref_date.isoformat()).order_by(Test.date.asc()).all()

    # Alle Sperrtage für die nächsten 14 Tage abrufen
    end_window = ref_date + timedelta(days=14)
    blocks = db.query(StudyBlock).filter(
        StudyBlock.date >= ref_date.isoformat(),
        StudyBlock.date <= end_window.isoformat()
    ).all()

    blocked_all = set()
    blocked_subject: Dict[date, set] = {}
    for b in blocks:
        try:
            b_date = datetime.strptime(b.date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if b.type == "all" or not b.subject_id:
            blocked_all.add(b_date)
        else:
            if b_date not in blocked_subject:
                blocked_subject[b_date] = set()
            blocked_subject[b_date].add(b.subject_id)

    # Erledigte Aufgaben abrufen
    completed_rows = db.query(CompletedTask).all()
    completed_ids = {c.task_identifier for c in completed_rows}

    # Tagespläne für die nächsten 7 Tage generieren
    german_days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    german_months = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]

    next_7_days: List[DayPlan] = []
    for day_offset in range(7):
        cur_d = ref_date + timedelta(days=day_offset)
        d_str = cur_d.isoformat()
        day_label = f"{german_days[cur_d.weekday()]}, {cur_d.day}. {german_months[cur_d.month - 1]}"

        is_blk = cur_d in blocked_all
        blk_info = "Ganzer Tag frei (Sperrtag)" if is_blk else None

        tasks: List[PlanTaskItem] = []
        if not is_blk:
            for t in active_tests:
                task_item = calculate_task_for_date(
                    t, cur_d, grade_level, blocked_all, blocked_subject, completed_ids
                )
                if task_item:
                    tasks.append(task_item)

        total_min = sum(tsk.target_minutes for tsk in tasks if not tsk.is_completed)

        next_7_days.append(DayPlan(
            date=d_str,
            day_name=day_label,
            is_blocked=is_blk,
            block_info=blk_info,
            tasks=tasks,
            total_minutes=total_min
        ))

    today_plan = next_7_days[0]

    # Upcoming tests formatieren
    upcoming_list: List[TestRead] = []
    for t in active_tests:
        tr = TestRead(
            id=t.id,
            user_id=t.user_id,
            subject_id=t.subject_id,
            kind=t.kind,
            date=t.date,
            note=t.note,
            source_origin=t.source_origin,
            external_uid=t.external_uid,
            created_at=t.created_at,
            subject_name=t.subject.name if t.subject else "Fach",
            subject_icon=t.subject.icon if t.subject else "📚",
            subject_color=t.subject.color_code if t.subject else "#2563eb"
        )
        upcoming_list.append(tr)

    return PlanOverviewResponse(
        today_date=ref_date.isoformat(),
        grade_level=grade_level,
        today_plan=today_plan,
        upcoming_tests=upcoming_list,
        next_7_days=next_7_days
    )
