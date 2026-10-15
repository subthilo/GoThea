"""Einordnung von Dokumenten ohne KI: Fach, Thema, Art und Titel aus Dateiname und PDF-Text.

Dient als Rückfall, wenn keine KI verfügbar ist oder sie keine Antwort liefert, und für
saubere Dateinamen.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.taxonomy import Subject, Topic

SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "sub_math": ["mathe", "mathematik", "bruch", "brüche", "rational", "zahlen", "gleichung", "geometrie", "dreieck", "rechnen", "term", "dreisatz", "proportional", "prozent"],
    "sub_bio": ["bio", "biologie", "zelle", "mikroskop", "pflanze", "tier", "organell", "ökosystem", "chloroplast", "vakuole", "fotosynthese", "blattaufbau"],
    "sub_german": ["deutsch", "gedicht", "lyrik", "grammatik", "aufsatz", "inhaltsangabe", "satzbau", "ballade", "rechtschreibung", "kommasetzung", "erörterung"],
    "sub_english": ["englisch", "english", "vocabulary", "grammar", "tense", "present", "past", "words", "unit", "text", "reading", "simple past", "progressive"],
    "sub_geo": ["geografie", "geographie", "erdkunde", "karte", "kontinent", "klima", "ozean", "vulkan", "erde", "landschaft", "tektonik"],
    "sub_history": ["geschichte", "antike", "mittelalter", "rom", "griechenland", "ägypten", "ritter", "kaiser", "quelle", "neuzeit", "feudalismus"],
    "sub_physics": ["physik", "kraft", "optik", "licht", "spiegel", "geschwindigkeit", "energie", "magnet", "hebel", "akustik", "wärme"],
    "sub_chemie": ["chemie", "stoff", "reaktion", "atom", "molekül", "säure", "lauge", "teilchenmodell", "dichte", "aggregatzustand"],
    "sub_informatik": ["informatik", "computer", "algorithmus", "programmieren", "scratch", "python", "daten", "binär"],
    "sub_pb": ["politische bildung", "politik", "demokratie", "grundgesetz", "wahlen", "gesellschaft", "bundestag"],
    "sub_kunst": ["kunst", "zeichnen", "malen", "perspektive", "farben", "künstler", "skizze"],
    "sub_musik": ["musik", "noten", "tonleiter", "instrument", "komponist", "rhythmus", "orchester"],
    "sub_sport": ["sport", "bewegung", "regeln", "leichtathletik", "turnen", "training"],
    "sub_wat": ["wat", "wirtschaft", "arbeit", "technik", "beruf", "werkstoff", "holz", "metall"],
    "sub_ler": ["ler", "ethik", "religion", "philosophie", "werte", "glaube"],
    "sub_franzoesisch": ["französisch", "franzoesisch", "vocabulaire", "grammaire", "français"],
    "sub_orga": ["stundenplan", "wochenplan", "timetable", "organisation", "termine", "schulwoche", "ferien"],
}


# Fachnamen, wie die KI sie nennt, auf Fach-IDs abbilden (auch Kurzformen und Altnamen)
SUBJECT_NAME_TO_ID: Dict[str, str] = {
    "mathematik": "sub_math",
    "mathe": "sub_math",
    "biologie": "sub_bio",
    "bio": "sub_bio",
    "deutsch": "sub_german",
    "german": "sub_german",
    "englisch": "sub_english",
    "english": "sub_english",
    "geschichte": "sub_history",
    "history": "sub_history",
    "geografie": "sub_geo",
    "geographie": "sub_geo",
    "erdkunde": "sub_geo",
    "geo": "sub_geo",
    "physik": "sub_physics",
    "physics": "sub_physics",
    "chemie": "sub_chemie",
    "informatik": "sub_informatik",
    "politische bildung": "sub_pb",
    "pb": "sub_pb",
    "kunst": "sub_kunst",
    "musik": "sub_musik",
    "sport": "sub_sport",
    "ler": "sub_ler",
    "wat": "sub_wat",
    "französisch": "sub_franzoesisch",
    "franzoesisch": "sub_franzoesisch",
    "spanisch": "sub_spanisch",
    "latein": "sub_latein",
    "russisch": "sub_russisch",
    "astronomie": "sub_astronomie",
    "organisation": "sub_orga",
    "stundenplan": "sub_orga",
    "stundenplan & organisation": "sub_orga",
}


def clean_title_from_filename(filename: str) -> str:
    base = Path(filename).stem
    cleaned = re.sub(r"[_\-\.]+", " ", base)
    words = cleaned.strip().split()
    return " ".join(w.capitalize() for w in words) if words else "Unbenanntes Material"

def sanitize_filename_part(text: str) -> str:
    """Wandelt Umlaute und Sonderzeichen für saubere Dateinamen um."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    return cleaned.strip("_")


def detect_kind_from_filename_and_text(filename: str, text: str) -> str:
    lower_f = filename.lower()
    lower_t = text.lower()
    if any(k in lower_f or k in lower_t for k in ["stundenplan", "wochenplan", "timetable"]):
        return "Stundenplan"
    if any(k in lower_f or k in lower_t for k in ["heft", "notiz", "mitschrift", "hefter"]):
        return "Hefterseite"
    if any(k in lower_f or k in lower_t for k in ["buch", "lehrbuch", "seite", "kapitel"]):
        return "Buchauszug"
    if any(k in lower_f or k in lower_t for k in ["klassenarbeit", "klausur"]):
        return "Klassenarbeit"
    if any(k in lower_f or k in lower_t for k in ["test", "probe", "kontrolle", "uebungszettel"]):
        return "Test"
    return "Arbeitsblatt"


def predict_subject(db: Session, corpus: str) -> Optional[str]:
    """Fach mit den meisten Schlüsselwörtern im Text (Fachname zählt dreifach); sonst das erste aktive Fach."""
    all_subjects = db.query(Subject).filter_by(is_active=True).all()
    subject_map = {s.id: s for s in all_subjects}

    best_subject_id = None
    best_score = 0
    for sub_id, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in corpus)
        if sub_id in subject_map and subject_map[sub_id].name.lower() in corpus:
            score += 3
        if score > best_score:
            best_score = score
            best_subject_id = sub_id

    if not best_subject_id and all_subjects:
        best_subject_id = all_subjects[0].id
    return best_subject_id


def predict_topic(db: Session, subject_id: str, corpus: str) -> Optional[str]:
    """Thema des Fachs, dessen Namenswörter (länger als 3 Zeichen) am häufigsten im Text stehen."""
    predicted_topic_id = None
    best_score = 0
    for top in db.query(Topic).filter_by(subject_id=subject_id).all():
        score = sum(1 for w in top.name.lower().split() if len(w) > 3 and w in corpus)
        if score > best_score:
            best_score = score
            predicted_topic_id = top.id
    return predicted_topic_id


def predict_subject_and_topic(
    db: Session,
    filename: str,
    text: str
) -> Tuple[str, Optional[str]]:
    """Heuristische Fach- und Themenprognose anhand von Dateinamen und extrahiertem Text."""
    corpus = f"{filename} {text}".lower()
    subject_id = predict_subject(db, corpus)
    if not subject_id:
        return "sub_math", None
    return subject_id, predict_topic(db, subject_id, corpus)
