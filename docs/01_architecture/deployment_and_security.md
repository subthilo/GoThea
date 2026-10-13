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

---

## 4. Elternmodus & PIN-Sicherheitsarchitektur (`parent_auth.py`)

Um versehentliche Datenverluste durch die Schülerin (z. B. unabsichtliches Löschen von Mitschriften oder Manipulieren von Klassenarbeiten) auszuschließen, sind alle administrativen und destruktiven Operationen durch einen **PIN-geschützten Elternbereich** abgesichert:

### 1. Authentifizierung & Session-Management
* **PIN-Konfiguration:** Die 4-stellige Eltern-PIN wird über die Umgebungsvariable `PARENT_PIN` (Default: `1234`) gesteuert.
* **Signiertes Session-Cookie:** Nach erfolgreicher PIN-Eingabe an `POST /api/v1/auth/parent/unlock` setzt das Backend ein HTTP-Only-Cookie `gothea_parent_session` mit einer Gültigkeitsdauer von **1 Stunde**.
* **Manuelle & automatische Sperre:** Eltern können den Modus jederzeit über das Header-Badge sperren (`POST /api/v1/auth/parent/lock`). Nach Ablauf der Session sperrt sich das System automatisch.

### 2. Brute-Force & Lockout-Schutz
* Das Backend zählt fehlgeschlagene PIN-Eingaben IP- und sitzungsübergreifend.
* **Lockout nach 5 Fehlversuchen:** Nach 5 falschen Eingaben blockiert das System jegliche weiteren Versuche für **5 Minuten** (HTTP `429 Too Many Requests`). Die UI zeigt einen Countdown mit verbleibenden Sperrminuten.

### 3. Abgesicherte API-Endpunkte (`Depends(require_parent)`)
Ohne gültige Eltern-Session weisen folgende Endpunkte Anfragen mit HTTP `401 Unauthorized` ab:
* `DELETE /api/v1/materials/{id}` (Endgültiges Löschen von Dokumenten und Chunks)
* `PATCH /api/v1/materials/{id}` (Ändern von Schulfach, Thema, Titel oder Art)
* `POST /api/v1/materials/merge` (Zusammenführen von Dokumenten & Quell-Löschung)
* `POST /api/v1/materials/{id}/reorder-pages` (Umordnen oder Löschen von PDF-Seiten)
* `POST /api/v1/env/staging/reset` (Rücksetzen der Staging-Datenbank)
* `POST /api/v1/books/seed` (Manueller Lehrbuch-Import)

### 4. Clientseitige Schutzschicht
* Alle geschützten Schaltflächen im Frontend tragen die CSS-Klasse `.parent-only`.
* Ist der Elternmodus inaktiv, werden diese Buttons visuell ausgeblendet oder öffnen beim Anklicken das sichere PIN-Eingabe-Modal (`#modal-parent-pin`).

