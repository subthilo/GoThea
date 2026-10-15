from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic
from backend.app.services import topic_consolidation as tc
from backend.app.services.topic_catalog import build_catalog_text, protected_topic_names, resolve_topic


def _topic(db, tid, name, subject_id="sub_physics", area=None):
    t = Topic(id=tid, subject_id=subject_id, name=name, area=area, grade_level=7)
    db.add(t)
    db.commit()
    return t


def _material(db, mid, topic_id, title="Doc"):
    m = Material(id=mid, user_id="usr_thea", subject_id="sub_physics", topic_id=topic_id, title=title,
                 kind="Mitschrift", filename=f"{mid}.pdf", file_path=f"/tmp/{mid}.pdf")
    db.add(m)
    db.commit()
    return m


def test_resolve_topic_reuses_existing_case_insensitively(db_session):
    _topic(db_session, "top_hooke", "Hookesches Gesetz")
    topic = resolve_topic(db_session, "sub_physics", "hookesches gesetz", "Mechanik")
    assert topic.id == "top_hooke" and topic.area == "Mechanik"
    new = resolve_topic(db_session, "sub_physics", "Optische Linsen", "Optik")
    assert new.id != "top_hooke" and new.area == "Optik"
    assert resolve_topic(db_session, "sub_physics", "  ", None) is None


def test_catalog_text_lists_topics_with_area(db_session):
    _topic(db_session, "top_hooke", "Hookesches Gesetz", area="Mechanik")
    text = build_catalog_text(db_session)
    assert "Hookesches Gesetz [Mechanik]" in text


def test_validate_groups_rejects_bad_plans(db_session):
    a = _topic(db_session, "top_a", "Hookesches Gesetz")
    b = _topic(db_session, "top_b", "Hookesches Gesetz und Federkonstante")
    topics = {"top_a": a, "top_b": b}
    ok = [tc.TopicGroup("Hookesches Gesetz", "Mechanik", ["top_a", "top_b"])]
    assert tc.validate_groups(ok, topics, set()) is None
    assert "fehlen" in tc.validate_groups([tc.TopicGroup("X", None, ["top_a"])], topics, set())
    assert "umbenannt" in tc.validate_groups([tc.TopicGroup("Neu", None, ["top_a", "top_b"])], topics, {"Hookesches Gesetz"})


def test_consolidation_merges_references_and_drops_unused(db_session):
    protected = next(iter(protected_topic_names()["sub_physics"]))
    seed = db_session.query(Topic).filter_by(subject_id="sub_physics", name=protected).first()
    fine = _topic(db_session, "top_fine", f"{protected} – Detail")
    other = _topic(db_session, "top_other", "Hookesches Gesetz und Federkonstante")
    unused = _topic(db_session, "top_unused", "Physik der Klasse 7")
    _material(db_session, "mat_1", fine.id, "Notiz 1")
    _material(db_session, "mat_2", other.id, "Notiz 2")
    db_session.add(Dossier(id="dos_1", user_id="usr_thea", subject_id="sub_physics", topic_id=fine.id, title="Mappe"))
    db_session.commit()

    def fake_model(payload):
        ids = [t["id"] for t in payload["themen"]]
        groups = [{"name": protected, "bereich": "Mechanik", "ids": [seed.id, "top_fine"]},
                  {"name": "Hookesches Gesetz", "bereich": "Mechanik", "ids": ["top_other"]}]
        rest = [i for i in ids if i not in (seed.id, "top_fine", "top_other")]
        names = {t["id"]: t["name"] for t in payload["themen"]}
        groups += [{"name": names[i], "bereich": "Mechanik", "ids": [i]} for i in rest]
        return {"themen": groups}

    subject = db_session.get(Subject, "sub_physics")
    plan = tc.plan_for_subject(db_session, subject, ask=fake_model)
    assert plan.error is None and "top_unused" in plan.delete_unused
    tc.apply_plan(db_session, plan)

    assert db_session.get(Topic, "top_fine") is None and db_session.get(Topic, "top_unused") is None
    assert db_session.get(Material, "mat_1").topic_id == seed.id
    assert db_session.get(Dossier, "dos_1").topic_id == seed.id
    renamed = db_session.get(Topic, "top_other")
    assert renamed.name == "Hookesches Gesetz" and renamed.area == "Mechanik"
    assert db_session.get(Topic, seed.id).name == protected


def test_book_topics_do_not_count_and_are_cleared(db_session):
    chapter_topic = _topic(db_session, "top_chapter", "Register & Nachschlagen")
    book = Material(id="mat_book", user_id="usr_thea", subject_id="sub_physics", topic_id=chapter_topic.id,
                    title="Physik plus", kind="Buch", filename="b.pdf", file_path="/tmp/b.pdf")
    db_session.add(book)
    db_session.commit()

    subject = db_session.get(Subject, "sub_physics")
    plan = tc.plan_for_subject(db_session, subject, ask=lambda payload: {"themen": [
        {"name": t["name"], "bereich": "Mechanik", "ids": [t["id"]]} for t in payload["themen"]]})
    assert "top_chapter" in plan.delete_unused
    tc.apply_plan(db_session, plan)
    assert db_session.get(Material, "mat_book").topic_id is None
    assert db_session.get(Topic, "top_chapter") is None
