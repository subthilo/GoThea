# 01.4 Sicherheits- und Datenschutzkonzept

## 1. Lokale Datenhoheit & Datensparsamkeit

GoThea verarbeitet hochsensible Schülerdaten (Noten, Termine, Schulmaterialien und Mitschriften). Die Architektur garantiert strikte lokale Datenhoheit:

1. **Keine PII an externe KI-APIs:**
   * Schülernamen, Schuladressen oder private Identifikatoren werden vor API-Aufrufen an externe Foundation-Modelle (OpenAI) strikt anonymisiert bzw. maskiert.
2. **Lokale Datenbanken:**
   * Alle Profildaten, Notizen und Prüfungstermine verbleiben auf dem lokalen Raspberry Pi in verschlüsselten/gesicherten SQLite-Dateien (`data/prod/app_data.db` bzw. `data/staging/app_data.db`).

---

## 2. IServ-Zugangsdaten-Schutz (AES-256-GCM Vault)

Um Termine und Aufgaben via CalDAV und WebDAV ohne API-Schlüssel abzurufen, müssen Benutzername und Passwort hinterlegt werden.
* **Kein Klartext in der Datenbank:** Das Passwort wird **niemals** als Plaintext in `iserv_accounts.encrypted_secret` gespeichert.
* **Verschlüsselung:** Symmetrische Authenticated Encryption mittels **AES-256-GCM**.
* **Key-Management:** Der Verschlüsselungsschlüssel (`ISERV_SECRET_KEY`) wird ausschließlich als sichere Umgebungsvariable auf dem Raspberry Pi verwaltet und verlässt diesen zu keinem Zeitpunkt.

---

## 3. Offline-Resilienz

Bei einem Ausfall der Internetverbindung bleibt das System voll funktionsfähig für:
* Den Lernplan und Countdown (berechnet rein lokal und deterministisch).
* Das interaktive Whiteboard (lokales Zeichnen, Notizen und Skizzen).
* Den Abruf bereits synchronisierter oder hochgeladener Unterrichtsmaterialien.
