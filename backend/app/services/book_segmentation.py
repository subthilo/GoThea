import json
import logging
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import pypdf
from sqlalchemy.orm import Session

from backend.app.services.document_kinds import NEVER_BOOK_KINDS, normalize_kind
from backend.app.prompts.book_toc import BOOK_TOC_SYSTEM_PROMPT
from backend.app.services.llm import chat_params
from backend.app.models.material import Material
from backend.app.models.taxonomy import Topic

logger = logging.getLogger(__name__)

# Pro Buch darf nur eine Segmentierung gleichzeitig laufen (Upload-Hintergrund vs. Bücher-Tab)
_segmentation_locks: Dict[str, threading.Lock] = {}
_segmentation_locks_guard = threading.Lock()
_segmentations_running: Set[str] = set()


def _get_book_lock(book_id: str) -> threading.Lock:
    with _segmentation_locks_guard:
        return _segmentation_locks.setdefault(book_id, threading.Lock())


def is_segmentation_running(book_id: str) -> bool:
    with _segmentation_locks_guard:
        return book_id in _segmentations_running

# Bekannte Kapiteldefinitionen für "Fundamente der Mathematik, Ausgabe B, Gymnasium, Klasse 7"
# Basierend auf der Vision-Analyse des Original-Inhaltsverzeichnisses
FUNDAMENTE_MATHE_7_CHAPTERS = [
    {
        "unit_number": 0,
        "title": "Titelei & Vorbereitung zur Lernausgangslage",
        "start_pdf_page": 1,
        "end_pdf_page": 14,
        "book_start_page": 1,
        "book_end_page": 10,
        "kind": "Buchauszug",
        "topic_name": "Fundamente der Mathematik",
        "focus": "Titelei, Inhaltsverzeichnis und diagnostische Vorbereitung zur Lernausgangslage Klasse 7.",
        "sections": [
            {"title": "Deine Grundlagen aus der Grundschulzeit", "book_page": 6, "relative_page": 6, "level": 2}
        ]
    },
    {
        "unit_number": 1,
        "title": "Kapitel 1: Zuordnungen und Proportionalität",
        "start_pdf_page": 15,
        "end_pdf_page": 46,
        "book_start_page": 11,
        "book_end_page": 42,
        "kind": "Buchauszug",
        "topic_name": "Dreisatz und proportionale Zuordnungen",
        "focus": "Zuordnungen, grafische Darstellung, proportionale und antiproportionale Zuordnungen, Dreisatz.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 12, "relative_page": 2, "level": 2},
            {"title": "1.1 Zuordnungen", "book_page": 14, "relative_page": 4, "level": 2},
            {"title": "1.2 Grafische Darstellung", "book_page": 18, "relative_page": 8, "level": 2},
            {"title": "1.3 Proportionale Zuordnungen", "book_page": 22, "relative_page": 12, "level": 2},
            {"title": "1.4 Dreisatz für proportionale Zuordnungen", "book_page": 26, "relative_page": 16, "level": 2},
            {"title": "1.5 Antiproportionale Zuordnungen", "book_page": 30, "relative_page": 20, "level": 2},
            {"title": "1.6 Dreisatz für antiproportionale Zuordnungen", "book_page": 34, "relative_page": 24, "level": 2},
            {"title": "1.7 Vermischte Aufgaben", "book_page": 37, "relative_page": 27, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 40, "relative_page": 30, "level": 2},
            {"title": "Zusammenfassung", "book_page": 42, "relative_page": 32, "level": 2}
        ]
    },
    {
        "unit_number": 2,
        "title": "Kapitel 2: Prozent- und Zinsrechnung",
        "start_pdf_page": 47,
        "end_pdf_page": 78,
        "book_start_page": 43,
        "book_end_page": 74,
        "kind": "Buchauszug",
        "topic_name": "Prozent- und Zinsrechnung",
        "focus": "Prozentschreibweise, Grundbegriffe, Prozentwert, Grundwert, prozentuale Veränderung und Zinsen.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 44, "relative_page": 2, "level": 2},
            {"title": "2.1 Prozentschreibweise", "book_page": 46, "relative_page": 4, "level": 2},
            {"title": "2.2 Grundbegriffe der Prozentrechnung", "book_page": 50, "relative_page": 8, "level": 2},
            {"title": "2.3 Prozentwert berechnen", "book_page": 52, "relative_page": 10, "level": 2},
            {"title": "2.4 Prozentsatz berechnen", "book_page": 54, "relative_page": 12, "level": 2},
            {"title": "2.5 Grundwert berechnen", "book_page": 56, "relative_page": 14, "level": 2},
            {"title": "Streifzug: Promille", "book_page": 58, "relative_page": 16, "level": 2},
            {"title": "2.6 Prozentuale Veränderung", "book_page": 60, "relative_page": 18, "level": 2},
            {"title": "2.7 Zinsen", "book_page": 65, "relative_page": 23, "level": 2},
            {"title": "Streifzug: Sparpläne und Tilgungspläne", "book_page": 68, "relative_page": 26, "level": 2},
            {"title": "2.8 Vermischte Aufgaben", "book_page": 70, "relative_page": 28, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 72, "relative_page": 30, "level": 2},
            {"title": "Zusammenfassung", "book_page": 74, "relative_page": 32, "level": 2}
        ]
    },
    {
        "unit_number": 3,
        "title": "Kapitel 3: Rationale Zahlen",
        "start_pdf_page": 79,
        "end_pdf_page": 114,
        "book_start_page": 75,
        "book_end_page": 110,
        "kind": "Buchauszug",
        "topic_name": "Rationale Zahlen",
        "focus": "Ganze Zahlen, Zahlengerade, Koordinatensystem, Addition, Subtraktion, Multiplikation und Division rationaler Zahlen.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 76, "relative_page": 2, "level": 2},
            {"title": "3.1 Ganze Zahlen und Zahlengerade", "book_page": 78, "relative_page": 4, "level": 2},
            {"title": "3.2 Erweiterung des Koordinatensystems", "book_page": 80, "relative_page": 6, "level": 2},
            {"title": "3.3 Ganze Zahlen vergleichen und ordnen", "book_page": 82, "relative_page": 8, "level": 2},
            {"title": "3.4 Zustandsänderungen", "book_page": 84, "relative_page": 10, "level": 2},
            {"title": "3.5 Rationale Zahlen", "book_page": 87, "relative_page": 13, "level": 2},
            {"title": "3.6 Rationale Zahlen addieren und subtrahieren", "book_page": 89, "relative_page": 15, "level": 2},
            {"title": "3.7 Rationale Zahlen multiplizieren und dividieren", "book_page": 95, "relative_page": 21, "level": 2},
            {"title": "Streifzug: Rechenspiele", "book_page": 99, "relative_page": 25, "level": 2},
            {"title": "3.8 Rechnen mit allen Grundrechenarten", "book_page": 100, "relative_page": 26, "level": 2},
            {"title": "Streifzug: Den Taschenrechner kennenlernen", "book_page": 102, "relative_page": 28, "level": 2},
            {"title": "3.9 Ausmultiplizieren und Ausklammern", "book_page": 104, "relative_page": 30, "level": 2},
            {"title": "3.10 Vermischte Aufgaben", "book_page": 107, "relative_page": 33, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 108, "relative_page": 34, "level": 2},
            {"title": "Zusammenfassung", "book_page": 110, "relative_page": 36, "level": 2}
        ]
    },
    {
        "unit_number": 4,
        "title": "Kapitel 4: Geometrische Konstruktionen",
        "start_pdf_page": 115,
        "end_pdf_page": 160,
        "book_start_page": 111,
        "book_end_page": 156,
        "kind": "Buchauszug",
        "topic_name": "Geometrie & Winkelbeziehungen",
        "focus": "Kreis, Senkrechte und Parallele, Dreiecke, Winkelsumme, Kongruenzsätze, Mittelsenkrechte, Umkreis und Inkreis.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 112, "relative_page": 2, "level": 2},
            {"title": "4.1 Kreis", "book_page": 114, "relative_page": 4, "level": 2},
            {"title": "4.2 Senkrecht und parallel", "book_page": 117, "relative_page": 7, "level": 2},
            {"title": "4.3 Dreiecke", "book_page": 120, "relative_page": 10, "level": 2},
            {"title": "4.4 Winkelsumme im Dreieck", "book_page": 124, "relative_page": 14, "level": 2},
            {"title": "4.5 Dynamische Geometrie-Software", "book_page": 128, "relative_page": 18, "level": 2},
            {"title": "4.6 Kongruenzsätze", "book_page": 131, "relative_page": 21, "level": 2},
            {"title": "4.7 Probleme lösen mit Dreieckskonstruktionen", "book_page": 137, "relative_page": 27, "level": 2},
            {"title": "4.8 Mittelsenkrechte und Winkelhalbierende", "book_page": 140, "relative_page": 30, "level": 2},
            {"title": "4.9 Umkreis und Inkreis beim Dreieck", "book_page": 143, "relative_page": 33, "level": 2},
            {"title": "4.10 Höhe und Seitenhalbierende im Dreieck", "book_page": 147, "relative_page": 37, "level": 2},
            {"title": "4.11 Vermischte Aufgaben", "book_page": 151, "relative_page": 41, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 154, "relative_page": 44, "level": 2},
            {"title": "Zusammenfassung", "book_page": 156, "relative_page": 46, "level": 2}
        ]
    },
    {
        "unit_number": 5,
        "title": "Kapitel 5: Terme und Gleichungen",
        "start_pdf_page": 161,
        "end_pdf_page": 198,
        "book_start_page": 157,
        "book_end_page": 194,
        "kind": "Buchauszug",
        "topic_name": "Terme und lineare Gleichungen",
        "focus": "Variablen, Terme vereinfachen, lineare Gleichungen lösen, Äquivalenzumformungen und Modellieren.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 158, "relative_page": 2, "level": 2},
            {"title": "5.1 Variablen und Terme", "book_page": 160, "relative_page": 4, "level": 2},
            {"title": "5.2 Terme vereinfachen", "book_page": 164, "relative_page": 8, "level": 2},
            {"title": "5.3 Gleichungen", "book_page": 167, "relative_page": 11, "level": 2},
            {"title": "Streifzug: Sprache in der Mathematik", "book_page": 170, "relative_page": 14, "level": 2},
            {"title": "5.4 Äquivalenzumformungen", "book_page": 172, "relative_page": 16, "level": 2},
            {"title": "5.5 Sonderfälle beim Lösen von Gleichungen", "book_page": 176, "relative_page": 20, "level": 2},
            {"title": "5.6 Mit Gleichungen modellieren", "book_page": 178, "relative_page": 22, "level": 2},
            {"title": "Streifzug: Gleichungen mit einem CAS lösen", "book_page": 182, "relative_page": 26, "level": 2},
            {"title": "5.7 Verhältnisgleichungen und Bruchgleichungen", "book_page": 184, "relative_page": 28, "level": 2},
            {"title": "5.8 Ungleichungen", "book_page": 187, "relative_page": 31, "level": 2},
            {"title": "5.9 Vermischte Aufgaben", "book_page": 189, "relative_page": 33, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 192, "relative_page": 36, "level": 2},
            {"title": "Zusammenfassung", "book_page": 194, "relative_page": 38, "level": 2}
        ]
    },
    {
        "unit_number": 6,
        "title": "Kapitel 6: Flächen",
        "start_pdf_page": 199,
        "end_pdf_page": 222,
        "book_start_page": 195,
        "book_end_page": 218,
        "kind": "Buchauszug",
        "topic_name": "Geometrie & Winkelbeziehungen",
        "focus": "Flächeninhalt von Dreiecken, Parallelogrammen, Trapezen, Drachenvierecken und zusammengesetzten Figuren.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 196, "relative_page": 2, "level": 2},
            {"title": "6.1 Flächeninhalt eines Dreiecks", "book_page": 198, "relative_page": 4, "level": 2},
            {"title": "6.2 Winkelsumme im Viereck", "book_page": 202, "relative_page": 8, "level": 2},
            {"title": "6.3 Flächeninhalt eines Parallelogramms", "book_page": 204, "relative_page": 10, "level": 2},
            {"title": "6.4 Flächeninhalt von Trapez und Drachenviereck", "book_page": 208, "relative_page": 14, "level": 2},
            {"title": "Streifzug: Flächeninhalt beliebiger Figuren", "book_page": 212, "relative_page": 18, "level": 2},
            {"title": "6.5 Vermischte Aufgaben", "book_page": 215, "relative_page": 21, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 216, "relative_page": 22, "level": 2},
            {"title": "Zusammenfassung", "book_page": 218, "relative_page": 24, "level": 2}
        ]
    },
    {
        "unit_number": 7,
        "title": "Kapitel 7: Daten",
        "start_pdf_page": 223,
        "end_pdf_page": 258,
        "book_start_page": 219,
        "book_end_page": 254,
        "kind": "Buchauszug",
        "topic_name": "Absolute und relative Häufigkeiten",
        "focus": "Absolute und relative Häufigkeiten, Diagramme, Histogramme, statistische Kennwerte und Boxplots.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 220, "relative_page": 2, "level": 2},
            {"title": "7.1 Absolute und relative Häufigkeit", "book_page": 222, "relative_page": 4, "level": 2},
            {"title": "7.2 Diagramme", "book_page": 226, "relative_page": 8, "level": 2},
            {"title": "7.3 Klasseneinteilung und Histogramme", "book_page": 230, "relative_page": 12, "level": 2},
            {"title": "7.4 Kennwerte", "book_page": 234, "relative_page": 16, "level": 2},
            {"title": "7.5 Tabellenkalkulation", "book_page": 238, "relative_page": 20, "level": 2},
            {"title": "7.6 Boxplots", "book_page": 242, "relative_page": 24, "level": 2},
            {"title": "7.7 Statistische Erhebungen", "book_page": 246, "relative_page": 28, "level": 2},
            {"title": "7.8 Vermischte Aufgaben", "book_page": 249, "relative_page": 31, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 252, "relative_page": 34, "level": 2},
            {"title": "Zusammenfassung", "book_page": 254, "relative_page": 36, "level": 2}
        ]
    },
    {
        "unit_number": 8,
        "title": "Kapitel 8: Ähnlichkeit",
        "start_pdf_page": 259,
        "end_pdf_page": 278,
        "book_start_page": 255,
        "book_end_page": 274,
        "kind": "Buchauszug",
        "topic_name": "Geometrie & Winkelbeziehungen",
        "focus": "Kongruente und ähnliche Figuren, Kongruenzabbildungen, Maßstäbe, Umfang und Flächeninhalt ähnlicher Figuren.",
        "sections": [
            {"title": "Dein Fundament (Wiederholung)", "book_page": 256, "relative_page": 2, "level": 2},
            {"title": "8.1 Kongruente Figuren", "book_page": 258, "relative_page": 4, "level": 2},
            {"title": "8.2 Kongruenzabbildungen", "book_page": 261, "relative_page": 7, "level": 2},
            {"title": "8.3 Ähnliche Figuren", "book_page": 265, "relative_page": 11, "level": 2},
            {"title": "8.4 Umfang und Flächeninhalt ähnlicher Figuren", "book_page": 268, "relative_page": 14, "level": 2},
            {"title": "Streifzug: CAS-Einsatz bei Ähnlichkeit", "book_page": 270, "relative_page": 16, "level": 2},
            {"title": "8.5 Vermischte Aufgaben", "book_page": 271, "relative_page": 17, "level": 2},
            {"title": "Prüfe dein neues Fundament", "book_page": 272, "relative_page": 18, "level": 2},
            {"title": "Zusammenfassung", "book_page": 274, "relative_page": 20, "level": 2}
        ]
    },
    {
        "unit_number": 9,
        "title": "Kapitel 9: Methodenkarten",
        "start_pdf_page": 279,
        "end_pdf_page": 282,
        "book_start_page": 275,
        "book_end_page": 278,
        "kind": "Buchauszug",
        "topic_name": "Fundamente der Mathematik",
        "focus": "Methodenkarten und Strategien zum strukturierten mathematischen Arbeiten und Problemlösen.",
        "sections": [
            {"title": "Methodenkarten & Lösungsstrategien", "book_page": 276, "relative_page": 2, "level": 2}
        ]
    },
    {
        "unit_number": 10,
        "title": "Kapitel 10: Anhang & Lösungen",
        "start_pdf_page": 283,
        "end_pdf_page": 304,
        "book_start_page": 279,
        "book_end_page": 300,
        "kind": "Lösungsheft",
        "topic_name": "Fundamente der Mathematik",
        "focus": "Vollständige Lösungen und Kontrollhilfen für alle Aufgaben des Lehrbuchs.",
        "sections": [
            {"title": "Lösungen aller Aufgaben", "book_page": 280, "relative_page": 2, "level": 2}
        ]
    }
]

FRANZ_VORKURS_SECTIONS = [
    {"title": "1. Begrüßen und verabschieden (Bonjour ! Au revoir !)", "book_page": 4, "relative_page": 4, "level": 2},
    {"title": "2. Sagen, wie es einem geht (Ça va ?)", "book_page": 6, "relative_page": 6, "level": 2},
    {"title": "3. Sagen, wie man heißt (Comment tu t'appelles ?)", "book_page": 8, "relative_page": 8, "level": 2},
    {"title": "4. Sagen, wie alt man ist (Tu as quel âge ?)", "book_page": 10, "relative_page": 10, "level": 2},
    {"title": "5. Sagen, wo man wohnt (Où tu habites ?)", "book_page": 14, "relative_page": 14, "level": 2},
    {"title": "6. Sagen, was man mag (J'aime les jeux vidéo et le chocolat)", "book_page": 18, "relative_page": 18, "level": 2},
    {"title": "7. Sagen, was man nicht mag (Je n'aime pas...)", "book_page": 22, "relative_page": 22, "level": 2},
    {"title": "Abschluss & Lernziele", "book_page": 26, "relative_page": 26, "level": 2}
]

PHYSIK_PLUS_7_CHAPTERS = [
    {
        "unit_number": 1,
        "title": "Mechanik",
        "start_pdf_page": 7,
        "end_pdf_page": 36,
        "book_start_page": 5,
        "book_end_page": 34,
        "kind": "Buchauszug",
        "topic_name": "Mechanik & Kräfte",
        "focus": "Kräfte, Wirkungen, Federkraftmesser, Gewichtskraft, Wechselwirkung, Reibung, einfache Maschinen (Rollen, Hebel, geneigte Ebene) sowie mechanische Arbeit und Leistung.",
        "sections": [
            {"title": "1.1 Kraft & Wirkungen von Kräften", "book_page": 6, "relative_page": 2, "level": 2},
            {"title": "1.2 Federkraftmesser & Darstellen von Kräften", "book_page": 8, "relative_page": 4, "level": 2},
            {"title": "1.3 Gewichtskraft & Gravitation", "book_page": 11, "relative_page": 7, "level": 2},
            {"title": "1.4 Wechselwirkung von Kräften", "book_page": 13, "relative_page": 9, "level": 2},
            {"title": "Streifzug: In der Schwerelosigkeit", "book_page": 14, "relative_page": 10, "level": 2},
            {"title": "Aufgaben & Zusammenfassung: Kraft", "book_page": 15, "relative_page": 11, "level": 2},
            {"title": "1.5 Reibung & Reibungskräfte", "book_page": 16, "relative_page": 12, "level": 2},
            {"title": "1.6 Haft-, Gleit- und Rollreibung", "book_page": 16, "relative_page": 12, "level": 2},
            {"title": "Projekt: Sicheres Radfahren", "book_page": 20, "relative_page": 16, "level": 2},
            {"title": "1.7 Rollen & Flaschenzüge", "book_page": 22, "relative_page": 18, "level": 2},
            {"title": "1.8 Mechanische Arbeit", "book_page": 24, "relative_page": 20, "level": 2},
            {"title": "1.9 Geneigte Ebene & Hebel", "book_page": 26, "relative_page": 22, "level": 2},
            {"title": "1.10 Mechanische Leistung", "book_page": 28, "relative_page": 24, "level": 2},
            {"title": "Projekt: Hebel am Fahrrad", "book_page": 30, "relative_page": 26, "level": 2},
            {"title": "Aufgaben & Zusammenfassung: Mechanik", "book_page": 33, "relative_page": 29, "level": 2}
        ]
    },
    {
        "unit_number": 2,
        "title": "Energie in Natur und Technik",
        "start_pdf_page": 37,
        "end_pdf_page": 52,
        "book_start_page": 35,
        "book_end_page": 50,
        "kind": "Buchauszug",
        "topic_name": "Energie & Umwelt",
        "focus": "Physikalische Bedeutung der Energie, Energieformen, Energieumwandlung, Energieübertragung, Energieerhaltungssatz und rationelle Energienutzung.",
        "sections": [
            {"title": "2.1 Physikalische Bedeutung der Energie", "book_page": 36, "relative_page": 2, "level": 2},
            {"title": "2.2 Energieformen & Speicherung", "book_page": 37, "relative_page": 3, "level": 2},
            {"title": "2.3 Umwandlung & Übertragung von Energie", "book_page": 39, "relative_page": 5, "level": 2},
            {"title": "2.4 Energie für Lebensprozesse", "book_page": 40, "relative_page": 6, "level": 2},
            {"title": "2.5 Energie auf dem Weg zum Verbraucher", "book_page": 41, "relative_page": 7, "level": 2},
            {"title": "2.6 Kraftwerke & Umweltbelastung", "book_page": 43, "relative_page": 9, "level": 2},
            {"title": "2.7 Energieerhaltungssatz", "book_page": 44, "relative_page": 10, "level": 2},
            {"title": "Projekt: Wind als alternative Energiequelle", "book_page": 45, "relative_page": 11, "level": 2},
            {"title": "2.8 Rationelle Nutzung von Energie", "book_page": 46, "relative_page": 12, "level": 2},
            {"title": "Aufgaben & Zusammenfassung: Energie", "book_page": 50, "relative_page": 16, "level": 2}
        ]
    },
    {
        "unit_number": 3,
        "title": "Wärmelehre",
        "start_pdf_page": 53,
        "end_pdf_page": 105,
        "book_start_page": 51,
        "book_end_page": 103,
        "kind": "Buchauszug",
        "topic_name": "Wärmelehre & Thermodynamik",
        "focus": "Teilchenmodell, Temperaturmessung, Kelvin-Skala, thermische Energie und Wärme, Ausdehnung von Körpern, Aggregatzustandsänderungen, Wärmeübertragung und Wärmekraftmaschinen.",
        "sections": [
            {"title": "3.1 Aufbau der Stoffe aus Teilchen", "book_page": 52, "relative_page": 2, "level": 2},
            {"title": "Teilbarkeit der Stoffe & Brown’sche Bewegung", "book_page": 54, "relative_page": 4, "level": 2},
            {"title": "3.2 Temperatur, thermische Energie und Wärme", "book_page": 56, "relative_page": 6, "level": 2},
            {"title": "Die Kelvin-Skala & Berechnung der Wärme", "book_page": 57, "relative_page": 7, "level": 2},
            {"title": "Streifzug: Gefühlte Temperatur", "book_page": 64, "relative_page": 14, "level": 2},
            {"title": "3.3 Thermisches Verhalten der Körper (Ausdehnung)", "book_page": 66, "relative_page": 16, "level": 2},
            {"title": "3.4 Aggregatzustandsänderungen (Schmelzen, Sieden)", "book_page": 72, "relative_page": 22, "level": 2},
            {"title": "3.5 Wärmeübertragung & Wetter (Leitung, Konvektion, Strahlung)", "book_page": 80, "relative_page": 30, "level": 2},
            {"title": "3.6 Wärme in der Technik (Motoren, Wärmepumpe, Kollektoren)", "book_page": 94, "relative_page": 44, "level": 2},
            {"title": "Aufgaben & Zusammenfassung: Wärmelehre", "book_page": 103, "relative_page": 53, "level": 2}
        ]
    },
    {
        "unit_number": 4,
        "title": "Register & Anhang",
        "start_pdf_page": 106,
        "end_pdf_page": 108,
        "book_start_page": 104,
        "book_end_page": 106,
        "kind": "Buchauszug",
        "topic_name": "Register & Nachschlagen",
        "focus": "Stichwortverzeichnis und Sachregister zum schnellen Nachschlagen physikalischer Fachbegriffe.",
        "sections": [
            {"title": "Sachregister", "book_page": 104, "relative_page": 1, "level": 2}
        ]
    }
]

DEUTSCHBUCH_7_CHAPTERS = [
    {
        "unit_number": 1,
        "title": "Kapitel 1: On sein, off sein, ich sein – Über Medien informieren",
        "start_pdf_page": 16,
        "end_pdf_page": 39,
        "book_start_page": 13,
        "book_end_page": 36,
        "kind": "Buchauszug",
        "topic_name": "Sprechen – Zuhören – Schreiben",
        "focus": "Informierende Texte untersuchen, Vergleiche anstellen und einen informierenden Text verfassen.",
        "sections": [
            {"title": "1.1 Immer online? – Informationen entnehmen und vergleichen", "book_page": 14, "relative_page": 2, "level": 2},
            {"title": "1.2 Influencer – Informierende Texte untersuchen", "book_page": 24, "relative_page": 12, "level": 2},
            {"title": "1.3 Fit in ... – Einen informierenden Text verfassen", "book_page": 33, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 2,
        "title": "Kapitel 2: Faszinierendes Mittelalter – Beschreiben und erklären",
        "start_pdf_page": 40,
        "end_pdf_page": 57,
        "book_start_page": 37,
        "book_end_page": 54,
        "kind": "Buchauszug",
        "topic_name": "Sprechen – Zuhören – Schreiben",
        "focus": "Gegenstände und Wege beschreiben, Abläufe erklären und Vorgangsbeschreibungen anfertigen.",
        "sections": [
            {"title": "2.1 Leben auf der Burg – Gegenstände und Wege beschreiben", "book_page": 38, "relative_page": 2, "level": 2},
            {"title": "2.2 Wie lebten die Menschen im Mittelalter? – Abläufe erklären", "book_page": 46, "relative_page": 10, "level": 2},
            {"title": "2.3 Fit in ... – Einen Vorgang beschreiben", "book_page": 52, "relative_page": 16, "level": 2}
        ]
    },
    {
        "unit_number": 3,
        "title": "Kapitel 3: Jedem Trend hinterher? – Argumentieren und überzeugen",
        "start_pdf_page": 58,
        "end_pdf_page": 79,
        "book_start_page": 55,
        "book_end_page": 76,
        "kind": "Buchauszug",
        "topic_name": "Sprechen – Zuhören – Schreiben",
        "focus": "Meinungen formulieren und begründen, schriftlich argumentieren und materialgestützt Stellung beziehen.",
        "sections": [
            {"title": "3.1 Sag, was du denkst! – Eine Meinung formulieren und begründen", "book_page": 56, "relative_page": 2, "level": 2},
            {"title": "3.2 Streitpunkt: Schönheitsideale – Schriftlich argumentieren", "book_page": 66, "relative_page": 12, "level": 2},
            {"title": "3.3 Fit in ... – Materialgestützt argumentieren", "book_page": 74, "relative_page": 20, "level": 2}
        ]
    },
    {
        "unit_number": 4,
        "title": "Kapitel 4: Besondere Momente – Schildern",
        "start_pdf_page": 80,
        "end_pdf_page": 95,
        "book_start_page": 77,
        "book_end_page": 92,
        "kind": "Buchauszug",
        "topic_name": "Sprechen – Zuhören – Schreiben",
        "focus": "Mit Sprache malen, Reportagen untersuchen und emotionale Schilderungen verfassen.",
        "sections": [
            {"title": "4.1 Die Zeit steht still – Mit Sprache „malen“", "book_page": 78, "relative_page": 2, "level": 2},
            {"title": "4.2 Felsklettern – Eine Reportage untersuchen", "book_page": 87, "relative_page": 11, "level": 2},
            {"title": "4.3 Fit in ... – Schildern", "book_page": 90, "relative_page": 14, "level": 2}
        ]
    },
    {
        "unit_number": 5,
        "title": "Kapitel 5: Von cleveren Typen – Alte und neue Erzählungen",
        "start_pdf_page": 96,
        "end_pdf_page": 119,
        "book_start_page": 93,
        "book_end_page": 116,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Kurze Geschichten und Kalendergeschichten untersuchen, Inhalte wiedergeben und Inhaltsangaben schreiben.",
        "sections": [
            {"title": "5.1 Unterhaltsames und Lehrreiches – Kurze Geschichten untersuchen", "book_page": 94, "relative_page": 2, "level": 2},
            {"title": "5.2 Eine überraschende Wende! – Inhalte wiedergeben", "book_page": 103, "relative_page": 11, "level": 2},
            {"title": "5.3 Fit in ... – Eine Inhaltsangabe schreiben", "book_page": 113, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 6,
        "title": "Kapitel 6: „Es ist nicht geheuer dort ...“ – Jugendromane lesen und verstehen",
        "start_pdf_page": 120,
        "end_pdf_page": 141,
        "book_start_page": 117,
        "book_end_page": 138,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Handlung und Figuren untersuchen (z. B. Krabat), gestaltend schreiben und innere Monologe verfassen.",
        "sections": [
            {"title": "6.1 „Krabat“ – Handlung und Figuren untersuchen", "book_page": 118, "relative_page": 2, "level": 2},
            {"title": "6.2 „Die Insel der besonderen Kinder“ – Gestaltend schreiben", "book_page": 131, "relative_page": 15, "level": 2},
            {"title": "6.3 Fit in ... – Einen inneren Monolog verfassen", "book_page": 137, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 7,
        "title": "Kapitel 7: Gedichte erzählen Geschichten – Balladen untersuchen und gestalten",
        "start_pdf_page": 142,
        "end_pdf_page": 167,
        "book_start_page": 139,
        "book_end_page": 164,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Balladen erschließen und vortragen, Balladen in Reportagen umgestalten und Hörspiele produzieren.",
        "sections": [
            {"title": "7.1 Schaurig und spannend – Balladen erschließen und vortragen", "book_page": 140, "relative_page": 2, "level": 2},
            {"title": "7.2 Stoff für eine Reportage – Eine Ballade umgestalten", "book_page": 156, "relative_page": 18, "level": 2},
            {"title": "7.3 Projekt – Eine Ballade verstehen und als Hörspiel gestalten", "book_page": 161, "relative_page": 23, "level": 2}
        ]
    },
    {
        "unit_number": 8,
        "title": "Kapitel 8: „Paul Vier und die Schröders“ – Ein Jugendstück untersuchen und spielen",
        "start_pdf_page": 168,
        "end_pdf_page": 187,
        "book_start_page": 165,
        "book_end_page": 184,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Figuren und dramatische Konflikte analysieren, Spielszenen verfassen und Szenen auf der Bühne darstellen.",
        "sections": [
            {"title": "8.1 Neue Nachbarn – Figuren und ihre Konflikte untersuchen", "book_page": 166, "relative_page": 2, "level": 2},
            {"title": "8.2 Die Lage spitzt sich zu – Szenen schreiben und spielen", "book_page": 177, "relative_page": 13, "level": 2},
            {"title": "8.3 Projekt – Ein Theaterstück aufführen", "book_page": 182, "relative_page": 18, "level": 2}
        ]
    },
    {
        "unit_number": 9,
        "title": "Kapitel 9: Werbung – Sachtexte und Medien untersuchen",
        "start_pdf_page": 188,
        "end_pdf_page": 217,
        "book_start_page": 185,
        "book_end_page": 214,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Werbung analysieren, Strategien durchschauen, Informationen recherchieren und Sachtexte kritisch prüfen.",
        "sections": [
            {"title": "9.1 Gesehen und gekauft? – Informationen erschließen und vergleichen", "book_page": 186, "relative_page": 2, "level": 2},
            {"title": "9.2 Fernsehwerbung – Informationen recherchieren, auswerten und präsentieren", "book_page": 204, "relative_page": 20, "level": 2},
            {"title": "9.3 Fit in ... – Einen Sachtext untersuchen", "book_page": 212, "relative_page": 28, "level": 2}
        ]
    },
    {
        "unit_number": 10,
        "title": "Kapitel 10: „Spin or God is a DJ“ – Einen Kurzfilm untersuchen",
        "start_pdf_page": 218,
        "end_pdf_page": 227,
        "book_start_page": 215,
        "book_end_page": 224,
        "kind": "Buchauszug",
        "topic_name": "Lesen – Umgang mit Texten und Medien",
        "focus": "Filmanalyse, Filmsprache (Kamera, Schnitt, Ton) und filmische Gestaltungselemente kennenlernen.",
        "sections": [
            {"title": "10.1 Wenn Gott ein DJ wäre – Story und Figuren des Films kennen lernen", "book_page": 216, "relative_page": 2, "level": 2},
            {"title": "10.2 Kamera, Schnitt und Ton – Die Sprache des Films untersuchen", "book_page": 219, "relative_page": 5, "level": 2},
            {"title": "10.3 Projekt – Eine Filmsequenz drehen", "book_page": 223, "relative_page": 9, "level": 2}
        ]
    },
    {
        "unit_number": 11,
        "title": "Kapitel 11: Mit Wörtern spielen – Wort und Bedeutung",
        "start_pdf_page": 228,
        "end_pdf_page": 243,
        "book_start_page": 225,
        "book_end_page": 240,
        "kind": "Buchauszug",
        "topic_name": "Nachdenken über Sprache",
        "focus": "Wortbedeutungen erforschen, Metaphern, Sprachebenen, Mehrsprachigkeit und Jugendsprache.",
        "sections": [
            {"title": "11.1 Verstehen und missverstehen – Die Bedeutung von Wörtern untersuchen", "book_page": 226, "relative_page": 2, "level": 2},
            {"title": "11.2 Wie sprecht ihr denn? – Sprachen in unserer Klasse", "book_page": 233, "relative_page": 9, "level": 2},
            {"title": "11.3 Projekt – Das Jugendwort unserer Schule", "book_page": 240, "relative_page": 16, "level": 2}
        ]
    },
    {
        "unit_number": 12,
        "title": "Kapitel 12: Grammatiktraining – Rund um Wortarten, Sätze und Satzglieder",
        "start_pdf_page": 244,
        "end_pdf_page": 289,
        "book_start_page": 241,
        "book_end_page": 286,
        "kind": "Buchauszug",
        "topic_name": "Nachdenken über Sprache",
        "focus": "Wortarten, Verbformen, Konjunktiv, Satzglieder (Subjekt, Prädikat, Objekte, Adverbiale) und Satzgefüge.",
        "sections": [
            {"title": "12.1 Kuriose Erfindungen – Wortarten und Formen des Verbs untersuchen", "book_page": 242, "relative_page": 2, "level": 2},
            {"title": "12.2 Geniale Entdeckungen und Experimente – Satzglieder und Sätze untersuchen", "book_page": 265, "relative_page": 25, "level": 2},
            {"title": "12.3 Fit in ... – Grammatikwissen gezielt anwenden", "book_page": 283, "relative_page": 43, "level": 2}
        ]
    },
    {
        "unit_number": 13,
        "title": "Kapitel 13: Rechtschreibung – Mit Training zur Meisterschaft",
        "start_pdf_page": 290,
        "end_pdf_page": 321,
        "book_start_page": 287,
        "book_end_page": 318,
        "kind": "Buchauszug",
        "topic_name": "Nachdenken über Sprache",
        "focus": "Rechtschreibstrategien, Groß- und Kleinschreibung, Getrennt- und Zusammenschreibung sowie Kommasetzung.",
        "sections": [
            {"title": "13.1 Sportlich, sportlich! – Strategien nutzen und Regeln beachten", "book_page": 288, "relative_page": 2, "level": 2},
            {"title": "13.2 Sport ist … – Zeichen setzen", "book_page": 302, "relative_page": 16, "level": 2},
            {"title": "13.3 Fit in … Rechtschreibung", "book_page": 310, "relative_page": 24, "level": 2}
        ]
    },
    {
        "unit_number": 14,
        "title": "Kapitel 14: Orientierungswissen & Nachschlagen",
        "start_pdf_page": 322,
        "end_pdf_page": 383,
        "book_start_page": 319,
        "book_end_page": 380,
        "kind": "Buchauszug",
        "topic_name": "Orientierungswissen & Nachschlagen",
        "focus": "Zusammenfassendes Nachschlagewerk für Sprechen, Schreiben, Textuntersuchung, Grammatik und Register.",
        "sections": [
            {"title": "Sprechen und Zuhören", "book_page": 319, "relative_page": 1, "level": 2},
            {"title": "Schreiben", "book_page": 321, "relative_page": 3, "level": 2},
            {"title": "Umgang mit Texten und Medien", "book_page": 331, "relative_page": 13, "level": 2},
            {"title": "Nachdenken über Sprache", "book_page": 344, "relative_page": 26, "level": 2},
            {"title": "Textarten- & Quellenverzeichnis", "book_page": 370, "relative_page": 52, "level": 2},
            {"title": "Sachregister", "book_page": 373, "relative_page": 55, "level": 2}
        ]
    }
]

APLUS_1_CHAPTERS = [
    {
        "unit_number": 0,
        "title": "C'est parti ! (Einstieg)",
        "start_pdf_page": 10,
        "end_pdf_page": 17,
        "book_start_page": 8,
        "book_end_page": 15,
        "kind": "Buchauszug",
        "topic_name": "Französisch Grundlagen",
        "focus": "Erste Kontakte, Begrüßung, Alphabet, Zahlen und Vorlieben auf Französisch.",
        "sections": [
            {"title": "1. Bonjour ! (Begrüßung & Vorstellung)", "book_page": 8, "relative_page": 1, "level": 2},
            {"title": "2. Tu as quel âge ? (Zahlen 1-12 & Alter)", "book_page": 10, "relative_page": 3, "level": 2},
            {"title": "3. Dans la classe (Gegenstände im Klassenzimmer)", "book_page": 11, "relative_page": 4, "level": 2},
            {"title": "4. J'aime les jeux vidéo et le chocolat (Vorlieben)", "book_page": 12, "relative_page": 5, "level": 2},
            {"title": "5. Les animaux et les couleurs (Tiere & Farben)", "book_page": 14, "relative_page": 7, "level": 2}
        ]
    },
    {
        "unit_number": 1,
        "title": "Unité 1: Bienvenue à Paris !",
        "start_pdf_page": 18,
        "end_pdf_page": 39,
        "book_start_page": 16,
        "book_end_page": 37,
        "kind": "Buchauszug",
        "topic_name": "Sich und seinen Wohnort vorstellen",
        "focus": "Paris entdecken, sich und Freunde vorstellen, Wegbeschreibungen und Sehenswürdigkeiten.",
        "sections": [
            {"title": "Vocabulaire thématique: La ville de Paris", "book_page": 16, "relative_page": 1, "level": 2},
            {"title": "Volet 1: Les amis de Gabin", "book_page": 18, "relative_page": 3, "level": 2},
            {"title": "Volet 2: Coucou, c'est nous !", "book_page": 23, "relative_page": 8, "level": 2},
            {"title": "Volet 3: Qu'est-ce qu'il y a à Paris ?", "book_page": 28, "relative_page": 13, "level": 2},
            {"title": "Atelier: Notre quartier", "book_page": 32, "relative_page": 17, "level": 2},
            {"title": "Bilan & Auto-contrôle", "book_page": 34, "relative_page": 19, "level": 2}
        ]
    },
    {
        "unit_number": 2,
        "title": "Unité 2: Ma famille",
        "start_pdf_page": 40,
        "end_pdf_page": 63,
        "book_start_page": 38,
        "book_end_page": 61,
        "kind": "Buchauszug",
        "topic_name": "Seine Familie vorstellen",
        "focus": "Familienmitglieder, Verwandtschaftsverhältnisse, Tagesabläufe und Freizeitaktivitäten.",
        "sections": [
            {"title": "Vocabulaire thématique: La famille", "book_page": 38, "relative_page": 1, "level": 2},
            {"title": "Volet 1: Tu as des frères et sœurs ?", "book_page": 40, "relative_page": 3, "level": 2},
            {"title": "Volet 2: Qu'est-ce que tu fais avec ta famille ?", "book_page": 47, "relative_page": 10, "level": 2},
            {"title": "Lecture: Le journal de Jeanne", "book_page": 50, "relative_page": 13, "level": 2},
            {"title": "Atelier: Mon arbre généalogique", "book_page": 54, "relative_page": 17, "level": 2},
            {"title": "Bilan & Auto-contrôle", "book_page": 58, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 3,
        "title": "Unité 3: Ma chambre et moi",
        "start_pdf_page": 64,
        "end_pdf_page": 87,
        "book_start_page": 62,
        "book_end_page": 85,
        "kind": "Buchauszug",
        "topic_name": "Sein Zimmer vorstellen",
        "focus": "Möbel, Präpositionen des Ortes, Alltagsgegenstände und die eigene Umgebung beschreiben.",
        "sections": [
            {"title": "Vocabulaire thématique: La chambre et la maison", "book_page": 62, "relative_page": 1, "level": 2},
            {"title": "Volet 1: Chez Noé", "book_page": 64, "relative_page": 3, "level": 2},
            {"title": "Volet 2: Qu'est-ce que vous faites ?", "book_page": 70, "relative_page": 9, "level": 2},
            {"title": "Volet 3: Ma chambre raconte ma vie !", "book_page": 73, "relative_page": 12, "level": 2},
            {"title": "Atelier: Mon lieu préféré", "book_page": 78, "relative_page": 17, "level": 2},
            {"title": "Bilan & Auto-contrôle", "book_page": 82, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 4,
        "title": "Unité 4: Au collège",
        "start_pdf_page": 88,
        "end_pdf_page": 109,
        "book_start_page": 86,
        "book_end_page": 107,
        "kind": "Buchauszug",
        "topic_name": "Schule und Stundenplan",
        "focus": "Schulalltag in Frankreich, Fächer, Stundenplan, Uhrzeiten und Schulleben.",
        "sections": [
            {"title": "Vocabulaire thématique: L'école et les matières", "book_page": 86, "relative_page": 1, "level": 2},
            {"title": "Volet 1: La vie au collège", "book_page": 88, "relative_page": 3, "level": 2},
            {"title": "Volet 2: Leur emploi du temps est super !", "book_page": 93, "relative_page": 8, "level": 2},
            {"title": "Volet 3: Notre collège et nous", "book_page": 98, "relative_page": 13, "level": 2},
            {"title": "Atelier: Notre école de rêve", "book_page": 102, "relative_page": 17, "level": 2},
            {"title": "Bilan & Auto-contrôle", "book_page": 106, "relative_page": 21, "level": 2}
        ]
    },
    {
        "unit_number": 5,
        "title": "Unité 5: Un pique-nique à Paris",
        "start_pdf_page": 110,
        "end_pdf_page": 135,
        "book_start_page": 108,
        "book_end_page": 133,
        "kind": "Buchauszug",
        "topic_name": "Essen, Einkaufen & Verabredungen",
        "focus": "Lebensmittel, Einkaufsdialoge auf dem Markt, Mengenangaben und Rezepte.",
        "sections": [
            {"title": "Vocabulaire thématique: La nourriture et les courses", "book_page": 108, "relative_page": 1, "level": 2},
            {"title": "Volet 1: On se retrouve à La Villette !", "book_page": 110, "relative_page": 3, "level": 2},
            {"title": "Volet 2: On fait les courses ensemble !", "book_page": 115, "relative_page": 8, "level": 2},
            {"title": "Volet 3: Le secret des madeleines", "book_page": 120, "relative_page": 13, "level": 2},
            {"title": "Atelier: Recette de cuisine", "book_page": 126, "relative_page": 19, "level": 2},
            {"title": "Bilan & Auto-contrôle", "book_page": 130, "relative_page": 23, "level": 2}
        ]
    },
    {
        "unit_number": 6,
        "title": "Module 6: Une carte postale",
        "start_pdf_page": 136,
        "end_pdf_page": 139,
        "book_start_page": 134,
        "book_end_page": 137,
        "kind": "Buchauszug",
        "topic_name": "Postkarten & Ferien",
        "focus": "Über Ferien und Wetter berichten, Postkarten schreiben.",
        "sections": [
            {"title": "Volet: Une carte postale de vacances", "book_page": 134, "relative_page": 1, "level": 2},
            {"title": "Atelier d'écriture: Écrire une carte postale", "book_page": 136, "relative_page": 3, "level": 2}
        ]
    },
    {
        "unit_number": 7,
        "title": "Anhang: Grammatik & Vokabular",
        "start_pdf_page": 140,
        "end_pdf_page": 226,
        "book_start_page": 138,
        "book_end_page": 224,
        "kind": "Buchauszug",
        "topic_name": "Grammatik, Verbtabellen & Wörterbuch",
        "focus": "Systematische Grammatikübersicht, Konjugationstabellen und Französisch-Deutsches Vokabular.",
        "sections": [
            {"title": "Grammaire: Systematische Grammatikübersicht", "book_page": 138, "relative_page": 1, "level": 2},
            {"title": "Tableaux de conjugaison (Verbtabellen)", "book_page": 164, "relative_page": 27, "level": 2},
            {"title": "Vocabulaire par unité (Lernwortschatz)", "book_page": 168, "relative_page": 31, "level": 2},
            {"title": "Dictionnaire français-allemand", "book_page": 200, "relative_page": 63, "level": 2}
        ]
    }
]


def segment_book_material(
    db: Session,
    book: Material,
    chapters_spec: List[Dict[str, Any]],
    target_dir: Optional[Path] = None,
    force: bool = False
) -> List[Material]:
    """
    Teilt ein Schulbuch-Material anhand einer Kapitelspezifikation in
    einzelne Kapitel-PDFs und Child-Material-Einträge auf.
    """
    if not book.file_path or not os.path.exists(book.file_path):
        raise FileNotFoundError(f"PDF-Datei für Buch {book.id} nicht gefunden: {book.file_path}")

    dest_folder = target_dir or Path(book.file_path).parent
    dest_folder.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(book.file_path)
    total_pages = len(reader.pages)

    if book.kind != "Buch":
        book.kind = "Buch"

    # Vorhandene Topics des Fachs cachen
    topics_by_name = {
        t.name.lower(): t for t in db.query(Topic).filter_by(subject_id=book.subject_id).all()
    }

    # Bereits existierende Kapitel für dieses Buch prüfen
    existing_children = {
        m.dossier_order: m for m in db.query(Material).filter_by(parent_id=book.id).all()
    }

    created_or_updated: List[Material] = []
    rewritten_ids: List[str] = []

    for idx, spec in enumerate(chapters_spec):
        unit_num = spec.get("unit_number", idx)
        start_pdf = max(1, spec.get("start_pdf_page", spec.get("book_start_page", 1)))
        end_pdf = min(total_pages, spec.get("end_pdf_page", spec.get("book_end_page", total_pages)))

        if start_pdf > total_pages:
            continue

        page_count = end_pdf - start_pdf + 1
        chap_id = f"{book.id}_ch{unit_num:02d}"
        chap_filename = f"{book.id}_Kapitel_{unit_num:02d}.pdf"
        chap_path = dest_folder / chap_filename

        # 1. Kapitel-PDF via pypdf extrahieren
        if force or not chap_path.exists() or chap_path.stat().st_size == 0:
            rewritten_ids.append(chap_id)
            writer = pypdf.PdfWriter()
            for p_idx in range(start_pdf - 1, end_pdf):
                writer.add_page(reader.pages[p_idx])
            with open(chap_path, "wb") as f_out:
                writer.write(f_out)
            logger.info(f"📄 Kapitel {unit_num} extrahiert: {chap_path.name} ({page_count} Seiten, PDF {start_pdf}-{end_pdf})")

        file_size = chap_path.stat().st_size if chap_path.exists() else 0

        # 2. Thema verknüpfen: nur ein vorhandenes Thema übernehmen. Kapitel umfassen meist mehrere
        #    Unterrichtseinheiten; eigene Kapitel-Themen würden den Themenkatalog verwässern.
        topic_name = spec.get("topic_name")
        matched_topic = topics_by_name.get(topic_name.lower()) if topic_name else None

        # 3. Material-Eintrag erstellen oder aktualisieren
        order = unit_num + 2  # Master ist meist Order 1
        child = existing_children.get(order)
        if not child:
            child = db.query(Material).filter_by(id=chap_id).first()

        sec_list = spec.get("sections", [])
        sec_json = json.dumps(sec_list, ensure_ascii=False) if sec_list else None

        if not child:
            child = Material(
                id=chap_id,
                user_id=book.user_id,
                subject_id=book.subject_id,
                topic_id=matched_topic.id if matched_topic else None,
                dossier_id=book.dossier_id,
                dossier_order=order,
                parent_id=book.id,
                title=spec.get("title", f"Kapitel {unit_num}"),
                kind=spec.get("kind", "Buchauszug"),
                filename=chap_filename,
                file_path=str(chap_path),
                file_size=file_size,
                mime_type="application/pdf",
                page_count=page_count,
                start_page=spec.get("book_start_page", start_pdf),
                end_page=spec.get("book_end_page", end_pdf),
                summary=spec.get("focus"),
                toc_json=sec_json,
            )
            db.add(child)
        else:
            child.title = spec.get("title", child.title)
            child.parent_id = book.id
            child.topic_id = matched_topic.id if matched_topic else child.topic_id
            child.file_path = str(chap_path)
            child.file_size = file_size
            child.page_count = page_count
            child.start_page = spec.get("book_start_page", start_pdf)
            child.end_page = spec.get("book_end_page", end_pdf)
            child.summary = spec.get("focus")
            if sec_json:
                child.toc_json = sec_json

        created_or_updated.append(child)

    # Kapitel aus einer früheren Segmentierung, die es nicht mehr gibt, entfernen
    kept_ids = {c.id for c in created_or_updated}
    kept_paths = {c.file_path for c in created_or_updated} | {book.file_path}
    stale_paths: List[Path] = []
    stale_ids: List[str] = []
    for stale in db.query(Material).filter_by(parent_id=book.id).all():
        if stale.id not in kept_ids:
            stale_ids.append(stale.id)
            logger.info(f"🗑️ Veraltetes Kapitel entfernt: {stale.title} ({stale.id})")
            if stale.file_path and stale.file_path not in kept_paths:
                stale_paths.append(Path(stale.file_path))
            db.delete(stale)

    try:
        if book.kind != "Buch":
            book.kind = "Buch"
        db.commit()
        for stale_path in stale_paths:
            stale_path.unlink(missing_ok=True)
        _refresh_rendered_pages(created_or_updated, rewritten_ids + stale_ids)
        logger.info(f"✅ Schulbuch {book.title} ({book.id}) erfolgreich in {len(created_or_updated)} Kapitel segmentiert.")
        return created_or_updated
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Fehler bei der Buchsegmentierung für {book.id}: {e}", exc_info=True)
        raise


def _refresh_rendered_pages(chapters: List[Material], outdated_ids: List[str]) -> None:
    """Verwirft veraltete Seitenbilder und rendert die Kapitel im Hintergrund vor."""
    try:
        from backend.app.services.page_renderer import page_renderer
        if outdated_ids:
            page_renderer.purge_material_cache(outdated_ids)
        from backend.app.services.page_extraction import PRIORITY_BOOK_BACKFILL, page_extraction_service
        for chap in chapters:
            page_renderer.queue_material(chap.id, chap.file_path, chap.mime_type, chap.page_count)
            page_extraction_service.queue_material(chap.id, PRIORITY_BOOK_BACKFILL)
    except Exception as e:
        logger.warning(f"Kapitel konnten nicht zum Vorrendern eingereiht werden: {e}")


def is_candidate_book(material: Material) -> bool:
    """
    Prüft, ob ein Material ein Schulbuch ist, das in Kapitel segmentiert werden sollte.
    """
    if material.parent_id is not None:
        return False
    if material.mime_type != "application/pdf":
        return False
    # Ausdrücklich als etwas anderes erkannte Dokumente (Vokabelliste, Test, Mitschrift ...) nie zerlegen
    if normalize_kind(material.kind, default="") in NEVER_BOOK_KINDS:
        return False

    kind_lower = (material.kind or "").lower()
    if kind_lower in ("buch", "lehrbuch"):
        return True

    title_lower = (material.title or "").lower()
    book_keywords = [
        "buch", "lehrbuch", "schulbuch", "arbeitsbuch", "arbeitsheft", "workbook", "vorkurs",
        "fundamente", "cornelsen", "klett", "duden", "westermann",
        "mathematik", "englisch", "französisch", "franzoesisch", "biologie", "physik", "klasse 7"
    ]
    if material.page_count and material.page_count >= 20:
        if any(kw in title_lower for kw in book_keywords):
            return True
        if material.page_count >= 25:
            return True

    return False


def extract_chapters_from_pdf_outline(pdf_path: Path, total_pages: int) -> List[Dict[str, Any]]:
    """
    Extrahiert Kapitelgrenzen und Unterabschnitte aus den PDF-Lesezeichen (Document Outline),
    falls vorhanden. Sehr schnell und 100 % präzise für digitale Schulbuch-PDFs.
    """
    if not pdf_path.exists():
        return []

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        raw_outline = reader.outline
        if not raw_outline:
            return []

        def _flatten_outline(items, level=1) -> List[tuple]:
            res = []
            for item in items:
                if isinstance(item, list):
                    res.extend(_flatten_outline(item, level=level + 1))
                else:
                    try:
                        title = str(getattr(item, "title", item)).strip()
                        page_num = reader.get_destination_page_number(item)
                        if page_num is not None and 0 <= page_num < total_pages:
                            res.append((title, page_num + 1, level))
                    except Exception:
                        pass
            return res

        extracted = _flatten_outline(raw_outline)
        if len(extracted) < 2:
            return []

        # Sortieren nach Startseite
        extracted.sort(key=lambda x: x[1])

        # Prüfen, ob Level-1-Einträge existieren
        level1_items = [x for x in extracted if x[2] == 1]
        if len(level1_items) >= 2:
            chapter_entries = level1_items
            sub_entries = [x for x in extracted if x[2] > 1]
        else:
            unique_items = []
            for title, p_num, lvl in extracted:
                if not unique_items or p_num > unique_items[-1][1]:
                    unique_items.append((title, p_num, lvl))
            chapter_entries = unique_items
            sub_entries = []

        if len(chapter_entries) < 2:
            return []

        chapters: List[Dict[str, Any]] = []
        for idx, (title, start_p, lvl) in enumerate(chapter_entries):
            end_p = chapter_entries[idx + 1][1] - 1 if idx + 1 < len(chapter_entries) else total_pages
            if end_p < start_p:
                end_p = start_p

            chapter_sections = []
            for sub_title, sub_p, sub_lvl in sub_entries:
                if start_p <= sub_p <= end_p:
                    chapter_sections.append({
                        "title": sub_title,
                        "book_page": sub_p,
                        "relative_page": max(1, sub_p - start_p + 1),
                        "level": sub_lvl
                    })

            chapters.append({
                "unit_number": idx + 1,
                "title": title,
                "start_pdf_page": start_p,
                "end_pdf_page": end_p,
                "book_start_page": start_p,
                "book_end_page": end_p,
                "kind": "Buchauszug",
                "topic_name": title,
                "focus": f"Kapitel: {title}",
                "sections": chapter_sections
            })
        logger.info(f"📑 {len(chapters)} Kapitel mit Unterabschnitten direkt aus PDF-Bookmarks erkannt.")
        return chapters
    except Exception as e:
        logger.warning(f"Konnte PDF-Outline nicht parsen: {e}")
        return []


# Inhaltsverzeichnisse stehen in den ersten Seiten; lange TOCs (z. B. Deutschbuch) brauchen viel Text
TOC_SCAN_PAGES = 20
TOC_MAX_TEXT_CHARS = 15000


def extract_chapters_with_ai(file_path: Path, total_pages: int, title_hint: str = "") -> List[Dict[str, Any]]:
    """
    Analysiert die ersten Seiten eines Schulbuchs (Inhaltsverzeichnis) via OpenAI.
    Unterstützt sowohl digitale Texte als auch eingescannte Bildseiten (Vision).
    """
    from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL
    if not OPENAI_API_KEY or not file_path.exists():
        return []

    try:
        import json
        from openai import OpenAI
        from backend.app.services.material_ingestion import render_material_page_as_image, prepare_image_base64_for_vision

        client = OpenAI(api_key=OPENAI_API_KEY)

        reader = pypdf.PdfReader(str(file_path))
        toc_text = ""
        max_scan_pages = min(TOC_SCAN_PAGES, len(reader.pages))
        for p_idx in range(max_scan_pages):
            t = (reader.pages[p_idx].extract_text() or "").strip()
            if t:
                toc_text += f"\n--- Dokumentseite im PDF: Seite {p_idx + 1} ---\n" + t


        # Wenn digitaler Text vorhanden ist:
        if len(toc_text.strip()) > 150 and any(k in toc_text.lower() for k in ["inhalt", "kapitel", "unit", "inhaltsverzeichnis"]):
            messages = [
                {"role": "system", "content": BOOK_TOC_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Buchtitel: {title_hint}\nGesamtseitenzahl: {total_pages}\nAchte genau auf die PDF-Seitenzahlen in den Trennzeilen und berechne den Offset zu den gedruckten Buchseiten.\n\nInhaltsverzeichnis-Text:\n{toc_text[:TOC_MAX_TEXT_CHARS]}"
                }
            ]
        else:
            # Gescannte PDF: Seiten als Bilder rendern und an Vision übergeben (bis zu Seite 20)
            user_content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": f"Buchtitel: {title_hint}\nGesamtseiten: {total_pages}\nHier sind die Inhaltsverzeichnis-Seiten des gescannten Buchs. Achte genau auf die PDF-Seitenzahlen in den Trennzeilen und berechne den Offset zu den gedruckten Buchseiten."
                }
            ]
            for p_num in range(2, min(TOC_SCAN_PAGES, total_pages) + 1):
                try:
                    img_bytes, mime = render_material_page_as_image(str(file_path), "application/pdf", page_num=p_num)
                    b64 = prepare_image_base64_for_vision(img_bytes, mime)
                    user_content.append({
                        "type": "text",
                        "text": f"--- Dokumentseite im PDF: Seite {p_num} ---"
                    })
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}
                    })
                except Exception:
                    pass

            if len(user_content) <= 1:
                return []

            messages = [
                {"role": "system", "content": BOOK_TOC_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ]

        response = client.chat.completions.create(**chat_params(
            OPENAI_MODEL,
            temperature=0.1,
            messages=messages,
            response_format={"type": "json_object"}
        ))

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        raw_chaps = data.get("chapters", [])
        if not isinstance(raw_chaps, list) or len(raw_chaps) < 1:
            return []

        valid_chaps = []
        for c in raw_chaps:
            sp = int(c.get("start_pdf_page", 1))
            ep = int(c.get("end_pdf_page", sp))
            b_sp = int(c.get("book_start_page", sp))
            if 1 <= sp <= total_pages:
                ep = min(total_pages, max(sp, ep))
                sections = []
                for s in c.get("sections", []):
                    if isinstance(s, dict) and "title" in s:
                        bp = int(s.get("book_page", b_sp))
                        rp = int(s.get("relative_page", max(1, bp - b_sp + 1)))
                        sections.append({
                            "title": str(s.get("title")),
                            "book_page": bp,
                            "relative_page": rp,
                            "level": int(s.get("level", 2))
                        })

                valid_chaps.append({
                    "unit_number": len(valid_chaps) + 1,
                    "title": str(c.get("title", f"Kapitel {len(valid_chaps) + 1}")),
                    "start_pdf_page": sp,
                    "end_pdf_page": ep,
                    "book_start_page": b_sp,
                    "book_end_page": int(c.get("book_end_page", ep)),
                    "kind": "Buchauszug",
                    "topic_name": str(c.get("topic_name") or c.get("title")),
                    "focus": str(c.get("focus") or ""),
                    "sections": sections
                })

        logger.info(f"🤖 {len(valid_chaps)} Kapitel via OpenAI Inhaltsanalyse extrahiert.")
        return valid_chaps
    except Exception as e:
        logger.warning(f"Konnte Kapitel nicht via KI extrahieren: {e}")
        return []


def auto_segment_if_known(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """
    Prüft, ob für das gegebene Buch eine bekannte Kapiteltabelle vorliegt
    (z. B. Fundamente der Mathematik, À plus! 1, Physik Plus, Deutschbuch 7), und segmentiert es automatisch.
    """
    title_lower = (book.title or "").lower()
    if "fundamente" in title_lower and "mathematik" in title_lower:
        return segment_book_material(db, book, FUNDAMENTE_MATHE_7_CHAPTERS, force=force)
    if any(k in title_lower for k in ["aplus", "a plus", "à plus"]):
        return segment_book_material(db, book, APLUS_1_CHAPTERS, force=force)
    if "physik" in title_lower and "plus" in title_lower:
        return segment_book_material(db, book, PHYSIK_PLUS_7_CHAPTERS, force=force)
    if "deutschbuch" in title_lower:
        return segment_book_material(db, book, DEUTSCHBUCH_7_CHAPTERS, force=force)
    return None


def auto_detect_and_segment_book(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """Segmentiert ein Buch; parallele Aufrufe für dasselbe Buch warten aufeinander."""
    with _get_book_lock(book.id):
        with _segmentation_locks_guard:
            _segmentations_running.add(book.id)
        try:
            return _auto_detect_and_segment_book_unlocked(db, book, force=force)
        finally:
            with _segmentation_locks_guard:
                _segmentations_running.discard(book.id)


def _auto_detect_and_segment_book_unlocked(db: Session, book: Material, force: bool = False) -> Optional[List[Material]]:
    """
    Vollautomatische Pipeline zur Erkennung und Segmentierung von Schulbüchern:
    1. Prüft, ob bereits Kapitel existieren.
    2. Prüft bekannte Lehrbücher (Fundamente der Mathematik, Deutschbuch 7, Physik Plus 7 etc.).
    3. Liest PDF-Outline / Bookmarks aus (für digitale Lehrbücher).
    4. Nutzt OpenAI Inhaltsverzeichnis-Analyse (Text oder Vision für Scans).
    """
    if not book.file_path or not os.path.exists(book.file_path):
        return None

    # Bereits segmentiert?
    if not force:
        existing_children = db.query(Material).filter_by(parent_id=book.id).count()
        if existing_children > 0:
            return db.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()

    # 1. Bekannte Vorlagen prüfen
    known = auto_segment_if_known(db, book, force=force)
    if known:
        return known

    pdf_path = Path(book.file_path)

    # 2. PDF Outline / Lesezeichen prüfen
    outline_chapters = extract_chapters_from_pdf_outline(pdf_path, book.page_count)
    if outline_chapters:
        return segment_book_material(db, book, outline_chapters, force=force)

    # 3. KI Inhaltsverzeichnis-Erkennung (Vision/Text)
    ai_chapters = extract_chapters_with_ai(pdf_path, book.page_count, title_hint=book.title)
    if ai_chapters:
        return segment_book_material(db, book, ai_chapters, force=force)

    return None


def trigger_background_book_segmentation(material_id: str):
    """
    Startet die automatische Buchsegmentierung asynchron in einem Hintergrund-Thread,
    damit Web-Uploads und Inbox-Verarbeitung blitzschnell antworten.
    """
    with _segmentation_locks_guard:
        if material_id in _segmentations_running:
            logger.info(f"📚 Segmentierung für {material_id} läuft bereits.")
            return
        # Sofort als laufend markieren, damit die Bücherliste es direkt anzeigen kann
        _segmentations_running.add(material_id)

    def _worker():
        from backend.app.database import SessionLocal
        db = SessionLocal()
        try:
            book = db.query(Material).filter_by(id=material_id).first()
            if not book:
                return
            logger.info(f"📚 Hintergrund-Segmentierung für Buch '{book.title}' ({book.id}) gestartet...")
            result = auto_detect_and_segment_book(db, book)
            if result:
                logger.info(f"✅ Hintergrund-Segmentierung für Buch '{book.title}' erfolgreich abgeschlossen: {len(result)} Kapitel.")
                try:
                    from backend.app.services.book_topic_catalog import extend_catalog_for_subject
                    extend_catalog_for_subject(db, book.subject_id)
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Themenkatalog nach Segmentierung von {book.id} nicht erweitert: {e}")
            else:
                logger.info(f"ℹ️ Für Buch '{book.title}' wurden keine separaten Kapitel extrahiert (bleibt Gesamtbuch).")
                from backend.app.services.page_renderer import page_renderer
                page_renderer.queue_material(book.id, book.file_path, book.mime_type, book.page_count)
        except Exception as e:
            logger.error(f"❌ Fehler bei Hintergrund-Segmentierung für {material_id}: {e}", exc_info=True)
        finally:
            db.close()
            with _segmentation_locks_guard:
                _segmentations_running.discard(material_id)

    thread = threading.Thread(target=_worker, daemon=True, name=f"BookSegmenter-{material_id}")
    thread.start()


def get_chapter_sections(material: Material, parent_book: Optional[Material] = None) -> List[Dict[str, Any]]:
    """
    Liefert die Unterabschnitte (Inhaltsverzeichnis-Einträge) für ein Kapitel-Material.
    Priorität:
    1. Gespeicherter `material.toc_json` im Material.
    2. Fallback für bekannte Bücher (z. B. Fundamente der Mathematik 7 nach Kapitelnummer / Titel).
    3. Leere Liste, falls keine Unterabschnitte bekannt sind.
    """
    if material.toc_json:
        try:
            parsed = json.loads(material.toc_json)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass

    # Fallback-Ermittlung anhand Titel oder Kapitelnummer
    title_search = f"{(parent_book.title if parent_book else '')} {material.title or ''} {material.filename or ''}".lower()

    if "fundamente" in title_search or "mathematik 7" in title_search or "mathe7" in title_search or "lehrbuch" in title_search:
        # Finde unit_number aus material.title oder dossier_order oder id
        for spec in FUNDAMENTE_MATHE_7_CHAPTERS:
            unit_num = spec.get("unit_number")
            matches = False
            if f"kapitel {unit_num}:" in (material.title or "").lower() or f"kapitel {unit_num} " in (material.title or "").lower():
                matches = True
            elif unit_num == 0 and ("titelei" in (material.title or "").lower() or "lernausgangslage" in (material.title or "").lower()):
                matches = True
            elif f"_ch{unit_num:02d}" in (material.id or "") or f"kapitel_{unit_num:02d}" in (material.filename or "").lower():
                matches = True
            elif material.dossier_order is not None and material.dossier_order == unit_num + 2:
                matches = True
            elif material.start_page == spec.get("book_start_page"):
                matches = True

            if matches:
                return spec.get("sections", [])

    if "à plus" in title_search or "vorkurs" in title_search or "franz" in title_search:
        return FRANZ_VORKURS_SECTIONS

    if "physik" in title_search:
        for p_chap in PHYSIK_PLUS_7_CHAPTERS:
            if (p_chap["title"].lower() in (material.title or "").lower()) or \
               (material.dossier_order is not None and material.dossier_order == p_chap["unit_number"] + 2) or \
               (material.start_page == p_chap["book_start_page"]):
                return p_chap.get("sections", [])

    if "deutschbuch" in title_search:
        for d_chap in DEUTSCHBUCH_7_CHAPTERS:
            if (d_chap["title"].lower() in (material.title or "").lower()) or \
               (material.dossier_order is not None and material.dossier_order == d_chap["unit_number"] + 2) or \
               (material.start_page == d_chap["book_start_page"]):
                return d_chap.get("sections", [])

    return []


def get_all_book_sections(book: Material) -> List[Dict[str, Any]]:
    """
    Liefert alle Abschnitte für ein gesamtes Buch (z. B. wenn das Buch nicht segmentiert ist
    oder als Gesamtwerk geöffnet wird), bezogen auf die absoluten PDF-Seiten des Gesamtbuchs.
    """
    title_lower = f"{(book.title or '')} {(book.filename or '')}".lower()
    all_sections: List[Dict[str, Any]] = []

    if "fundamente" in title_lower or "mathematik" in title_lower or "mathe7" in title_lower:
        for chap in FUNDAMENTE_MATHE_7_CHAPTERS:
            chap_title = chap.get("title", "")
            chap_start_pdf = chap.get("start_pdf_page", 1)
            chap_book_start = chap.get("book_start_page", chap_start_pdf)

            all_sections.append({
                "title": chap_title,
                "book_page": chap_book_start,
                "relative_page": chap_start_pdf,
                "level": 1
            })

            for sec in chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", chap_book_start),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    if "à plus" in title_lower or "vorkurs" in title_lower or "franz" in title_lower:
        return FRANZ_VORKURS_SECTIONS

    if "physik" in title_lower:
        for p_chap in PHYSIK_PLUS_7_CHAPTERS:
            chap_start_pdf = p_chap.get("start_pdf_page", p_chap["book_start_page"])
            all_sections.append({
                "title": p_chap["title"],
                "book_page": p_chap["book_start_page"],
                "relative_page": chap_start_pdf,
                "level": 1
            })
            for sec in p_chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", p_chap["book_start_page"]),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    if "deutschbuch" in title_lower:
        for d_chap in DEUTSCHBUCH_7_CHAPTERS:
            chap_start_pdf = d_chap.get("start_pdf_page", d_chap["book_start_page"])
            all_sections.append({
                "title": d_chap["title"],
                "book_page": d_chap["book_start_page"],
                "relative_page": chap_start_pdf,
                "level": 1
            })
            for sec in d_chap.get("sections", []):
                rel_p = sec.get("relative_page", 1)
                all_sections.append({
                    "title": sec.get("title", ""),
                    "book_page": sec.get("book_page", d_chap["book_start_page"]),
                    "relative_page": chap_start_pdf + rel_p - 1,
                    "level": sec.get("level", 2)
                })
        return all_sections

    return []


