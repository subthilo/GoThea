import os
import re
import io
import json
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.services.material_ingestion import (
    render_material_page_as_image,
    sanitize_filename_part,
    prepare_image_base64_for_vision
)

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. DER 23-FÄCHER-KANON (RLP BRANDENBURG & GYMNASIUM)
# ==============================================================================

CANONICAL_SUBJECTS: Dict[str, Dict[str, Any]] = {
    "organisation": {
        "id": "sub_orga",
        "name": "Organisation",
        "icon": "📅",
        "color_code": "#6366f1",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["orga", "organisation", "stundenplan", "termine", "allgemein"],
        "topics": [
            ("Stundenplan & Termine", 7, "E", "Wochenplan, Raumbelegungen, Sprechzeiten"),
        ]
    },
    "math": {
        "id": "sub_math",
        "name": "Mathematik",
        "icon": "📐",
        "color_code": "#2563eb",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["ma", "mathe", "mathematik", "m", "math"],
        "topics": [
            ("Rationale Zahlen", 7, "E", "Rechnen mit negativen Zahlen, Brüche und Dezimalbrüche ordnen"),
            ("Terme und lineare Gleichungen", 7, "E", "Termumformungen, Äquivalenzumformungen"),
            ("Prozent- und Zinsrechnung", 7, "E", "Grundwert, Prozentwert, Prozentsatz, Zinseszins"),
            ("Geometrie & Dreiecke", 7, "E", "Winkelsumme, Dreieckskonstruktionen SWS/WSW/SSS"),
        ]
    },
    "german": {
        "id": "sub_german",
        "name": "Deutsch",
        "icon": "📖",
        "color_code": "#f59e0b",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["de", "deutsch", "d", "german"],
        "topics": [
            ("Balladen analysieren", 7, "E", "Metrum, Reimschema, sprachliche Bilder"),
            ("Argumentieren & Erörtern", 7, "E", "Dreischritt: Behauptung, Begründung, Beispiel"),
            ("Satzgefüge & Grammatik", 7, "E", "Subjunktionen, Relativsätze, Kommasetzung"),
        ]
    },
    "english": {
        "id": "sub_english",
        "name": "Englisch",
        "icon": "🇬🇧",
        "color_code": "#8b5cf6",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["en", "eng", "englisch", "english", "e"],
        "topics": [
            ("Past Tenses (Simple vs. Progressive)", 7, "E", "Signal words, storytelling in the past"),
            ("Conditional Clauses I & II", 7, "E", "Real and unreal conditions, if-clauses"),
            ("Life in the UK & Culture", 7, "E", "Landeskunde, London, schools in Britain"),
        ]
    },
    "bio": {
        "id": "sub_bio",
        "name": "Biologie",
        "icon": "🌿",
        "color_code": "#10b981",
        "min_grade": 5,
        "max_grade": 13,
        "aliases": ["bio", "biologie", "b", "biology"],
        "topics": [
            ("Fotosynthese und Blattaufbau", 7, "E", "Zellulärer Aufbau, Lichtabsorption, Wortgleichung"),
            ("Mikroskopieren & Zellaufbau", 7, "E", "Tier- und Pflanzenzelle, Zellkern, Organellen"),
            ("Ökosystem Wald und See", 7, "E", "Biotische/abiotische Faktoren, Nahrungsketten"),
        ]
    },
    "physics": {
        "id": "sub_physics",
        "name": "Physik",
        "icon": "⚡",
        "color_code": "#ec4899",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["ph", "phy", "physik", "physics"],
        "topics": [
            ("Optik: Reflexion & Brechung", 7, "E", "Reflexionsgesetz, ebener Spiegel, Sammellinsen"),
            ("Mechanik: Kräfte & Masse", 7, "E", "Gewichtskraft F=m*g, Hookesches Gesetz, Kraftmesser"),
            ("Einfache Maschinen: Hebel", 7, "E", "Hebelgesetz, Drehmoment, feste und lose Rollen"),
        ]
    },
    "chemistry": {
        "id": "sub_chemie",
        "name": "Chemie",
        "icon": "🧪",
        "color_code": "#06b6d4",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["ch", "che", "chemie", "chemistry"],
        "topics": [
            ("Stoffe und ihre Eigenschaften", 7, "E", "Dichte, Schmelz- und Siedetemperatur, Aggregatzustände"),
            ("Chemische Reaktionen", 7, "E", "Reaktionsgleichungen, Stoffumwandlung, Energieumsatz"),
            ("Teilchenmodell & Atome", 7, "E", "Atomaufbau, Element vs. Verbindung, Atombilanz"),
        ]
    },
    "history": {
        "id": "sub_history",
        "name": "Geschichte",
        "icon": "📜",
        "color_code": "#64748b",
        "min_grade": 5,
        "max_grade": 13,
        "aliases": ["ge", "ges", "geschichte", "history"],
        "topics": [
            ("Das Mittelalter: Lebenswelten", 7, "E", "Feudalismus, Ständegesellschaft, Rittertum"),
            ("Aufbruch in die Neuzeit", 7, "E", "Buchdruck, Renaissance, Entdeckungsfahrten"),
        ]
    },
    "geo": {
        "id": "sub_geo",
        "name": "Geografie",
        "icon": "🌍",
        "color_code": "#059669",
        "min_grade": 5,
        "max_grade": 13,
        "aliases": ["geo", "geografie", "geographie", "erdkunde", "ek", "geography"],
        "topics": [
            ("Klimazonen & Vegetationszonen", 7, "E", "Tropen bis Polarzone, Klimadiagramme auswerten"),
            ("Kräfte der Erde: Plattentektonik", 7, "E", "Erdbeben, Vulkanismus, Kontinentalverschiebung"),
        ]
    },
    "pb": {
        "id": "sub_pb",
        "name": "Politische Bildung",
        "icon": "⚖️",
        "color_code": "#475569",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["pb", "politik", "politische bildung", "pol", "sozialkunde", "gemeinschaftskunde"],
        "topics": [
            ("Demokratie & Mitbestimmung", 7, "E", "Wahlen, Klassensprecher, Kommunalpolitik"),
            ("Medien & Meinungsbildung", 7, "E", "Fake News, Informationsfreiheit, soziale Netzwerke"),
        ]
    },
    "wat": {
        "id": "sub_wat",
        "name": "WAT / Wirtschaft",
        "icon": "🛠️",
        "color_code": "#d97706",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["wat", "wirtschaft", "technik", "wirtschaft-arbeit-technik", "wi"],
        "topics": [
            ("Werkstoffe & Fertigung", 7, "E", "Holz, Metall, Kunststoff, Werkzeuge und Sicherheit"),
            ("Ernährung & Haushalt", 7, "E", "Nährstoffe, Zubereitung, Haushaltsbudget"),
            ("Berufsorientierung", 7, "E", "Berufsfelder, Stärkenanalyse, Praktikumsvorbereitung"),
        ]
    },
    "art": {
        "id": "sub_kunst",
        "name": "Kunst",
        "icon": "🎨",
        "color_code": "#f43f5e",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["ku", "kunst", "bildende kunst", "bk", "art"],
        "topics": [
            ("Grafik & Zeichentechniken", 7, "E", "Schraffur, Perspektive, Fluchtpunkt"),
            ("Farbenlehre & Malerei", 7, "E", "Farbkontraste nach Itten, Farbmischung"),
            ("Plastik & Dreidimensionalität", 7, "E", "Ton, Papierplastik, Skulptur"),
        ]
    },
    "music": {
        "id": "sub_musik",
        "name": "Musik",
        "icon": "🎵",
        "color_code": "#a855f7",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["mu", "musik", "music"],
        "topics": [
            ("Notenlehre & Rhythmus", 7, "E", "Violin- und Bassschlüssel, Taktarten, Synkopen"),
            ("Instrumentenkunde", 7, "E", "Orchesteraufbau, Holz-/Blechblasinstrumente, Saiteninstrumente"),
            ("Epochen der Musikgeschichte", 7, "E", "Barock, Klassik, Romantik, Moderne"),
        ]
    },
    "sports": {
        "id": "sub_sport",
        "name": "Sport",
        "icon": "🏃",
        "color_code": "#14b8a6",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["sp", "spo", "sport", "sporttheorie", "pe"],
        "topics": [
            ("Leichtathletik", 7, "E", "Sprint, Weitsprung, Kugelstoßen, Ausdauerlauf"),
            ("Sportspiele", 7, "E", "Basketball, Volleyball, Fußball, Handball Regeln"),
            ("Fitness & Trainingslehre", 7, "E", "Aufwärmen, Dehnen, Ausdauer, Kraft"),
        ]
    },
    "ler": {
        "id": "sub_ler",
        "name": "LER / Ethik",
        "icon": "🧭",
        "color_code": "#0d9488",
        "min_grade": 5,
        "max_grade": 13,
        "aliases": ["ler", "ethik", "philosophie", "phil", "lebensgestaltung"],
        "topics": [
            ("Ich und die Gemeinschaft", 7, "E", "Identität, Rollenbilder, Freundschaft"),
            ("Werte & Konflikte", 7, "E", "Gerechtigkeit, Toleranz, Streitkultur"),
            ("Religionen & Weltanschauungen", 7, "E", "Weltreligionen im Vergleich, Feste und Bräuche"),
        ]
    },
    "religion": {
        "id": "sub_religion",
        "name": "Religion",
        "icon": "🕊️",
        "color_code": "#8b5cf6",
        "min_grade": 1,
        "max_grade": 13,
        "aliases": ["reli", "rel", "religion", "evangelische religion", "katholische religion"],
        "topics": [
            ("Altes und Neues Testament", 7, "E", "Bibelaufbau, Gleichnisse, Schöpfungsberichte"),
            ("Glaube & Ethik im Alltag", 7, "E", "Nächstenliebe, Verantwortung für die Schöpfung"),
        ]
    },
    "inf": {
        "id": "sub_informatik",
        "name": "Informatik",
        "icon": "💻",
        "color_code": "#3b82f6",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["inf", "itg", "informatik", "computer science", "cs"],
        "topics": [
            ("Algorithmen & Flussdiagramme", 7, "E", "Schrittfolgen, Verzweigungen, Schleifen"),
            ("Daten & Codierung", 7, "E", "Binärsystem, Pixelgrafik, Textcodierung"),
            ("Sicherheit & Datenschutz", 7, "E", "Passwörter, Urheberrecht, Privatsphäre"),
        ]
    },
    "french": {
        "id": "sub_franzoesisch",
        "name": "Französisch",
        "icon": "🇫🇷",
        "color_code": "#2563eb",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["fr", "fra", "französisch", "franzoesisch", "french"],
        "topics": [
            ("Grundwortschatz & Dialoge", 7, "E", "Sich vorstellen, Familie, Schule in Frankreich"),
            ("Grammatik: Verben auf -er", 7, "E", "Präsens-Konjugation, Verneinung ne...pas"),
            ("Passé Composé Einführung", 7, "E", "Bildung mit avoir, regelmäßige Partizipien"),
        ]
    },
    "spanish": {
        "id": "sub_spanisch",
        "name": "Spanisch",
        "icon": "🇪🇸",
        "color_code": "#ef4444",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["spa", "spanisch", "spanish", "es"],
        "topics": [
            ("Grundwortschatz & Begrüßung", 7, "E", "Sich vorstellen, Zahlen, Alltag"),
            ("Regelmäßige Verben (-ar, -er, -ir)", 7, "E", "Konjugation im Presente"),
            ("Ser vs. Estar", 7, "E", "Dauerhafte Eigenschaften vs. Zustände"),
        ]
    },
    "latin": {
        "id": "sub_latein",
        "name": "Latein",
        "icon": "🏛️",
        "color_code": "#b45309",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["la", "lat", "latein", "latin"],
        "topics": [
            ("Deklinationen (a-/o-Deklination)", 7, "E", "Kasusfunktionen, KNG-Kongruenz"),
            ("Verben: Präsens & Perfekt", 7, "E", "Konjugationsklassen, Personalendungen"),
            ("Römisches Alltagsleben", 7, "E", "Forum Romanum, Thermen, Wagenrennen"),
        ]
    },
    "russian": {
        "id": "sub_russisch",
        "name": "Russisch",
        "icon": "🇷🇺",
        "color_code": "#b91c1c",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["ru", "russisch", "russian"],
        "topics": [
            ("Kyrillische Schrift & Aussprache", 7, "E", "Alphabet, Vokalreduktion, Betonung"),
            ("Grundwortschatz & Familie", 7, "E", "Einfache Dialoge, Begrüßungen"),
        ]
    },
    "ancient_greek": {
        "id": "sub_altgriechisch",
        "name": "Altgriechisch",
        "icon": "🏺",
        "color_code": "#92400e",
        "min_grade": 8,
        "max_grade": 13,
        "aliases": ["gr", "griechisch", "altgriechisch", "greek"],
        "topics": [
            ("Griechisches Alphabet", 8, "E", "Schrift, Hauchlaute, Akzente"),
            ("O- und A-Deklination", 8, "E", "Kasus, Formenlehre"),
        ]
    },
    "astronomy": {
        "id": "sub_astronomie",
        "name": "Astronomie",
        "icon": "🔭",
        "color_code": "#6366f1",
        "min_grade": 9,
        "max_grade": 13,
        "aliases": ["ast", "astronomie", "astro", "astronomy"],
        "topics": [
            ("Unser Sonnensystem", 9, "E", "Planeten, Monde, Sonnenfinsternis"),
            ("Orientierung am Nachthimmel", 9, "E", "Sternbilder, Polarstern, Himmelskoordinaten"),
        ]
    },
    "theater": {
        "id": "sub_ds",
        "name": "Darstellendes Spiel",
        "icon": "🎭",
        "color_code": "#f97316",
        "min_grade": 7,
        "max_grade": 13,
        "aliases": ["ds", "darstellendes spiel", "theater", "drama"],
        "topics": [
            ("Körper & Raum", 7, "E", "Präsenz, Körpersprache, Freeze"),
            ("Rollen & Status", 7, "E", "Statuswippe, Monolog, Dialoggestaltung"),
        ]
    }
}

# Aufbau eines schnellen Such-Index für Aliase und Abkürzungen
ALIAS_TO_CANONICAL_KEY: Dict[str, str] = {}
for key, data in CANONICAL_SUBJECTS.items():
    ALIAS_TO_CANONICAL_KEY[key.lower()] = key
    ALIAS_TO_CANONICAL_KEY[data["name"].lower()] = key
    for alias in data.get("aliases", []):
        ALIAS_TO_CANONICAL_KEY[alias.lower()] = key

def match_subject_to_canonical(query_str: str) -> Optional[Dict[str, Any]]:
    """Ermittelt das passende kanonische Fach anhand von Name oder Abkürzung."""
    raw = (query_str or "").strip()
    if not raw:
        return None

    # Normalisierung: führende Sonderzeichen (*, #, -) und Turnuskürzel wie (A), (B), [A], [B] entfernen
    clean = re.sub(r"^[\*#\-_]+", "", raw).strip().lower()
    clean_no_week = re.sub(r"[\(\[\{][ab][\)\]\}]", "", clean).strip()

    # 1. Direkter Match im Alias-Index
    for cand in [clean, clean_no_week]:
        if cand in ALIAS_TO_CANONICAL_KEY:
            canon_key = ALIAS_TO_CANONICAL_KEY[cand]
            return CANONICAL_SUBJECTS[canon_key]

    # 2. Token-basiertes Matching für Zusammensetzungen (z. B. "*Sp DÜCK gewo" -> "sp", "En(B)" -> "en")
    tokens = re.findall(r"[a-zäöüß]+", clean)
    for tok in tokens:
        if tok in ALIAS_TO_CANONICAL_KEY:
            canon_key = ALIAS_TO_CANONICAL_KEY[tok]
            return CANONICAL_SUBJECTS[canon_key]

    # 3. Substring Match für längere Bezeichnungen (>= 3 Zeichen)
    for alias, canon_key in ALIAS_TO_CANONICAL_KEY.items():
        if len(alias) >= 3 and (alias in clean or clean in alias):
            return CANONICAL_SUBJECTS[canon_key]

    return None

def get_or_create_organisation_subject(db: Session) -> Subject:
    """Holt oder erstellt das übergeordnete Fach 'Organisation' (📅) für Stundenpläne."""
    sub = db.query(Subject).filter(
        (Subject.id == "sub_orga") |
        (Subject.name.in_(["Organisation", "Stundenplan & Organisation", "Stundenplan"]))
    ).first()
    if not sub:
        sub = Subject(
            id="sub_orga",
            name="Organisation",
            icon="📅",
            color_code="#6366f1",
            min_grade=1,
            max_grade=13,
            is_active=True
        )
        db.add(sub)
        db.flush()
    return sub


def is_timetable_document(
    filename: str = "",
    text: str = "",
    raw_ai_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Prüft zuverlässig, ob ein Dokument (aus Upload oder Inbox) ein Stundenplan ist.
    """
    if raw_ai_data and isinstance(raw_ai_data, dict):
        d_art = (raw_ai_data.get("dokumentart") or "").strip().lower()
        fach = (raw_ai_data.get("fach") or "").strip().lower()
        title = (raw_ai_data.get("inhaltlicher_titel") or "").strip().lower()
        if d_art == "stundenplan" or fach in ("organisation", "stundenplan") or "stundenplan" in title or "stundenplan" in d_art:
            return True

    lower_f = (filename or "").lower()
    if any(k in lower_f for k in ["stundenplan", "timetable", "wochenplan", "stunden_plan", "stundenuebersicht"]):
        return True

    lower_t = (text or "").lower()
    if "stundenplan" in lower_t or "wochenplan" in lower_t:
        return True

    weekdays = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag"]
    found_weekdays = sum(1 for d in weekdays if d in lower_t)
    if found_weekdays >= 3 and any(w in lower_t for w in ["stunde", "a-woche", "b-woche", "pause", "unterricht", "u-stunde", "u-std"]):
        return True

    return False


def sync_subjects_to_database(
    db: Session,
    subject_candidates: List[str]
) -> Tuple[List[Subject], List[Subject]]:
    """
    Prüft eine Liste von Fächern (aus dem Stundenplan) gegen die Datenbank.
    Legt noch nicht existierende Fächer automatisch an und aktiviert sie.
    Gibt (created_subjects, existing_subjects) zurück.
    """
    created_subjects: List[Subject] = []
    existing_subjects: List[Subject] = []
    
    # Alle aktiven und inaktiven Fächer laden
    all_db_subjects = db.query(Subject).all()

    # Migration / Bereinigung: Falls 'Bildende Kunst' in der DB existiert, zu 'Kunst' vereinheitlichen
    for s in all_db_subjects:
        if s.name.strip().lower() in ("bildende kunst", "kunst") and s.name != "Kunst":
            s.name = "Kunst"
            db.flush()

    # Indexe nach potenzieller Umbenennung aktualisieren
    all_db_subjects = db.query(Subject).all()
    db_by_name = {s.name.lower(): s for s in all_db_subjects}
    db_by_id = {s.id: s for s in all_db_subjects}

    for raw_cand in subject_candidates:
        cand_str = str(raw_cand).strip()
        if not cand_str:
            continue

        canonical = match_subject_to_canonical(cand_str)
        if canonical:
            target_name = canonical["name"]
            target_id = canonical["id"]
            icon = canonical["icon"]
            color = canonical["color_code"]
            min_grade = canonical["min_grade"]
            max_grade = canonical["max_grade"]
            initial_topics = canonical.get("topics", [])
        else:
            # Fallback: Freies Fach anlegen
            target_name = cand_str.capitalize()
            target_id = f"sub_{uuid.uuid4().hex[:8]}"
            icon = "📚"
            color = "#2563eb"
            min_grade = 1
            max_grade = 13
            initial_topics = []

        # Prüfen, ob bereits in DB
        matched_db_subject = None
        if target_name.lower() in db_by_name:
            matched_db_subject = db_by_name[target_name.lower()]
        elif target_id in db_by_id:
            matched_db_subject = db_by_id[target_id]

        if matched_db_subject:
            # Falls inaktiv, reaktivieren
            if not matched_db_subject.is_active:
                matched_db_subject.is_active = True
                db.flush()
            if matched_db_subject not in existing_subjects:
                existing_subjects.append(matched_db_subject)
        else:
            # Neu anlegen
            # Prüfen, ob ID schon vergeben ist
            if db.query(Subject).filter_by(id=target_id).first():
                target_id = f"sub_{uuid.uuid4().hex[:8]}"

            new_subject = Subject(
                id=target_id,
                name=target_name,
                icon=icon,
                color_code=color,
                min_grade=min_grade,
                max_grade=max_grade,
                is_active=True
            )
            db.add(new_subject)
            db.flush()

            # Initiale Themen für die 7. Klasse hinzufügen
            for t_title, grade, rlp_lvl, desc in initial_topics:
                top = Topic(
                    id=f"top_{uuid.uuid4().hex[:8]}",
                    subject_id=new_subject.id,
                    name=t_title,
                    grade_level=grade,
                    rlp_level_code=rlp_lvl,
                    standard_competencies=desc
                )
                db.add(top)
            
            db.flush()
            created_subjects.append(new_subject)
            db_by_name[target_name.lower()] = new_subject
            db_by_id[new_subject.id] = new_subject

    db.commit()
    return created_subjects, existing_subjects

# ==============================================================================
# 3. STUNDENPLAN-ANALYSE (OPENAI & VISION / HEURISTIK)
# ==============================================================================

def query_openai_timetable_analyzer(
    file_path: Path,
    extracted_text: str,
    mime_type: str,
    api_key: str,
    model_name: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Analysiert einen Stundenplan (Scan, Foto oder PDF) mittels OpenAI.
    Extrahiert alle Schulfächer, die Klasse und die Struktur.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = """Du bist ein Experte für die Digitalisierung deutscher Schulunterlagen und Stundenpläne (Gymnasium Brandenburg, Untis-Format).
Analysiere diesen Stundenplan (Tabelle, Foto oder PDF) und antworte AUSSCHLIESSLICH im JSON-Format mit folgenden Schlüsseln:
{
  "ist_stundenplan": true,
  "klasse": "z. B. 7D oder 7a",
  "schuljahr": "z. B. 2026/2027",
  "titel": "Prägnanter Titel, z. B. 'Stundenplan Thea - Klasse 7D (A/B-Woche)'",
  "wochentyp": "A-Woche | B-Woche | A/B-Woche",
  "hat_wechselwochen": true,
  "erkannte_faecher": [
    "Vollständige deutsche Namen aller im Stundenplan vorkommenden Schulfächer aus A-Woche UND B-Woche (z. B. Mathematik, Deutsch, Englisch, Biologie, Französisch, Physik, Chemie, Kunst, Musik, Sport, Geografie, Geschichte, Politische Bildung, WAT / Wirtschaft, LER / Ethik, Religion, Informatik)"
  ],
  "wochenplan": {
    "Montag": [{"stunde": 1, "fach": "Deutsch", "kuerzel": "D", "raum": "201", "lehrer": "DÜCK", "woche": "beide"}],
    "Dienstag": [],
    "Mittwoch": [],
    "Donnerstag": [],
    "Freitag": []
  },
  "wechsel_details": "Erklärung der Abweichungen zwischen A-Woche und B-Woche (z. B. 'Montag 5./6. Stunde: Sport in A-Woche, Englisch in B-Woche')",
  "zusammenfassung": "Kurze Übersicht, z. B. 'Stundenplan für Thea (Klasse 7D) mit A/B-Wochenwechsel und 14 Schulfächern.'"
}

WICHTIG ZU WECHSELWOCHEN (A-WOCHE & B-WOCHE):
- Beachte Wechselwochen (A-Woche und B-Woche)! Stundenpläne (insbesondere Untis) haben oft am Rand oder im Fuß 'A Woche' oder 'B Woche' vermerkt, oder handschriftliche bzw. geteilte Zellen (z. B. '*Sp DÜCK gewo' mit handschriftlichem 'En(B)').
- Nimm Fächer BEIDER Wochen in 'erkannte_faecher' auf, damit kein Schulfach verloren geht!
- Erfasse handschriftliche Notizen und Korrekturen sorgfältig (z. B. handschriftlicher Schülername 'Thea' oder Turnus-Fächer wie 'En(B)').

WICHTIG ZU FACH-NAMEN & KÜRZELN:
- 'Bildende Kunst' oder 'Ku' IMMER einfach als 'Kunst' benennen (nicht 'Bildende Kunst').
- Löse typische Abkürzungen auf:
  D -> Deutsch (z. B. 'D DÜCK 201')
  Ma / M -> Mathematik (z. B. 'Ma HORN 303')
  En / E -> Englisch (z. B. 'En SCHD 104' oder handschriftlich 'En(B)')
  Fr -> Französisch (ACHTUNG: 'Fr PAYS 203' ist das Unterrichtsfach Französisch, NIEMALS der Wochentag Freitag!)
  Bio -> Biologie (z. B. 'Bio DEWI 207')
  Ph -> Physik (z. B. 'Ph BIEL 106')
  Ch -> Chemie (z. B. 'Ch SCHW 210')
  Ku -> Kunst
  Mu -> Musik (z. B. 'Mu ERDM N1.2')
  *Sp / Sp -> Sport (z. B. '*Sp DÜCK gewo')
  Ge -> Geschichte (ACHTUNG: 'Ge DÜCK 102' ist Geschichte, NICHT Geografie!)
  Geo -> Geografie (z. B. 'Geo SCHÖ 101')
  PB -> Politische Bildung (z. B. 'PB LAUT 315')
  WAT -> WAT / Wirtschaft (z. B. 'WAT BIEL 105')
  LER -> LER / Ethik (z. B. 'LER EISE 007')
  Rel -> Religion (z. B. 'Rel SCHN 302')
  Inf -> Informatik
- Pausen / Ganztag wie '*Mittag' oder '*GT-Mittag' sind KEINE Schulfächer und dürfen NICHT in 'erkannte_faecher' aufgenommen werden!
- Gib in 'erkannte_faecher' JEDES erkannte Fach genau EINMAL als vollständigen Klarnamen an.
"""

        if extracted_text and len(extracted_text.strip()) >= 80:
            user_content = f"Dateiname: {file_path.name}\n\nTextinhalt:\n{extracted_text[:4000]}"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        else:
            img_bytes, img_mime = render_material_page_as_image(str(file_path), mime_type, page_num=1)
            b64_img = prepare_image_base64_for_vision(img_bytes, img_mime)
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Dateiname: {file_path.name}\nBitte analysiere dieses Foto/diesen Scan eines Stundenplans."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "high"}}
                    ]
                }
            ]

        effective_model = model_name if "gpt-4o" in model_name else "gpt-4o-mini"
        response = client.chat.completions.create(
            model=effective_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Fehler bei OpenAI-Stundenplananalyse: {e}")
        return {}

def heuristic_timetable_analyzer(
    file_path: Path,
    extracted_text: str
) -> Dict[str, Any]:
    """
    Offline-Heuristik zur Erkennung von Stundenplänen und Schulfächern
    anhand von Schlüsselwörtern und Abkürzungen.
    """
    corpus = f"{file_path.name} {extracted_text}".lower()
    
    # Prüfen, ob es ein Stundenplan ist
    is_timetable = any(kw in corpus for kw in [
        "stundenplan", "timetable", "wochenplan", "montag", "dienstag", "mittwoch", "donnerstag", "freitag"
    ])
    
    found_subjects = set()
    # Alle Abkürzungen und Namen aus unserem Kanon prüfen
    words = re.findall(r"\b[A-Za-zÄÖÜäöüß]{1,20}\b", f"{file_path.name} {extracted_text}")
    for w in words:
        cand = match_subject_to_canonical(w)
        if cand:
            found_subjects.add(cand["name"])

    # Fallback-Klasse ermitteln
    grade_match = re.search(r"(\d{1,2})\s*([a-zA-Z]?)", corpus)
    grade_str = f"Klasse {grade_match.group(1)}{grade_match.group(2)}" if grade_match else "Klasse 7"

    return {
        "ist_stundenplan": is_timetable,
        "klasse": grade_str,
        "schuljahr": "2026/2027",
        "titel": f"Stundenplan {grade_str}",
        "erkannte_faecher": sorted(list(found_subjects)),
        "wochenplan": {},
        "zusammenfassung": f"Automatisch erkannter Stundenplan mit {len(found_subjects)} Fächern."
    }

# ==============================================================================
# 4. GESAMT-VERARBEITUNG EINER STUNDENPLAN-DATEI
# ==============================================================================

@dataclass
class TimetableImportResult:
    material_id: str
    material_title: str
    filename: str
    detected_subjects: List[str]
    created_subjects: List[Subject]
    existing_subjects: List[Subject]
    dossier_id: str
    dossier_title: str
    timetable_grid: Dict[str, Any]
    summary: str

def process_and_import_timetable(
    db: Session,
    file_path: Path,
    materials_dir: Path,
    user_id: str = "usr_thea"
) -> TimetableImportResult:
    """
    Zentrale Funktion zum Verarbeiten eines hochgeladenen Stundenplans:
    1. Analysiert den Inhalt (KI oder Heuristik).
    2. Erkennt alle enthaltenen Fächer.
    3. Trägt fehlende Fächer automatisch in die 'subjects'-Tabelle ein.
    4. Verschiebt den Stundenplan nach materials/ und verknüpft ihn mit dem Dossier 'Stundenplan & Organisation'.
    """
    file_bytes = file_path.read_bytes()
    ext = file_path.suffix.lower() or ".pdf"
    mime_type = "application/pdf" if ext == ".pdf" else "image/png"

    # Text extrahieren falls PDF
    extracted_text = ""
    page_count = 1
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            extracted_text = "\n".join(page.get_text() for page in doc)
        except Exception:
            pass

    # 1. Analyse durchführen
    analysis_data = {}
    if OPENAI_API_KEY:
        analysis_data = query_openai_timetable_analyzer(
            file_path=file_path,
            extracted_text=extracted_text,
            mime_type=mime_type,
            api_key=OPENAI_API_KEY,
            model_name=OPENAI_MODEL
        )

    if not analysis_data or not analysis_data.get("erkannte_faecher"):
        analysis_data = heuristic_timetable_analyzer(file_path, extracted_text)

    detected_names = analysis_data.get("erkannte_faecher", [])
    title = analysis_data.get("titel") or f"Stundenplan {file_path.stem}"

    # 2. Fächer synchronisieren (fehlende anlegen)
    created_subs, existing_subs = sync_subjects_to_database(db, detected_names)

    # 3. Dossier "Stundenplan & Organisation" anlegen / finden
    # Als Fach nutzen wir das dedizierte Fach Organisation (sub_orga)
    orga_sub = get_or_create_organisation_subject(db)
    primary_sub_id = orga_sub.id

    dossier = db.query(Dossier).filter_by(
        user_id=user_id,
        kind="organisation",
        title="Stundenplan & Organisation"
    ).first()

    if not dossier:
        dossier = Dossier(
            id=f"dos_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            subject_id=primary_sub_id,
            title="Stundenplan & Organisation",
            kind="organisation",
            color_code="#6366f1",
            icon="📅",
            description="Stundenpläne, Schultermine und organisatorische Übersichten"
        )
        db.add(dossier)
        db.flush()

    # 4. Physische Datei dauerhaft speichern
    mat_id = f"mat_{uuid.uuid4().hex[:8]}"
    clean_title = sanitize_filename_part(title)
    norm_filename = f"Organisation_Stundenplan_{clean_title}{ext}"
    perm_path = materials_dir / f"{mat_id}{ext}"
    perm_path.write_bytes(file_bytes)

    # 5. Material anlegen
    existing_count = db.query(Material).filter_by(dossier_id=dossier.id).count()
    material = Material(
        id=mat_id,
        user_id=user_id,
        subject_id=primary_sub_id,
        dossier_id=dossier.id,
        dossier_order=existing_count + 1,
        title=title,
        kind="Stundenplan",
        filename=norm_filename,
        file_path=str(perm_path),
        file_size=len(file_bytes),
        mime_type=mime_type,
        page_count=page_count,
        extracted_text=extracted_text or None,
        summary=analysis_data.get("zusammenfassung") or f"Stundenplan mit {len(detected_names)} erkannten Fächern."
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    # Erste Seite vorab rendern für Sofort-Anzeige
    try:
        from backend.app.services.material_ingestion import pre_cache_material_pages
        pre_cache_material_pages(material.id, material.file_path, material.mime_type, max_pages=1)
    except Exception:
        pass

    return TimetableImportResult(
        material_id=material.id,
        material_title=material.title,
        filename=norm_filename,
        detected_subjects=detected_names,
        created_subjects=created_subs,
        existing_subjects=existing_subs,
        dossier_id=dossier.id,
        dossier_title=dossier.title,
        timetable_grid=analysis_data.get("wochenplan", {}),
        summary=material.summary
    )
