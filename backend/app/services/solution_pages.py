"""Welche Seiten eines Dokuments Lösungen sind – die sieht Thea nicht (Seitenbild, Download, Volltext).

Gesperrt wird nur nach Angaben, die die Eltern beim Upload bestätigt haben: die Dokumentart („Lösungsheft“ →
ganzes Dokument) und die Lösungsseiten der Voranalyse. Die Markierung der Seiten-Erschließung
(material_pages.is_solution_page) zählt hier bewusst nicht: Sie trifft auch Methodenseiten mit Beispiellösung
(gemessen 24.10. auf Staging, z. B. Chemie Buch S. 20 „Protokollieren“), und die braucht Thea.
Später (Bearbeitungs-Ablauf): Lösungen frei, sobald Thea abgegeben hat.
"""
import json
from typing import Set


# Statt der Lösungsseite: A4-Blatt mit dem Schloss aus frontend/Icons/Schloss.svg (Seitenverhältnis wie eine Seite,
# damit Leser und Tafel nicht springen)
LOCKED_PAGE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 595 842" width="595" height="842">'
    '<rect width="595" height="842" fill="#F1F5F9"/>'
    '<g transform="translate(222.5 346) scale(1.5)" fill="none" stroke="#94A3B8" stroke-width="4" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="24" y="44" width="52" height="40" rx="6"/>'
    '<path d="M 34 44 L 34 32 A 16 16 0 0 1 66 32 L 66 44"/>'
    '<line x1="50" y1="58" x2="50" y2="70"/></g></svg>'
)


def whole_document(material) -> bool:
    return "lösung" in (material.kind or "").lower()


def pages(material) -> Set[int]:
    """Lösungsseiten laut Voranalyse (Seiten in der Datei)."""
    try:
        return {int(p) for p in json.loads(material.solution_pages_json or "[]")}
    except (ValueError, TypeError):
        return set()


def is_solution_page(material, page: int) -> bool:
    return whole_document(material) or page in pages(material)
