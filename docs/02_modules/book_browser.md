# 02.8 Schulbücher & Lehrwerke-Browser (`book_browser`)

## 1. Übersicht & Zielsetzung

Mit dem **Bücher-Browser** (`#tab-books`) erhält GoThea eine spezialisierte Ansicht zum Durchblättern und interaktiven Erkunden kompletter Schulbücher und Lehrwerke.

Schulbücher (wie das 196-seitige Mathematik-Lehrbuch für die 7. Klasse) sind als zusammenhängende Groß-PDFs (oft 60 MB+) auf Tablets unhandlich, langsam zu laden und unübersichtlich. Der Bücher-Browser löst dies durch eine strukturierte **Master-Detail-Architektur**:
* **Bücher-Regal (Shelf):** Schneller Wechsel zwischen verfügbaren Lehrwerken nach Schulfach und Klassenstufe.
* **Inhaltsverzeichnis & Sektions-Navigator (TOC):** Schneller Direktzugriff auf alle Lerneinheiten und Kapitel mit Seitenzahlen, Themenzuordnung und didaktischen Schwerpunkten.
* **Sektions-Reader & Seiten-Viewer:** Gestochen scharfes Retina-Rendering einzelner Buchseiten (150 DPI) ohne Speicherengpässe auf dem Raspberry Pi.
* **One-Tap Tafel-Übernahme:** Jede beliebige Buchseite oder Lerneinheit kann mit einem Klick (*„🎨 Auf Tafel öffnen“*) direkt in die Whiteboard-Engine als Arbeitsblatt übernommen werden.

---

## 2. Master-Child Datenmodell & Segmentierung

Die Repräsentation in der Datenbank ([Material](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/backend/app/models/material.py) & [Dossier](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/backend/app/models/dossier.py)) baut auf der Master-Child-Hierarchie auf:

```
[ Dossier: "Mathematik – Lehrbuch 7. Klasse" ] (kind = 'lehrbuch')
   │
   ├── Master [ Material: id = "mat_book_math_7" ] (kind = 'Buch', 196 Seiten)
   │     │
   │     ├── Child [ Material: "Kapitel 0: Titelei & Konzept" ] (S. 1–9)
   │     ├── Child [ Material: "Lerneinheit 1: Zahlen & Rechenoperationen" ] (S. 10–21)
   │     ├── Child [ Material: "Lerneinheit 2: Das Viereck" ] (S. 22–49)
   │     ├── Child [ Material: "Lerneinheit 3: Reelle Zahlen & Wurzeln" ] (S. 50–77)
   │     ├── Child [ Material: "Lerneinheit 4: Länge, Umfang & Fläche" ] (S. 78–89)
   │     ├── Child [ Material: "Lerneinheit 5: Der Kreis" ] (S. 90–111)
   │     ├── Child [ Material: "Lerneinheit 6: Ähnlichkeit der Dreiecke" ] (S. 112–137)
   │     ├── Child [ Material: "Lerneinheit 7: Gleichungssysteme" ] (S. 138–151)
   │     ├── Child [ Material: "Lerneinheit 8: Satz des Pythagoras" ] (S. 152–173)
   │     ├── Child [ Material: "Lerneinheit 9: Datenverarbeitung" ] (S. 174–187)
   │     └── Child [ Material: "Anhang: Jahreswiederholung & Lösungen" ] (S. 188–196)
```

Jedes Kind-Material speichert:
* `parent_id`: Verweis auf das Master-Buch
* `start_page` & `end_page`: Reale Buchseitennummerierung
* `page_count`: Umfang des Kapitels
* `topic_id`: Verknüpfung mit dem Brandenburger Rahmenlehrplan (RLP)
* `summary`: Didaktische Schwerpunkte (Formeln, Lehrsätze, Methoden)

---

## 3. UI-Komponenten & Interaktion

### 1. Bücher-Regal (`#books-shelf-selector`)
* Übersicht der verfügbaren Lehrwerke mit Fach-Icon, Titel, Autoren und Lerneinheiten.
* Ermöglicht das Umschalten zwischen Büchern mit sofortiger Aktualisierung des Inhaltsverzeichnisses.

### 2. Kapitel-Katalog (`#book-catalog-view`)
* **Übersichts-Kacheln:** Präsentiert alle Lerneinheiten in einem aufgeräumten, responsiven Raster (Grid) mit Einheit-Badge, Titel, Seitenzahlen (`S. 22–49 (28 S.)`), Rahmenlehrplan-Themen und didaktischem Schwerpunkt.
* **Echtzeit-Suche:** Sofortiges Filtern nach Kapiteltiteln, Themen oder Stichworten (z. B. *"Viereck"*, *"Kreis"*, *"Pythagoras"*).
* **Fokus-Öffnen:** Ein Klick auf eine Kachel öffnet nahtlos den vollbreiten Reader für dieses Kapitel.

### 3. Vollbreiter Sektions-Reader (`#book-reader-view`)
* **100% Dokumentbreite:** Keine störende Seitenleiste neben dem Dokument – die Buchseite füllt die gesamte Bildschirmbreite aus, sodass Formeln, Graphiken und Texte auf Tablets (z. B. iPad) groß, gestochen scharf und optimal lesbar sind.
* **Standard-Modus:** Automatisch auf volle Dokumentbreite (`mode-width`) voreingestellt mit vertikalem Scrollen.
* **Navigation & Quick-Jump:**
  * *← Alle Kapitel:* Rückkehr zur Katalog-Übersicht.
  * *☰ Kapitel wechseln:* Öffnet einen Offcanvas-Drawer von links zum schnellen Kapitelwechsel ohne die Leseposition zu verlassen.
  * *◀ Vorh. Einheit / Nächste Einheit ▶:* Direktes Weiterspringen zum nächsten Kapitel.
  * *◀ Vorherige Seite / Nächste Seite ▶:* Blättern innerhalb der Lerneinheit.
  * *Schnellauswahl-Pills:* Klickbare Seitennummern am unteren Rand zum direkten Anspringen.
* **Tafel-Übernahme:** *„🎨 Auf Tafel öffnen“* übernimmt das Dokument direkt auf das Whiteboard.
* **PDF-Download:** Direkter Downloadlink des segmentierten Kapitels.

### 4. Whiteboard-Übergabe
* Über den Button **„🎨 Auf Tafel öffnen“** wird die aktive Lerneinheit direkt in die Whiteboard-Engine übergeben (`loadWorksheetOnWhiteboard`). Die Schülerin kann Buchaufgaben direkt mit dem Apple Pencil auf der Tafel lösen und handschriftliche Rechenschritte festhalten.

---

## 4. Priorisiertes Hintergrund-Rendering & Smart Prefetching

Um jegliche Wartezeiten beim Blättern zu eliminieren, setzt GoThea auf den `PageRenderingService` mit einer mehrstufigen Prioritäts-Warteschlange:

| Stufe | Priorität | Auslöser | Verhalten |
|---|---|---|---|
| **1 (LIVE)** | Höchste | Direkter Seitenaufruf im Browser (`GET /preview`) | Fast-Path: Sofortige Auslieferung aus Cache (< 5 ms) oder direktes Rendern mit 100% CPU. Pausiert Hintergrund-Jobs. |
| **2 (PREFETCH)** | Hoch | Blättern zu Seite `P` | Reicht `P+1`, `P-1` und `P+2` mit Priorität 2 ein. Lädt Seiten parallel im Browser vor. |
| **3 (BACKGROUND)** | Niedrig | Serverstart / Neuer Dokumenten-Upload | Wandert im Leerlauf mit gedrosselter Priorität durch alle noch ungerenderten Seiten aller Dokumente. |

* **Zero-Wait Caching**: Jede gerenderte Seite wird als kompaktes JPEG (120 DPI) persistent unter `data/cache/rendered_pages/` abgelegt.
* **CPU-Schonung auf dem Raspberry Pi**: Der Hintergrund-Worker pausiert bei Live-Anfragen sofort und legt Mikropausen (40 ms) zwischen Seiten ein.

---

## 5. REST-API Schnittstellen

* `GET /api/v1/books`: Liefert die Liste aller verfügbaren Schulbücher.
* `GET /api/v1/books/{book_id}`: Liefert Buch-Metadaten und die sortierte Liste aller Lerneinheiten/Kapitel.
* `GET /api/v1/books/{book_id}/chapters/{chapter_id}`: Liefert Detaildaten einer einzelnen Lerneinheit.
* `GET /api/v1/materials/{id}/preview?page={p}`: Liefert die gerenderte Seite (Live-Priorität 1).
* `POST /api/v1/materials/{id}/prefetch?page={p}`: Stößt das vorausschauende Rendern der nächsten Seiten an (Priorität 2).
