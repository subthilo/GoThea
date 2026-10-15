"""Suche in Theas Unterlagen: Index folgt den Seiten, Fundstellen, Lösungen nur für Eltern."""
from sqlalchemy import text

from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
from backend.app.models.taxonomy import Topic, TopicBookRef
from backend.app.services import material_search
from backend.app.services.material_search import ensure_search_index, query_terms, search
from backend.app.services.parent_auth import issue_token


def _material(db, mid, title, kind="Mitschrift", subject="sub_math", pages=(), **kw):
    db.add(Material(id=mid, subject_id=subject, title=title, kind=kind, filename=f"{mid}.pdf",
                    file_path=f"/tmp/{mid}.pdf", page_count=max(1, len(pages)), **kw))
    db.flush()
    for n, body in enumerate(pages, start=1):
        db.add(MaterialPage(material_id=mid, page_number=n, content_key=f"{mid}_p{n}", text=body))
    db.commit()


def _filler(db, n=6):
    """Unbeteiligte Dokumente: BM25 braucht eine Sammlung, sonst wiegt jedes Wort gleich wenig."""
    for i in range(n):
        _material(db, f"mat_f{i}", f"Thema {i}", pages=[f"Text über Vulkane, Gedichte und Vokabeln {i}"])


def _ids(hits):
    return [(h.material_id, h.page) for h in hits]


def test_query_terms_drop_filler_words_and_stem():
    assert query_terms("Wie geht der Dreisatz?") == ["dreisatz"]
    assert query_terms("Wie teilt man durch Brüche?") == ["teil", "durch", "brüch"]
    assert query_terms("Was ist eine antiproportionale Zuordnung") == ["antiproportional", "zuordnung"]


def test_finds_pages_by_word_start_and_ignores_umlauts(db_session):
    _filler(db_session)
    _material(db_session, "mat_a", "Mathe", pages=["Brüche kürzen und erweitern", "Dezimalzahlen"])
    assert _ids(search(db_session, "Bruche")) == [("mat_a", 1)]          # Umlaut egal
    assert _ids(search(db_session, "Wie erweitert man?")) == [("mat_a", 1)]  # Wortanfang „erweiter“


def test_title_counts_for_pages_without_the_word(db_session):
    _filler(db_session)
    _material(db_session, "mat_k", "Kehrwert und Zuordnungen", pages=["«S: 1/3 → 3/1»"])
    _material(db_session, "mat_x", "Zahlen", pages=["Der Kehrwert wird hier nur erwähnt, sonst geht es um Zahlen."])
    assert _ids(search(db_session, "Kehrwert"))[0] == ("mat_k", 1)


def test_index_follows_page_changes_and_deletion(db_session):
    _material(db_session, "mat_r", "Blatt", pages=["Hebel", "Rolle", "Flaschenzug"])
    page = db_session.query(MaterialPage).filter_by(material_id="mat_r", page_number=2).one()
    page.text = "Schiefe Ebene"
    db_session.commit()
    assert _ids(search(db_session, "Rolle")) == []
    assert _ids(search(db_session, "Ebene")) == [("mat_r", 2)]

    db_session.get(Material, "mat_r").title = "Einfache Maschinen"
    db_session.commit()
    assert {h.title for h in search(db_session, "Hebel")} == {"Einfache Maschinen"}

    db_session.delete(db_session.get(Material, "mat_r"))
    db_session.commit()
    assert search(db_session, "Flaschenzug") == []
    assert db_session.execute(text("SELECT count(*) FROM page_search")).scalar() == 0


def test_solutions_are_hidden_for_thea_but_not_for_parents(db_session):
    _material(db_session, "mat_s", "Zyklus", kind="Arbeitsblatt", pages=["Zyklus Aufgaben", "Zyklus Lösungen"],
              solution_pages_json="[2]")
    _material(db_session, "mat_l", "Anhang & Lösungen", kind="Lösungsheft", pages=["Zyklus Lösung S. 40"])
    _material(db_session, "mat_m", "Notiz", pages=["Zyklus Erwartungshorizont"])
    db_session.query(MaterialPage).filter_by(material_id="mat_m").one().is_solution_page = True
    db_session.commit()
    assert _ids(search(db_session, "Zyklus")) == [("mat_s", 1)]
    parent_hits = search(db_session, "Zyklus", include_solutions=True)
    assert set(_ids(parent_hits)) == {("mat_s", 1), ("mat_s", 2), ("mat_l", 1), ("mat_m", 1)}
    assert all(h.is_solution for h in parent_hits if h.material_id != "mat_s" or h.page == 2)


def test_book_chapter_hits_name_the_printed_page(db_session):
    _material(db_session, "mat_book", "Fundamente der Mathematik 7", kind="Buch")
    _material(db_session, "mat_book_ch06", "Kapitel 6: Flächen", kind="Buchauszug", parent_id="mat_book",
              start_page=195, pages=["Flächen", "Vierecke", "Rechtecke", "Flächeninhalt eines Dreiecks"])
    hit = search(db_session, "Flächeninhalt Dreieck")[0]
    assert (hit.material_id, hit.page, hit.book_page, hit.book_id) == ("mat_book_ch06", 4, 198, "mat_book")
    assert hit.label == "Fundamente der Mathematik 7, S. 198"
    assert "⟦Flächeninhalt⟧" in hit.snippet


def test_filters_and_labels(db_session):
    _material(db_session, "mat_p", "Kraft", subject="sub_physics", pages=["Kraft in Newton", "Kraftpfeile"])
    _material(db_session, "mat_q", "Kraft im Alltag", kind="Arbeitsblatt", pages=["Kraft"])
    assert {h.material_id for h in search(db_session, "Kraft", subject_id="sub_physics")} == {"mat_p"}
    assert {h.material_id for h in search(db_session, "Kraft", kind="Arbeitsblatt")} == {"mat_q"}
    labels = {h.label for h in search(db_session, "Kraft")}
    assert "Mitschrift „Kraft“, Seite 1" in labels and "Arbeitsblatt „Kraft im Alltag“" in labels


def test_existing_database_gets_its_index_rebuilt(db_session, engine):
    _material(db_session, "mat_o", "Alt", pages=["Fotosynthese im Blatt"])
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM page_search"))
    ensure_search_index(engine)
    assert _ids(search(db_session, "Fotosynthese")) == [("mat_o", 1)]


def test_api_hides_solutions_without_parent_token(client, db_session):
    _material(db_session, "mat_s", "Zyklus", kind="Arbeitsblatt", pages=["Zyklus", "Zyklus Lösung"],
              solution_pages_json="[2]")
    thea = client.get("/api/v1/search", params={"q": "Zyklus"}).json()
    assert [(h["material_id"], h["page"]) for h in thea] == [("mat_s", 1)]
    token, _ = issue_token()
    parent = client.get("/api/v1/search", params={"q": "Zyklus"}, headers={"X-Parent-Token": token}).json()
    assert len(parent) == 2
    assert client.get("/api/v1/search", params={"q": ""}).status_code == 422


def test_search_module_registers_index_for_new_databases():
    # Der Index entsteht mit material_pages (after_create), Voraussetzung für alle Tests oben
    assert material_search._on_pages_table_created is not None


def test_snippet_drops_markdown_and_handwriting_marks():
    assert material_search.clean_snippet("## Kraft **1.5** «S: ⟦Hebel⟧ links» [Abbildung: Waage] | a |") == \
        "Kraft 1.5 ⟦Hebel⟧ links [Abbildung: Waage] a"


def _book_with_toc(db):
    _material(db, "mat_b", "Fundamente der Mathematik 7 – Ausgabe B Gymnasium", kind="Buch")
    _material(db, "mat_b_ch01", "Kapitel 1: Zuordnungen", kind="Buchauszug", parent_id="mat_b", start_page=11,
              pages=["Zuordnungen und Proportionalität"])  # erst Seite 1 erschlossen
    _material(db, "mat_b_ch10", "Anhang & Lösungen", kind="Lösungsheft", parent_id="mat_b", start_page=279)
    db.add(Topic(id="top_z", subject_id="sub_math", name="Proportionale Zuordnungen", grade_level=7))
    db.add_all([
        TopicBookRef(topic_id="top_z", material_id="mat_b_ch01", section_title="1.4 Dreisatz für proportionale Zuordnungen",
                     start_page=16, end_page=19, book_page=26),
        TopicBookRef(topic_id="top_z", material_id="mat_b_ch10", section_title="Lösungen zum Dreisatz",
                     start_page=2, end_page=3, book_page=280),
    ])
    db.commit()


def test_book_sections_from_the_table_of_contents_are_found_before_extraction(db_session):
    _filler(db_session)
    _book_with_toc(db_session)
    hit = search(db_session, "Wie geht der Dreisatz?")[0]
    assert (hit.source, hit.material_id, hit.page, hit.page_to, hit.book_id) == ("toc", "mat_b_ch01", 16, 19, "mat_b")
    assert hit.label == "Fundamente der Mathematik 7, S. 26"
    assert hit.section == "1.4 Dreisatz für proportionale Zuordnungen"
    assert all(not h.is_solution for h in search(db_session, "Dreisatz"))
    assert any(h.is_solution for h in search(db_session, "Dreisatz", include_solutions=True))


def test_table_of_contents_index_follows_topic_renames(db_session):
    _book_with_toc(db_session)
    assert search(db_session, "Verhältnisrechnung") == []
    db_session.get(Topic, "top_z").name = "Verhältnisrechnung"
    db_session.commit()
    assert [h.section for h in search(db_session, "Verhältnisrechnung")] == ["1.4 Dreisatz für proportionale Zuordnungen"]
