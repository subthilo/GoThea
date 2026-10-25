from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from backend.app.database import Base


class Painting(Base):
    """Ein Bild, das Thea gemalt hat (Hintergrund einer Seite oder eine Kachel).

    Bild und Platz sind getrennt: wo es erscheint, steht in painting_slots. So bleiben alte Bilder erhalten,
    ein Bild kann an mehreren Plätzen hängen, und „neu malen“ zerstört nichts.
    Das fertige Bild rendert der Browser; es liegt als Datei in DATA_DIR/paintings/.
    """
    __tablename__ = "paintings"

    id = Column(String, primary_key=True, default=lambda: f"pnt_{uuid.uuid4().hex[:8]}")
    kind = Column(String, nullable=False)          # 'background' oder 'tile'
    format = Column(String, nullable=False)        # 'square' (Hintergrund) bzw. Kachelart aus js/paint_slots.js
    strokes_json = Column(Text, nullable=True)     # Striche im Format des Zeichenkerns (zum Weitermalen)
    image_file = Column(String, nullable=True)     # Dateiname in DATA_DIR/paintings/
    archived_at = Column(DateTime, nullable=True)  # von Thea weggeräumt (zurückholbar)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_paintings_kind_format", "kind", "format"),
    )


class PaintingSlot(Base):
    """Ein Platz, an dem ein Bild erscheint, z. B. 'dashboard' oder 'subject-detail/sub_math/tile/tafel'."""
    __tablename__ = "painting_slots"

    slot_key = Column(String, primary_key=True)
    painting_id = Column(String, ForeignKey("paintings.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
