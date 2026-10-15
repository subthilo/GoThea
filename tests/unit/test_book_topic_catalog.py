import json

from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic, TopicBookRef
from backend.app.services import book_topic_catalog as btc


def _book_with_chapter(db, sections, chapter_pages=12):
    book = Material(id="mat_pbook", user_id="usr_thea", subject_id="sub_physics", title="Physik plus", kind="Buch",
                    filename="b.pdf", file_path="/tmp/b.pdf", page_count=100)
    chapter = Material(id="mat_pbook_ch01", user_id="usr_thea", subject_id="sub_physics", parent_id="mat_pbook",
                       title="Mechanik", kind="Buchauszug", filename="c.pdf", file_path="/tmp/c.pdf",
                       page_count=chapter_pages, toc_json=json.dumps(sections), dossier_order=3)
    db.add_all([book, chapter])
    db.commit()


SECTIONS = [
    {"title": "1.1 Kraft & Wirkungen", "book_page": 6, "relative_page": 2},
    {"title": "1.3 Gewichtskraft & Gravitation", "book_page": 11, "relative_page": 7},
    {"title": "1.5 Reibung", "book_page": 13, "relative_page": 9},
    {"title": "1.6 Haft-, Gleit- und Rollreibung", "book_page": 13, "relative_page": 9},
    {"title": "Register", "book_page": 16, "relative_page": 12},
]


def test_collect_sections_with_page_ranges(db_session):
    _book_with_chapter(db_session, SECTIONS)
    secs = list(btc.collect_book_sections(db_session, "sub_physics").values())
    ranges = [(s.title, s.start_page, s.end_page) for s in secs]
    assert ranges == [
        ("1.1 Kraft & Wirkungen", 2, 6),
        ("1.3 Gewichtskraft & Gravitation", 7, 8),
        ("1.5 Reibung", 9, 9),                         # nächster Abschnitt beginnt auf derselben Seite
        ("1.6 Haft-, Gleit- und Rollreibung", 9, 11),
        ("Register", 12, 12),
    ]


def test_catalog_from_book_maps_existing_topics_and_links_pages(db_session):
    _book_with_chapter(db_session, SECTIONS)
    for t in db_session.query(Topic).filter_by(subject_id="sub_physics").all():
        db_session.delete(t)
    thea_topic = Topic(id="top_thea", subject_id="sub_physics", name="Masse und Gewichtskraft", grade_level=7)
    db_session.add(thea_topic)
    db_session.add(Material(id="mat_note", user_id="usr_thea", subject_id="sub_physics", topic_id="top_thea",
                            title="Notiz Gewichtskraft", kind="Mitschrift", filename="n.pdf", file_path="/tmp/n.pdf"))
    db_session.commit()

    def fake_model(payload):
        ids = {a["titel"]: a["id"] for b in payload["buecher"] for k in b["kapitel"] for a in k["abschnitte"]}
        assert [t["id"] for t in payload["bestehende_themen"]] == ["top_thea"]
        return {"themen": [
            {"name": "Kräfte und ihre Wirkungen", "bereich": "Mechanik", "abschnitte": [ids["1.1 Kraft & Wirkungen"]]},
            {"name": "Gewichtskraft und Gravitation", "bereich": "Mechanik",
             "abschnitte": [ids["1.3 Gewichtskraft & Gravitation"]], "bestehende_themen": ["top_thea"]},
            {"name": "Reibung", "bereich": "Mechanik",
             "abschnitte": [ids["1.5 Reibung"], ids["1.6 Haft-, Gleit- und Rollreibung"]]},
        ]}

    plan = btc.plan_catalog(db_session, db_session.get(Subject, "sub_physics"), ask=fake_model)
    assert plan.error is None
    assert [s.title for s in plan.omitted_sections] == ["Register"]
    btc.apply_catalog(db_session, plan)

    gravity = db_session.get(Topic, "top_thea")
    assert gravity.name == "Gewichtskraft und Gravitation" and gravity.area == "Mechanik"
    assert db_session.get(Material, "mat_note").topic_id == "top_thea"
    reibung = db_session.query(Topic).filter_by(subject_id="sub_physics", name="Reibung").one()
    refs = db_session.query(TopicBookRef).filter_by(topic_id=reibung.id).order_by(TopicBookRef.start_page).all()
    assert [(r.material_id, r.start_page, r.end_page) for r in refs] == [("mat_pbook_ch01", 9, 9), ("mat_pbook_ch01", 9, 11)]
    assert db_session.query(Topic).filter_by(subject_id="sub_physics").count() == 3


def test_validate_catalog_rejects_bad_plans(db_session):
    _book_with_chapter(db_session, SECTIONS)
    sections = btc.collect_book_sections(db_session, "sub_physics")
    topic = Topic(id="top_x", subject_id="sub_physics", name="X", grade_level=7)
    topics = {"top_x": topic}
    ok = [btc.CatalogGroup("X", "Mechanik", ["s1"], ["top_x"])]
    assert btc.validate_catalog(ok, sections, topics) is None
    assert "mehrfach" in btc.validate_catalog([btc.CatalogGroup("A", None, ["s1"], ["top_x"]),
                                               btc.CatalogGroup("B", None, ["s1"], [])], sections, topics)
    assert "fehlen" in btc.validate_catalog([btc.CatalogGroup("A", None, ["s1"], [])], sections, topics)
    assert "Unbekannte" in btc.validate_catalog([btc.CatalogGroup("A", None, ["s99"], ["top_x"])], sections, topics)


def test_existing_topics_must_not_be_merged(db_session):
    _book_with_chapter(db_session, SECTIONS)
    sections = btc.collect_book_sections(db_session, "sub_physics")
    topics = {tid: Topic(id=tid, subject_id="sub_physics", name=tid, grade_level=7) for tid in ("top_a", "top_b")}
    merged = [btc.CatalogGroup("Kräfte", "Mechanik", ["s1"], ["top_a", "top_b"])]
    assert "zusammengelegt" in btc.validate_catalog(merged, sections, topics)


def _fake_catalog(payload):
    ids = {a["titel"]: a["id"] for b in payload["buecher"] for k in b["kapitel"] for a in k["abschnitte"]}
    existing = [t["id"] for t in payload["bestehende_themen"]]
    groups = [{"name": "Reibung", "bereich": "Mechanik",
               "abschnitte": [ids["1.5 Reibung"], ids["1.6 Haft-, Gleit- und Rollreibung"]]}]
    groups += [{"name": f"Umbenannt {i}", "bereich": "Neu", "abschnitte": [], "bestehende_themen": [tid]}
               for i, tid in enumerate(existing)]
    return {"themen": groups}


def test_saved_plan_is_applied_exactly_and_rejected_after_changes(db_session):
    from backend.app.services.topic_plans import load_plan, save_plan
    _book_with_chapter(db_session, SECTIONS)
    subject = db_session.get(Subject, "sub_physics")
    plan = btc.plan_catalog(db_session, subject, ask=_fake_catalog)
    save_plan("catalog", subject.id, plan, btc.catalog_fingerprint(db_session, subject.id))

    restored = btc.catalog_plan_from_dict(load_plan("catalog", subject.id, btc.catalog_fingerprint(db_session, subject.id)))
    assert [(g.name, g.section_ids) for g in restored.groups] == [(g.name, g.section_ids) for g in plan.groups]
    assert restored.sections == plan.sections

    db_session.add(Topic(id="top_new", subject_id="sub_physics", name="Neues Thema", grade_level=7))
    db_session.commit()
    import pytest
    with pytest.raises(ValueError):
        load_plan("catalog", subject.id, btc.catalog_fingerprint(db_session, subject.id))


def test_automatic_extension_keeps_existing_topic_names(db_session, monkeypatch):
    _book_with_chapter(db_session, SECTIONS)
    for t in db_session.query(Topic).filter_by(subject_id="sub_physics").all():
        db_session.delete(t)
    db_session.add(Topic(id="top_known", subject_id="sub_physics", name="Masse und Gewichtskraft", area="Mechanik", grade_level=7))
    db_session.commit()
    monkeypatch.setattr("backend.app.config.OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(btc, "_ask_model", _fake_catalog)

    plan = btc.extend_catalog_for_subject(db_session, "sub_physics")

    assert plan.error is None
    known = db_session.get(Topic, "top_known")
    assert (known.name, known.area) == ("Masse und Gewichtskraft", "Mechanik")   # nicht umbenannt
    assert db_session.query(Topic).filter_by(subject_id="sub_physics", name="Reibung").one().area == "Mechanik"


def test_extension_is_skipped_without_api_key(db_session, monkeypatch):
    monkeypatch.setattr("backend.app.config.OPENAI_API_KEY", "")
    assert btc.extend_catalog_for_subject(db_session, "sub_physics") is None
