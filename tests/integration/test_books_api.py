import pypdf
import pytest

from backend.app.models.material import Material
from backend.app.services.book_segmentation import segment_book_material

BOOK_ID = "mat_test_book"
TEST_CHAPTERS = [
    {"unit_number": 0, "title": "Titelei", "start_pdf_page": 1, "end_pdf_page": 4,
     "book_start_page": 1, "book_end_page": 4, "focus": "Inhaltsverzeichnis", "sections": []},
    {"unit_number": 1, "title": "Lerneinheit 1: Zahlen und Rechenoperationen", "start_pdf_page": 5, "end_pdf_page": 16,
     "book_start_page": 10, "book_end_page": 21, "focus": "Rechnen mit rationalen Zahlen",
     "sections": [{"title": "1.1 Brüche", "book_page": 12, "relative_page": 3, "level": 2}]},
    {"unit_number": 2, "title": "Lerneinheit 2: Satz des Pythagoras", "start_pdf_page": 17, "end_pdf_page": 30,
     "book_start_page": 22, "book_end_page": 35, "focus": "Metrische Beziehungen und Satz des Pythagoras", "sections": []},
]


@pytest.fixture(autouse=True)
def segmented_test_book(db_session, tmp_path):
    pdf_path = tmp_path / "testbuch.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(30):
        writer.add_blank_page(width=200, height=300)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    book = Material(id=BOOK_ID, user_id="usr_thea", subject_id="sub_math", title="Mathematik – Testbuch 7",
                    kind="Buch", filename="testbuch.pdf", file_path=str(pdf_path), mime_type="application/pdf",
                    page_count=30)
    db_session.add(book)
    db_session.commit()
    segment_book_material(db_session, book, TEST_CHAPTERS)


def test_list_books_api(client):
    res = client.get("/api/v1/books")
    assert res.status_code == 200
    book = next(b for b in res.json() if b["id"] == BOOK_ID)
    assert book["total_pages"] == 30
    assert book["chapters_count"] == 3
    assert book["subject_name"] == "Mathematik"
    assert "preview" in book["cover_preview_url"]


def test_get_book_detail_api(client):
    res = client.get(f"/api/v1/books/{BOOK_ID}")
    assert res.status_code == 200
    data = res.json()
    assert data["total_pages"] == 30
    assert len(data["chapters"]) == 3

    ch1 = data["chapters"][1]
    assert ch1["chapter_number"] == 1
    assert "Zahlen und Rechenoperationen" in ch1["title"]
    assert (ch1["start_page"], ch1["end_page"], ch1["page_count"]) == (10, 21, 12)
    assert "file" in ch1["file_url"] and "preview" in ch1["preview_url"]
    assert ch1["sections"][0]["title"] == "1.1 Brüche"

    ch2 = data["chapters"][2]
    assert "Pythagoras" in ch2["focus"]
    assert ch2["page_count"] == 14


def test_get_book_chapter_api(client):
    res = client.get(f"/api/v1/books/{BOOK_ID}/chapters/{BOOK_ID}_ch02")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == f"{BOOK_ID}_ch02"
    assert (data["start_page"], data["end_page"], data["page_count"]) == (22, 35, 14)
    assert "Pythagoras" in data["title"]
    assert isinstance(data["sections"], list)


def test_get_book_not_found(client):
    res = client.get("/api/v1/books/non_existent_book_id")
    assert res.status_code == 404
    assert "nicht gefunden" in res.json()["detail"]


def test_get_book_chapter_not_found(client):
    res = client.get(f"/api/v1/books/{BOOK_ID}/chapters/non_existent_chap_id")
    assert res.status_code == 404
    assert "nicht gefunden" in res.json()["detail"]


def test_books_seed_endpoint_is_gone(client):
    assert client.post("/api/v1/books/seed").status_code in (404, 405)


def test_unsegmented_book_fallback_api(client, db_session):
    from backend.app.models.material import Material
    single_book = Material(
        id="mat_test_single_book",
        user_id="usr_thea",
        subject_id="sub_math",
        title="Ein einzelnes Buch ohne Kapitel",
        kind="Buch",
        filename="single_book.pdf",
        file_path="/tmp/single_book.pdf",
        file_size=1024,
        mime_type="application/pdf",
        page_count=50,
        start_page=1,
        end_page=50
    )
    db_session.add(single_book)
    db_session.commit()

    res = client.get("/api/v1/books/mat_test_single_book")
    assert res.status_code == 200
    data = res.json()
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["id"] == "mat_test_single_book"
    assert data["chapters"][0]["page_count"] == 50
    assert data["chapters_count"] == 1



def test_resegment_book_requires_parent(strict_client):
    res = strict_client.post(f"/api/v1/books/{BOOK_ID}/resegment")
    assert res.status_code == 403


def test_resegment_book_not_found(client):
    res = client.post("/api/v1/books/mat_does_not_exist/resegment")
    assert res.status_code == 404


def test_resegment_known_book(client, db_session, tmp_path):
    import pypdf
    from backend.app.models.material import Material

    pdf_path = tmp_path / "physik.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(108):
        writer.add_blank_page(width=200, height=300)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    db_session.add(Material(
        id="mat_physik_api",
        user_id="usr_thea",
        subject_id="sub_math",
        title="Physik Plus 7",
        kind="Buch",
        filename="physik.pdf",
        file_path=str(pdf_path),
        mime_type="application/pdf",
        page_count=108
    ))
    db_session.commit()

    res = client.post("/api/v1/books/mat_physik_api/resegment")
    assert res.status_code == 200
    assert res.json()["chapters_count"] == 4
