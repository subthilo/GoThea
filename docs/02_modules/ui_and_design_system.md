# GoThea – iPadOS Design-System & Ergonomie-Architektur

Dokumentiert die UI/UX-Transformation von GoThea zu einer nativen **iPadOS-Erfahrung** mit großen Touch-Kacheln (Squircles), Vektor-Iconographie und radikaler Textreduktion.

---

## 1. Didaktische und ergonomische Zielsetzung

GoThea ist als multimodale Lernzentrale für das Apple iPad (mit Apple Pencil) optimiert.
Bei der täglichen Nutzung durch eine Schülerin der 7. Klasse führen lange Erklärungstexte, verschachtelte Button-Hierarchien und unruhige Listen zu kognitiver Überlastung (*cognitive load*).

### Kernprinzipien des Designs
1. **Direct Manipulation statt Textmenüs:** Bereiche und Fächer werden direkt als große, anfassbare Kacheln angetippt – nicht über kleine, textlastige Listenbuttons.
2. **Kein administrativer Ballast:** Angaben wie *„7. Klasse Gymnasium • Land Brandenburg (Niveaustufe E)“* oder *„Humboldt-Gymnasium Eichwalde • Klasse 7D“* werden aus den Arbeitsansichten verbannt. Sie gehören in die Stammdaten, nicht in den aktiven Lernfokus.
3. **iPadOS Springboard- & Widget-Ästhetik:** Anlehnung an iOS/iPadOS-App-Icons und interaktive Widgets mit harmonischen Farbtönen, abgerundeten Squircles und haptischem Touch-Feedback.
4. **Marken-Klarheit:** Vollständige Bereinigung von kindlichen Eulen-Symbolen (`🦉`) zugunsten einer eleganten, modernen Typografie (`GoThea`).

---

## 2. Das Squircle App-Tile System

Alle Hauptbereiche der Benutzeroberfläche nutzen einheitliche, vertikale App-Kacheln:

```
┌─────────────────────────┐
│                         │
│     ┌─────────────┐     │  <- 68px x 68px Icon-Container
│     │   ( SVG )   │     │     (20px border-radius, farblich getönt)
│     └─────────────┘     │
│                         │
│        Mathematik       │  <- Prägnanter Titel (kein Untertitel)
│                         │
└─────────────────────────┘
```

### CSS-Spezifikation (`frontend/style.css`)

```css
/* Standard Squircle App-Kachel */
.subject-card,
.subject-app-tile,
.dash-quick-card,
.subject-action-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 22px;
  padding: 24px 16px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  user-select: none;
  transition: transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.18s ease,
              border-color 0.18s ease;
  position: relative;
  overflow: hidden;
}

/* Haptisches Touch-Feedback beim Antippen */
.subject-card:active,
.dash-quick-card:active,
.subject-action-card:active {
  transform: scale(0.95);
}

/* Hover-Lift für Desktop/Maus */
.subject-card:hover,
.dash-quick-card:hover,
.subject-action-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.28);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.4);
}
```

---

## 3. Die drei Haupt-Kachelzonen

### A. Dashboard Schnell-Aktionen (`.dash-quick-grid`)
Vier primäre Einstiegszonen direkt unter dem Tages-Stundenplan:
* **Tafel (`Tafel.svg`):** Sofortiger Wechsel zur freien digitalen Schiefertafel.
* **Hausaufgaben (`Hausaufgaben.svg`):** Direkter Sprung zum Wochen-Lernplaner.
* **Bücher (`Bücher.svg`):** Öffnet den digitalen Schulbuch-Browser.
* **Upload (`Upload.svg`):** Schneller Dokument- und Notizen-Scan.

*Layout:* 4 Spalten im Querformat (`repeat(4, 1fr)`), 2 Spalten auf Smartphones (`repeat(2, 1fr)`).

### B. Schulfächer-Raster (`.subjects-grid`)
* Jedes Fach wird dynamisch als `.subject-app-tile` gerendert.
* Der Icon-Hintergrund wird subtil mit der jeweiligen Fachfarbe getönt (`${subColor}20`).
* Unter dem Icon steht ausschließlich der Fachname (`Mathematik`, `Biologie`, `Physik`, etc.).
* *Layout:* Responsives Grid mit `repeat(auto-fill, minmax(136px, 1fr))` und `16px` Lücke.

### C. Fach-Detailansicht (`.subject-action-cards-grid`)
Auf der Fachseite ersetzen drei große Touch-Kacheln die alte Button-Leiste:
1. **Tafel (`Tafel.svg`):** Digitale Tafel für dieses Schulfach mit KI-Tutorin Luna.
2. **Üben (`Übungen.svg`):** Öffnet die adaptive Lückentext- und Methoden-Arena.
3. **Upload (`Upload.svg`):** Material-/Hefter-Upload mit Fach-Vorauswahl.

---

## 4. Vektor-Iconographie (`frontend/Icons/`)

Das System nutzt eine Sammlung von über 55 handgezeichneten und kuratierten SVG-Vektorgrafiken.

### Dynamisches Mapping (`frontend/app.js`)
* `getSubjectIconUrl(name)`:
  * Weist Fächern automatisch das passende Fach-Icon zu (z. B. `Mathematik.svg`, `Biologie.svg`, `Physik.svg`, `Geschichte.svg`, `Englisch.svg`, `Geografie.svg`, etc.).
  * Normalisiert Umlaute und Sonderzeichen für robuste Treffer.
* `getDocumentIconUrl(kind, title)`:
  * Erkennt Dokumenttypen (Arbeitsblatt, Hefter, Tafelbild, Schulbuch, Test, Notiz) und liefert das entsprechende Dokument-Icon (`Arbeitsblatt.svg`, `Hefter.svg`, etc.).

---

## 5. Scrolling & Viewport-Optimierung

### Behebung von Scroll-Blockaden
* **Problem:** Bei extremen Breiten (z. B. iPad Querformat oder Desktop-Monitoren) waren Hauptansichten durch starre `overflow: hidden`-Attribute auf Eltern-Containern nicht mehr scrollbar.
* **Lösung:**
  * Globale Viewport-Höhe dynamisch über `100dvh` (Dynamic Viewport Height) gesteuert.
  * `.app-content` und `.tab-pane` besitzen einheitliches `overflow-y: auto` mit `overscroll-behavior: contain`.
  * Reader-Ansicht im Buch-Browser besitzt einen separaten Zen-Modus mit Zoom-Umschalter (*Ganze Seite einpassen* vs. *Volle Breite*).

---

## 6. Bereinigung von Branding & Eulen-Assets

| Vorkommen alt | Status neu | Begründung |
| :--- | :--- | :--- |
| Logo Header (`🦉 GoThea`) | Saubere Typografie `GoThea` | Modernes, reiferes Erscheinungsbild |
| Favicon (`🦉`) | Geometrisches SVG-Logo mit Farbgradient | Einheitlich im Browser-Tab |
| Whiteboard-Tutor (`🦉 Tutor fragen`) | `✨ Tutor fragen` | Klare KI-Assoziation ohne Kitsch |
| Level-Progression (`GoThea-Meisterin 🦉✨`) | `GoThea-Meisterin ✨` | Konsistenz im Gamification-System |
| Upload-Spinners (`🦉 Analysiere...`) | `Analysiere Dokument...` | Ruhige, professionelle Statusmeldung |
