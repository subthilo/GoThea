import pytest
from backend.app.services.book_seeder import seed_textbooks_if_empty

@pytest.fixture(autouse=True)
def seed_book_for_tests(db_session):
    seed_textbooks_if_empty(db_session, user_id="usr_thea")

def test_list_books_api(client):
    res = client.get("/api/v1/books")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    math_book = next((b for b in data if "Mathematik" in b["title"]), None)
    assert math_book is not None
    assert math_book["id"] == "mat_book_math_7"
    assert math_book["total_pages"] == 196
    assert math_book["chapters_count"] == 11
    assert math_book["grade_level"] == 7
    assert math_book["subject_name"] == "Mathematik"
    assert "preview" in math_book["cover_preview_url"]

def test_get_book_detail_api(client):
    res = client.get("/api/v1/books/mat_book_math_7")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "mat_book_math_7"
    assert data["total_pages"] == 196
    assert len(data["chapters"]) == 11

    # Kapitel 1 prüfen
    ch1 = data["chapters"][1]
    assert ch1["chapter_number"] == 1
    assert "Zahlen und Rechenoperationen" in ch1["title"]
    assert ch1["start_page"] == 10
    assert ch1["end_page"] == 21
    assert ch1["page_count"] == 12
    assert "file" in ch1["file_url"]
    assert "preview" in ch1["preview_url"]

    # Kapitel 8 (Pythagoras) prüfen
    ch8 = next((c for c in data["chapters"] if "Pythagoras" in c["title"] or "Metrische Beziehungen" in c["title"]), None)
    assert ch8 is not None
    assert ch8["start_page"] == 152
    assert ch8["end_page"] == 173
    assert ch8["page_count"] == 22
    assert "Satz des Pythagoras" in ch8["focus"]

def test_get_book_chapter_api(client):
    res = client.get("/api/v1/books/mat_book_math_7/chapters/mat_book_math_7_ch8")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "mat_book_math_7_ch8"
    assert data["start_page"] == 152
    assert data["end_page"] == 173
    assert data["page_count"] == 22
    assert "Pythagoras" in data["title"] or "Metrische Beziehungen" in data["title"]

def test_get_book_not_found(client):
    res = client.get("/api/v1/books/non_existent_book_id")
    assert res.status_code == 404
    assert "nicht gefunden" in res.json()["detail"]

def test_get_book_chapter_not_found(client):
    res = client.get("/api/v1/books/mat_book_math_7/chapters/non_existent_chap_id")
    assert res.status_code == 404
    assert "nicht gefunden" in res.json()["detail"]
