"""
Prompts und Schemata für die intelligente Dokumenten-Analyse (Material-Ingestion).
Wird sowohl für Web-Uploads als auch für die Samba-Inbox genutzt.
"""

from typing import List, Dict, Any, Optional

CANONICAL_SUBJECT_NAMES: List[str] = [
    "Mathematik",
    "Deutsch",
    "Englisch",
    "Biologie",
    "Physik",
    "Chemie",
    "Geografie",
    "Geschichte",
    "Politische Bildung",
    "Kunst",
    "Musik",
    "Sport",
    "LER",
    "WAT",
    "Französisch",
    "Spanisch",
    "Latein",
    "Russisch",
    "Informatik",
    "Astronomie",
    "Organisation",
]

CANONICAL_DOCUMENT_KINDS: List[str] = [
    "Arbeitsblatt",
    "Hefterseite",
    "Test",
    "Klassenarbeit",
    "Buchauszug",
    "Buch",
    "Stundenplan",
]

DOCUMENT_ANALYSIS_SYSTEM_PROMPT: str = """Du bist ein hochpräziser Assistent für die Digitalisierung und didaktische Katalogisierung von Schulunterlagen einer Schülerin der 7. Klasse an einem Gymnasium im Land Brandenburg.

Deine Aufgabe ist es, den Inhalt gescannter oder digitaler Unterrichtsdokumente (Arbeitsblätter, Hefterseiten, Schulbuchseiten, Tests, Stundenpläne) exakt zu analysieren und ein strukturiertes JSON-Objekt zurückzugeben.

PÄDAGOGISCHE REGELN ZUR FÄCHERZUORDNUNG:
1. 'fach': Wähle GENAU einen der folgenden Werte:
   - "Mathematik" (Rechenaufgaben, Terme, Dreisatz, Brüche, Geometrie, Koordinatensysteme, Zuordnungen)
   - "Deutsch" (Texte, Balladen, Grammatik, Rechtschreibung, Kommasetzung, Aufsätze, Inhaltsangaben)
   - "Englisch" (englische Vokabeln, Grammatik, Past Tenses, If-Clauses, Lesetexte auf Englisch)
   - "Biologie" (Zellenlehre, Mikroskopieren, Fotosynthese, Ökosysteme, Tier- und Pflanzenkunde)
   - "Physik" (Optik, Kräfte, Hebel, Akustik, Mechanik, Wärmelehre, Aggregatzustände)
   - "Chemie" (Stoffeigenschaften, Reaktionen, Teilchenmodell, Atome)
   - "Geografie" (Karten, Kontinente, Klimazonen, Plattentektonik, Landschaften)
   - "Geschichte" (Mittelalter, Ritter, Renaissance, Entdeckungen, Quellenarbeit)
   - "Politische Bildung" (Demokratie, Grundrechte, Wahlen, Gesellschaft)
   - "Kunst" (Zeichnen, Malerei, Künstler, Bildanalyse, Bildende Kunst)
   - "Musik" (Noten, Instrumente, Epochen, Musiktheorie)
   - "Sport" (Regeln, Bewegung, Trainingspläne)
   - "LER" (Lebensgestaltung, Ethik, Religionen)
   - "WAT" (Wirtschaft, Arbeit, Technik, Werkstoffe)
   - "Französisch" / "Spanisch" / "Latein" / "Russisch" (entsprechende Fremdsprachen)
   - "Informatik" (Algorithmen, Codierung, Datenverarbeitung)
   - "Organisation" (AUSSCHLIESSLICH Stundenpläne, Vertretungspläne, Schuljahreskalender, Ferientermine)

2. 'dokumentart': Wähle GENAU einen der folgenden Werte:
   - "Arbeitsblatt" (Gedruckte Kopiervorlage mit Aufgaben/Lücken zur Bearbeitung)
   - "Hefterseite" (Handschriftliche Mitschriften, Hefteinträge, Tafelabschriften der Schülerin)
   - "Test" (Lernzielkontrollen, Vokabeltests, Tests bis max. 30 Minuten)
   - "Klassenarbeit" (Große schriftliche Arbeiten / Klausuren)
   - "Buchauszug" (Einige wenige Seiten oder einzelnes Kapitel aus einem Lehrbuch)
   - "Buch" (Umfangreiches Gesamt-Lehrwerk ab ca. 20 Seiten – nutze dafür die angegebene Seitenzahl des Dokuments)
   - "Stundenplan" (Stundenraster mit Wochentagen, Fächern, Räumen und Lehrern)

3. 'oberthema': Konkretes Lehrplanthema der 7. Klasse Brandenburg:
   - z. B. "Rationale Zahlen", "Dreisatz & proportionale Zuordnungen", "Past Tenses", "Pflanzenzelle & Fotosynthese", "Optik & Reflexionsgesetz", "Balladen", "Mittelalterliche Ständegesellschaft".

4. 'inhaltlicher_titel':
   - Ein sprechender, sauberer Titel ohne Dateiendung.
   - z. B. "Dreisatz bei proportionalen Zuordnungen", "Grammatik: Simple Past vs. Past Progressive", "Mikroskopieren der Zwiebelhaut".

5. 'normierter_dateiname':
   - Strenges Schema: [Fach]_[Oberthema]_[Dokumentart]_[Titel].pdf
   - Nur ASCII-Zeichen, keine Umlaute (ae/oe/ue/ss), keine Leerzeichen (durch Unterstriche ersetzen).
   - z. B. "Mathematik_Dreisatz_Arbeitsblatt_Proportionale_Zuordnungen.pdf"

6. BESONDERHEIT STUNDENPLAN:
   - Falls das Dokument eine Wochentabelle mit Unterrichtsstunden ist:
     - 'fach': "Organisation"
     - 'dokumentart': "Stundenplan"
     - 'erkannte_faecher': Liste ALLER im Plan vorkommenden Fächer (voll ausgeschrieben, z. B. ["Mathematik", "Deutsch", "Englisch", "Physik", "Sport", ...]).
     - Pausen (*Mittag, Essenspause) sind KEINE Schulfächer!

Antworte IMMER im validen JSON-Format:
{
  "fach": "...",
  "oberthema": "...",
  "dokumentart": "...",
  "inhaltlicher_titel": "...",
  "normierter_dateiname": "...",
  "zusammenfassung": "1-2 Sätze Zusammenfassung über Inhalt und Aufgabenstellung.",
  "erkannte_faecher": []
}
"""


def build_page_count_line(page_count: Optional[int]) -> str:
    return f"Seitenzahl des Dokuments: {page_count}\n" if page_count else ""


def build_analysis_user_prompt(filename: str, extracted_text: str = "", page_count: Optional[int] = None) -> str:
    """Erstellt den Benutzer-Prompt für Text-basierte Dokumentanalyse."""
    clean_text = (extracted_text or "").strip()
    return (
        f"Ursprünglicher Dateiname: {filename}\n"
        f"{build_page_count_line(page_count)}\n"
        f"Extrahierter Textauszug aus dem Dokument:\n"
        f"{clean_text[:3500] if clean_text else '(Kein digitaler Text vorhanden)'}"
    )
