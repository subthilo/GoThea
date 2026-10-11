# 02.5 Multimodale Whiteboard Engine

Die **Whiteboard Engine** stellt das digitale Klassenzimmer für Schüler und den KI-Tutor bereit. Sie wurde gezielt für den Einsatz auf dem **iPad mit Apple Pencil via iPadOS Safari** konzipiert und optimiert.

---

## 1. iPad- & Apple-Pencil-Erfassung (Low-Latency)

* **Hardwarebeschleunigtes HiDPI Retina Rendering:**
  * Canvas-Puffer wird dynamisch mit `window.devicePixelRatio` (auf iPad üblicherweise 2.0) skaliert.
  * Scharfe Vektordarstellung ohne Verpixelung auf Retina-Displays.
* **Apple Pencil Präzision & Latenz-Optimierung:**
  * **Coalesced Event Batching:** Alle 240-Hz-Punkte eines Touch-Events (`e.getCoalescedEvents()`) werden in einen einzigen zusammenhängenden Hardware-Pfad (`beginPath -> lineTo / quadraticCurveTo -> stroke`) gebündelt, was über 80% der GPU-Draw-Calls und Browser-Kontext-Wechsel einspart.
  * **Midpoint Quadratic Bézier Spline Glättung:** Weiche, kantenfreie Kurvenführung in Echtzeit durch kontinuierliche Mittelpunkts-Quadratur ohne Rechenaufwand (< 2 ns pro Punkt) oder Eingabeverzögerung.
  * **Konstante Strichstärke (Fineliner-Modus):** Einmaliges Setzen von `ctx.lineWidth` beim Strichbeginn verhindert context-thrashing und sorgt für gestochen scharfe Vektordarstellung.
* **Palm Rejection (Handflächenerkennung):**
  * Umschaltbarer **Stift-Modus**: Wenn aktiv, werden alle Touches mit `pointerType === "touch"` beim Zeichnen ignoriert, sodass die Hand natürlich auf dem iPad-Glas abgelegt werden kann.
* **100% Unterdrückung nativer Safari-Gesten & Callouts:**
  * Das native iOS Edit-Menü (**„Teilen ...“**) und Vergrößerungsglas-Gesten werden durch unbedingtes Abfangen aller `touchstart`-, `touchmove`-, `touchend`- und `touchcancel`-Events mit `{ capture: true, passive: false }` unterbunden.
  * WebKit-spezifische Gesten (`gesturestart`, `gesturechange`, `gestureend`) sowie `selectstart` und `selectionchange` werden auf Dokumentebene neutralisiert.
  * Globales CSS-Regelwerk: `-webkit-touch-callout: none !important;` und `-webkit-user-select: none !important;`.


---

## 2. Dualer Radierer-Modus

Das Whiteboard bietet zwei spezialisierte Radierer-Modi, die direkt über die schwebende iPad-Toolbar gewechselt werden können:

### A. 🧹 Pixel-Radierer
* **Funktionsweise:** Schaltet den Canvas-Kontext auf `globalCompositeOperation = 'destination-out'`.
* **Anwendungsfall:** Feinmotorisches Freiradieren einzelner Linienteile, mathematischer Rechenschritte oder kleiner Skizzendetails.
* **Stärke:** Einstellbar über die 3 Pinselgrößen (Fein, Normal, Dick).

### B. 🎯 Objekt-Radierer
* **Funktionsweise:** Vektorbasierter Schnittstellen- und Distanztest:
  1. **Bounding-Box Vorfilterung:** Schneller Ausschluss von Strichen außerhalb des Radierradius.
  2. **Punkt-zu-Segment Distanzberechnung:** Berechnet den minimalen orthogonalen bzw. Eckpunkt-Abstand des Radierpunktes zu jedem Liniensegment eines Strichs ($dist(P, \overline{AB})$).
* **Anwendungsfall:** Berührt der Schüler einen Strich auch nur minimal, wird der gesamte Strich (Buchstabe, Zahl, geometrische Form) sofort gelöscht.
* **Performance:** Sofortiges Feedback ohne Ruckeln selbst bei Hunderten Strichen.

---

## 3. Unbegrenzte vertikale Tafel (Infinite Canvas), Pinch-to-Zoom & Zoom-Steuerung

Schüler können Rechenwege nach unten beliebig fortführen und für detailgenaues Ausfüllen von Arbeitsblattlücken stufenlos heranzoomen:

* **1:1 Physikalisches Zwei-Finger-Scrollen:**
  * Wenn zwei Finger das iPad-Glas berühren (`touches.length === 2`), wird das Zeichnen unterbrochen.
  * Bewegen sich die Finger parallel, wird die Verschiebung 1:1 auf `panY` und `panX` übertragen.
* **Pinch-to-Zoom Gestensteuerung (100% – 350%):**
  * Ändert sich der Abstand zwischen den Fingern ($\Delta d > 8\text{px}$), wechselt das Board nahtlos in den Pinch-Zoom-Modus.
  * Der Zoomfaktor `scale` wird kontinuierlich im Bereich von $1.0$ (100%) bis $3.5$ (350%) moduliert.
* **Toolbar-Zoomsteuerung:**
  * Direkte Zoom-Buttons in der schwebenden iPad-Toolbar:
    * `➖`: Verkleinern um 25% bis zum Minimum von 100%.
    * `100%`: Ein-Klick-Reset auf Standardgröße und mittige Zentrierung.
    * `➕`: Vergrößern um 25% bis zum Maximum von 350%.
* **Virtuelles Koordinatensystem & Zoom-Transformation:**
  * Strichkoordinaten werden invariant im weltweiten Tafelkoordinatensystem gespeichert:
    $$x_{board} = \frac{x_{screen} - panX}{scale}, \quad y_{board} = \frac{y_{screen} - panY}{scale}$$
  * Rendering: `ctx.setTransform(dpr * scale, 0, 0, dpr * scale, panX * dpr, panY * dpr)` verschiebt und skaliert sowohl die Schüler-Zeichenebene als auch das KI-Overlay absolut synchron.
  * Das Arbeitsblatt-Underlay folgt derselben Transformation via hardwarebeschleunigtem CSS: `transform: translate(panX, panY) scale(scale); transform-origin: 0 0;`.
* **Proportionale Strichstärken-Skalierung (Fine Pen Scaling):**
  * Um zu verhindern, dass Stiftstriche bei 2.5-fachem Zoom unnatürlich fett werden und Lücken überdecken, skaliert GoThea die Strichstärke beim Zeichnen invers zum Zoomfaktor:
    $$\text{stroke.width} = \frac{\text{baseWidth}}{scale}$$
  * Ermöglicht dem Schüler das Schreiben kleiner, exakter Zahlen und Wörter in engste Arbeitsblattzeilen, die nach dem Herauszoomen auf 100% gestochen scharf und passgenau bleiben.
* **Scroll-UI:**
  * Dezente, automatisch ausblendende Scrollbar am rechten Rand (`.wb-scroll-track` und `.wb-scroll-thumb`).
  * „⤒ Zum Anfang“-Button: Erscheint automatisch ab 60px Scroll-Tiefe und animiert weich (`1 - (1-t)^3`) zum Tafelursprung zurück.

---

## 4. Universelles Undo / Redo (Aktions-Stack)

Alle Aktionen werden auf einem reversiblen Stack protokolliert:
* `add_stroke`: Zeichnen eines Strichs (Rückgängig: Entfernen des Strichs).
* `delete_strokes`: Objektradierung (Rückgängig: Wiederherstellen gelöschter Striche an ihren exakten Indexpositionen).
* `clear_canvas`: Tafel-Leeren (Rückgängig: Wiederherstellen des gesamten Board-Zustands).
* **Kompakte Dropdown-Toolbar:** Stift-Typ (`#wb-tool-select`), Strichstärke (`#wb-size-select`) und Farbe (`#wb-color-select` mit Live-Farbpunkt `#wb-color-indicator`) sind platzsparend als native Dropdown-Menüs organisiert. Dadurch ist die schwebende Leiste deutlich schmaler und passt perfekt auf jede iPad-Bildschirmbreite sowie Split-View.
* **Tastatur-Shortcuts:** `Cmd/Ctrl + Z` (Undo), `Cmd/Ctrl + Y` (Redo), `P` (Stift), `H` (Marker), `E` (Radierer-Toggle).

---

## 5. Multi-Layer Stacking Architektur & Arbeitsblatt-Hinterlegung

GoThea trennt die Anzeigeschichten streng nach Z-Index, um komfortables Schreiben **auf** Dokumenten zu ermöglichen, ohne das Original zu beschädigen:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Ebene 5 (z-index: 10): Schwebende Werkzeugleiste (#wb-toolbar)         │
├────────────────────────────────────────────────────────────────────────┤
│ Ebene 4 (z-index: 8):  Dokument-Leiste (#wb-doc-topbar, z.B. Schließen)│
├────────────────────────────────────────────────────────────────────────┤
│ Ebene 3 (z-index: 5):  KI-Overlay (#wb-overlay: Boxen, Formel-Tipps)   │
├────────────────────────────────────────────────────────────────────────┤
│ Ebene 2 (z-index: 2):  Schüler-Canvas (#wb-canvas: Apple Pencil Ink)   │
├────────────────────────────────────────────────────────────────────────┤
│ Ebene 1 (z-index: 1):  Dokument-Underlay (#wb-doc-underlay, Vorlage)   │
└────────────────────────────────────────────────────────────────────────┘
```

* **Ebene 1 – Dokument-Underlay (`#wb-doc-underlay`):**
  * Enthält gerenderte Seiten des Arbeitsblatts oder Schulhefters als Seitenstapel (`.wb-doc-page-card`).
  * Multi-Page-Support: Bei mehrseitigen PDFs werden alle Seiten untereinander als DIN-A4-Karten angeordnet.
* **Ebene 2 – Schüler-Schreibebene (`#wb-canvas`):**
  * Transparenter Canvas mit `z-index: 2`, der **über** dem Dokument liegt.
  * Stift- und Marker-Eingaben erscheinen direkt auf dem gedruckten Text oder in den Formularfeldern des Arbeitsblatts.
* **Radierer-Schutz (Eraser Immunity):**
  * Weder der Pixel-Radierer (`destination-out`), noch der Objekt-Radierer, noch „Tafel leeren“ berühren das Dokument auf Ebene 1.
  * Das Arbeitsblatt bleibt permanent und fehlerfrei erhalten; radiert wird ausschließlich die Schülertinte auf Ebene 2.
* **Ebene 3 – KI-Overlay Canvas (`#wb-overlay`):**
  * Transparent (`pointer-events: none;`, `z-index: 5`) für sokratische Hinweise (`highlight_box`, `latex_hint`).

---

## 6. Persistenz & WebSocket-Schnittstelle

* **Non-Blocking Auto-Save:**
  * Bei Beendigung eines Strichs wird ein entprellter Speichervorgang (`scheduleAutoSave`, 1200ms Debounce) angestoßen.
  * Sendet das kompakte JSON der Vektorstriche an `PUT /api/v1/whiteboard/sessions/{id}/state`.
  * Kein teures synchrones `toDataURL()` während des Schreibens.
* **WebSocket (`/ws/tutor/{session_id}`):**
  * Bidirektionaler Kanal für Heartbeats (`ping`/`pong`).
  * Barge-In Erkennung: Unterbricht KI-Sprachausgaben sofort, wenn der Schüler den Stift ansetzt (`pencil_touch`).
  * Live-Empfang didaktischer Hinweise (`board_actions`).
