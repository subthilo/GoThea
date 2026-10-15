"""Volltextsuche über Theas Unterlagen: die erschlossenen Seiten (material_pages) samt Titel und
Zusammenfassung ihres Dokuments. Grundlage für die Lupe in der App und für Lunas Werkzeug
„Unterlagen durchsuchen“.

Der Index ist eine SQLite-FTS5-Tabelle, die Datenbank-Trigger aktuell halten – egal, auf welchem Weg
Seiten erschlossen, umnummeriert oder gelöscht werden. Lösungen bleiben für Thea verborgen
(serverseitig), bis der Bearbeitungs-Ablauf sie nach dem Abgeben freigibt.
"""
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from backend.app.models.material_page import MaterialPage

logger = logging.getLogger(__name__)

# Umlaute und Akzente zählen gleich („Brüche“ = „bruche“); Suchwörter werden als Wortanfang gesucht
_DDL = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS page_search USING fts5(
         material_id UNINDEXED, page_number UNINDEXED, title, summary, text,
         tokenize = 'unicode61 remove_diacritics 2')""",
    # Zeile im Index = rowid der Seite in material_pages
    """CREATE TRIGGER IF NOT EXISTS page_search_insert AFTER INSERT ON material_pages BEGIN
         INSERT INTO page_search(rowid, material_id, page_number, title, summary, text)
         SELECT new.rowid, new.material_id, new.page_number, m.title, coalesce(m.summary, ''), new.text
         FROM materials m WHERE m.id = new.material_id;
       END""",
    """CREATE TRIGGER IF NOT EXISTS page_search_delete AFTER DELETE ON material_pages BEGIN
         DELETE FROM page_search WHERE rowid = old.rowid;
       END""",
    """CREATE TRIGGER IF NOT EXISTS page_search_update AFTER UPDATE OF page_number, text, material_id
       ON material_pages BEGIN
         DELETE FROM page_search WHERE rowid = old.rowid;
         INSERT INTO page_search(rowid, material_id, page_number, title, summary, text)
         SELECT new.rowid, new.material_id, new.page_number, m.title, coalesce(m.summary, ''), new.text
         FROM materials m WHERE m.id = new.material_id;
       END""",
    """CREATE TRIGGER IF NOT EXISTS page_search_material AFTER UPDATE OF title, summary ON materials BEGIN
         UPDATE page_search SET title = new.title, summary = coalesce(new.summary, '')
         WHERE material_id = new.id;
       END""",
]

_REBUILD = """INSERT INTO page_search(rowid, material_id, page_number, title, summary, text)
  SELECT p.rowid, p.material_id, p.page_number, m.title, coalesce(m.summary, ''), p.text
  FROM material_pages p JOIN materials m ON m.id = p.material_id"""


def _create_index(connection) -> None:
    for statement in _DDL:
        connection.execute(text(statement))


@event.listens_for(MaterialPage.__table__, "after_create")
def _on_pages_table_created(target, connection, **kw):
    """Neue Datenbanken (auch in den Tests) bekommen den Index zusammen mit material_pages."""
    if connection.dialect.name == "sqlite":
        _create_index(connection)


def ensure_search_index(engine) -> None:
    """Legt Index und Trigger in bestehenden Datenbanken an und baut den Index neu auf, wenn er nicht
    zu den Seiten passt (z. B. beim ersten Start mit dieser Version)."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        _create_index(conn)
        indexed = conn.execute(text("SELECT count(*) FROM page_search")).scalar()
        pages = conn.execute(text("SELECT count(*) FROM material_pages")).scalar()
        if indexed != pages:
            conn.execute(text("DELETE FROM page_search"))
            conn.execute(text(_REBUILD))
            logger.info(f"🔍 Suchindex neu aufgebaut: {pages} Seiten.")


# ---------------------------------------------------------------------------
# Anfrage
# ---------------------------------------------------------------------------

# Füllwörter aus Fragen, wie Thea sie stellt („Wie geht der Dreisatz?“)
_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines",
    "und", "oder", "aber", "wie", "was", "wo", "wann", "warum", "wer", "welche", "welcher", "welches",
    "ist", "sind", "war", "geht", "gehen", "mache", "macht", "machen", "man", "ich", "du", "wir",
    "mich", "mir", "dich", "von", "vom", "zu", "zum", "zur", "im", "in", "an", "am", "auf", "aus",
    "bei", "mit", "nach", "fuer", "für", "über", "ueber", "um", "es", "sich", "auch", "noch", "nicht",
    "kann", "muss", "soll", "hatten", "haben", "hat", "steht", "stand", "nochmal", "mal",
    "bitte", "genau", "eigentlich", "heisst", "heißt", "heißen", "heissen", "zwischen", "unterschied",
    "erklaer", "erklär", "erkläre", "erklaere", "finde", "finden", "wieder",
}

_ENDINGS = ("ungen", "en", "er", "es", "st", "e", "n", "s", "t")


def _stem(word: str) -> str:
    """Grobe Grundform für die Wortanfangssuche: „Brüchen“ → „brüch“, „Zuordnungen“ → „zuordn“."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def query_terms(query: str) -> List[str]:
    words = re.findall(r"[\wäöüß]+", query.lower())
    terms: List[str] = []
    for w in words:
        if w in _STOPWORDS or len(w) < 2 or w.isdigit():
            continue
        stem = _stem(w)
        if stem not in terms:
            terms.append(stem)
    return terms


def _match_expression(terms: List[str]) -> str:
    return " OR ".join(f'"{t}"*' for t in terms)


@dataclass
class SearchHit:
    material_id: str
    page: int
    title: str
    kind: str
    subject_id: str
    subject_name: str
    label: str                       # Fundstelle zum Vorlesen/Anzeigen, z. B. „Mathebuch S. 84“
    snippet: str                     # Textausschnitt, Treffer in [ ]
    book_page: Optional[int] = None  # Seitenzahl im gedruckten Buch (bei Buchkapiteln)
    is_solution: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


def _is_solution(kind: str, page: int, is_solution_page: bool, solution_pages_json: Optional[str]) -> bool:
    if is_solution_page or "lösung" in (kind or "").lower():
        return True
    try:
        return page in (json.loads(solution_pages_json) if solution_pages_json else [])
    except (ValueError, TypeError):
        return False


def _label(kind: str, title: str, page: int, page_count: int, book_title: Optional[str],
           book_page: Optional[int]) -> str:
    if book_title and book_page:
        return f"{book_title}, S. {book_page}"
    where = f", Seite {page}" if page_count and page_count > 1 else ""
    return f"{kind} „{title}“{where}"


_SEARCH_SQL = """
SELECT ps.material_id, ps.page_number, m.title, m.kind, m.subject_id, s.name AS subject_name,
       m.page_count, m.start_page, m.solution_pages_json, mp.is_solution_page, parent.title AS book_title,
       snippet(page_search, 4, '[', ']', ' … ', 16) AS snip,
       bm25(page_search, 0.0, 0.0, :w_title, :w_summary, 1.0) AS score
FROM page_search ps
JOIN material_pages mp ON mp.rowid = ps.rowid
JOIN materials m ON m.id = ps.material_id
JOIN subjects s ON s.id = m.subject_id
LEFT JOIN materials parent ON parent.id = m.parent_id
WHERE page_search MATCH :match {filters}
ORDER BY score
LIMIT :fetch
"""

# Gewichte der Spalten (Seitentext = 1), gemessen mit scripts/eval_search.py an 19 echten Fragen:
# Der Titel beschreibt das ganze Dokument – wichtig für Mitschriften, auf denen oft nur Zahlen stehen
# (Titel 6: Treffer@1 13/19 statt 10/19 bei 1). Die KI-Zusammenfassungen sind zu allgemein und
# verschlechtern die Reihenfolge (Gewicht 2: 11/19), daher vorerst 0.
TITLE_WEIGHT = 6.0
SUMMARY_WEIGHT = 0.0


def search(
    db: Session,
    query: str,
    include_solutions: bool = False,
    subject_id: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 10,
) -> List[SearchHit]:
    """Durchsucht die erschlossenen Seiten. include_solutions nur im Eltern-Modus setzen."""
    terms = query_terms(query)
    if not terms:
        return []
    filters, params = "", {"match": _match_expression(terms), "w_title": TITLE_WEIGHT,
                           "w_summary": SUMMARY_WEIGHT, "fetch": max(limit * 4, 40)}
    if subject_id:
        filters += " AND m.subject_id = :subject_id"
        params["subject_id"] = subject_id
    if kind:
        filters += " AND m.kind = :kind"
        params["kind"] = kind

    hits: List[SearchHit] = []
    for row in db.execute(text(_SEARCH_SQL.format(filters=filters)), params).mappings():
        solution = _is_solution(row["kind"], row["page_number"], bool(row["is_solution_page"]),
                                row["solution_pages_json"])
        if solution and not include_solutions:
            continue
        book_page = row["start_page"] + row["page_number"] - 1 if row["start_page"] and row["book_title"] else None
        hits.append(SearchHit(
            material_id=row["material_id"],
            page=row["page_number"],
            title=row["title"],
            kind=row["kind"],
            subject_id=row["subject_id"],
            subject_name=row["subject_name"],
            label=_label(row["kind"], row["title"], row["page_number"], row["page_count"],
                         row["book_title"], book_page),
            snippet=" ".join((row["snip"] or "").split()),
            book_page=book_page,
            is_solution=solution,
        ))
        if len(hits) >= limit:
            break
    return hits
