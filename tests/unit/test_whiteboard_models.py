from backend.app.models.whiteboard import TutorSession
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.test import Test

def test_create_tutor_session_model(db_session):
    subject = Subject(id="sub_math_wb", name="Mathe WB", color_code="#2563eb", icon="📐")
    db_session.add(subject)
    db_session.commit()

    session = TutorSession(
        subject_id="sub_math_wb",
        title="Mathe Übung",
        grade_level=7,
        board_state_json='[{"tool":"pen","color":"#ffffff","points":[]}]',
        snapshot_data_url="data:image/png;base64,mock",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.id.startswith("ses_")
    assert session.user_id == "usr_thea"
    assert session.subject_id == "sub_math_wb"
    assert session.subject.name == "Mathe WB"
    assert session.end_time is None
    assert "data:image/png" in session.snapshot_data_url

def test_tutor_session_relationships(db_session):
    subject = Subject(id="sub_bio_wb", name="Bio WB", color_code="#10b981", icon="🌿")
    topic = Topic(id="top_bio_cell", subject_id="sub_bio_wb", name="Zellteilung", grade_level=7)
    test_obj = Test(id="tst_bio_test", subject_id="sub_bio_wb", date="2026-10-20", kind="Test")
    db_session.add_all([subject, topic, test_obj])
    db_session.commit()

    session = TutorSession(
        subject_id="sub_bio_wb",
        topic_id="top_bio_cell",
        test_id="tst_bio_test",
        title="Zellbiologie Vorbereitung",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.subject.name == "Bio WB"
    assert session.topic.name == "Zellteilung"
    assert session.test.id == "tst_bio_test"
