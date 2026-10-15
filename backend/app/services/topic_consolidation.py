"""
Führt doppelte und zu feine Themen eines Fachs auf mittlere Ebene zusammen.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import not_, or_
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.models.taxonomy import Subject, Topic, TopicBookRef
from backend.app.models.whiteboard import TutorSession
from backend.app.prompts.topic_consolidation import TOPIC_CONSOLIDATION_SYSTEM_PROMPT
from backend.app.services.document_kinds import BUCH, BUCHAUSZUG
from backend.app.services.llm import chat_params
from backend.app.services.topic_plans import fingerprint

logger = logging.getLogger(__name__)

TOPIC_REFERENCES = (Material, Dossier, TutorSession, TopicBookRef)
# Bücher und ihre Kapitel umfassen viele Unterrichtseinheiten -> kein Thema auf mittlerer Ebene.
# Kapitel erkennt man am Buch (parent_id), nicht an der Art (Kapiteltabellen setzen z. B. "Lösungsheft").
IS_BOOK_OR_CHAPTER = or_(Material.kind.in_((BUCH, BUCHAUSZUG)), Material.parent_id.isnot(None))


@dataclass
class TopicGroup:
    name: str
    area: Optional[str]
    topic_ids: List[str]


@dataclass
class ConsolidationPlan:
    subject_id: str
    subject_name: str
    groups: List[TopicGroup] = field(default_factory=list)
    delete_unused: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _usage_count(db: Session, topic_id: str) -> int:
    count = sum(db.query(model).filter_by(topic_id=topic_id).count() for model in (Dossier, TutorSession, TopicBookRef))
    return count + db.query(Material).filter(Material.topic_id == topic_id, not_(IS_BOOK_OR_CHAPTER)).count()


def _ask_model(payload: dict) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(**chat_params(
        OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": TOPIC_CONSOLIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
    ))
    return json.loads(response.choices[0].message.content or "{}")


def _has_book_refs(db: Session, topic_id: str) -> bool:
    return db.query(TopicBookRef).filter_by(topic_id=topic_id).count() > 0


def validate_groups(groups: List[TopicGroup], topics: Dict[str, Topic],
                    book_topics: Optional[set] = None) -> Optional[str]:
    """Prüft den KI-Vorschlag; liefert eine Fehlerbeschreibung oder None."""
    seen: List[str] = [tid for g in groups for tid in g.topic_ids]
    if sorted(seen) != sorted(topics):
        missing = set(topics) - set(seen)
        extra = [t for t in seen if t not in topics or seen.count(t) > 1]
        return f"IDs fehlen oder doppelt: fehlend={sorted(missing)}, unbekannt/doppelt={sorted(set(extra))}"
    names = [g.name.strip().lower() for g in groups]
    if len(names) != len(set(names)) or not all(names):
        return "Gruppennamen leer oder nicht eindeutig"
    book_topics = book_topics or set()
    for g in groups:
        in_book = [topics[t].name for t in g.topic_ids if t in book_topics]
        if len(in_book) > 1:
            return f"Buchthemen zusammengelegt: {in_book}"
    return None


def plan_for_subject(db: Session, subject: Subject, ask=_ask_model) -> ConsolidationPlan:
    plan = ConsolidationPlan(subject_id=subject.id, subject_name=subject.name)
    all_topics = db.query(Topic).filter_by(subject_id=subject.id).all()

    # Ungenutzte Themen fallen weg, genutzte werden gruppiert
    used: Dict[str, Topic] = {}
    for topic in all_topics:
        if _usage_count(db, topic.id) == 0:
            plan.delete_unused.append(topic.id)
        else:
            used[topic.id] = topic
    if len(used) < 2:
        plan.groups = [TopicGroup(t.name, t.area, [t.id]) for t in used.values()]
        return plan

    payload = {
        "fach": subject.name,
        "themen": [
            {
                "id": t.id,
                "name": t.name,
                "bereich": t.area,
                "aus_buch": _has_book_refs(db, t.id),
                "dokumente": [m.title for m in db.query(Material).filter(
                    Material.topic_id == t.id, not_(IS_BOOK_OR_CHAPTER)).limit(6)],
            }
            for t in used.values()
        ],
    }
    raw = ask(payload)
    groups = [
        TopicGroup(str(g.get("name", "")).strip(), (g.get("bereich") or "").strip() or None, [str(i) for i in g.get("ids", [])])
        for g in raw.get("themen", []) if isinstance(g, dict)
    ]
    book_topics = {tid for tid in used if _has_book_refs(db, tid)}
    plan.error = validate_groups(groups, used, book_topics)
    if not plan.error:
        plan.groups = groups
    return plan


def consolidation_fingerprint(db: Session, subject_id: str) -> str:
    topics = sorted((t.id, t.name, _usage_count(db, t.id)) for t in db.query(Topic).filter_by(subject_id=subject_id))
    return fingerprint(topics)


def consolidation_plan_from_dict(data: dict) -> ConsolidationPlan:
    return ConsolidationPlan(subject_id=data["subject_id"], subject_name=data["subject_name"],
                             groups=[TopicGroup(**g) for g in data["groups"]],
                             delete_unused=list(data["delete_unused"]), error=data.get("error"))


def merge_topics(db: Session, target: Topic, others: List[Topic]) -> None:
    """Hängt alle Verweise der anderen Themen auf das Zielthema um und löscht die anderen."""
    for other in others:
        for model in TOPIC_REFERENCES:
            db.query(model).filter_by(topic_id=other.id).update({"topic_id": target.id})
        db.delete(other)
    db.flush()


def apply_plan(db: Session, plan: ConsolidationPlan) -> None:
    if plan.error:
        raise ValueError(plan.error)
    db.query(Material).filter(Material.subject_id == plan.subject_id, IS_BOOK_OR_CHAPTER) \
        .update({"topic_id": None}, synchronize_session=False)
    for group in plan.groups:
        topics = [db.get(Topic, tid) for tid in group.topic_ids]
        book_topic = next((t for t in topics if _has_book_refs(db, t.id)), None)
        target = book_topic \
            or next((t for t in topics if t.name.strip().lower() == group.name.lower()), None) or topics[0]
        if book_topic is not None:
            # Buchthemen behalten Namen und Bereich (Katalog aus dem Inhaltsverzeichnis)
            target.area = target.area or group.area
        else:
            target.area = group.area or target.area
            target.name = group.name
        merge_topics(db, target, [t for t in topics if t.id != target.id])
    for tid in plan.delete_unused:
        topic = db.get(Topic, tid)
        if topic is not None and _usage_count(db, tid) == 0:
            db.delete(topic)
    db.commit()
