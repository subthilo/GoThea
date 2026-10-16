"""Tafel-Verwaltung im Browser: Wer etwas anderes öffnet oder beginnt, schließt die aktuelle Tafel –
gespeichert, mit Vorschaubild – und kann sie aus der Liste wieder öffnen. Tafeln gehören zu ihrem Fach."""
import base64
import json
import re

from tests.e2e.board_helpers import (
    DRAW_JS,
    INK_PIXELS_JS,
    _draw_and_capture_save,
    _line,
    _open_board,
    upload_document,
)


def _pixels(page):
    return page.evaluate(INK_PIXELS_JS)


def _board_count(page, subject_id="sub_math"):
    return page.evaluate(
        "(s) => fetch(`/api/v1/boards?subject_id=${s}`).then(r => r.json()).then(l => l.length)", subject_id)


def _settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)


def test_new_board_keeps_the_old_one_which_can_be_reopened(app_page):
    _open_board(app_page)
    _draw_and_capture_save(app_page, _line(200, 200, 400, 260))
    old_title = app_page.text_content("#wb-board-title")

    # "Neu": die alte Tafel wird vollständig und mit Vorschaubild gespeichert, die neue ist leer
    with app_page.expect_request(lambda r: r.method == "PUT" and r.url.endswith("/state")
                                 and "snapshot_data_url" in (r.post_data or "")):
        app_page.click("#btn-wb-new-session")
    _settle(app_page)
    assert _pixels(app_page) == 0

    # Die alte Tafel steht mit Vorschaubild in der Liste und öffnet sich wieder mit ihren Strichen
    app_page.click("#btn-wb-boards")
    item = app_page.locator(".wb-boards-item:has(img.wb-boards-thumb)").first
    item.wait_for()
    assert old_title in item.text_content()
    item.click()
    _settle(app_page)
    assert _pixels(app_page) > 0
    assert app_page.text_content("#wb-board-title") == old_title
    assert app_page.problems.errors == []


def test_switching_subject_opens_that_subjects_board_and_back(app_page):
    _open_board(app_page)
    app_page.select_option("#wb-subject-select", "sub_math")
    _settle(app_page)
    app_page.click("#btn-wb-new-session")
    _settle(app_page)
    _draw_and_capture_save(app_page, _line(220, 300, 420, 330))
    math_pixels = _pixels(app_page)
    assert math_pixels > 0

    app_page.select_option("#wb-subject-select", "sub_bio")
    _settle(app_page)
    assert "Biologie" in app_page.text_content("#wb-board-title")
    app_page.click("#btn-wb-new-session")
    _settle(app_page)
    assert _pixels(app_page) == 0  # die Mathe-Striche liegen nicht über der Bio-Tafel

    app_page.select_option("#wb-subject-select", "sub_math")
    _settle(app_page)
    # Live gezeichnet vs. aus dem Speicher neu gezeichnet: Kantenglättung weicht um wenige Pixel ab
    assert abs(_pixels(app_page) - math_pixels) <= max(5, math_pixels * 0.02)
    assert app_page.problems.errors == []


def test_empty_boards_are_discarded_when_left(app_page):
    _open_board(app_page)
    app_page.click("#btn-wb-new-session")
    _settle(app_page)
    after_first = _board_count(app_page)

    app_page.click("#btn-wb-new-session")  # die erste neue Tafel ist leer und wird verworfen
    _settle(app_page)
    assert _board_count(app_page) == after_first
    assert app_page.problems.errors == []


def _draw_on_document_page(page):
    """Zeichnet mitten auf die Dokumentseite und wartet, bis die Seiten-Notiz gespeichert ist."""
    box = page.evaluate("""() => {
      const c = document.getElementById("wb-canvas").getBoundingClientRect();
      const i = document.getElementById("wb-doc-underlay-img").getBoundingClientRect();
      // im sichtbaren oberen Teil der Seite (die Seite ist meist höher als die Tafel)
      return { x: i.left - c.left + i.width / 2, y: i.top - c.top + Math.min(150, i.height / 2) };
    }""")
    with page.expect_response(lambda r: r.request.method == "PUT" and "/annotations" in r.url) as resp:
        page.evaluate(DRAW_JS, {"pts": _line(box["x"] - 40, box["y"], box["x"] + 40, box["y"] + 10),
                                "type": "pen", "pressure": 0.6, "ids": [1]})
    assert resp.value.ok


def _turn_page(page, button, page_no):
    with page.expect_response(lambda r: r.request.method == "GET" and f"/pages/{page_no}/annotations" in r.url):
        page.click(button)
    page.wait_for_timeout(200)


def test_opening_a_note_from_another_subject_does_not_carry_the_board(app_page):
    _open_board(app_page)
    app_page.select_option("#wb-subject-select", "sub_math")
    _settle(app_page)
    app_page.click("#btn-wb-new-session")
    _settle(app_page)
    _draw_and_capture_save(app_page, _line(200, 520, 420, 560))
    math_pixels = _pixels(app_page)

    note_id = upload_document(app_page, "Zellatmung", "sub_bio")
    with app_page.expect_response(lambda r: "/pages/1/annotations" in r.url and r.request.method == "GET"):
        app_page.evaluate("(id) => window.openMaterialOnWhiteboard(id, 'sub_bio')", note_id)
    app_page.wait_for_timeout(200)
    assert app_page.is_visible("#wb-doc-topbar")
    assert app_page.text_content("#wb-board-title") == "Zellatmung"
    assert _pixels(app_page) == 0  # die Mathe-Rechnung liegt nicht über der Mitschrift

    # Notizen gehören zur Seite
    _draw_on_document_page(app_page)
    assert _pixels(app_page) > 0
    _turn_page(app_page, "#btn-wb-doc-next", 2)
    assert _pixels(app_page) == 0
    _turn_page(app_page, "#btn-wb-doc-prev", 1)
    assert _pixels(app_page) > 0

    # Schließen speichert die Notizen; die Mathe-Tafel ist unverändert
    app_page.click("#btn-wb-doc-close")
    _settle(app_page)
    assert not app_page.is_visible("#wb-doc-topbar")
    app_page.select_option("#wb-subject-select", "sub_math")
    _settle(app_page)
    assert abs(_pixels(app_page) - math_pixels) <= max(5, math_pixels * 0.02)
    assert app_page.problems.errors == []


def test_tall_document_page_is_not_cut_off_when_scrolled(app_page):
    """Hochformatige Seiten sind höher als die Tafel; ihr unterer Teil muss beim Scrollen sichtbar werden."""
    import io

    from PIL import Image
    note_id = upload_document(app_page, "Hochformat", "sub_bio", pages=1)
    app_page.evaluate("(id) => window.openMaterialOnWhiteboard(id, 'sub_bio')", note_id)
    _settle(app_page)
    app_page.wait_for_function("document.getElementById('wb-doc-underlay-img').naturalWidth > 0", timeout=5000)
    page_bottom = app_page.evaluate("""() => {
      const i = document.getElementById('wb-doc-underlay-img');
      const v = document.getElementById('wb-viewport').getBoundingClientRect();
      return {imgBottom: i.offsetTop + i.offsetHeight, viewportH: v.height, x: v.left + v.width / 2, top: v.top};
    }""")
    assert page_bottom["imgBottom"] > page_bottom["viewportH"]  # Seite ragt wirklich über die Tafel hinaus
    # So weit scrollen, wie die Tafel es täte, dass das Seitenende unten im Bild steht
    # (Seitenende 250 px über dem unteren Tafelrand, dort liegt keine Werkzeugleiste)
    shift = page_bottom["imgBottom"] - (page_bottom["viewportH"] - 250)
    app_page.evaluate(f"() => {{ document.getElementById('wb-doc-underlay').style.transform = 'translate(0px, -{shift}px) scale(1)'; }}")
    y = page_bottom["top"] + page_bottom["viewportH"] - 280  # knapp über dem Seitenende
    png = app_page.screenshot(clip={"x": page_bottom["x"], "y": y, "width": 1, "height": 1})
    assert Image.open(io.BytesIO(png)).convert("RGB").getpixel((0, 0)) == (255, 255, 255)


def test_subject_page_lists_boards_with_preview_on_expand(app_page):
    _open_board(app_page)
    _draw_and_capture_save(app_page, _line(200, 200, 400, 260))
    title = app_page.text_content("#wb-board-title")
    with app_page.expect_request(lambda r: r.method == "PUT" and r.url.endswith("/state")
                                 and "snapshot_data_url" in (r.post_data or "")):
        app_page.click("#btn-wb-new-session")
    _settle(app_page)

    # Fachseite der Tafel (welches Fach aktiv ist, hängt von vorherigen Tests ab)
    subject_id = app_page.evaluate(
        "(t) => fetch('/api/v1/boards').then(r => r.json()).then(l => l.find(b => b.title === t).subject_id)", title)
    # Tafeln als Zeilen; die Vorschau lädt erst beim Aufklappen
    app_page.evaluate("(s) => openSubjectDetail(s)", subject_id)
    row = app_page.locator(f"#subject-boards-grid .board-row:has(.board-row-preview):has-text('{title}')").first
    row.wait_for(timeout=5000)
    img = row.locator(".board-row-preview img")
    assert img.get_attribute("src") is None
    row.locator(".doc-row-name").click()
    app_page.wait_for_function("(el) => el.complete && el.naturalWidth > 0", arg=img.element_handle(), timeout=5000)

    # „Öffnen“ bringt die Tafel auf den Schirm
    row.locator(".board-row-open").click()
    app_page.wait_for_selector("#tab-whiteboard.active", timeout=5000)
    _settle(app_page)
    assert app_page.text_content("#wb-board-title") == title
    assert _pixels(app_page) > 0
    assert app_page.problems.errors == []


def test_board_rename_for_all_and_delete_only_for_parents(app_page, parent_pin):
    _open_board(app_page)
    _draw_and_capture_save(app_page, _line(200, 200, 400, 260))
    current_id = app_page.evaluate("fetch('/api/v1/boards').then(r => r.json()).then(l => l[0].id)")
    subject_id = app_page.evaluate("fetch('/api/v1/boards').then(r => r.json()).then(l => l[0].subject_id)")
    app_page.evaluate("(s) => openSubjectDetail(s)", subject_id)
    row = app_page.locator(f"#subject-boards-grid .board-row[data-board-id='{current_id}']")
    row.wait_for(timeout=5000)

    # Thea: umbenennen ja, löschen nein
    app_page.once("dialog", lambda d: d.accept("Bruchrechnung QZB"))
    row.locator(".board-row-rename").click()
    app_page.wait_for_selector(f".board-row[data-board-id='{current_id}'] .doc-row-name:has-text('Bruchrechnung QZB')", timeout=5000)
    row.locator(".doc-row-name").click()
    assert not row.locator(".board-row-delete").is_visible()

    # Eltern: die gerade geöffnete Tafel löschen – danach darf nichts mehr auf sie speichern
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)
    row = app_page.locator(f"#subject-boards-grid .board-row[data-board-id='{current_id}']")
    if "open" not in (row.get_attribute("class") or ""):
        row.locator(".doc-row-name").click()
    app_page.once("dialog", lambda d: d.accept())
    row.locator(".board-row-delete").click()
    app_page.wait_for_selector(f".board-row[data-board-id='{current_id}']", state="detached", timeout=5000)
    ids = app_page.evaluate("fetch('/api/v1/boards').then(r => r.json()).then(l => l.map(b => b.id))")
    assert current_id not in ids
    _settle(app_page)
    assert app_page.problems.errors == []


def test_header_scrolls_sideways_on_narrow_ipad_and_board_list_stays_visible(app_page):
    """iPad hochkant: die Kopfleiste der Tafel wird nicht abgeschnitten, sondern lässt sich seitlich wischen;
    die Tafel-Liste geht trotzdem vollständig sichtbar unter ihrem Knopf auf."""
    app_page.set_viewport_size({"width": 834, "height": 1194})
    _open_board(app_page)
    bar = app_page.locator(".wb-header-bar")
    assert bar.evaluate("el => el.scrollWidth > el.clientWidth")

    # Bis ans Ende wischen: der letzte Knopf (Vollbild) liegt dann ganz in der Leiste und ist erreichbar
    bar.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
    btn = app_page.locator("#btn-wb-fullscreen").bounding_box()
    box = bar.bounding_box()
    assert btn["x"] >= box["x"] and btn["x"] + btn["width"] <= box["x"] + box["width"] + 1
    hit = app_page.evaluate("([x, y]) => document.elementFromPoint(x, y).closest('#btn-wb-fullscreen') !== null",
                            [btn["x"] + btn["width"] / 2, btn["y"] + btn["height"] / 2])
    assert hit

    # Tafel-Liste: ganz im Bild und obenauf, nicht von der Leiste abgeschnitten
    bar.evaluate("el => { el.scrollLeft = 0; }")
    app_page.click("#btn-wb-boards")
    panel = app_page.locator("#wb-boards-panel")
    panel.wait_for(state="visible", timeout=5000)
    p = panel.bounding_box()
    assert p["x"] >= 0 and p["x"] + p["width"] <= 834 and p["y"] + p["height"] <= 1194
    trigger = app_page.locator("#btn-wb-boards").bounding_box()
    assert p["y"] >= trigger["y"] + trigger["height"]  # direkt unter ihrem Knopf
    on_top = app_page.evaluate("([x, y]) => document.elementFromPoint(x, y).closest('#wb-boards-panel') !== null",
                               [p["x"] + p["width"] / 2, p["y"] + min(40, p["height"] / 2)])
    assert on_top
    assert app_page.problems.errors == []


# 1×1-PNG als Vorschaubild
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def test_board_row_loads_preview_on_expand_and_stays_open(app_page):
    board = {"id": "board_row_probe", "title": "Bruchrechnung Probe", "subject_id": "sub_math",
             "subject_name": "Mathematik", "has_thumbnail": True,
             "updated_at": "2026-10-16T08:00:00", "created_at": "2026-10-16T08:00:00"}
    thumb_requests = []
    app_page.route(re.compile(r".*/api/v1/boards\?subject_id=sub_math$"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps([board])))

    def thumb(route):
        thumb_requests.append(route.request.url)
        route.fulfill(status=200, content_type="image/png", body=_PNG)
    app_page.route(re.compile(r".*/api/v1/boards/board_row_probe/thumbnail.*"), thumb)

    app_page.evaluate("openSubjectDetail('sub_math')")
    row = app_page.locator('.board-row[data-board-id="board_row_probe"]')
    row.wait_for(timeout=5000)
    assert row.locator(".doc-row-head").get_attribute("aria-expanded") == "false"
    assert thumb_requests == []  # Vorschau erst beim Aufklappen

    row.locator(".doc-row-name").click()
    app_page.wait_for_function(
        "document.querySelector('.board-row[data-board-id=\"board_row_probe\"] img').complete")
    assert "open" in row.get_attribute("class")
    assert row.locator(".doc-row-head").get_attribute("aria-expanded") == "true"
    assert len(thumb_requests) == 1

    # Neu zeichnen (z. B. nach Umbenennen): die Zeile bleibt offen
    app_page.evaluate("loadSubjectBoards('sub_math')")
    app_page.wait_for_load_state("networkidle")
    row = app_page.locator('.board-row[data-board-id="board_row_probe"]')
    assert "open" in row.get_attribute("class")

    row.locator(".doc-row-head").press("Enter")
    assert "open" not in row.get_attribute("class")
    assert app_page.problems.errors == []
