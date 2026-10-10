# 02.5 Multimodale Whiteboard Engine

Die **Whiteboard Engine** stellt das digitale Klassenzimmer für Schüler (Fokus: 7. Klasse Gymnasium) und den KI-Tutor bereit. Sie wurde gezielt für den Einsatz auf dem **iPad mit Apple Pencil via iPadOS Safari** konzipiert und optimiert.

---

## 1. iPad- & Apple-Pencil-Erfassung (Low-Latency)

* **Hardwarebeschleunigtes HiDPI Retina Rendering:**
  * Canvas-Puffer wird dynamisch mit `window.devicePixelRatio` (auf iPad üblicherweise 2.0) skaliert.
  * Scharfe Vektordarstellung ohne Verpixelung auf Retina-Displays.
* **Apple Pencil Präzision:**
  * Kontinuierliche Pfadsegmente via `quadraticCurveTo` mit Coalesced Events (`e.getCoalescedEvents()`).
  * Druckstufenerfassung (`e.pressure`) zur dynamischen Strichstärkenmodulation bei Füller und Textmarker.
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

## 3. Unbegrenzte vertikale Tafel (Infinite Canvas) & Zwei-Finger-Scrollen

Schüler können Rechenwege und Mitschriften nach unten beliebig fortführen:

* **1:1 Physikalisches Zwei-Finger-Scrollen:**
  * Wenn zwei Finger das iPad-Glas berühren (`touches.length === 2`), wird das Zeichnen unterbrochen und der Scroll-Modus aktiviert.
  * Die relative Distanz zum Start-Mittelpunkt ($\Delta y = y_{center} - y_{startCenter}$) wird 1:1 direkt auf den vertikalen Offset `panY` übertragen (keine künstliche Trägheit, keine Latenz).
* **Virtuelles Koordinatensystem:**
  * Strichkoordinaten werden intern im weltweiten Tafelkoordinatensystem gespeichert ($y_{board} = y_{screen} - panY$).
  * `setTransform(dpr, 0, 0, dpr, panX * dpr, panY * dpr)` verschiebt sowohl die Zeichenebene als auch die KI-Overlay-Ebene synchron.
* **Muster-Offset:**
  * Das gewählte Hintergrundmuster (Kariert, Liniert, Kreide) scrollt via `backgroundPositionY = panY` nahtlos mit.
* **Scroll-UI:**
  * Dezente, automatisch ausblendende Scrollbar am rechten Rand (`.wb-scroll-track` und `.wb-scroll-thumb`).
  * „⤒ Zum Anfang“-Button: Erscheint automatisch ab 60px Scroll-Tiefe und führt bei Klick eine sanfte kubische Rückkehranimation (`1 - (1-t)^3`) zum Tafelanfang durch.
* **Desktop-Kompatibilität:**
  * Unterstützt auch Trackpad-Zwei-Finger-Scrollen und Mausrad (`wheel`-Event).

---

## 4. Universelles Undo / Redo (Aktions-Stack)

Alle Aktionen werden auf einem reversiblen Stack protokolliert:
* `add_stroke`: Zeichnen eines Strichs (Rückgängig: Entfernen des Strichs).
* `delete_strokes`: Objektradierung (Rückgängig: Wiederherstellen gelöschter Striche an ihren exakten Indexpositionen).
* `clear_canvas`: Tafel-Leeren (Rückgängig: Wiederherstellen des gesamten Board-Zustands).
* **Tastatur-Shortcuts:** `Cmd/Ctrl + Z` (Undo), `Cmd/Ctrl + Y` (Redo), `P` (Stift), `H` (Marker), `E` (Radierer-Toggle).

---

## 5. Dual-Layer-Architektur & KI-Overlay

* **Ink Canvas (`wb-canvas`):** Die persistierte Zeichenebene des Schülers.
* **Overlay Canvas (`wb-overlay`):** Eine vollkommen transparente Ebene (`pointer-events: none;`, `z-index: 5`) direkt über dem Ink Canvas:
  * Empfängt sokratische Hilfestellungen vom Backend.
  * Unterstützt farbige Markierungsboxen (`highlight_box`) und LaTeX-Formelhinweise (`latex_hint`).
  * Lässt den Schüler weiterzeichnen, während Hinweise eingeblendet werden.

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
