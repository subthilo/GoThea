"""Gemeinsame Hilfen der Browser-Tests für die Tafel: Pointer-Events wie Safari auf dem iPad senden,
Tinte zählen, auf den Auto-Save warten."""
import json

SAVE_TIMEOUT_MS = 6000

DRAW_JS = """
(args) => {
  const c = document.getElementById("wb-canvas");
  const r = c.getBoundingClientRect();
  const fire = (type, id, x, y, pressure) => c.dispatchEvent(new PointerEvent(type, {
    pointerId: id, pointerType: args.type, pressure: pressure, isPrimary: id === args.ids[0],
    clientX: r.left + x, clientY: r.top + y, bubbles: true, cancelable: true }));
  for (const id of args.ids) fire("pointerdown", id, args.pts[0][0], args.pts[0][1], args.pressure);
  for (const [x, y] of args.pts.slice(1)) for (const id of args.ids) fire("pointermove", id, x, y, args.pressure);
  const last = args.pts[args.pts.length - 1];
  for (const id of args.ids) fire("pointerup", id, last[0], last[1], 0);
}
"""

INK_PIXELS_JS = """
() => {
  const c = document.getElementById("wb-canvas");
  const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
}
"""


def _line(x0, y0, x1, y1, steps=12):
    return [[x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps] for i in range(steps + 1)]


def _open_board(page):
    page.click('.nav-tab[data-tab="whiteboard"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)  # Canvas-Größe nach dem Tab-Wechsel


def _draw(page, pts, pointer_type="pen", pressure=0.7, ids=(1,)):
    page.evaluate(DRAW_JS, {"pts": pts, "type": pointer_type, "pressure": pressure, "ids": list(ids)})


def _draw_and_capture_save(page, pts, **kw):
    """Zeichnet und liefert die gespeicherten Striche aus dem folgenden Auto-Save."""
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/state"), timeout=SAVE_TIMEOUT_MS) as resp:
        _draw(page, pts, **kw)
    assert resp.value.ok
    return json.loads(json.loads(resp.value.request.post_data)["board_state_json"])


def upload_document(page, title, subject_id, pages=2, kind="Mitschrift"):
    """Lädt ein leeres PDF über die API hoch (ohne KI) und liefert die Material-ID."""
    import io
    from urllib.parse import urljoin

    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=420)
    buf = io.BytesIO()
    writer.write(buf)
    base = page.url
    pre = page.request.post(urljoin(base, "/api/v1/materials/pre-analyze"), multipart={
        "file": {"name": "mitschrift.pdf", "mimeType": "application/pdf", "buffer": buf.getvalue()}})
    assert pre.ok
    conf = page.request.post(urljoin(base, "/api/v1/materials/confirm"), data={
        "upload_token": pre.json()["upload_token"], "subject_id": subject_id, "title": title, "kind": kind})
    assert conf.ok
    return conf.json()["id"]
