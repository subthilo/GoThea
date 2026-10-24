"""Schutz des Zeichenkerns (frontend/js/ink_core.js): Er ist fragil und mühsam erarbeitet.

Schlägt dieser Test fehl, wurde der Kern geändert. Das ist erlaubt, aber nur bewusst:
eigener Commit, tests/e2e/test_pencil.py grün, Prüfung durch den Nutzer auf dem iPad –
dann hier die neue Prüfsumme eintragen.
"""
import hashlib
from pathlib import Path

INK_CORE = Path(__file__).resolve().parents[2] / "frontend" / "js" / "ink_core.js"
EXPECTED_SHA256 = "a942858b3da9ec70158b4df1074b152ce2238f9cad4bc6b3ca4a8dff96dfe8f9"


def test_ink_core_is_only_changed_deliberately():
    actual = hashlib.sha256(INK_CORE.read_bytes()).hexdigest()
    assert actual == EXPECTED_SHA256, (
        "Zeichenkern geändert: eigener Commit, Pencil-Tests, iPad-Check – dann EXPECTED_SHA256 aktualisieren.")
