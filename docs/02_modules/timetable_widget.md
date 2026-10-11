# 02.7 Stundenplan & Schulalltag-Organisation (`timetable_widget`)

## 1. Übersicht & Zielsetzung

Der Stundenplan ist der zentrale Taktgeber für Theas Schulalltag (Klasse 7D, Humboldt-Gymnasium Eichwalde). 

Bisher musste der Stundenplan als statisches Dokument (PDF oder Foto) geöffnet und mühsam gescrollt oder gezoomt werden. Mit dem Subsystem **Stundenplan & Organisation** wurde GoThea um ein **vollwertiges, natives Stundenplan-Widget** erweitert:
* **Eigene interaktive Seite (`#tab-timetable`):** Vollständiges Wochenraster (Montag bis Freitag, 1. bis 8. Stunde) mit scharfem Typografie-Layout, Fachfarben, Lehrerkürzeln und Raumangaben.
* **Tages-Widget auf dem Dashboard:** Sofortiger Überblick über den aktuellen Tag beim Öffnen der App („Dein Schultag heute“).
* **A-/B-Wochen-Support:** Automatischer Wechsel zwischen geraden und ungeraden Kalenderwochen mit manuellem Umschalter.
* **Deep-Link-Verzahnung:** Direkte Interaktion aus dem Stundenplan in das Whiteboard (Tafel) und die Material-Mediathek.
* **Original-Scan-Verknüpfung:** Jederzeitiger Absprung in den hochgeladenen Original-Scan im optimierten Dokumenten-Viewer.

---

## 2. Untis-Stundenraster & Zeiten (Klasse 7D)

Das Glockenraster des Humboldt-Gymnasiums Eichwalde teilt den Schultag in 9 Einheiten ein, einschließlich der geteilten 6. Stunde (`6.1` und `6.2`):

| Periode | Bezeichnung | Uhrzeit | Typische Nutzung |
| :--- | :--- | :--- | :--- |
| **1** | 1. Std | 07:45 – 08:30 | 1. Block (Hälfte 1) |
| **2** | 2. Std | 08:30 – 09:15 | 1. Block (Hälfte 2) |
| *Pause*| Hofpause | 09:15 – 09:45 | 30 Min. Hofpause |
| **3** | 3. Std | 09:45 – 10:30 | 2. Block (Hälfte 1) |
| **4** | 4. Std | 10:30 – 11:15 | 2. Block (Hälfte 2) |
| *Pause*| Kleine Pause | 11:15 – 11:25 | 10 Min. Wechselpause |
| **5** | 5. Std | 11:25 – 12:10 | 3. Block Beginn / Dienstag: GT-Mittag |
| **6** | 6.1 Std | 12:15 – 13:00 | 3. Block Ende / Dienstag: GT-Mittag |
| **7** | 6.2 Std | 13:05 – 13:50 | Mo/Mi/Do/Fr: Mittagspause / Di: PB (315) |
| **8** | 7. Std | 13:55 – 14:40 | 4. Block Beginn (z. B. WAT, LER) |
| **9** | 8. Std | 14:40 – 15:25 | 4. Block Ende |

---

## 3. Der A-/B-Wochen Turnus (Alternating Weeks)

In Brandenburg und am Humboldt-Gymnasium Eichwalde wechseln bestimmte Unterrichtsstunden im zweiwöchentlichen Turnus:

### Kalenderwochen-Logik
* **Ungerade Kalenderwoche (z. B. KW 41, 43, 45):** **🅰️ A-Woche**
* **Gerade Kalenderwoche (z. B. KW 40, 42, 44):** **🅱️ B-Woche**

### Konkreter Stunden-Unterschied (Montag):
* **Montag 5. & 6.1 Stunde (11:25 – 13:00):**
  * **In A-Woche:** **Sport** (`*Sp`, Fr. DÜCK, Turnhalle `gewo`)
  * **In B-Woche:** **Englisch** (`En`, Fr. SCHD, Raum `104`)

### UI-Integration:
Im Stundenplan-Header kann die Schülerin mit einem Klick zwischen `🅰️ A-Woche` und `🅱️ B-Woche` umschalten. Ein Hinweiskasten erläutert Abweichungen transparent.

---

## 4. Übersicht Theas Stundenplan (Klasse 7D)

```
┌──────┬──────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
│ Std  │ MONTAG               │ DIENSTAG             │ MITTWOCH             │ DONNERSTAG           │ FREITAG              │
├──────┼──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ 1    │ Deutsch (201)        │ Biologie (207)       │ Physik (106)         │ Englisch (104)       │ Geschichte (102)     │
│ 2    │ Deutsch (201)        │ Biologie (207)       │ Physik (106)         │ Englisch (104)       │ Musik (N1.2)         │
│ 3    │ Mathematik (303)     │ Französisch (203)    │ Deutsch (201)        │ Sport (gewo)         │ Französisch (203)    │
│ 4    │ Mathematik (303)     │ Französisch (203)    │ Deutsch (201)        │ Sport (gewo)         │ Französisch (203)    │
│ 5    │ 🅰️Sport / 🅱️Englisch │ *GT-Mittag (Mensa)   │ Englisch (104)       │ Chemie (210)         │ Mathematik (303)     │
│ 6.1  │ 🅰️Sport / 🅱️Englisch │ *GT-Mittag (Mensa)   │ *Mittag (Mensa)      │ *Mittag (Mensa)      │ Mathematik (303)     │
│ 6.2  │ *Mittag (Mensa)      │ Polit. Bildung (315) │ Geografie (101)      │ Musik (N1.2)         │ *Mittag (Mensa)      │
│ 7    │ WAT / Wirtsch. (105) │ LER / Rel (007/302)  │                      │                      │                      │
│ 8    │ WAT / Wirtsch. (105) │ LER / Rel (007/302)  │                      │                      │                      │
└──────┴──────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

---

## 5. UI-Komponenten & User Experience

### 1. Dashboard „Dein Schultag heute“
* Zeigt die Unterrichtsstunden des aktuellen Tages in chronologischer Reihenfolge.
* Am Wochenende wird automatisch der Vorgriff auf den kommenden **Montag** angezeigt.
* Jeder Block hebt Fach-Icon, Fachname, Lehrer, Raum und Uhrzeit hervor.

### 2. Wochenplan-Raster (`#tab-timetable`)
* Glassmorphism-Karten mit individueller Fach-Akzentfarbe (`border-left: 4px solid var(--accent)`).
* Doppelstunden-Markierung (`🔗 Doppelstunde`).
* Kennzeichnung von Wechselstunden (`🔄 Turnus A` / `🔄 Turnus B`).
* Eigener sanfter Grauton für Mensa- & Mittagspausen.

### 3. Slot-Detail-Modal (`#modal-tt-slot-detail`)
Ein Klick auf einen beliebigen Unterrichtsblock öffnet ein interaktives Aktionsmenü:
1. **🎨 Auf Tafel öffnen:**
   Startet die Whiteboard-Engine, setzt automatisch das Schulfach und legt eine neue Live-Tafel für die Unterrichtsstunde an.
2. **📚 Materialien zum Fach:**
   Wechselt in die Mediathek und filtert sofort nach Heftern, Arbeitsblättern und Büchern des jeweiligen Fachs.
3. **📄 Original-Stundenplan ansehen:**
   Öffnet den hochgeladenen Scan im In-App Dokumenten-Viewer.

---

## 6. Datenmodell (`timetable_slots`)

Das Datenmodell ist in `backend/app/models/timetable.py` implementiert:

```python
class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), default="usr_thea", nullable=False)
    day_of_week = Column(String, nullable=False)   # "Montag" ... "Freitag"
    period = Column(Integer, nullable=False)       # 1 bis 9
    period_label = Column(String, nullable=True)   # "1. Std", "6.1 Std"
    start_time = Column(String, nullable=True)     # "07:45"
    end_time = Column(String, nullable=True)       # "08:30"
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True)
    subject_code = Column(String, nullable=True)   # "D", "Ma", "*Sp"
    subject_name = Column(String, nullable=False)  # "Deutsch", "Mathematik"
    custom_title = Column(String, nullable=True)   # "*Mittag"
    teacher = Column(String, nullable=True)        # "DÜCK", "HORN"
    room = Column(String, nullable=True)           # "201", "303", "gewo"
    week_type = Column(String, default="both")     # "both", "A", "B"
    is_double_period = Column(Boolean, default=False)
    is_break = Column(Boolean, default=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
```

---

## 7. REST-API Endpoints

* `GET /api/v1/timetable`: Liefert gesamten Wochenplan mit Slots, Perioden und Metadaten (optional `?week_type=A|B`).
* `GET /api/v1/timetable/today`: Liefert chronologische Stunden des aktuellen Tages (oder Montags).
* `POST /api/v1/timetable/slot`: Fügt eine Stunde hinzu.
* `PUT /api/v1/timetable/slot/{id}`: Ändert Raum, Lehrer, Zeiten oder Notizen.
* `DELETE /api/v1/timetable/slot/{id}`: Löscht eine Stunde.
* `POST /api/v1/timetable/reset`: Setzt den Plan atomar auf Theas Werkseinstellungen (Klasse 7D) zurück.
