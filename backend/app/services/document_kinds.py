"""
Zentrale Definition der Dokumentarten in GoThea.

Dokumentart = was ein Dokument ist. Der Bearbeitungsstand (bearbeitet, ausgewertet,
besprochen) ist davon getrennt und gehört nicht hierher.
"""
from typing import Dict, Optional, Tuple

ARBEITSBLATT = "Arbeitsblatt"      # Einzelnes Übungsdokument zu einem Unterthema (auch Kopien aus Arbeitsheften)
MITSCHRIFT = "Mitschrift"          # Von Thea handschriftlich angelegte Notizen / Hefteinträge
BUCH = "Buch"                      # Schulbuch oder Arbeitsheft (wird in Kapitel segmentiert)
BUCHAUSZUG = "Buchauszug"          # Kapitel eines Buchs (entsteht durch Segmentierung)
TEST = "Test"                      # Von der Lehrkraft bewertete Leistung: Test, Diktat, bewertetes Protokoll
KLASSENARBEIT = "Klassenarbeit"    # Große schriftliche Arbeit / Klausur
VOKABELLISTE = "Vokabelliste"      # Vokabeln mit Übersetzung und Beispielsätzen
SONSTIGES = "Sonstiges"            # Passt in keine andere Art
STUNDENPLAN = "Stundenplan"

DOCUMENT_KINDS = [
    ARBEITSBLATT, MITSCHRIFT, BUCH, BUCHAUSZUG, TEST, KLASSENARBEIT,
    VOKABELLISTE, SONSTIGES, STUNDENPLAN,
]

# Frühere Bezeichnungen -> heutige Dokumentart
LEGACY_KINDS: Dict[str, str] = {
    "Hefterseite": MITSCHRIFT,
    "Hefter": MITSCHRIFT,
    "Klausur": KLASSENARBEIT,
    "Übungszettel": ARBEITSBLATT,
    "Lehrbuch": BUCH,
    "Arbeitsheft": BUCH,
    "Diktat": TEST,
}

# Dokumentarten, die nie als Buch segmentiert werden
NEVER_BOOK_KINDS = {MITSCHRIFT, TEST, KLASSENARBEIT, VOKABELLISTE, SONSTIGES, STUNDENPLAN}


def normalize_kind(kind: Optional[str], default: str = SONSTIGES) -> str:
    """Bildet beliebige Eingaben (auch alte Bezeichnungen) auf eine gültige Dokumentart ab."""
    k = (kind or "").strip()
    if k in DOCUMENT_KINDS:
        return k
    if k in LEGACY_KINDS:
        return LEGACY_KINDS[k]
    lowered = {d.lower(): d for d in DOCUMENT_KINDS}
    lowered.update({legacy.lower(): new for legacy, new in LEGACY_KINDS.items()})
    return lowered.get(k.lower(), default)


def dossier_for_kind(kind: str, title: str, topic_or_subject: str, subject_name: str) -> Tuple[str, str]:
    """Liefert (Mappen-Titel, Mappen-Art), in die ein Dokument dieser Art einsortiert wird."""
    if kind == STUNDENPLAN:
        return "Stundenplan & Organisation", "organisation"
    if kind in (BUCH, BUCHAUSZUG):
        return f"Lehrbuch: {title}", "lehrbuch"
    if kind == MITSCHRIFT:
        return f"Mitschriften: {topic_or_subject}", "hefter"
    if kind in (TEST, KLASSENARBEIT):
        return f"Tests & Arbeiten: {subject_name}", "testsammlung"
    if kind == VOKABELLISTE:
        return f"Vokabeln: {subject_name}", "vokabeln"
    if kind == SONSTIGES:
        return f"Sonstiges: {subject_name}", "sonstiges"
    return f"Arbeitsblätter: {topic_or_subject}", "uebungsmappe"
