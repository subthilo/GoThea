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
from backend.app.models.taxonomy import TopicBookRef

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


# Inhaltsverzeichnis der Bücher (Themenkatalog: Thema → Abschnitt eines Kapitels mit Seiten). Findet
# Buchstellen, bevor ihre Seiten erschlossen sind, und deutsche Themennamen auch für französische Bücher.
_TOC_DDL = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS toc_search USING fts5(
         section_title, topic_name, area, tokenize = 'unicode61 remove_diacritics 2')""",
    """CREATE TRIGGER IF NOT EXISTS toc_search_insert AFTER INSERT ON topic_book_refs BEGIN
         INSERT INTO toc_search(rowid, section_title, topic_name, area)
         SELECT new.rowid, new.section_title, t.name, coalesce(t.area, '') FROM topics t WHERE t.id = new.topic_id;
       END""",
    """CREATE TRIGGER IF NOT EXISTS toc_search_delete AFTER DELETE ON topic_book_refs BEGIN
         DELETE FROM toc_search WHERE rowid = old.rowid;
       END""",
    """CREATE TRIGGER IF NOT EXISTS toc_search_update AFTER UPDATE ON topic_book_refs BEGIN
         DELETE FROM toc_search WHERE rowid = old.rowid;
         INSERT INTO toc_search(rowid, section_title, topic_name, area)
         SELECT new.rowid, new.section_title, t.name, coalesce(t.area, '') FROM topics t WHERE t.id = new.topic_id;
       END""",
    """CREATE TRIGGER IF NOT EXISTS toc_search_topic AFTER UPDATE OF name, area ON topics BEGIN
         UPDATE toc_search SET topic_name = new.name, area = coalesce(new.area, '')
         WHERE rowid IN (SELECT rowid FROM topic_book_refs WHERE topic_id = new.id);
       END""",
]

_TOC_REBUILD = """INSERT INTO toc_search(rowid, section_title, topic_name, area)
  SELECT r.rowid, r.section_title, t.name, coalesce(t.area, '')
  FROM topic_book_refs r JOIN topics t ON t.id = r.topic_id"""


def _create_index(connection) -> None:
    for statement in _DDL:
        connection.execute(text(statement))


def _create_toc_index(connection) -> None:
    for statement in _TOC_DDL:
        connection.execute(text(statement))


@event.listens_for(MaterialPage.__table__, "after_create")
def _on_pages_table_created(target, connection, **kw):
    """Neue Datenbanken (auch in den Tests) bekommen den Index zusammen mit material_pages."""
    if connection.dialect.name == "sqlite":
        _create_index(connection)


@event.listens_for(TopicBookRef.__table__, "after_create")
def _on_book_refs_table_created(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        _create_toc_index(connection)


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
        _create_toc_index(conn)
        indexed = conn.execute(text("SELECT count(*) FROM toc_search")).scalar()
        refs = conn.execute(text("SELECT count(*) FROM topic_book_refs")).scalar()
        if indexed != refs:
            conn.execute(text("DELETE FROM toc_search"))
            conn.execute(text(_TOC_REBUILD))
            logger.info(f"🔍 Inhaltsverzeichnis-Index neu aufgebaut: {refs} Abschnitte.")


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


def _match_expression(terms: List[str], all_terms: bool = False) -> str:
    return (" AND " if all_terms else " OR ").join(f'"{t}"*' for t in terms)


def short_book_title(title: str) -> str:
    """„Deutschbuch Gymnasium 7 – Berlin, Brandenburg, …“ → „Deutschbuch Gymnasium 7“."""
    return title.split(" – ")[0].strip() if title else title


@dataclass
class SearchHit:
    material_id: str
    page: int
    title: str
    kind: str
    subject_id: str
    subject_name: str
    label: str                       # Fundstelle zum Vorlesen/Anzeigen, z. B. „Mathebuch S. 84“
    snippet: str                     # Textausschnitt, Treffer zwischen ⟦ und ⟧
    book_page: Optional[int] = None  # Seitenzahl im gedruckten Buch (bei Buchkapiteln)
    book_id: Optional[str] = None    # Buch, zu dem das Kapitel gehört (zum Öffnen im Buch-Leser)
    is_solution: bool = False
    source: str = "page"             # "page" = erschlossene Seite, "toc" = Abschnitt laut Inhaltsverzeichnis
    section: Optional[str] = None    # Abschnitt im Buch (bei "toc")
    page_to: Optional[int] = None    # letzte Seite des Abschnitts im Kapitel (bei "toc")

    def to_dict(self) -> Dict:
        return asdict(self)


def _is_solution(kind: str, page: int, is_solution_page: bool, solution_pages_json: Optional[str]) -> bool:
    if is_solution_page or "lösung" in (kind or "").lower():
        return True
    try:
        return page in (json.loads(solution_pages_json) if solution_pages_json else [])
    except (ValueError, TypeError):
        return False


# Markdown und Handschrift-Markierungen der Erschließung („## “, „**“, „«S: …»“) stören im Ausschnitt
_SNIPPET_NOISE = re.compile(r"#{1,6}\s|\*\*|__|«[SL]:\s?|»|«|\|")


def clean_snippet(snippet: str) -> str:
    return " ".join(_SNIPPET_NOISE.sub(" ", snippet or "").split())


def _label(kind: str, title: str, page: int, page_count: int, book_title: Optional[str],
           book_page: Optional[int]) -> str:
    if book_title and book_page:
        return f"{short_book_title(book_title)}, S. {book_page}"
    where = f", Seite {page}" if page_count and page_count > 1 else ""
    return f"{kind} „{title}“{where}"


_SEARCH_SQL = """
SELECT ps.material_id, ps.page_number, m.title, m.kind, m.subject_id, s.name AS subject_name,
       m.page_count, m.start_page, m.solution_pages_json, mp.is_solution_page, m.parent_id,
       parent.title AS book_title,
       snippet(page_search, 4, '⟦', '⟧', ' … ', 16) AS snip,
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


_TOC_SQL = """
SELECT r.material_id, r.start_page, r.end_page, r.book_page, r.section_title, t.name AS topic_name,
       ch.title, ch.kind, ch.subject_id, s.name AS subject_name, ch.parent_id, book.title AS book_title,
       bm25(toc_search, 3.0, 1.0, 0.5) AS score
FROM toc_search
JOIN topic_book_refs r ON r.rowid = toc_search.rowid
JOIN topics t ON t.id = r.topic_id
JOIN materials ch ON ch.id = r.material_id
JOIN subjects s ON s.id = ch.subject_id
LEFT JOIN materials book ON book.id = ch.parent_id
WHERE toc_search MATCH :match {filters}
ORDER BY score
LIMIT :fetch
"""


def _search_pages(db: Session, match: str, include_solutions: bool, filters: str, params: dict,
                  limit: int) -> List[SearchHit]:
    hits: List[SearchHit] = []
    for row in db.execute(text(_SEARCH_SQL.format(filters=filters)), {**params, "match": match}).mappings():
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
            snippet=clean_snippet(row["snip"]),
            book_page=book_page,
            book_id=row["parent_id"],
            is_solution=solution,
        ))
        if len(hits) >= limit:
            break
    return hits


def _search_toc(db: Session, match: str, include_solutions: bool, filters: str, params: dict,
                limit: int) -> List[SearchHit]:
    hits: List[SearchHit] = []
    for row in db.execute(text(_TOC_SQL.format(filters=filters.replace("m.", "ch."))),
                          {**params, "match": match}).mappings():
        solution = "lösung" in f"{row['kind']} {row['section_title']}".lower()
        if solution and not include_solutions:
            continue
        book = short_book_title(row["book_title"] or row["title"])
        where = f"S. {row['book_page']}" if row["book_page"] else f"Kapitel „{row['title']}“"
        hits.append(SearchHit(
            material_id=row["material_id"],
            page=row["start_page"],
            title=row["title"],
            kind=row["kind"],
            subject_id=row["subject_id"],
            subject_name=row["subject_name"],
            label=f"{book}, {where}",
            snippet=f"Inhaltsverzeichnis: {row['section_title']} (Thema: {row['topic_name']})",
            book_page=row["book_page"],
            book_id=row["parent_id"],
            is_solution=solution,
            source="toc",
            section=row["section_title"],
            page_to=row["end_page"],
        ))
        if len(hits) >= limit:
            break
    return hits


# Wie Buchabschnitte (Inhaltsverzeichnis) und Seitentreffer gemischt werden. Gemessen an 19 Fragen
# (17 mit Buchstelle), Kennzahl „richtige Buchstelle unter den ersten 3“: nur Seiten 6/17,
# bis zu 2 Abschnitte zuerst 14/17, Abschnitte nur bei allen Suchwörtern 10/17.
MERGE_MODE = "toc_first"
TOC_FIRST_MAX = 2


def _merge(pages: List[SearchHit], toc: List[SearchHit], limit: int) -> List[SearchHit]:
    def covered(t: SearchHit) -> bool:  # eine Seite aus diesem Abschnitt steht schon weit oben
        return any(p.material_id == t.material_id and t.page <= p.page <= (t.page_to or t.page)
                   for p in pages[:3])
    if MERGE_MODE == "pages":
        merged = pages
    elif MERGE_MODE == "interleave":
        merged = [h for pair in zip(toc, pages) for h in pair] + toc[len(pages):] + pages[len(toc):]
    elif MERGE_MODE == "toc_first_dedupe":
        merged = [t for t in toc if not covered(t)][:TOC_FIRST_MAX] + pages
    else:  # toc_first
        shown = toc[:TOC_FIRST_MAX]
        merged = shown + [p for p in pages if not any((p.material_id, p.page) == (t.material_id, t.page)
                                                      for t in shown)]
    return merged[:limit]


def search(
    db: Session,
    query: str,
    include_solutions: bool = False,
    subject_id: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 10,
) -> List[SearchHit]:
    """Durchsucht erschlossene Seiten und das Inhaltsverzeichnis der Bücher.
    include_solutions nur im Eltern-Modus setzen."""
    terms = query_terms(query)
    if not terms:
        return []
    filters, params = "", {"w_title": TITLE_WEIGHT, "w_summary": SUMMARY_WEIGHT, "fetch": max(limit * 4, 40)}
    if subject_id:
        filters += " AND m.subject_id = :subject_id"
        params["subject_id"] = subject_id
    if kind:
        filters += " AND m.kind = :kind"
        params["kind"] = kind
    match = _match_expression(terms)
    pages = _search_pages(db, match, include_solutions, filters, params, limit)
    # Im Inhaltsverzeichnis sind die Einträge kurz: ein einzelnes passendes Wort („Einheit“) ist oft
    # Zufall. Daher zuerst alle Suchwörter verlangen, nur wenn das nichts findet, eines.
    toc = _search_toc(db, _match_expression(terms, all_terms=True), include_solutions, filters, params, limit)
    if not toc and len(terms) > 1:
        toc = _search_toc(db, match, include_solutions, filters, params, limit)
    return _merge(pages, toc, limit)
