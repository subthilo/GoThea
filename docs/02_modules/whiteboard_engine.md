# 02.5 Multimodale Whiteboard Engine

## 1. iPad- & Apple-Pencil-Erfassung

* **Low-Latency Rendering:** HTML5 2D Canvas mit Hardwarebeschleunigung.
* **PointerEvents:**
  * Druckstufen (`event.pressure`) für natürliche Strichstärken.
  * Neigungserkennung (`event.tiltX`, `event.tiltY`).
  * **Palm Rejection:** Handflächenerkennung (`pointerType === 'pen'`) verhindert Fehlstriche beim Auflegen der Hand auf das iPad.

---

## 2. Vektor- und Frame-Extraktion

* **Stroke-Aggregator:** Führt Striche als glatte Vektorkurven (Bézier-Pfade) zusammen.
* **Snapshot-Diffing:** Erkennt, wann eine neue Rechnung oder Skizze abgeschlossen ist (Pause im Schreibfluss).
* **Overlay-Layer:** Der KI-Tutor zeichnet Hinweise (farbige Rahmen, Pfeile, LaTeX-Formeln) auf einen transparenten Overlay-Canvas direkt über die Mitschrift des Schülers.
