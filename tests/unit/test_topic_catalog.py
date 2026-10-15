from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic
from backend.app.services import topic_consolidation as tc
from backend.app.services.seeder import seed_database
from backend.app.services.topic_catalog import build_catalog_text, resolve_topic


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
    assert tc.validate_groups([tc.TopicGroup("Hookesches Gesetz", "Mechanik", ["top_a", "top_b"])], topics) is None
    assert "fehlen" in tc.validate_groups([tc.TopicGroup("X", None, ["top_a"])], topics)
    dup = [tc.TopicGroup("X", None, ["top_a"]), tc.TopicGroup("x", None, ["top_b"])]
    assert "eindeutig" in tc.validate_groups(dup, topics)


def test_consolidation_merges_references_and_drops_unused(db_session):
    coarse = _topic(db_session, "top_coarse", "Mechanik: Kräfte & Masse (Test)")
    fine = _topic(db_session, "top_fine", "Masse und Gewichtskraft: proportionale Zuordnung")
    other = _topic(db_session, "top_other", "Hookesches Gesetz und Federkonstante")
    _topic(db_session, "top_unused", "Physik der Klasse 7 (Test)")
    _material(db_session, "mat_1", fine.id, "Notiz 1")
    _material(db_session, "mat_2", other.id, "Notiz 2")
    _material(db_session, "mat_3", coarse.id, "Notiz 3")
    db_session.add(Dossier(id="dos_1", user_id="usr_thea", subject_id="sub_physics", topic_id=fine.id, title="Mappe"))
    db_session.commit()

    def fake_model(payload):
        ids = {t["id"] for t in payload["themen"]}
        assert ids == {"top_coarse", "top_fine", "top_other"}
        return {"themen": [
            {"name": "Masse und Gewichtskraft", "bereich": "Mechanik", "ids": ["top_fine", "top_coarse"]},
            {"name": "Hookesches Gesetz", "bereich": "Mechanik", "ids": ["top_other"]},
        ]}

    subject = db_session.get(Subject, "sub_physics")
    plan = tc.plan_for_subject(db_session, subject, ask=fake_model)
    assert plan.error is None and "top_unused" in plan.delete_unused
    tc.apply_plan(db_session, plan)

    target = db_session.get(Topic, "top_fine")
    assert target.name == "Masse und Gewichtskraft" and target.area == "Mechanik"
    assert db_session.get(Topic, "top_coarse") is None and db_session.get(Topic, "top_unused") is None
    assert db_session.get(Material, "mat_3").topic_id == "top_fine"
    assert db_session.get(Dossier, "dos_1").topic_id == "top_fine"
    assert db_session.get(Topic, "top_other").name == "Hookesches Gesetz"


def test_seeder_does_not_recreate_removed_placeholder_topics(db_session):
    placeholder = db_session.query(Topic).filter_by(subject_id="sub_physics").first()
    name = placeholder.name
    db_session.delete(placeholder)
    db_session.commit()
    seed_database(db_session)
    assert db_session.query(Topic).filter_by(subject_id="sub_physics", name=name).count() == 0


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


def test_chapters_with_unusual_kind_do_not_count(db_session):
    topic = _topic(db_session, "top_appendix", "Fundamente der Mathematik (Test)")
    db_session.add(Material(id="mat_ch10", user_id="usr_thea", subject_id="sub_physics", topic_id=topic.id,
                            parent_id="mat_somebook", title="Anhang & Lösungen", kind="Lösungsheft",
                            filename="c.pdf", file_path="/tmp/c.pdf"))
    db_session.commit()
    plan = tc.plan_for_subject(db_session, db_session.get(Subject, "sub_physics"), ask=lambda p: {"themen": []})
    assert "top_appendix" in plan.delete_unused


def test_consolidation_plan_roundtrip_and_fingerprint(db_session):
    from dataclasses import asdict
    _topic(db_session, "top_a", "Hookesches Gesetz")
    plan = tc.ConsolidationPlan("sub_physics", "Physik", [tc.TopicGroup("Hookesches Gesetz", "Mechanik", ["top_a"])], ["top_x"])
    assert tc.consolidation_plan_from_dict(asdict(plan)) == plan
    before = tc.consolidation_fingerprint(db_session, "sub_physics")
    _material(db_session, "mat_new", "top_a")
    assert tc.consolidation_fingerprint(db_session, "sub_physics") != before


def test_consolidation_never_merges_or_renames_book_topics(db_session):
    from backend.app.models.taxonomy import TopicBookRef
    wald = _topic(db_session, "top_wald", "Der Wald als Ökosystem")
    nahrung = _topic(db_session, "top_nahrung", "Nahrungsbeziehungen im Wald")
    stray = _topic(db_session, "top_stray", "Waldtiere (eigene Notiz)")
    db_session.add(Material(id="mat_ch", user_id="usr_thea", subject_id="sub_physics", title="Kap", kind="Buchauszug",
                            parent_id="mat_b", filename="k.pdf", file_path="/tmp/k.pdf"))
    for t in (wald, nahrung):
        db_session.add(TopicBookRef(topic_id=t.id, material_id="mat_ch", section_title=t.name, start_page=1, end_page=2))
    _material(db_session, "mat_s", stray.id, "Notiz Waldtiere")
    db_session.commit()

    merged = tc.plan_for_subject(db_session, db_session.get(Subject, "sub_physics"), ask=lambda p: {"themen": [
        {"name": "Wald", "bereich": "Ökologie", "ids": ["top_wald", "top_nahrung", "top_stray"]}]})
    assert "Buchthemen zusammengelegt" in merged.error

    ok = tc.plan_for_subject(db_session, db_session.get(Subject, "sub_physics"), ask=lambda p: {"themen": [
        {"name": "Wald als Lebensraum", "bereich": "Ökologie", "ids": ["top_wald", "top_stray"]},
        {"name": "Nahrung neu benannt", "bereich": "Ökologie", "ids": ["top_nahrung"]}]})
    assert ok.error is None
    tc.apply_plan(db_session, ok)
    assert db_session.get(Topic, "top_wald").name == "Der Wald als Ökosystem"      # Buchthema behält Namen
    assert db_session.get(Topic, "top_nahrung").name == "Nahrungsbeziehungen im Wald"
    assert db_session.get(Topic, "top_stray") is None
    assert db_session.get(Material, "mat_s").topic_id == "top_wald"
