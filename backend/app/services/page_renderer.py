import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import logging
from pathlib import Path
from queue import PriorityQueue, Empty
from typing import Iterable, Optional, Tuple, Dict, Set

from backend.app.config import PAGE_CACHE_DIR

logger = logging.getLogger(__name__)

# Prioritätsstufen: Niedrigere Zahl = Höhere Priorität
PRIORITY_LIVE = 1        # Sofortiger Live-Aufruf aus dem Browser
PRIORITY_PREFETCH = 2    # Benachbarte Seiten der aktuell aktiven Lerneinheit
PRIORITY_BACKGROUND = 3  # Vollständiger Hintergrund-Scan aller Dokumente

# Cache-Dateiname: {material_id}_p{seite}_{mtime}.jpg
CACHE_NAME_RE = re.compile(r"^(?P<doc>.+)_p(?P<page>\d+)_(?P<mtime>\d+)\.jpg$")


class PageRenderingService:
    """
    Intelligenter Seiten-Rendering- und Caching-Dienst für GoThea.
    Verwaltet einen persistenten JPEG-Cache auf der Festplatte/SSD und eine
    priorisierte Hintergrund-Warteschlange (PriorityQueue).

    - Live-Anfragen verdrängen Hintergrund-Jobs und erhalten 100% CPU.
    - Hintergrund-Worker rendert proaktiv alle Seiten im Leerlauf.
    - Doppel-Renderings werden über In-Flight-Events synchronisiert.
    """

    def __init__(self):
        self._queue: PriorityQueue = PriorityQueue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Priorisierungs- & Sperrmechanismen
        self._live_active_lock = threading.Lock()
        self._live_in_progress_count = 0

        # Vermeidung von Queue-Duplikaten
        self._queued_items: Set[str] = set()
        self._queued_lock = threading.Lock()

        # In-Flight Synchronisation (verhindert doppeltes Rendern derselben Seite)
        self._in_flight_renders: Dict[str, threading.Event] = {}
        self._in_flight_lock = threading.Lock()

        # Seitenzahlen pro (Pfad, mtime), damit nicht jedes Rendering das ganze PDF parst
        self._page_counts: Dict[Tuple[str, int], int] = {}
        self._page_counts_lock = threading.Lock()

        self._rendered_in_background = 0

        PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Startet den Hintergrund-Worker-Thread, falls noch nicht aktiv."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="PageRenderingBackgroundWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("🚀 PageRenderingService Hintergrund-Worker gestartet.")

    def stop(self):
        """Beendet den Hintergrund-Worker geordnet."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("🛑 PageRenderingService Hintergrund-Worker gestoppt.")

    def get_cache_path(self, material_id: Optional[str], file_path: str, page_num: int) -> Path:
        """Ermittelt den Speicherort im Festplatten-Cache basierend auf mtime."""
        p = Path(file_path)
        try:
            mtime = int(p.stat().st_mtime) if p.exists() else 0
        except Exception:
            mtime = 0
        doc_key = material_id or p.stem
        return PAGE_CACHE_DIR / f"{doc_key}_p{page_num}_{mtime}.jpg"

    def render_page(
        self,
        file_path: str,
        mime_type: str,
        page_num: int = 1,
        material_id: Optional[str] = None,
        priority: int = PRIORITY_LIVE
    ) -> Tuple[bytes, str]:
        """
        Gibt die gerenderte Seite als JPEG zurück.
        1. Bei Cache-Hit: Sofortige Auslieferung (< 5ms).
        2. Bei Cache-Miss: Sofortiges Rendering mit Fast-Path.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Materialdatei nicht gefunden: {file_path}")

        # Bilddateien (PNG, JPG, WebP) direkt liefern
        if "image" in mime_type.lower() or path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            out_mime = mime_type or "image/jpeg"
            if out_mime == "application/octet-stream":
                out_mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            return path.read_bytes(), out_mime

        cache_file = self.get_cache_path(material_id, file_path, page_num)

        # 1. Schneller Cache-Check
        if cache_file.exists() and cache_file.stat().st_size > 0:
            if priority == PRIORITY_LIVE and material_id:
                self.prefetch_adjacent_pages(material_id, file_path, mime_type, page_num)
            return cache_file.read_bytes(), "image/jpeg"

        # 2. In-Flight Koordination (verhindert doppeltes Rendern)
        render_key = f"{material_id or file_path}_{page_num}"
        my_event = None
        with self._in_flight_lock:
            if render_key in self._in_flight_renders:
                existing_event = self._in_flight_renders[render_key]
            else:
                existing_event = None
                my_event = threading.Event()
                self._in_flight_renders[render_key] = my_event

        if existing_event is not None:
            # Ein anderer Thread rendert genau diese Seite gerade -> warten
            existing_event.wait(timeout=15.0)
            if cache_file.exists() and cache_file.stat().st_size > 0:
                return cache_file.read_bytes(), "image/jpeg"

        # 3. Wir rendern die Seite
        if priority == PRIORITY_LIVE:
            with self._live_active_lock:
                self._live_in_progress_count += 1

        try:
            img_bytes, out_mime = self._do_render(path, page_num, cache_file, low_priority=priority == PRIORITY_BACKGROUND)
            # Bei Live-Aufruf direkt Nachbarseiten mit Prio 2 vorwärmen
            if priority == PRIORITY_LIVE and material_id:
                self.prefetch_adjacent_pages(material_id, file_path, mime_type, page_num)
            return img_bytes, out_mime
        finally:
            if priority == PRIORITY_LIVE:
                with self._live_active_lock:
                    self._live_in_progress_count = max(0, self._live_in_progress_count - 1)

            with self._in_flight_lock:
                ev = self._in_flight_renders.pop(render_key, None)
                if ev:
                    ev.set()

    def get_page_count(self, path: Path) -> Optional[int]:
        """Seitenzahl eines PDFs, gecacht pro Datei-Version."""
        if path.suffix.lower() != ".pdf":
            return None
        try:
            key = (str(path), int(path.stat().st_mtime))
        except OSError:
            return None
        with self._page_counts_lock:
            if key in self._page_counts:
                return self._page_counts[key]
        try:
            from pypdf import PdfReader
            count = len(PdfReader(str(path)).pages)
        except Exception:
            return None
        with self._page_counts_lock:
            self._page_counts[key] = count
        return count

    def _do_render(self, path: Path, page_num: int, cache_file: Path, low_priority: bool = False) -> Tuple[bytes, str]:
        """Führt das physische Rendering mit pdftoppm oder fitz durch."""
        actual_page = max(1, page_num)
        total_pages = self.get_page_count(path)
        if total_pages:
            actual_page = max(1, min(page_num, total_pages))

        # A) Bevorzugt auf Linux/Raspberry Pi: pdftoppm JPEG (120 DPI, hochoptimiert)
        pdftoppm_bin = shutil.which("pdftoppm") or ("/usr/bin/pdftoppm" if Path("/usr/bin/pdftoppm").exists() else None)
        if pdftoppm_bin:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    out_prefix = os.path.join(tmpdir, "page")
                    # Hintergrundjobs mit niedrigster CPU-Priorität, damit Live-Anfragen
                    # (auch die der jeweils anderen Umgebung) Vorrang haben
                    nice_bin = shutil.which("nice") if low_priority else None
                    cmd = ([nice_bin, "-n", "19"] if nice_bin else []) + [
                        pdftoppm_bin,
                        "-jpeg",
                        "-r", "120",
                        "-f", str(actual_page),
                        "-l", str(actual_page),
                        "-singlefile",
                        str(path),
                        out_prefix
                    ]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
                    out_jpg = f"{out_prefix}.jpg"
                    if res.returncode == 0 and os.path.exists(out_jpg):
                        img_bytes = Path(out_jpg).read_bytes()
                        try:
                            cache_file.write_bytes(img_bytes)
                        except Exception:
                            pass
                        return img_bytes, "image/jpeg"
            except Exception as e:
                logger.warning(f"pdftoppm fehlgeschlagen für {path.name} (Seite {actual_page}): {e}")

        # B) PyMuPDF (fitz) Fallback falls installiert
        try:
            import fitz
            doc = fitz.open(str(path))
            total_pages = len(doc)
            target_page = max(0, min(actual_page - 1, total_pages - 1))
            page = doc.load_page(target_page)
            pix = page.get_pixmap(dpi=120)
            img_bytes = pix.tobytes("jpeg")
            try:
                cache_file.write_bytes(img_bytes)
            except Exception:
                pass
            return img_bytes, "image/jpeg"
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"fitz Fallback nicht verfügbar für {path}: {e}")

        return path.read_bytes(), "application/pdf"

    def prefetch_adjacent_pages(
        self,
        material_id: str,
        file_path: str,
        mime_type: str,
        current_page: int
    ):
        """Reiht die nächsten und vorherigen Seiten mit hoher Priorität (2) in die Queue ein."""
        # Nächste Seite (P+1) ist am wahrscheinlichsten
        self.queue_page(material_id, file_path, mime_type, current_page + 1, priority=PRIORITY_PREFETCH)
        # Vorherige Seite (P-1)
        if current_page > 1:
            self.queue_page(material_id, file_path, mime_type, current_page - 1, priority=PRIORITY_PREFETCH)
        # Übernächste Seite (P+2)
        self.queue_page(material_id, file_path, mime_type, current_page + 2, priority=PRIORITY_PREFETCH)

    def queue_page(
        self,
        material_id: str,
        file_path: str,
        mime_type: str,
        page_num: int,
        priority: int = PRIORITY_BACKGROUND
    ):
        """Fügt eine Einzelseite priorisiert zur Hintergrund-Warteschlange hinzu."""
        if page_num < 1:
            return
        cache_key = f"{material_id}_{page_num}"

        # Vorab prüfen, ob bereits auf Platte vorhanden
        cache_file = self.get_cache_path(material_id, file_path, page_num)
        if cache_file.exists() and cache_file.stat().st_size > 0:
            return

        with self._queued_lock:
            if cache_key in self._queued_items:
                return
            self._queued_items.add(cache_key)

        # In die PriorityQueue: (priority, counter, payload)
        self._queue.put((priority, time.time(), (material_id, file_path, mime_type, page_num)))

    def queue_material(
        self,
        material_id: str,
        file_path: str,
        mime_type: str,
        page_count: int,
        priority: int = PRIORITY_BACKGROUND
    ):
        """Reiht alle Seiten eines Materials zur Hintergrundgenerierung ein."""
        if "pdf" not in mime_type.lower() and not file_path.lower().endswith(".pdf"):
            return
        total = max(1, page_count or 1)
        for p in range(1, total + 1):
            self.queue_page(material_id, file_path, mime_type, p, priority=priority)

    def queue_all_database_materials(self, db_session_factory):
        """
        Liest alle Dokumente aus der Datenbank und reiht noch ungerenderte Seiten
        mit Hintergrund-Priorität (3) ein.
        """
        def _scan():
            time.sleep(1.0)  # Kurze Verzögerung nach App-Start
            db = db_session_factory()
            try:
                from backend.app.models.material import Material
                materials = db.query(Material).all()
                # Gesamtbücher mit Kapiteln werden nur über ihre Kapitel angezeigt -> nicht doppelt rendern
                parents_with_children = {m.parent_id for m in materials if m.parent_id}
                queued_count = 0
                for mat in materials:
                    if mat.id in parents_with_children:
                        continue
                    if not mat.file_path or not Path(mat.file_path).exists():
                        continue
                    # Bilder (z. B. Stundenplan-Fotos) werden direkt ausgeliefert, nicht gerendert
                    if "pdf" not in (mat.mime_type or "").lower() and not mat.file_path.lower().endswith(".pdf"):
                        continue
                    p_count = mat.page_count or 1
                    real_count = self.get_page_count(Path(mat.file_path))
                    if real_count:
                        p_count = min(p_count, real_count)
                    for p in range(1, p_count + 1):
                        cache_file = self.get_cache_path(mat.id, mat.file_path, p)
                        if not cache_file.exists():
                            self.queue_page(mat.id, mat.file_path, mat.mime_type, p, priority=PRIORITY_BACKGROUND)
                            queued_count += 1
                removed = self.cleanup_stale_cache({m.id: m.file_path for m in materials})
                logger.info(f"📚 {queued_count} ungerenderte Seiten in Hintergrund-Queue eingereiht, {removed} veraltete Cache-Bilder entfernt.")
            except Exception as e:
                logger.warning(f"Fehler beim Scannen der Materialien für Hintergrund-Cache: {e}")
            finally:
                db.close()

        threading.Thread(target=_scan, name="InitialPageCacheScan", daemon=True).start()

    def purge_material_cache(self, material_ids: Iterable[str]) -> int:
        """Entfernt alle gerenderten Seiten der angegebenen Materialien."""
        ids = set(material_ids)
        removed = 0
        for f in PAGE_CACHE_DIR.glob("*.jpg"):
            m = CACHE_NAME_RE.match(f.name)
            if m and m.group("doc") in ids:
                f.unlink(missing_ok=True)
                removed += 1
        return removed

    def cleanup_stale_cache(self, current_files: Dict[str, str]) -> int:
        """
        Entfernt Cache-Bilder gelöschter Materialien und veralteter Datei-Versionen
        (z. B. nach Neu-Segmentierung). current_files: {material_id: file_path}
        """
        current_mtimes: Dict[str, int] = {}
        for mat_id, file_path in current_files.items():
            try:
                current_mtimes[mat_id] = int(Path(file_path).stat().st_mtime)
            except (OSError, TypeError):
                pass
        removed = 0
        for f in PAGE_CACHE_DIR.glob("*.jpg"):
            m = CACHE_NAME_RE.match(f.name)
            if not m:
                continue
            if current_mtimes.get(m.group("doc")) != int(m.group("mtime")):
                f.unlink(missing_ok=True)
                removed += 1
        return removed

    def _worker_loop(self):
        """Arbeitet die Queue ab. Pausiert sofort, wenn ein Live-Request aktiv ist."""
        while not self._stop_event.is_set():
            # 1. Wenn ein Live-Request rendert: CPU vollständig freigeben!
            while self._live_in_progress_count > 0 and not self._stop_event.is_set():
                time.sleep(0.06)

            try:
                priority, _, item = self._queue.get(timeout=0.6)
            except Empty:
                continue

            material_id, file_path, mime_type, page_num = item
            cache_key = f"{material_id}_{page_num}"

            with self._queued_lock:
                self._queued_items.discard(cache_key)

            cache_file = self.get_cache_path(material_id, file_path, page_num)
            if cache_file.exists() and cache_file.stat().st_size > 0:
                self._queue.task_done()
                continue

            # Erneuter Check vor CPU-intensiver Arbeit
            while self._live_in_progress_count > 0 and not self._stop_event.is_set():
                time.sleep(0.06)

            try:
                self.render_page(
                    file_path=file_path,
                    mime_type=mime_type,
                    page_num=page_num,
                    material_id=material_id,
                    priority=priority
                )
            except Exception as e:
                logger.debug(f"Hintergrund-Rendering Fehler für {cache_key}: {e}")
            finally:
                self._queue.task_done()

            if priority == PRIORITY_BACKGROUND:
                self._rendered_in_background += 1
                if self._queue.empty():
                    logger.info(f"🖼️ Hintergrund-Rendering abgeschlossen ({self._rendered_in_background} Seiten).")
                    self._rendered_in_background = 0
                elif self._rendered_in_background % 100 == 0:
                    logger.info(f"🖼️ Hintergrund-Rendering: {self._rendered_in_background} Seiten, ca. {self._queue.qsize()} ausstehend.")

            # Mikropause zwischen Hintergrundseiten, um den Raspberry Pi kühl zu halten
            time.sleep(0.04)


# Globales Singleton für das gesamte Backend
page_renderer = PageRenderingService()
