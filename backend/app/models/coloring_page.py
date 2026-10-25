from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Integer, Float, Text
from backend.app.database import Base


class ColoringPage(Base):
    """Ein Ausmalbild, von den Eltern als SVG hochgeladen (Konzept-Doc, Tab „Ausmalbilder“).

    Die Felder berechnet der Server im Hintergrund; das Ergebnis liegt in DATA_DIR/coloring/<id>.json,
    das Original in <id>.svg (geht nie an Theas Browser – SVGs können Skripte enthalten).
    """
    __tablename__ = "coloring_pages"

    id = Column(String, primary_key=True, default=lambda: f"cpg_{uuid.uuid4().hex[:8]}")
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="rechnet")  # rechnet | berechnet | freigegeben | fehler
    error = Column(Text, nullable=True)
    width = Column(Float, nullable=True)     # im 1000er-Raster (längere Seite = 1000)
    height = Column(Float, nullable=True)
    field_count = Column(Integer, nullable=True)
    archived_at = Column(DateTime, nullable=True)  # von den Eltern entfernt (Dateien bleiben für bemalte Bilder)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
