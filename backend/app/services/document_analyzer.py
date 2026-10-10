import os
import re
import io
import json
import uuid
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.app.models import Subject, Topic, Dossier, Material
from backend.app.services.material_ingestion import (
    render_material_page_as_image,
    clean_title_from_filename,
    detect_kind_from_filename_and_text,
    SUBJECT_KEYWORDS,
)

def predict_subject_and_topic(
    db: Session,
    filename: str,
    text: str
) -> Tuple[str, Optional[str]]:
    """Heuristische Fach- und Themenprognose anhand von Dateinamen und extrahiertem Text."""
    corpus = f"{filename} {text}".lower()
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

    predicted_topic_id = None
    if best_subject_id:
        topics = db.query(Topic).filter_by(subject_id=best_subject_id).all()
        best_t_score = 0
        for top in topics:
            t_words = top.name.lower().split()
            t_score = sum(2 for w in t_words if len(w) > 3 and w in corpus)
            if t_score > best_t_score:
                best_t_score = t_score
                predicted_topic_id = top.id

    return best_subject_id or "sub_math", predicted_topic_id

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
}

@dataclass
class DocumentAnalysisResult:
    subject_id: str
    subject_name: str
    topic_id: Optional[str]
    topic_name: Optional[str]
    kind: str
    title: str
    normalized_filename: str
    dossier_title: str
    dossier_kind: str
    summary: Optional[str] = None


def sanitize_filename_part(text: str) -> str:
    """Wandelt Umlaute und Sonderzeichen für saubere Dateinamen um."""
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
        "ß": "ss"
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    # Nur alphanumerische Zeichen und Unterstriche
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    return cleaned.strip("_")


def prepare_image_base64_for_vision(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Skaliert ein Bild auf max. 1600x1600 Pixel und liefert Base64-JPEG."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return base64.b64encode(image_bytes).decode("utf-8")


def query_openai_analyzer(
    file_path: Path,
    extracted_text: str,
    mime_type: str,
    api_key: str,
    model_name: str
) -> Optional[Dict[str, Any]]:
    """Fragt OpenAI nach Fach, Thema, Dokumentart, Titel und Zusammenfassung."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt_instruction = """Analysiere diesen Schul-Scan oder dieses Unterrichtsdokument einer 7.-Klässlerin (Gymnasium Brandenburg).
Lies den Inhalt, handschriftliche Notizen, Arbeitsblatt-Aufgaben oder Buchseiten und antworte AUSSCHLIESSLICH im JSON-Format mit folgenden Schlüsseln:
{
  "fach": "Mathematik | Physik | Chemie | Biologie | Informatik | Astronomie | Deutsch | Englisch | Französisch | Spanisch | Latein | Russisch | Geschichte | Geografie | Politische Bildung | WAT | LER | Kunst | Musik | Sport",
  "oberthema": "Konkretes Schulthema (z. B. Rationale Zahlen, Christianisierung, Akustik, Grammatik, Zellenlehre...)",
  "dokumentart": "Arbeitsblatt | Hefterseite | Test | Klassenarbeit | Buchauszug | Buch",
  "inhaltlicher_titel": "Präziser inhaltlicher deutscher Titel (z. B. Dreisatz: Muffinrezept von 12 auf 30 umrechnen, Aufbau der Pflanzenzelle)",
  "normierter_dateiname": "Dateiname nach Schema: [Fach]_[Oberthema]_[Dokumentart]_[Titel].pdf (ASCII-kompatibel, keine Umlaute)",
  "zusammenfassung": "1-2 prägnante Sätze über den Inhalt und die Aufgaben"
}
"""

        # Wenn ausreichend digitaler Text vorhanden ist: Text-Prompt (extrem schnell & kostengünstig)
        if extracted_text and len(extracted_text.strip()) >= 80:
            user_content = (
                f"Ursprünglicher Dateiname: {file_path.name}\n\n"
                f"Dokumententext (Auszug):\n{extracted_text[:3500]}"
            )
            messages = [
                {"role": "system", "content": prompt_instruction},
                {"role": "user", "content": user_content}
            ]
        else:
            # Reiner Scan / Bild: Seite 1 als Bild an Vision-Modell senden
            img_bytes, img_mime = render_material_page_as_image(str(file_path), mime_type, page_num=1)
            b64_img = prepare_image_base64_for_vision(img_bytes, img_mime)
            messages = [
                {"role": "system", "content": prompt_instruction},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Ursprünglicher Dateiname: {file_path.name}\nBitte analysiere diese gescannte Seite."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "low"}}
                    ]
                }
            ]

        # Wenn model_name gpt-6 enthält oder unpassend ist, auf gpt-4o-mini zurückfallen
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
        print(f"Warnung: OpenAI Inhaltsanalyse fehlgeschlagen ({e}), verwende Heuristik-Fallback.")
        return None


def analyze_document_content(
    db: Session,
    file_path: Path,
    extracted_text: str = "",
    mime_type: str = "application/pdf"
) -> DocumentAnalysisResult:
    """
    Zentrale Analysefunktion für Dokumente aus der Inbox oder dem Upload.
    Verwendet KI-Inhaltsanalyse falls OPENAI_API_KEY konfiguriert ist,
    sonst robusten Heuristik-Fallback.
    """
    raw_ai_data = None
    if OPENAI_API_KEY:
        raw_ai_data = query_openai_analyzer(
            file_path=file_path,
            extracted_text=extracted_text,
            mime_type=mime_type,
            api_key=OPENAI_API_KEY,
            model_name=OPENAI_MODEL
        )

    if raw_ai_data and isinstance(raw_ai_data, dict):
        # 1. Fach zuordnen
        fach_str = (raw_ai_data.get("fach") or "").strip().lower()
        subject = None
        # Direkt in DB nach Fachname suchen (z.B. "Mathematik", "Biologie", "Physik")
        for s in db.query(Subject).all():
            if s.name.lower() in fach_str or (fach_str and fach_str in s.name.lower()):
                subject = s
                break
        if not subject:
            subject_id = SUBJECT_NAME_TO_ID.get(fach_str)
            if not subject_id:
                for key, sid in SUBJECT_NAME_TO_ID.items():
                    if key in fach_str:
                        subject_id = sid
                        break
            if subject_id:
                subject = db.query(Subject).filter_by(id=subject_id).first()
        if not subject:
            # Fallback über Vorhersage
            pred_sub_id, _ = predict_subject_and_topic(db, file_path.name, extracted_text)
            subject = db.query(Subject).filter_by(id=pred_sub_id).first()
        if not subject:
            subject = db.query(Subject).first()

        subject_id = subject.id if subject else "sub_math"

        # 2. Thema zuordnen oder dynamisch anlegen
        oberthema = (raw_ai_data.get("oberthema") or "").strip()
        topic = None
        if oberthema:
            topic = db.query(Topic).filter(
                Topic.subject_id == subject_id,
                Topic.name.ilike(f"%{oberthema}%")
            ).first()

            if not topic:
                # Neues Thema für die 7. Klasse anlegen
                new_top_id = f"top_{uuid.uuid4().hex[:8]}"
                topic = Topic(
                    id=new_top_id,
                    subject_id=subject_id,
                    name=oberthema,
                    grade_level=7,
                    rlp_level_code="E",
                    standard_competencies=f"Automatisch erkannt: {oberthema}"
                )
                db.add(topic)
                db.flush()

        topic_id = topic.id if topic else None
        topic_name = topic.name if topic else (oberthema or None)

        # 3. Dokumentart
        kind = raw_ai_data.get("dokumentart") or "Arbeitsblatt"
        if kind not in ("Arbeitsblatt", "Hefterseite", "Buchauszug", "Buch", "Klassenarbeit", "Test"):
            kind = "Arbeitsblatt"

        # 4. Titel & normierter Dateiname
        title = raw_ai_data.get("inhaltlicher_titel") or clean_title_from_filename(file_path.name)
        norm_name = raw_ai_data.get("normierter_dateiname") or ""
        if not norm_name or not norm_name.endswith(".pdf"):
            ext = file_path.suffix.lower() or ".pdf"
            safe_fach = sanitize_filename_part(subject.name if subject else "Fach")
            safe_thema = sanitize_filename_part(topic_name or "Allgemein")
            safe_kind = sanitize_filename_part(kind)
            safe_title = sanitize_filename_part(title)
            norm_name = f"{safe_fach}_{safe_thema}_{safe_kind}_{safe_title}{ext}"

        # 5. Mappe bestimmen
        if kind in ("Buch", "Buchauszug"):
            dossier_title = f"Lehrbuch: {title}"
            dossier_kind = "lehrbuch"
        elif kind == "Hefterseite":
            dossier_title = f"Hefter: {topic_name or subject.name}"
            dossier_kind = "hefter"
        elif kind in ("Klassenarbeit", "Test"):
            dossier_title = f"Testsammlung: {subject.name}"
            dossier_kind = "testsammlung"
        else:
            dossier_title = f"Arbeitsblätter: {topic_name or subject.name}"
            dossier_kind = "uebungsmappe"

        summary = raw_ai_data.get("zusammenfassung")

        return DocumentAnalysisResult(
            subject_id=subject_id,
            subject_name=subject.name if subject else "Allgemein",
            topic_id=topic_id,
            topic_name=topic_name,
            kind=kind,
            title=title,
            normalized_filename=norm_name,
            dossier_title=dossier_title,
            dossier_kind=dossier_kind,
            summary=summary
        )

    # Heuristik-Fallback wenn keine KI verfügbar ist
    subject_id, topic_id = predict_subject_and_topic(db, file_path.name, extracted_text)
    subject = db.query(Subject).filter_by(id=subject_id).first()
    topic = db.query(Topic).filter_by(id=topic_id).first() if topic_id else None

    kind = detect_kind_from_filename_and_text(file_path.name, extracted_text)
    title = clean_title_from_filename(file_path.name)

    safe_fach = sanitize_filename_part(subject.name if subject else "Fach")
    safe_title = sanitize_filename_part(title)
    norm_name = f"{safe_fach}_{safe_title}{file_path.suffix.lower()}"

    if kind in ("Buch", "Buchauszug"):
        dossier_title = f"Lehrbuch: {title}"
        dossier_kind = "lehrbuch"
    elif kind == "Hefterseite":
        dossier_title = f"Hefter: {topic.name if topic else (subject.name if subject else 'Schule')}"
        dossier_kind = "hefter"
    elif kind in ("Klassenarbeit", "Test"):
        dossier_title = f"Testsammlung: {subject.name if subject else 'Schule'}"
        dossier_kind = "testsammlung"
    else:
        dossier_title = f"Arbeitsblätter: {topic.name if topic else (subject.name if subject else 'Schule')}"
        dossier_kind = "uebungsmappe"

    return DocumentAnalysisResult(
        subject_id=subject_id,
        subject_name=subject.name if subject else "Allgemein",
        topic_id=topic_id,
        topic_name=topic.name if topic else None,
        kind=kind,
        title=title,
        normalized_filename=norm_name,
        dossier_title=dossier_title,
        dossier_kind=dossier_kind,
        summary=f"{kind} zu {subject.name if subject else 'Lernstoff'}"
    )
