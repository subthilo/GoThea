"""Theas gemalte Hintergründe und Kacheln: speichern, Plätzen zuweisen, auflösen, wegräumen.

Ein Platz-Schlüssel nennt Seite / Fach / Kachel, stabil (Fach-ID oder fester Name, nie die Position in einer
Liste), z. B. 'dashboard', 'subject-detail/sub_math', 'dashboard/tile/sub_math'. Hat ein Platz mit Fach kein
Bild, gilt das Bild desselben Platzes ohne Fach (Rückfall-Kette): 'subject-detail/sub_math' → 'subject-detail'.
Ein Bild für alle Fachseiten genügt also, jedes Fach kann ein eigenes bekommen.

Das fertige Bild rendert der Browser und lädt es hoch; der Pi zeichnet nichts.
"""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app import config
from backend.app.models.painting import Painting, PaintingSlot

logger = logging.getLogger(__name__)

KINDS = ("background", "tile")
BACKGROUND_FORMAT = "square"
SLOT_KEY_RE = re.compile(r"^[a-z0-9_-]+(/[a-z0-9_-]+)*$")
FORMAT_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
MAX_SLOT_KEY = 200
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_STROKES_BYTES = 20 * 1024 * 1024

# Erkennung am Dateianfang, nicht am mitgeschickten Typ
_IMAGE_TYPES = {
    "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    "png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n",
    "jpg": lambda b: b[:3] == b"\xff\xd8\xff",
}
MEDIA_TYPES = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg"}


def paintings_dir() -> Path:
    path = config.DATA_DIR / "paintings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_path(painting: Painting) -> Optional[Path]:
    if not painting.image_file:
        return None
    path = paintings_dir() / painting.image_file
    return path if path.exists() else None


# ---- Plätze ----
def check_slot_key(key: str) -> str:
    if not key or len(key) > MAX_SLOT_KEY or not SLOT_KEY_RE.match(key):
        raise ValueError(f"Ungültiger Platz '{key}'.")
    return key


def slot_kind(key: str) -> str:
    """Kachel-Plätze tragen 'tile' im Schlüssel, alles andere ist ein Hintergrund."""
    return "tile" if "tile" in key.split("/") else "background"


def fallback_chain(key: str) -> List[str]:
    """Der Platz selbst, dann derselbe Platz für alle Fächer (Fach-IDs beginnen mit 'sub_')."""
    general = "/".join(p for p in key.split("/") if not p.startswith("sub_"))
    return [key] if not general or general == key else [key, general]


def resolve(db: Session, keys: List[str]) -> Dict[str, Optional[dict]]:
    """Für jeden Platz das Bild, das dort erscheint (samt Rückfall), oder None."""
    chains = {k: fallback_chain(check_slot_key(k)) for k in keys}
    wanted = {k for chain in chains.values() for k in chain}
    rows = (db.query(PaintingSlot, Painting)
            .join(Painting, Painting.id == PaintingSlot.painting_id)
            .filter(PaintingSlot.slot_key.in_(wanted), Painting.archived_at.is_(None))
            .all())
    by_key = {slot.slot_key: painting for slot, painting in rows}
    result: Dict[str, Optional[dict]] = {}
    for key, chain in chains.items():
        hit = next(((k, by_key[k]) for k in chain if k in by_key), None)
        result[key] = dict(summary(hit[1]), slot_key=hit[0]) if hit else None
    return result


def assign(db: Session, slot_key: str, painting: Painting) -> PaintingSlot:
    """Hängt das Bild an den Platz (ersetzt das bisherige dort; das alte Bild bleibt erhalten)."""
    check_slot_key(slot_key)
    if slot_kind(slot_key) != painting.kind:
        raise ValueError(f"Ein Bild der Art '{painting.kind}' passt nicht an den Platz '{slot_key}'.")
    slot = db.get(PaintingSlot, slot_key)
    if slot is None:
        slot = PaintingSlot(slot_key=slot_key)
        db.add(slot)
    slot.painting_id = painting.id
    slot.assigned_at = datetime.utcnow()
    painting.archived_at = None  # Zuweisen holt ein weggeräumtes Bild zurück
    db.commit()
    return slot


def slots_of(db: Session, painting_id: str) -> List[str]:
    rows = db.query(PaintingSlot.slot_key).filter(PaintingSlot.painting_id == painting_id).all()
    return sorted(r[0] for r in rows)


# ---- Bilder ----
def summary(painting: Painting) -> dict:
    # Millisekunden: zwei Speicherungen in derselben Sekunde brauchen verschiedene Adressen (Bild wird lange gecacht)
    version = int(painting.updated_at.timestamp() * 1000) if painting.updated_at else 0
    return dict(
        id=painting.id,
        kind=painting.kind,
        format=painting.format,
        archived=painting.archived_at is not None,
        created_at=painting.created_at,
        updated_at=painting.updated_at,
        image_url=f"/api/v1/paintings/{painting.id}/image?v={version}" if painting.image_file else None,
    )


def _check_strokes(strokes_json: Optional[str]) -> Optional[str]:
    if strokes_json is not None and len(strokes_json.encode("utf-8")) > MAX_STROKES_BYTES:
        raise ValueError("Zu viele Striche für ein Bild.")
    return strokes_json


def _image_ext(data: bytes) -> str:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Das Bild ist zu groß.")
    for ext, matches in _IMAGE_TYPES.items():
        if matches(data):
            return ext
    raise ValueError("Unbekanntes Bildformat (erwartet WebP, PNG oder JPEG).")


def _store_image(painting: Painting, data: bytes) -> None:
    ext = _image_ext(data)
    name = f"{painting.id}.{ext}"
    target = paintings_dir() / name
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    if painting.image_file and painting.image_file != name:
        (paintings_dir() / painting.image_file).unlink(missing_ok=True)
    painting.image_file = name


def create(db: Session, kind: str, fmt: str, strokes_json: Optional[str], image: Optional[bytes],
           slot_key: Optional[str] = None) -> Painting:
    if kind not in KINDS:
        raise ValueError(f"Unbekannte Art '{kind}'.")
    if kind == "background" and fmt != BACKGROUND_FORMAT:
        raise ValueError("Hintergründe sind quadratisch.")
    if not FORMAT_RE.match(fmt or ""):
        raise ValueError(f"Ungültiges Format '{fmt}'.")
    if slot_key is not None and slot_kind(check_slot_key(slot_key)) != kind:
        raise ValueError(f"Ein Bild der Art '{kind}' passt nicht an den Platz '{slot_key}'.")
    painting = Painting(kind=kind, format=fmt, strokes_json=_check_strokes(strokes_json))
    db.add(painting)
    db.flush()
    if image:
        _store_image(painting, image)
    db.commit()
    if slot_key is not None:
        assign(db, slot_key, painting)
    return painting


def update(db: Session, painting: Painting, strokes_json: Optional[str], image: Optional[bytes]) -> Painting:
    """Automatisches Speichern: überschreibt Striche und Bild dieses Bildes."""
    if strokes_json is not None:
        painting.strokes_json = _check_strokes(strokes_json)
    if image:
        _store_image(painting, image)
    painting.updated_at = datetime.utcnow()
    db.commit()
    return painting


def history(db: Session, slot_key: str, fmt: Optional[str] = None) -> List[Painting]:
    """„Meine Bilder“ für einen Platz: alle Bilder, die dorthin passen (gleiche Art und Format), auch weggeräumte.

    Das Format eines Kachel-Platzes kennt nur das Frontend (js/paint_slots.js) und schickt es mit.
    """
    kind = slot_kind(check_slot_key(slot_key))
    fmt = BACKGROUND_FORMAT if kind == "background" else fmt
    query = db.query(Painting).filter(Painting.kind == kind)
    if fmt:
        query = query.filter(Painting.format == fmt)
    return query.order_by(Painting.updated_at.desc()).all()


def archive(db: Session, painting: Painting) -> Painting:
    """Thea räumt weg: das Bild verschwindet von allen Plätzen, bleibt aber unter „Meine Bilder“."""
    painting.archived_at = datetime.utcnow()
    db.query(PaintingSlot).filter(PaintingSlot.painting_id == painting.id).delete()
    db.commit()
    return painting


def delete(db: Session, painting: Painting) -> None:
    """Endgültig löschen (nur Eltern): Zeile, Plätze und Bilddatei."""
    path = image_path(painting)
    db.query(PaintingSlot).filter(PaintingSlot.painting_id == painting.id).delete()
    db.delete(painting)
    db.commit()
    if path:
        path.unlink(missing_ok=True)
