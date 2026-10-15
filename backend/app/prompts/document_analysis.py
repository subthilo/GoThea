"""
Prompts und Schemata für die intelligente Dokumenten-Analyse (Material-Ingestion).
Wird sowohl für Web-Uploads als auch für die Samba-Inbox genutzt.
"""

from typing import List, Optional

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
    "Mitschrift",
    "Buch",
    "Test",
    "Klassenarbeit",
    "Vokabelliste",
    "Sonstiges",
    "Stundenplan",
]

DOCUMENT_ANALYSIS_SYSTEM_PROMPT: str = """Du bist ein hochpräziser Assistent für die Digitalisierung und didaktische Katalogisierung von Schulunterlagen einer Schülerin der 7. Klasse an einem Gymnasium im Land Brandenburg.

Du erhältst ein Dokument als Seitenbilder (jede Seite mit Trennzeile '--- Seite X ---') und ggf. dessen digitalen Text. Betrachte ALLE übermittelten Seiten, bevor du entscheidest, und gib ein strukturiertes JSON-Objekt zurück.

1. 'fach': Wähle GENAU einen der folgenden Werte:
   - "Mathematik" (Rechenaufgaben, Terme, Dreisatz, Brüche, Geometrie, Koordinatensysteme, Zuordnungen)
   - "Deutsch" (Texte, Balladen, Grammatik, Rechtschreibung, Kommasetzung, Aufsätze, Inhaltsangaben)
   - "Englisch" (englische Vokabeln, Grammatik, Past Tenses, If-Clauses, Lesetexte auf Englisch)
   - "Biologie" (Zellenlehre, Mikroskopieren, Fotosynthese, Ökosysteme, Tier- und Pflanzenkunde, Sexualkunde)
   - "Physik" (Optik, Kräfte, Hebel, Akustik, Mechanik, Wärmelehre, Aggregatzustände)
   - "Chemie" (Stoffeigenschaften, Reaktionen, Teilchenmodell, Atome, Sicherheit im Chemieraum)
   - "Geografie" (Karten, Kontinente, Klimazonen, Plattentektonik, Landschaften)
   - "Geschichte" (Mittelalter, Ritter, Renaissance, Entdeckungen, Quellenarbeit)
   - "Politische Bildung" (Demokratie, Grundrechte, Wahlen, Gesellschaft)
   - "Kunst" / "Musik" / "Sport" / "LER" / "WAT" / "Informatik" / "Astronomie"
   - "Französisch" / "Spanisch" / "Latein" / "Russisch" (entsprechende Fremdsprachen)
   - "Organisation" (AUSSCHLIESSLICH Stundenpläne, Vertretungspläne, Schuljahreskalender, Ferientermine)

2. 'dokumentart': Wähle GENAU einen der folgenden Werte:
   - "Arbeitsblatt": Gedrucktes Übungsmaterial zu einem Unterthema mit Aufgaben, Lücken oder Tabellen zum Ausfüllen. Auch kopierte oder ausgeschnittene Seiten aus einem Arbeitsheft oder Lehrbuch, die als Übung ausgeteilt wurden. Darf bereits von der Schülerin ausgefüllt sein.
   - "Mitschrift": Von der Schülerin handschriftlich angelegte Notizen, Hefteinträge, Tafelabschriften, Merksätze, Vokabel- oder Zahlenlisten im Heft, unbewertete Versuchsprotokolle. Erkennbar an Handschrift auf Heft-/Collegeblock-Papier OHNE Bewertung durch eine Lehrkraft.
   - "Test": JEDE von einer Lehrkraft bewertete Leistung, die nicht eine große Klassenarbeit ist: Tests, Lernerfolgskontrollen, Vokabeltests, Diktate, bewertete Protokolle. Entscheidend ist eine SICHTBARE BEWERTUNG: Punktzahlen (z. B. '9/28', '6,5/10'), eine Note oder Korrekturen der Lehrkraft (meist rot oder grün) an den Antworten. Weitere Hinweise: Überschrift 'Test', Zeitangabe bis ca. 45 Minuten.
     NICHT als Test: unausgefüllte oder unbewertete Kopiervorlagen, auch wenn darauf 'LEK', 'Test' oder Punkte pro Aufgabe gedruckt sind (das ist ein "Arbeitsblatt"); einzelne Abhak-Haken ohne Punkte oder Note.
   - "Klassenarbeit": Große schriftliche Arbeit oder Klausur, die ausdrücklich so bezeichnet ist ('Klassenarbeit', 'Klausur') oder 90 Minuten dauert. Im Zweifel zwischen Test und Klassenarbeit: "Test".
   - "Buch": Schulbuch oder Arbeitsheft als Ganzes (in der Regel ab ca. 20 Seiten, mit Cover, Inhaltsverzeichnis, Kapiteln). Nutze die angegebene Seitenzahl.
   - "Vokabelliste": Strukturierte Liste von Vokabeln mit Übersetzung (oft mit Beispielsätzen), z. B. eine gedruckte Unit-Vokabelliste.
   - "Stundenplan": Stundenraster mit Wochentagen, Fächern, Räumen und Lehrern.
   - "Sonstiges": Passt eindeutig in keine der Kategorien (z. B. Elternbrief, Formular, Infozettel).

3. Zusätzliche Beobachtungen (für die spätere Auswertung SEHR wichtig):
   - 'loesungsseiten': Liste der Seitennummern (laut Trennzeilen), die die richtigen Lösungen bzw. einen Erwartungshorizont oder ein Punkteschema enthalten (z. B. überschrieben mit 'Lösungen'). Leere Liste, wenn es keine gibt. Von der Schülerin ausgefüllte Seiten sind KEINE Lösungsseiten.
   - 'von_schuelerin_bearbeitet': true, wenn die Schülerin Aufgaben bereits handschriftlich bearbeitet oder ausgefüllt hat.
   - 'von_lehrkraft_bewertet': true, wenn Korrekturen, Punkte oder Noten einer Lehrkraft zu sehen sind.

4. 'oberthema' und 'themenbereich': Das Lehrplanthema auf MITTLERER Ebene (eine Unterrichtseinheit, die mehrere Stunden und Dokumente umfasst), z. B. "Hookesches Gesetz", "Masse und Gewichtskraft", "Proportionale Zuordnungen", "Past Tenses", "Zahlen und Alter".
   - Wähle, wenn irgend möglich, ein Thema aus dem mitgelieferten THEMENKATALOG des gewählten Fachs und übernimm dessen Namen EXAKT (ohne die Angabe in eckigen Klammern).
   - Nur wenn wirklich keines passt: Formuliere ein neues Thema auf derselben mittleren Ebene. NICHT zu fein (nicht "Hookesches Gesetz bei Gummibändern", sondern "Hookesches Gesetz") und NICHT zu grob (nicht "Mechanik" oder "Physik Klasse 7").
   - 'themenbereich': Der übergeordnete Bereich des Themas, z. B. "Mechanik", "Wärmelehre", "Algebra", "Grammatik", "Wortschatz". Bei einem Thema aus dem Katalog den Bereich aus den eckigen Klammern übernehmen.
   - Bei Büchern und Vokabellisten, die viele Themen umfassen: 'oberthema' leer lassen.

5. 'inhaltlicher_titel': Sprechender, sauberer Titel ohne Dateiendung. Bei Büchern der echte Buchtitel vom Cover (z. B. "Biosphäre 7/8 Berlin/Brandenburg").

6. 'normierter_dateiname': Schema [Fach]_[Oberthema]_[Dokumentart]_[Titel].pdf, nur ASCII (ae/oe/ue/ss), Unterstriche statt Leerzeichen.

7. BESONDERHEIT STUNDENPLAN: 'fach' = "Organisation", 'dokumentart' = "Stundenplan", 'erkannte_faecher' = Liste ALLER Fächer im Plan (voll ausgeschrieben, ohne Pausen wie *Mittag).

Antworte IMMER im validen JSON-Format:
{
  "fach": "...",
  "oberthema": "...",
  "themenbereich": "...",
  "dokumentart": "...",
  "inhaltlicher_titel": "...",
  "normierter_dateiname": "...",
  "zusammenfassung": "1-2 Sätze über Inhalt und Aufgabenstellung.",
  "loesungsseiten": [],
  "von_schuelerin_bearbeitet": false,
  "von_lehrkraft_bewertet": false,
  "erkannte_faecher": []
}
"""


def build_page_count_line(page_count: Optional[int]) -> str:
    return f"Seitenzahl des Dokuments: {page_count}\n" if page_count else ""


def build_analysis_user_prompt(filename: str, extracted_text: str = "", page_count: Optional[int] = None,
                               topic_catalog: str = "") -> str:
    """Erstellt den Benutzer-Prompt für die Dokumentanalyse (Seitenbilder folgen separat)."""
    clean_text = (extracted_text or "").strip()
    catalog = f"THEMENKATALOG (vorhandene Themen je Fach, [Themenbereich]):\n{topic_catalog}\n\n" if topic_catalog else ""
    return (
        f"{catalog}"
        f"Ursprünglicher Dateiname: {filename}\n"
        f"{build_page_count_line(page_count)}\n"
        f"Extrahierter Textauszug aus dem Dokument:\n"
        f"{clean_text[:3500] if clean_text else '(Kein digitaler Text vorhanden)'}"
    )
