"""Ausmalbilder im Eltern-Modus: SVG hochladen, Felder werden berechnet, Vorschau, freigeben; Thea sieht den Bereich nicht."""
import pytest

pytest.importorskip("shapely")

SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
       b'<path fill-rule="evenodd" d="M0 0H100V100H0Z M10 10H90V90H10Z"/><rect x="48" y="10" width="4" height="80"/></svg>')


def _parent(page, pin):
    page.click("#btn-parent-toggle")
    page.fill("#input-parent-pin", pin)
    page.click("#btn-submit-parent-pin")
    page.wait_for_function("document.body.classList.contains('parent-mode-active')")


def test_parents_upload_preview_and_release(app_page, parent_pin, tmp_path):
    app_page.click('.nav-tab[data-tab="uploads"]')
    assert not app_page.locator(".coloring-section").is_visible()  # Thea sieht den Bereich nicht
    _parent(app_page, parent_pin)
    app_page.locator(".coloring-section").wait_for(state="visible")

    name = f"Probe-{tmp_path.name[-8:]}"
    svg = tmp_path / f"{name}.svg"
    svg.write_bytes(SVG)
    app_page.set_input_files("#coloring-file-input", str(svg))
    row = app_page.locator(".coloring-row", has_text=name)
    row.wait_for()
    # Berechnung im Hintergrund; die Liste fragt nach, bis sie fertig ist
    app_page.locator(".coloring-row.status-berechnet", has_text=name).wait_for(timeout=20000)
    row = app_page.locator(".coloring-row", has_text=name)
    assert "2" in row.locator(".coloring-status").inner_text()
    assert row.locator(".coloring-thumb img").count() == 1

    row.locator(".doc-row-head").click()
    row.locator(".coloring-preview-svg").wait_for()
    assert row.locator(".coloring-preview-svg path").count() == 1  # nur die Linien

    row.locator(".coloring-release").click()
    app_page.locator(".coloring-row.status-freigegeben", has_text=name).wait_for()
    pages = app_page.evaluate("apiJson('/api/v1/coloring-pages')")
    assert any(p["name"] == name and p["status"] == "freigegeben" for p in pages)
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []
