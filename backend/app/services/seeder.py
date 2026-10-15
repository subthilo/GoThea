import logging

from sqlalchemy.orm import Session
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic

logger = logging.getLogger(__name__)

INITIAL_SUBJECTS = [
    {
        "id": "sub_math",
        "name": "Mathematik",
        "color_code": "#2563eb",
        "icon": "📐",
        "min_grade": 1,
        "max_grade": 13,
        "topics": [
            ("Rationale Zahlen", 7, "E", "Rechnen mit negativen Zahlen, Brüche und Dezimalbrüche ordnen"),
            ("Terme und lineare Gleichungen", 7, "E", "Termumformungen, Äquivalenzumformungen"),
            ("Prozent- und Zinsrechnung", 7, "E", "Grundwert, Prozentwert, Prozentsatz, Zinseszins"),
            ("Geometrie & Winkelbeziehungen", 7, "E", "Winkelsumme, Dreieckskonstruktionen SWS/WSW/SSS"),
        ]
    },
    {
        "id": "sub_bio",
        "name": "Biologie",
        "color_code": "#10b981",
        "icon": "🌿",
        "min_grade": 5,
        "max_grade": 13,
        "topics": [
            ("Fotosynthese und Blattaufbau", 7, "E", "Zellulärer Aufbau, Lichtabsorption, Stomata, Wortgleichung"),
            ("Mikroskopieren & Zellaufbau", 7, "E", "Tier- und Pflanzenzelle, Zellkern, Chloroplasten"),
            ("Ökosystem Wald und See", 7, "E", "Biotische/abiotische Faktoren, Nahrungsketten, Trophieebenen"),
        ]
    },
    {
        "id": "sub_german",
        "name": "Deutsch",
        "color_code": "#f59e0b",
        "icon": "📖",
        "min_grade": 1,
        "max_grade": 13,
        "topics": [
            ("Balladen analysieren", 7, "E", "Metrum, Reimschema, sprachliche Bilder und Motive"),
            ("Argumentieren & Erörtern", 7, "E", "Dreischritt: Behauptung, Begründung, Beispiel"),
            ("Satzgefüge & Kommasetzung", 7, "E", "Subjunktionen, Relativsätze, Infinitivgruppen"),
        ]
    },
    {
        "id": "sub_english",
        "name": "Englisch",
        "color_code": "#8b5cf6",
        "icon": "🇬🇧",
        "min_grade": 1,
        "max_grade": 13,
        "topics": [
            ("Past Tenses (Simple vs. Progressive)", 7, "E", "Signal words, storytelling in the past"),
            ("Conditional Clauses I & II", 7, "E", "Real and unreal conditions, if-clauses"),
            ("Life in the UK & Culture", 7, "E", "Landeskunde, London, schools in Britain"),
        ]
    },
    {
        "id": "sub_physics",
        "name": "Physik",
        "color_code": "#ec4899",
        "icon": "⚡",
        "min_grade": 7,
        "max_grade": 13,
        "topics": [
            ("Optik: Reflexion & Brechung", 7, "E", "Reflexionsgesetz, ebener Spiegel, Sammellinsen"),
            ("Mechanik: Kräfte & Masse", 7, "E", "Gewichtskraft F=m*g, Hookesches Gesetz, Kraftmesser"),
            ("Wärmelehre & Aggregatzustände", 7, "E", "Teilchenmodell, Temperatur, Schmelzen und Sieden"),
        ]
    },
    {
        "id": "sub_history",
        "name": "Geschichte",
        "color_code": "#64748b",
        "icon": "🏛️",
        "min_grade": 5,
        "max_grade": 13,
        "topics": [
            ("Das Mittelalter: Lebenswelten & Herrschaft", 7, "E", "Feudalismus, Ständegesellschaft, Rittertum"),
            ("Aufbruch in die Neuzeit", 7, "E", "Buchdruck, Renaissance, Entdeckungsfahrten"),
        ]
    },
    {
        "id": "sub_geo",
        "name": "Geografie",
        "color_code": "#06b6d4",
        "icon": "🌍",
        "min_grade": 5,
        "max_grade": 13,
        "topics": [
            ("Klimazonen & Vegetationszonen", 7, "E", "Tropen bis Polarzone, Klimadiagramme"),
            ("Kräfte der Erde: Plattentektonik", 7, "E", "Erdbeben, Vulkanismus, Kontinentalverschiebung"),
        ]
    },
    {
        "id": "sub_orga",
        "name": "Organisation",
        "color_code": "#6366f1",
        "icon": "📅",
        "min_grade": 1,
        "max_grade": 13,
        "topics": [
            ("Stundenplan", 7, "E", "Wochenstruktur, Raum- und Lehrereinteilung, A/B-Wochen"),
            ("Termine & Organisation", 7, "E", "Klassenarbeiten, Ferientermine, Wandertage"),
        ]
    }
]

def seed_database(db: Session):
    # 1. Default-User
    user = db.query(User).filter(User.id == "usr_thea").first()
    if not user:
        user = User(
            id="usr_thea",
            name="Thea",
            grade_level=7,
            school_type="Gymnasium",
            federal_state="Brandenburg"
        )
        db.add(user)

    # 2. Fächer und Themen für 7. Klasse Brandenburg
    for s_data in INITIAL_SUBJECTS:
        subject = db.query(Subject).filter(Subject.id == s_data["id"]).first()
        # Start-Themen nur für neu angelegte Fächer: danach wird der Themenkatalog aus Theas
        # Dokumenten aufgebaut und zusammengeführt; gelöschte Platzhalter sollen nicht wiederkommen
        is_new_subject = subject is None
        if not subject:
            subject = Subject(
                id=s_data["id"],
                name=s_data["name"],
                color_code=s_data["color_code"],
                icon=s_data["icon"],
                min_grade=s_data["min_grade"],
                max_grade=s_data["max_grade"],
                is_active=True
            )
            db.add(subject)
            db.flush()

        for t_name, grade, rlp_code, comp in (s_data["topics"] if is_new_subject else []):
            topic = db.query(Topic).filter(
                Topic.subject_id == subject.id,
                Topic.grade_level == grade,
                Topic.name == t_name
            ).first()
            if not topic:
                topic = Topic(
                    subject_id=subject.id,
                    name=t_name,
                    grade_level=grade,
                    rlp_level_code=rlp_code,
                    standard_competencies=comp
                )
                db.add(topic)

    # 3. Automatische Migration: Stundenpläne müssen zwingend 'sub_orga' zugeordnet sein
    import uuid
    from backend.app.models.material import Material
    from backend.app.models.dossier import Dossier

    orga_subject = db.query(Subject).filter(Subject.id == "sub_orga").first()
    if orga_subject:
        # Finde oder erstelle das Stundenplan-Dossier
        orga_dossier = db.query(Dossier).filter(
            (Dossier.subject_id == "sub_orga") & (Dossier.kind == "organisation")
        ).first()
        if not orga_dossier:
            orga_dossier = db.query(Dossier).filter(
                Dossier.title == "Stundenplan & Organisation"
            ).first()
            if orga_dossier:
                orga_dossier.subject_id = "sub_orga"
                orga_dossier.kind = "organisation"
                orga_dossier.color_code = orga_subject.color_code
            else:
                orga_dossier = Dossier(
                    id=f"dos_{uuid.uuid4().hex[:8]}",
                    user_id="usr_thea",
                    subject_id="sub_orga",
                    title="Stundenplan & Organisation",
                    kind="organisation",
                    color_code=orga_subject.color_code,
                    icon="📁",
                    description="Organisatorische Dokumente und Stundenpläne"
                )
                db.add(orga_dossier)
                db.flush()

        # Suche alle Materialien, die Stundenpläne sind, aber noch einem Schulfach zugeordnet sind
        timetable_materials = db.query(Material).filter(
            (Material.kind == "Stundenplan") |
            (Material.title.ilike("%stundenplan%"))
        ).all()

        for mat in timetable_materials:
            if mat.subject_id != "sub_orga":
                mat.subject_id = "sub_orga"
                mat.kind = "Stundenplan"
                mat.topic_id = None
                if orga_dossier:
                    mat.dossier_id = orga_dossier.id

    # 4. Nicht segmentierte Lehrbücher automatisch segmentieren
    try:
        from backend.app.services.book_segmentation import trigger_background_book_segmentation
        unsegmented_books = db.query(Material).filter(
            Material.kind == "Buch",
            Material.parent_id == None
        ).all()
        for b in unsegmented_books:
            children_count = db.query(Material).filter_by(parent_id=b.id).count()
            if children_count == 0:
                trigger_background_book_segmentation(b.id)
    except Exception as e:
        logger.warning(f"Konnte Lehrbücher nicht automatisch segmentieren: {e}")

    db.commit()
