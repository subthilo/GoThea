import json
import shutil
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.config import MATERIALS_DIR, PROJECT_ROOT
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic

def seed_textbooks_if_empty(db: Session, user_id: str = "usr_thea") -> Optional[str]:
    """
    Registriert das 7. Klasse Mathematik-Lehrbuch und dessen 11 extrahierte
    Kapitel in der Datenbank und kopiert die Kapitel-PDFs in das Materials-Verzeichnis.
    Idempotent: Wird nur ausgeführt, wenn das Buch noch nicht existiert.
    """
    # 1. Prüfen, ob das Buch bereits existiert
    existing = db.query(Material).filter(
        (Material.id == "mat_book_math_7") | (Material.title.ilike("%Mathematik – Lehrbuch%"))
    ).first()
    if existing:
        return existing.id

    # 2. Manifest suchen
    manifest_paths = [
        PROJECT_ROOT / "backend" / "app" / "resources" / "books" / "mathe_7" / "book_manifest.json",
        PROJECT_ROOT / "experiments" / "openai_study" / "staging_test" / "mathe_buch_7" / "book_manifest.json",
    ]
    manifest_file = next((p for p in manifest_paths if p.exists()), None)
    if not manifest_file:
        return None

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception:
        return None

    meta = manifest_data.get("book_metadata", {})
    chapters_meta = meta.get("chapters", [])
    kapitel_src_dir = manifest_file.parent / "kapitel"

    # 3. Schulfach sicherstellen
    sub_math = db.query(Subject).filter_by(id="sub_math").first()
    if not sub_math:
        sub_math = Subject(
            id="sub_math",
            name="Mathematik",
            color_code="#2563eb",
            icon="📐",
            min_grade=1,
            max_grade=13,
            is_active=True
        )
        db.add(sub_math)
        db.flush()

    # 4. Dossier / Lehrbuch-Mappe erstellen
    dossier = db.query(Dossier).filter_by(id="dos_math_book_7").first()
    if not dossier:
        dossier = Dossier(
            id="dos_math_book_7",
            user_id=user_id,
            subject_id=sub_math.id,
            title=meta.get("book_title", "Mathematik – Lehrbuch für die 7. Klasse"),
            kind="lehrbuch",
            icon="📚",
            color_code="#0284c7",
            description=f"Autoren: {meta.get('authors', '')}. Gesamtausgabe Klasse 7 (196 Seiten)."
        )
        db.add(dossier)
        db.flush()

    # 5. Master-Material anlegen
    # Als Master-PDF nutzen wir das Deckblatt/Titelei oder einen Platzhalter
    first_pdf = next(kapitel_src_dir.glob("*.pdf"), None) if kapitel_src_dir.exists() else None
    master_dest = MATERIALS_DIR / "mat_book_math_7.pdf"
    if first_pdf and first_pdf.exists() and not master_dest.exists():
        try:
            shutil.copy2(first_pdf, master_dest)
        except Exception:
            pass

    master_material = Material(
        id="mat_book_math_7",
        user_id=user_id,
        subject_id=sub_math.id,
        dossier_id=dossier.id,
        dossier_order=1,
        title=meta.get("book_title", "Mathematik – Lehrbuch für die 7. Klasse"),
        kind="Buch",
        filename="Mathematik_7_Lehrbuch_Gesamtausgabe.pdf",
        file_path=str(master_dest),
        file_size=master_dest.stat().st_size if master_dest.exists() else 60000000,
        mime_type="application/pdf",
        page_count=meta.get("total_pages", 196),
        start_page=1,
        end_page=meta.get("total_pages", 196),
        summary=f"Gesamt-Lehrbuch für Klasse 7 Gymnasium. Autoren: {meta.get('authors', '')}."
    )
    db.add(master_material)
    db.flush()

    # 6. Kind-Materialien für die einzelnen Kapitel anlegen
    topics_by_name = {t.name.lower(): t for t in db.query(Topic).filter_by(subject_id=sub_math.id).all()}

    # PDF-Dateien im Kapitel-Verzeichnis nach Dateinamen matchen
    pdf_files = sorted(list(kapitel_src_dir.glob("*.pdf"))) if kapitel_src_dir.exists() else []

    for idx, chap in enumerate(chapters_meta):
        unit_num = chap.get("unit_number", idx)
        chap_id = f"mat_book_math_7_ch{unit_num}"

        # Passende PDF finden
        matched_pdf = None
        for p in pdf_files:
            prefix = f"Kapitel_{unit_num:02d}"
            if prefix in p.name:
                matched_pdf = p
                break
        if not matched_pdf and idx < len(pdf_files):
            matched_pdf = pdf_files[idx]

        chap_dest = MATERIALS_DIR / f"{chap_id}.pdf"
        if matched_pdf and matched_pdf.exists() and not chap_dest.exists():
            try:
                shutil.copy2(matched_pdf, chap_dest)
            except Exception:
                pass

        # Topic zuordnen
        topic_name = chap.get("topic_name", "")
        matched_topic = topics_by_name.get(topic_name.lower())
        if not matched_topic and topic_name:
            # Falls Topic fehlt, anlegen
            matched_topic = Topic(
                id=f"top_math_auto_{unit_num}",
                subject_id=sub_math.id,
                name=topic_name,
                grade_level=7,
                rlp_level_code="E"
            )
            db.add(matched_topic)
            db.flush()
            topics_by_name[topic_name.lower()] = matched_topic

        page_count = chap.get("end_page", 1) - chap.get("start_page", 1) + 1

        child_mat = Material(
            id=chap_id,
            user_id=user_id,
            subject_id=sub_math.id,
            topic_id=matched_topic.id if matched_topic else None,
            dossier_id=dossier.id,
            dossier_order=unit_num + 2,
            parent_id=master_material.id,
            title=chap.get("title", f"Kapitel {unit_num}"),
            kind="Buchauszug",
            filename=matched_pdf.name if matched_pdf else f"Kapitel_{unit_num}.pdf",
            file_path=str(chap_dest),
            file_size=chap_dest.stat().st_size if chap_dest.exists() else 5000000,
            mime_type="application/pdf",
            page_count=page_count,
            start_page=chap.get("start_page"),
            end_page=chap.get("end_page"),
            summary=chap.get("focus")
        )
        db.add(child_mat)

    db.commit()
    return master_material.id
