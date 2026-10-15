"""Startseite aus Teilen: Dialog-Dateien werden eingesetzt, ?v= trägt die aktuelle Version der Frontend-Dateien."""
import os
import re
from pathlib import Path

import pytest

from backend.app.services.frontend_page import asset_version, render_index

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def test_index_route_serves_the_assembled_page_uncached(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["cache-control"].startswith("no-cache")
    html = res.text
    assert "include:" not in html and "{{v}}" not in html
    for dialog in sorted((FRONTEND / "dialogs").glob("*.html")):
        modal_id = re.search(r'id="(modal-[\w-]+)"', dialog.read_text()).group(1)
        assert html.count(f'id="{modal_id}"') == 1, modal_id


def test_every_script_and_stylesheet_exists_and_carries_the_version():
    html = render_index(FRONTEND)
    version = asset_version(FRONTEND)
    refs = re.findall(r'(?:src|href)="/static/([^"?]+)\?v=([^"]+)"', html)
    assert len(refs) > 30
    for path, v in refs:
        assert (FRONTEND / path).is_file(), path
        assert v == version


def _mini_frontend(tmp_path):
    (tmp_path / "dialogs").mkdir(parents=True)
    (tmp_path / "dialogs" / "a.html").write_text('  <div id="modal-a"></div>\n')
    (tmp_path / "app.js").write_text("1")
    (tmp_path / "index.html").write_text(
        '<body>\n  <!-- include: dialogs/a.html -->\n<script src="/static/app.js?v={{v}}"></script>\n</body>\n')
    return tmp_path


def test_include_keeps_the_markup_byte_for_byte(tmp_path):
    html = render_index(_mini_frontend(tmp_path))
    assert html.startswith('<body>\n  <div id="modal-a"></div>\n<script src="/static/app.js?v=')


def test_version_changes_when_a_frontend_file_changes(tmp_path):
    root = _mini_frontend(tmp_path)
    before = asset_version(root)
    js = root / "app.js"
    js.write_text("12")
    os.utime(js, ns=(js.stat().st_atime_ns, js.stat().st_mtime_ns + 1_000_000))
    assert asset_version(root) != before


@pytest.mark.parametrize("target", ["../secret.html", "dialogs/missing.html"])
def test_include_outside_the_folder_or_missing_fails(tmp_path, target):
    root = _mini_frontend(tmp_path / "fe")
    (tmp_path / "secret.html").write_text("geheim")
    (root / "index.html").write_text(f"<!-- include: {target} -->\n")
    with pytest.raises(FileNotFoundError):
        render_index(root)
