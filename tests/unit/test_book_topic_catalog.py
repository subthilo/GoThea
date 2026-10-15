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
