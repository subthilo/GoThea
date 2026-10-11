import pytest
from backend.app.models.timetable import TimetableSlot
from backend.app.models.taxonomy import Subject
from backend.app.models.user import User

def test_create_timetable_slot_model(db_session):
    sub = db_session.query(Subject).filter_by(id="sub_math").first()
    assert sub is not None

    slot = TimetableSlot(
        id="slot_unit_test_01",
        user_id="usr_thea",
        day_of_week="Montag",
        period=1,
        period_label="1. Std",
        start_time="07:45",
        end_time="08:30",
        subject_id=sub.id,
        subject_code="Ma",
        subject_name=sub.name,
        teacher="HORN",
        room="303",
        week_type="both",
        is_double_period=True,
        is_break=False,
        note="Doppelstunde Mathematik"
    )
    db_session.add(slot)
    db_session.commit()

    queried = db_session.query(TimetableSlot).filter_by(id="slot_unit_test_01").first()
    assert queried is not None
    assert queried.day_of_week == "Montag"
    assert queried.period == 1
    assert queried.teacher == "HORN"
    assert queried.room == "303"
    assert queried.subject is not None
    assert queried.subject.name == "Mathematik"
    assert queried.is_double_period is True
    assert queried.is_break is False
    assert queried.week_type == "both"
    assert queried.created_at is not None

def test_timetable_slot_break_without_subject(db_session):
    slot_break = TimetableSlot(
        id="slot_unit_test_break",
        user_id="usr_thea",
        day_of_week="Dienstag",
        period=5,
        period_label="5. Std",
        start_time="11:25",
        end_time="12:10",
        subject_id=None,
        subject_code="*GT-Mittag",
        subject_name="Ganztags-Mittag",
        custom_title="*GT-Mittag",
        teacher=None,
        room="Mensa",
        week_type="both",
        is_break=True
    )
    db_session.add(slot_break)
    db_session.commit()

    queried = db_session.query(TimetableSlot).filter_by(id="slot_unit_test_break").first()
    assert queried is not None
    assert queried.is_break is True
    assert queried.subject_id is None
    assert queried.subject is None
    assert queried.custom_title == "*GT-Mittag"

def test_timetable_alternating_week_filter(db_session):
    # A-Woche Slot
    slot_a = TimetableSlot(
        id="slot_turnus_a",
        user_id="usr_thea",
        day_of_week="Montag",
        period=5,
        subject_name="Sport",
        subject_code="*Sp",
        week_type="A"
    )
    # B-Woche Slot
    slot_b = TimetableSlot(
        id="slot_turnus_b",
        user_id="usr_thea",
        day_of_week="Montag",
        period=5,
        subject_name="Englisch",
        subject_code="En",
        week_type="B"
    )
    db_session.add_all([slot_a, slot_b])
    db_session.commit()

    # Filter für A-Woche
    slots_for_a = db_session.query(TimetableSlot).filter(
        TimetableSlot.day_of_week == "Montag",
        TimetableSlot.period == 5,
        TimetableSlot.week_type.in_(["both", "A"])
    ).all()
    assert len(slots_for_a) == 1
    assert slots_for_a[0].subject_code == "*Sp"

    # Filter für B-Woche
    slots_for_b = db_session.query(TimetableSlot).filter(
        TimetableSlot.day_of_week == "Montag",
        TimetableSlot.period == 5,
        TimetableSlot.week_type.in_(["both", "B"])
    ).all()
    assert len(slots_for_b) == 1
    assert slots_for_b[0].subject_code == "En"
