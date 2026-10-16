"""Seiten-Notizen gehen nicht verloren, wenn Thea schreibt, bevor das Seitenbild geladen ist."""
import json

from tests.e2e.board_helpers import DRAW_JS, _line, _open_board, upload_document


def test_notes_drawn_before_the_page_image_loads_are_saved(app_page):
    _open_board(app_page)
    note_id = upload_document(app_page, "Langsame Seite", "sub_bio")
    held = []
    app_page.route(f"**/api/v1/materials/{note_id}/preview**", lambda route: held.append(route))

    app_page.evaluate("(id) => { window.openMaterialOnWhiteboard(id, 'sub_bio'); }", note_id)
    app_page.wait_for_selector("#wb-doc-topbar", state="visible", timeout=5000)
    for _ in range(50):  # warten, bis das Seitenbild angefragt (und von uns festgehalten) wird
        if held:
            break
        app_page.wait_for_timeout(100)
    assert held, "Seitenbild wurde nicht angefragt"

    # Thea schreibt sofort, das Bild ist noch nicht da
    app_page.evaluate(DRAW_JS, {"pts": _line(400, 300, 520, 330), "type": "pen", "pressure": 0.6, "ids": [1]})
    app_page.wait_for_timeout(1200)  # länger als die Auto-Save-Verzögerung

    with app_page.expect_response(lambda r: r.request.method == "PUT" and "/annotations" in r.url,
                                  timeout=10000) as resp:
        for route in held:
            route.continue_()
    assert resp.value.ok
    saved = json.loads(resp.value.request.post_data)["strokes"]
    assert len(saved) == 1 and len(saved[0]["points"]) > 5

    # Nach dem Laden der (leeren) gespeicherten Notizen ist der Strich noch auf der Seite
    app_page.wait_for_timeout(500)
    strokes = app_page.evaluate("""(id) => fetch(`/api/v1/materials/${id}/pages/1/annotations`)
        .then(r => r.json()).then(d => (d.strokes || []).length)""", note_id)
    assert strokes == 1
    assert app_page.problems.errors == []
