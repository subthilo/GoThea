import io
import time
from pathlib import Path
from pypdf import PdfWriter

from backend.app.services.page_renderer import (
    PageRenderingService,
    PRIORITY_LIVE,
    PRIORITY_PREFETCH,
    PRIORITY_BACKGROUND
)

def create_sample_pdf(tmp_path: Path, pages: int = 3) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=400)
    pdf_path = tmp_path / "test_doc.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path

def test_page_renderer_image_direct(tmp_path):
    img_path = tmp_path / "photo.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

    svc = PageRenderingService()
    img_bytes, mime = svc.render_page(str(img_path), "image/png", page_num=1)
    assert mime == "image/png"
    assert b"fakeimagebytes" in img_bytes

def test_page_renderer_pdf_render_and_cache(tmp_path):
    pdf_path = create_sample_pdf(tmp_path, pages=3)
    svc = PageRenderingService()

    # 1. Erstes Rendern
    img_bytes, mime = svc.render_page(
        file_path=str(pdf_path),
        mime_type="application/pdf",
        page_num=1,
        material_id="mat_test_123",
        priority=PRIORITY_LIVE
    )
    assert mime == "image/jpeg"
    assert len(img_bytes) > 0

    # Cache-Datei muss nun existieren
    cache_path = svc.get_cache_path("mat_test_123", str(pdf_path), 1)
    assert cache_path.exists()
    assert cache_path.stat().st_size > 0

    # 2. Zweiter Aufruf (Cache-Hit)
    start_t = time.time()
    cached_bytes, cached_mime = svc.render_page(
        file_path=str(pdf_path),
        mime_type="application/pdf",
        page_num=1,
        material_id="mat_test_123",
        priority=PRIORITY_LIVE
    )
    duration = time.time() - start_t
    assert cached_bytes == img_bytes
    assert cached_mime == "image/jpeg"
    # Cache-Hit muss extrem schnell sein (< 100ms)
    assert duration < 0.1

def test_page_renderer_prefetch_and_queue(tmp_path):
    pdf_path = create_sample_pdf(tmp_path, pages=5)
    svc = PageRenderingService()

    # Vorab benachbarte Seiten anfordern
    svc.prefetch_adjacent_pages("mat_test_multi", str(pdf_path), "application/pdf", current_page=2)

    # Queue muss nun Jobs für Seite 3 (2+1), Seite 1 (2-1) und Seite 4 (2+2) enthalten
    assert not svc._queue.empty()
    item = svc._queue.get_nowait()
    # Prio muss PRIORITY_PREFETCH (2) sein
    assert item[0] == PRIORITY_PREFETCH
    assert item[2][0] == "mat_test_multi"

def test_prefetch_api_endpoint(client, tmp_path):
    # Material anlegen
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    files = {"file": ("mathe_vierecke.pdf", buf.getvalue(), "application/pdf")}
    res_pre = client.post("/api/v1/materials/pre-analyze", files=files)
    assert res_pre.status_code == 200
    token = res_pre.json()["upload_token"]

    confirm_res = client.post("/api/v1/materials/confirm", json={
        "upload_token": token,
        "subject_id": "sub_math",
        "title": "Vierecke & Polygone",
        "kind": "Arbeitsblatt"
    })
    assert confirm_res.status_code == 201
    mat_id = confirm_res.json()["id"]

    # Prefetch API anstoßen
    prefetch_res = client.post(f"/api/v1/materials/{mat_id}/prefetch?page=1")
    assert prefetch_res.status_code == 200
    assert prefetch_res.json()["status"] == "ok"
    assert prefetch_res.json()["prefetched_around_page"] == 1
