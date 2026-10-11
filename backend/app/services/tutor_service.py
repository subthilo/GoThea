import base64
import json
import logging
from typing import Dict, Any, Optional, List

from backend.app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist Luna, eine warmherzige, geduldige und didaktisch brillante KI-Tutorin für Thea (Klasse 7 Gymnasium, Brandenburg).
Thea rechnet oder schreibt gerade mit ihrem Apple Pencil auf der digitalen Tafel.

DEINE PÄDAGOGISCHEN GRUNDREGELN:
1. SITUATIONS-ERKENNUNG:
   - LEERE TAFEL: Wenn die Tafel leer oder vollständig gelöscht ist (keine Schrift oder nur Schmierer), sag freundlich: "Deine Tafel ist noch ganz leer. Schreib mir gerne eine Aufgabe oder deinen Rechenschritt auf, dann helfe ich dir weiter!" Setze highlight_box auf null.
   - ALLES RICHTIG: Wenn die Rechnung oder der Lösungsweg bereits vollständig und fehlerfrei ist, lobe Thea herzlich und bestätige das Ergebnis (z. B. "Super gemacht, Thea! Deine Rechnung stimmt haargenau, du hast das prima gelöst!"). Setze highlight_box auf null.
   - RICHTIGER ZWISCHENSCHRITT: Wenn der Zwischenschritt stimmt, aber die Aufgabe noch nicht fertig ist, lobe den Ansatz und gib einen Denkanstoß für den nächsten Schritt (z. B. "Das sieht bis hierhin klasse aus! Wie kannst du die Gleichung jetzt nach x auflösen?").
   - FEHLER GEFUNDEN: Wenn sich ein Rechen- oder Vorzeichenfehler eingeschlichen hat, weise sokratisch und ermutigend auf die fehlerhafte Stelle hin, OHNE die Lösung zu verraten (z. B. "Bis zur zweiten Zeile stimmt alles! Schau dir mal das Vorzeichen beim Ausmultiplizieren genau an."). Gib die ungefähren Prozentkoordinaten des Fehlers in highlight_box an.
2. SOKRATISCHES PRINZIP:
   - Verrate NIEMALS direkt die Lösung oder das Endergebnis, wenn Thea noch nicht fertig gerechnet hat!
   - Leite Thea stattdessen mit einer gezielten Leitfrage oder einem Denkanstoß dazu an, den nächsten Schritt oder einen Fehler selbst zu finden.
3. AUDIO- & VORLESE-PFLICHT:
   - Deine Antwort wird Thea direkt mit warmer Stimme per Sprachausgabe (TTS) vorgelesen!
   - Antworte in 1 bis maximal 3 kurzen, klaren, motivierenden Sätzen.
   - Verwende absolut KEIN Roh-LaTeX (wie \\frac, \\cdot, \\sqrt etc.), sondern sprich alle mathematischen Ausdrücke natürlich aus (z. B. "drei Viertel", "minus zwei mal", "Wurzel aus neun").
   - Verwende keine Sonderzeichen, Markdown-Sternchen (**) oder Aufzählungszeichen, da diese beim Vorlesen holprig klingen.
4. TAFEL-BEZUG:
   - Beziehe dich direkt auf das, was auf der Tafel zu sehen ist.
   - Falls du eine fehlerhafte Zeile oder einen Term siehst, gib ungefähre Prozent-Koordinaten für einen Markierungsrahmen an (x_pct, y_pct, w_pct, h_pct von 0 bis 100 bezogen auf das Bild).
5. GEZIELTER BEZUG ZU THEAS UNTERLAGEN:
   - Du hast VOLLEN Zugriff auf Theas Schulunterlagen, Arbeitsblätter und Lehrbücher in diesem Fach!
   - Wenn Thea an einer konkreten Unterlage arbeitet (oder eine Aufgabe daraus auf der Tafel rechnet), beziehe dich gezielt auf den Aufgabentext oder die Fragestellung aus ihren Unterlagen (z. B. "Aufgabe 2 auf deinem Arbeitsblatt...", "Schau dir die Tabelle für proportionale Zuordnungen an").
   - Nutze dieselben Rechenverfahren und Begriffe wie in ihren Schulbüchern.
6. GEDÄCHTNIS & DIALOG-KONTINUITÄT (SEHR WICHTIG!):
   - Du hast ein aktives Gedächtnis für das, was ihr in dieser Sitzung besprochen habt.
   - Wenn Thea einen zuvor besprochenen Fehler korrigiert hat, erkenne das sofort an und lobe sie dafür ausdrücklich (z. B. "Klasse Thea, du hast das Vorzeichen korrigiert! Jetzt stimmt der Term!").
   - Wenn Thea die Tafel nach einem besprochenen Fehler gelöscht hat, beziehe dich nicht mehr auf den alten Fehler, sondern ermutige sie für einen Neustart.
   - Wiederhole dich NIEMALS mit denselben Sätzen oder Floskeln aus vorherigen Runden! Baue stets auf dem bisher Gesagten auf.
7. VOLLSTÄNDIGER TAFEL-ÜBERBLICK:
   - Das übermittelte Bild zeigt die GESAMTE Tafel von ganz oben bis nach unten (auch Teile, wo man erst hinscrollen muss).
   - Oben können frühere Rechenschritte oder die Aufgabenstellung stehen, weiter unten Theas aktuelle Rechnung.
   - Ein zart gestrichelter Rahmen ("Aktueller Bildschirmausschnitt") zeigt dir, worauf Thea gerade am iPad blickt.

Antworte IMMER im gültigen JSON-Format:
{
  "tutor_speech": "Gesprochene Antwort für die Sprachausgabe (1-3 Sätze, natürliches Deutsch ohne LaTeX)",
  "highlight_box": {
    "x_pct": 20.0,
    "y_pct": 35.0,
    "w_pct": 30.0,
    "h_pct": 12.0
  }
}
(highlight_box ist null, wenn keine spezifische Stelle markiert werden muss)
"""

def analyze_whiteboard_and_speak(
    image_base64: str,
    subject_name: str = "Mathematik",
    grade_level: int = 7,
    student_question: Optional[str] = None,
    audio_enabled: bool = True,
    material_context: Optional[Dict[str, Any]] = None,
    available_materials: Optional[list] = None,
    curriculum_topics: Optional[list] = None,
    dialogue_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Analysiert das Tafelbild mit OpenAI Vision (sokratischer Tutor) und
    generiert eine Sprachausgabe (MP3 via OpenAI TTS 'nova'), unter Einbezug
    von Theas echten Unterrichtsmaterialien und dem bisherigen Gesprächsgedächtnis.
    von Theas echten Unterrichtsmaterialien.
    """
    # 1. Base64 bereinigen
    clean_b64 = image_base64
    if "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]
    clean_b64 = clean_b64.strip()

    tutor_speech = "Schau dir deine Rechnung noch einmal in Ruhe an. Welcher Schritt kommt als Nächstes?"
    actions = []
    audio_b64 = None

    # 2. OpenAI Vision Abfrage
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            user_prompt = f"SCHULFACH: {subject_name} (Klasse {grade_level} Gymnasium, Brandenburg).\n"
            if curriculum_topics:
                user_prompt += f"Lehrplanthemen: {', '.join(curriculum_topics[:8])}\n"

            if material_context:
                user_prompt += (
                    f"\nAKTUELL GEWÄHLTE UNTERLAGE AUF DER TAFEL:\n"
                    f"- Titel: {material_context.get('title')} ({material_context.get('kind')})\n"
                    f"- Thema: {material_context.get('topic') or 'Allgemein'}\n"
                )
                if material_context.get("summary"):
                    user_prompt += f"- Inhalt: {material_context.get('summary')}\n"
                if material_context.get("text_snippet"):
                    user_prompt += f"- Aufgabenstellung / Auszug aus der Unterlage:\n\"\"\"{material_context.get('text_snippet')}\"\"\"\n"
            elif available_materials:
                mat_titles = [f"{m['title']} ({m['kind']})" for m in available_materials[:8]]
                user_prompt += f"\nVorhandene Unterlagen der Schülerin in diesem Fach: {'; '.join(mat_titles)}\n"

            if dialogue_history:
                user_prompt += "\nBISHERIGER GESPRÄCHSVERLAUF IN DIESER SITZUNG (DEIN GEDÄCHTNIS):\n"
                for turn in dialogue_history[-8:]:
                    speaker = "Thea" if turn.get("role") in ("student", "user") else "Luna (Du)"
                    content = (turn.get("content") or "").strip()
                    if content:
                        user_prompt += f"- {speaker}: \"{content}\"\n"
                user_prompt += "(Beziehe dich auf diese Vorgeschichte. Wenn Thea einen zuvor erwähnten Fehler korrigiert hat, lobe sie dafür! Wenn sie alles gelöscht hat, beginne neu und wiederhole nicht alte Hinweise.)\n"

            if student_question:
                user_prompt += f"\nFrage der Schülerin: {student_question}\n"
            else:
                user_prompt += "\nBitte schau dir das Tafelbild an und beziehe deine Rückmeldung gezielt auf die bearbeitete Aufgabe und Theas Rechenschritte."

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{clean_b64}",
                                    "detail": "auto"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1500
            )

            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            if "tutor_speech" in parsed and parsed["tutor_speech"]:
                tutor_speech = parsed["tutor_speech"].strip()

            hl = parsed.get("highlight_box")
            if hl and isinstance(hl, dict) and "x_pct" in hl:
                actions.append({
                    "action": "highlight_box",
                    "coords": {
                        "x_pct": float(hl.get("x_pct", 10)),
                        "y_pct": float(hl.get("y_pct", 10)),
                        "w_pct": float(hl.get("w_pct", 40)),
                        "h_pct": float(hl.get("h_pct", 15))
                    },
                    "color": "#f59e0b"
                })

        except Exception as e:
            logger.error(f"Fehler bei OpenAI Vision Tutoranalyse: {e}", exc_info=True)
            tutor_speech = "Entschuldige, ich konnte dein Tafelbild gerade nicht analysieren. Bitte versuche es noch einmal."

        # 3. Audio-Synthese via OpenAI TTS (nova)
        if audio_enabled:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                tts_res = client.audio.speech.create(
                    model="tts-1",
                    voice="nova",
                    input=tutor_speech,
                    response_format="mp3"
                )
                audio_b64 = base64.b64encode(tts_res.content).decode("utf-8")
            except Exception as e:
                logger.warning(f"Fehler bei OpenAI TTS Sprachausgabe: {e}")
                audio_b64 = None
    else:
        # Fallback im Offline- / Testmodus
        tutor_speech = "Toll, dass du auf der Tafel arbeitest! Schau dir den letzten Schritt noch einmal genau an."
        actions.append({
            "action": "highlight_box",
            "coords": {"x": 120, "y": 140, "w": 320, "h": 85},
            "color": "#f59e0b"
        })

    return {
        "status": "success",
        "tutor_speech": tutor_speech,
        "audio_base64": audio_b64,
        "actions": actions
    }


EXERCISE_SYSTEM_PROMPT = """Du bist Luna, die warmherzige, didaktisch brillante Gymnasial-Tutorin für Thea (Klasse 7 Gymnasium, Brandenburg).
Deine Aufgabe ist es, eine motivierende, exakt auf Theas Lehrplan abgestimmte Übungsaufgabe für das digitale Whiteboard zu erstellen.

Unterstützte Aufgabentypen (exercise_type):
1. "fill_in_the_blank": Lückentext mit Fachbegriffen (z. B. Biologie Zellbestandteile, Physik Energieformen, Deutsch Grammatik/Rechtschreibung). Die Lücken im Text als [[Lücke 1: Begriff]] kennzeichnen. Eine Wortauswahl (word_bank) angeben.
2. "math_problem": Eine typische Rechenaufgabe für Klasse 7 (z. B. Gleichungen, Prozentrechnung, Rationale Zahlen, Bruchterme). Gegeben/Gesucht klar gegliedert, mit Zeilen zum Rechnen.
3. "math_example": Ein anschaulich vorgerechnetes Musterbeispiel ("So geht's Schritt für Schritt"), gefolgt von einer eigenen Übungsaufgabe ("Jetzt du!").
4. "physics_diagram": Physikalischer Zusammenhang (z. B. s-t-Diagramm, v-t-Diagramm, Federkraft F-s, Hebelgesetz mit Hebelarmen). Ein sauberes, valides, inline darstellbares SVG-Diagramm (viewBox='0 0 360 220', mit Koordinatenachsen, Beschriftungen t in s, s in m etc., feinem Gitter und eingetragenem Kurvenverlauf oder Kraftpfeilen) MUSS im Feld diagram_svg enthalten sein! Dazu 1-2 gezielte Ablese- oder Berechnungsfragen.
5. "formula_derivation": Herleitung oder Umstellung einer Formel (z. B. v = s/t nach s oder t umstellen, Dichte ρ = m/V, Hebelgesetz F1*l1 = F2*l2). Gegliedert in logische Einzelschritte mit Lücken/Fragezeichen für Theas nächsten Schritt.
6. "text_question": Ein kurzer, spannender Textauszug (z. B. aus Naturwissenschaften, Geschichte oder Deutsch) gefolgt von 2 gezielten Textverständnisfragen.

Format der JSON-Antwort:
{
  "exercise_type": "physics_diagram",
  "title": "Kurzer Titel der Aufgabe",
  "topic": "Themengebiet",
  "instructions": "Arbeitsauftrag für Thea (1-2 klare Sätze)",
  "content": {
    // Bei fill_in_the_blank: "text": "Text mit [[Lücke 1: Begriff]]", "word_bank": ["A", "B", "C"]
    // Bei math_problem: "problem_statement": "...", "given": "...", "prompt": "..."
    // Bei math_example: "example_title": "...", "example_solution": "...", "your_turn": "..."
    // Bei physics_diagram: "diagram_svg": "<svg viewBox='0 0 360 220' xmlns='http://www.w3.org/2000/svg'>...</svg>", "questions": ["..."]
    // Bei formula_derivation: "steps": [{"num": 1, "text": "...", "formula": "..."}]
    // Bei text_question: "text_snippet": "...", "questions": ["..."]
  },
  "solution_hint": "Didaktischer Lösungs-Tipp für Thea (wird erst bei Klick auf 'Tipp' aufgedeckt)",
  "tutor_speech": "Gesprochene Begrüßung/Einführung der Aufgabe für Thea (1-2 Sätze, natürliches Deutsch, ABSOLUT KEIN LaTeX!)"
}
"""

def generate_board_exercise(
    subject_name: str = "Mathematik",
    grade_level: int = 7,
    topic_name: Optional[str] = None,
    exercise_type: Optional[str] = "auto",
    custom_prompt: Optional[str] = None,
    difficulty: str = "mittel",
    material_context: Optional[Dict[str, Any]] = None,
    audio_enabled: bool = True
) -> Dict[str, Any]:
    """
    Generiert eine interaktive Übungsaufgabe (Lückentext, Rechenaufgabe, Musterbeispiel,
    Physik-Diagramm, Formel-Herleitung oder Textfrage) für das Whiteboard.
    """
    tutor_speech = f"Hier ist eine spannende Übungsaufgabe für dich. Schau sie dir in Ruhe an!"
    audio_b64 = None
    data = None

    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            user_prompt = (
                f"SCHULFACH: {subject_name} (Klasse {grade_level} Gymnasium, Brandenburg)\n"
                f"THEMA: {topic_name or 'Aktuelles Thema der Klassenstufe'}\n"
                f"SCHWIERIGKEITSGRAD: {difficulty}\n"
            )
            if exercise_type and exercise_type != "auto":
                user_prompt += f"GEWÜNSCHTER AUFGABENTYP: {exercise_type}\n"
            else:
                # Automatischer Typ je nach Fach
                if "Physik" in subject_name:
                    user_prompt += "GEWÜNSCHTER AUFGABENTYP: physics_diagram oder formula_derivation\n"
                elif "Mathematik" in subject_name:
                    user_prompt += "GEWÜNSCHTER AUFGABENTYP: math_problem oder math_example\n"
                elif "Biologie" in subject_name or "Deutsch" in subject_name or "Englisch" in subject_name:
                    user_prompt += "GEWÜNSCHTER AUFGABENTYP: fill_in_the_blank oder text_question\n"

            if custom_prompt:
                user_prompt += f"BESONDERER WUNSCH VON THEA: {custom_prompt}\n"

            if material_context:
                user_prompt += (
                    f"\nAKTUELL AUF DER TAFEL BEARBEITETES MATERIAL:\n"
                    f"- Titel: {material_context.get('title')}\n"
                    f"- Textauszug: {material_context.get('text_snippet', '')[:1500]}\n"
                )

            user_prompt += "\nErstelle jetzt die passende Aufgabe im JSON-Format gemäß System-Prompt."

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": EXERCISE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1800
            )

            raw_text = response.choices[0].message.content or "{}"
            data = json.loads(raw_text)
            if "tutor_speech" in data and data["tutor_speech"]:
                tutor_speech = data["tutor_speech"].strip()

        except Exception as e:
            logger.error(f"Fehler bei OpenAI Aufgaben-Generierung: {e}", exc_info=True)
            data = None

    # Fallback-Generierung (wenn kein API-Key oder bei API-Fehler)
    if not data or "content" not in data:
        ex_type = exercise_type if exercise_type and exercise_type != "auto" else (
            "physics_diagram" if "Physik" in subject_name else "math_problem"
        )
        if ex_type == "physics_diagram":
            data = {
                "exercise_type": "physics_diagram",
                "title": "Physik: Gleichförmige Bewegung im s-t-Diagramm",
                "topic": topic_name or "Mechanik & Bewegung",
                "instructions": "Lies aus dem s-t-Diagramm die Geschwindigkeit des Fahrrads ab.",
                "content": {
                    "diagram_svg": (
                        '<svg viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a; border-radius:8px; width:100%; max-width:360px;">'
                        '<line x1="45" y1="180" x2="340" y2="180" stroke="#94a3b8" stroke-width="2"/>'
                        '<line x1="45" y1="180" x2="45" y2="20" stroke="#94a3b8" stroke-width="2"/>'
                        '<polygon points="340,176 348,180 340,184" fill="#94a3b8"/>'
                        '<polygon points="41,20 45,12 49,20" fill="#94a3b8"/>'
                        '<text x="315" y="200" fill="#cbd5e1" font-size="12" font-family="sans-serif">t in s</text>'
                        '<text x="10" y="26" fill="#cbd5e1" font-size="12" font-family="sans-serif">s in m</text>'
                        '<line x1="45" y1="140" x2="330" y2="140" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<line x1="45" y1="100" x2="330" y2="100" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<line x1="45" y1="60" x2="330" y2="60" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<line x1="115" y1="20" x2="115" y2="180" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<line x1="185" y1="20" x2="185" y2="180" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<line x1="255" y1="20" x2="255" y2="180" stroke="#334155" stroke-dasharray="3,3"/>'
                        '<text x="110" y="196" fill="#94a3b8" font-size="11" font-family="sans-serif">2</text>'
                        '<text x="180" y="196" fill="#94a3b8" font-size="11" font-family="sans-serif">4</text>'
                        '<text x="250" y="196" fill="#94a3b8" font-size="11" font-family="sans-serif">6</text>'
                        '<text x="25" y="144" fill="#94a3b8" font-size="11" font-family="sans-serif">10</text>'
                        '<text x="25" y="104" fill="#94a3b8" font-size="11" font-family="sans-serif">20</text>'
                        '<text x="25" y="64" fill="#94a3b8" font-size="11" font-family="sans-serif">30</text>'
                        '<line x1="45" y1="180" x2="255" y2="60" stroke="#38bdf8" stroke-width="3.5" stroke-linecap="round"/>'
                        '<circle cx="185" cy="100" r="4.5" fill="#f59e0b"/>'
                        '</svg>'
                    ),
                    "questions": [
                        "Welche Strecke hat das Fahrrad nach t = 4 s zurückgelegt?",
                        "Berechne die Geschwindigkeit v = s / t in Metern pro Sekunde."
                    ]
                },
                "solution_hint": "Lies bei t = 4 s den Wert s = 20 m ab. Die Geschwindigkeit beträgt v = 20 m / 4 s = 5 m/s.",
                "tutor_speech": "Ich habe dir ein s-t-Diagramm für eine gleichförmige Bewegung auf die Tafel gelegt. Schau dir die Werte bei 4 Sekunden an!"
            }
        elif ex_type == "fill_in_the_blank":
            data = {
                "exercise_type": "fill_in_the_blank",
                "title": f"Lückentext: {topic_name or subject_name}",
                "topic": topic_name or subject_name,
                "instructions": "Setze die passenden Fachbegriffe aus der Wortauswahl in die Lücken ein.",
                "content": {
                    "text": "Bei einer gleichförmigen Bewegung ist die [[1:Geschwindigkeit]] über die gesamte Zeit hinweg [[2:konstant]]. Im Weg-Zeit-Diagramm ergibt das eine [[3:Gerade]].",
                    "blanks": [
                        {"id": 1, "expected_answer": "Geschwindigkeit", "alternatives": ["Tempo"], "hint": "Wie schnell sich der Körper bewegt.", "width_px": 170},
                        {"id": 2, "expected_answer": "konstant", "alternatives": ["gleich", "unverändert"], "hint": "Bedeutet, dass sich das Tempo nicht ändert.", "width_px": 150},
                        {"id": 3, "expected_answer": "Gerade", "alternatives": ["Linie"], "hint": "Eine gerade Linie ohne Biegung.", "width_px": 140}
                    ],
                    "word_bank": ["Geschwindigkeit", "konstant", "Gerade", "beschleunigt", "Parabel"]
                },
                "solution_hint": "Denke daran: gleichförmig bedeutet, dass sich das Tempo nicht ändert.",
                "tutor_speech": "Hier ist ein Lückentext für dich. Schreibe die Fachbegriffe direkt mit dem Stift in die Lücken!"
            }
        elif ex_type == "formula_derivation":
            data = {
                "exercise_type": "formula_derivation",
                "title": "Formel-Herleitung: Geschwindigkeit v = s / t",
                "topic": topic_name or "Formeln umstellen",
                "instructions": "Vervollständige die Schritte zum Umstellen der Geschwindigkeitsformel.",
                "content": {
                    "steps": [
                        {"num": 1, "text": "Ausgangsformel:", "formula": "v = s / t"},
                        {"num": 2, "text": "Beide Seiten mit t multiplizieren (* t):", "formula": "[ ? ]"},
                        {"num": 3, "text": "Formel nach der Zeit t auflösen:", "formula": "t = [ ? ]"}
                    ]
                },
                "solution_hint": "Multipliziere erst mit t: v * t = s. Teile dann durch v: t = s / v.",
                "tutor_speech": "Lass uns die Geschwindigkeitsformel herleiten und nach der Strecke und der Zeit umstellen!"
            }
        else: # math_problem
            data = {
                "exercise_type": "math_problem",
                "title": "Lineare Gleichung lösen",
                "topic": topic_name or "Terme und Gleichungen",
                "instructions": "Löse die Gleichung schrittweise nach der Variablen x auf.",
                "content": {
                    "problem_statement": "Bestimme den Wert von x:",
                    "given": "4x + 15 = 2x + 27",
                    "prompt": "1. x-Terme auf eine Seite bringen\n2. Zahlen auf die andere Seite bringen\n3. x berechnen"
                },
                "solution_hint": "Ziehe zuerst auf beiden Seiten 2x ab: 2x + 15 = 27. Ziehe dann 15 ab: 2x = 12.",
                "tutor_speech": "Ich habe dir eine Gleichung auf die Tafel gestellt. Bring zuerst die x-Terme auf eine Seite!"
            }
        tutor_speech = data.get("tutor_speech", tutor_speech)

    # Standardisierung von Lückentext-Inhalten sicherstellen
    if data.get("exercise_type") == "fill_in_the_blank":
        data["content"] = normalize_cloze_content(data.get("content", {}))

    # Audio TTS generieren falls aktiviert
    if audio_enabled and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            tts_res = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=tutor_speech,
                response_format="mp3"
            )
            audio_b64 = base64.b64encode(tts_res.content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Fehler bei TTS für Aufgabenstellung: {e}")
            audio_b64 = None

    return {
        "exercise_type": data.get("exercise_type", "math_problem"),
        "title": data.get("title", "Übungsaufgabe"),
        "topic": data.get("topic", topic_name),
        "instructions": data.get("instructions", ""),
        "content_json": json.dumps(data.get("content", {})),
        "solution_hint": data.get("solution_hint"),
        "tutor_speech": tutor_speech,
        "audio_base64": audio_b64
    }


def normalize_cloze_content(content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sorgt dafür, dass Lückentexte immer ein standardisiertes 'blanks'-Array
    mit id, expected_answer, alternatives, hint und width_px enthalten.
    """
    import re
    text = content.get("text", "")
    blanks = content.get("blanks")
    if not isinstance(blanks, list):
        blanks = []

    if not blanks and text:
        tokens = re.findall(r"\[\[(.*?)(?::(.*?))?\]\]", text)
        for idx, (p1, p2) in enumerate(tokens, 1):
            if p2:
                clean_id_str = re.sub(r"[^\d]", "", p1)
                bid = int(clean_id_str) if clean_id_str else idx
                expected = p2.strip()
            else:
                bid = idx
                expected = p1.strip()
            blanks.append({
                "id": bid,
                "expected_answer": expected,
                "alternatives": [],
                "hint": f"Überlege, welcher Begriff in Lücke {bid} passt.",
                "width_px": max(140, min(240, len(expected) * 14 + 40))
            })

    content["blanks"] = blanks
    if "word_bank" not in content or not isinstance(content["word_bank"], list) or not content["word_bank"]:
        content["word_bank"] = [b["expected_answer"] for b in blanks if "expected_answer" in b]

    return content


def evaluate_cloze_blanks_targeted(
    exercise_title: str,
    blanks_definition: List[Dict[str, Any]],
    submitted_items: List[Dict[str, Any]],
    audio_enabled: bool = True
) -> Dict[str, Any]:
    """
    Prüft gezielt zugeschnittene Handschrift-Ausschnitte für einzelne Lücken.
    Extrem schnell (< 1s), da kein riesiges Tafelbild analysiert wird,
    sondern nur Mini-Crops gegen bekannte Erwartungswerte.
    """
    blanks_map = {b.get("id"): b for b in blanks_definition if "id" in b}
    results = []

    # 1. Vorab-Filterung von leeren Einreichungen
    items_to_evaluate = []
    for item in submitted_items:
        bid = item.get("blank_id")
        crop_b64 = (item.get("crop_image_base64") or "").strip()
        b_def = blanks_map.get(bid, {})
        expected = b_def.get("expected_answer", "")
        hint = b_def.get("hint")

        if not crop_b64 or len(crop_b64) < 100:
            results.append({
                "blank_id": bid,
                "recognized_text": None,
                "is_correct": False,
                "feedback": "Hier wurde noch nichts eingetragen.",
                "hint": hint
            })
        else:
            items_to_evaluate.append({
                "blank_id": bid,
                "crop_b64": crop_b64,
                "expected": expected,
                "alternatives": b_def.get("alternatives", []),
                "hint": hint
            })

    tutor_speech = ""
    audio_b64 = None

    # 2. Falls Bilder zur Auswertung vorliegen und OpenAI konfiguriert ist
    if items_to_evaluate and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            system_instruction = (
                "Du bist eine empathische, didaktisch exakte Gymnasial-Tutorin für Thea (Klasse 7 Gymnasium).\n"
                "Deine Aufgabe: Bewerte handgeschriebene Lücken-Ausschnitte gegen den jeweiligen Erwartungswert.\n"
                "Schriftliche Toleranz: Berücksichtige kindliche Handschrift und typische Schreibvarianten (z. B. Groß-/Kleinschreibung, ß/ss).\n"
                "Antworte STRIKT als JSON mit folgendem Format:\n"
                "{\n"
                '  "evaluations": [\n'
                '    {\n'
                '      "blank_id": 1,\n'
                '      "recognized_text": "erkanntes Wort",\n'
                '      "is_correct": true,\n'
                '      "feedback": "Kurzes motivierendes Feedback",\n'
                '      "hint": null\n'
                '    }\n'
                '  ],\n'
                '  "tutor_speech": "Kurzer gesprochener Zuspruch (1-2 kurze Sätze, warmherzig, kein LaTeX)."\n'
                "}"
            )

            user_content = [
                {
                    "type": "text",
                    "text": f"Aufgabe: {exercise_title}\nBitte bewerte folgende Lückenausschnitte:"
                }
            ]

            for itm in items_to_evaluate:
                bid = itm["blank_id"]
                exp = itm["expected"]
                alts = ", ".join(itm["alternatives"]) if itm["alternatives"] else "keine weiteren"
                clean_img = itm["crop_b64"]
                if "," in clean_img:
                    clean_img = clean_img.split(",", 1)[1]

                user_content.append({
                    "type": "text",
                    "text": f"[Lücke {bid} | Erwarteter Begriff: '{exp}' | Akzeptierte Alternativen: {alts}]"
                })
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{clean_img.strip()}",
                        "detail": "low"
                    }
                })

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=600
            )

            raw_resp = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_resp)
            evals = parsed.get("evaluations", [])
            tutor_speech = parsed.get("tutor_speech", "").strip()

            evals_by_id = {e.get("blank_id"): e for e in evals if "blank_id" in e}
            for itm in items_to_evaluate:
                bid = itm["blank_id"]
                ev = evals_by_id.get(bid)
                if ev:
                    results.append({
                        "blank_id": bid,
                        "recognized_text": ev.get("recognized_text"),
                        "is_correct": bool(ev.get("is_correct")),
                        "feedback": ev.get("feedback") or ("Richtig!" if ev.get("is_correct") else "Noch nicht ganz richtig."),
                        "hint": ev.get("hint") or itm["hint"]
                    })
                else:
                    results.append({
                        "blank_id": bid,
                        "recognized_text": None,
                        "is_correct": False,
                        "feedback": "Konnte nicht eindeutig erkannt werden.",
                        "hint": itm["hint"]
                    })

        except Exception as e:
            logger.error(f"Fehler bei gezielter Lücken-Auswertung: {e}", exc_info=True)
            for itm in items_to_evaluate:
                results.append({
                    "blank_id": itm["blank_id"],
                    "recognized_text": None,
                    "is_correct": False,
                    "feedback": "Prüfung fehlgeschlagen, bitte wiederholen.",
                    "hint": itm["hint"]
                })
    elif items_to_evaluate:
        # Offline- / Testmodus
        for itm in items_to_evaluate:
            results.append({
                "blank_id": itm["blank_id"],
                "recognized_text": itm["expected"],
                "is_correct": True,
                "feedback": f"Super! '{itm['expected']}' ist richtig.",
                "hint": None
            })
        tutor_speech = "Sehr gut gemacht! Alle Lücken sind richtig ausgefüllt."

    # TTS für gesprochene Antwort erzeugen falls gewünscht
    if not tutor_speech:
        correct_count = sum(1 for r in results if r.get("is_correct"))
        if correct_count == len(blanks_definition) and correct_count > 0:
            tutor_speech = "Perfekt, Thea! Du hast alle Lücken fehlerfrei gelöst."
        elif correct_count > 0:
            tutor_speech = f"Guter Fortschritt! Du hast bereits {correct_count} Lücken richtig."
        else:
            tutor_speech = "Schau dir die Begriffe noch einmal an. Du bist auf dem richtigen Weg!"

    if audio_enabled and OPENAI_API_KEY and tutor_speech:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            tts_res = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=tutor_speech,
                response_format="mp3"
            )
            audio_b64 = base64.b64encode(tts_res.content).decode("utf-8")
        except Exception as e:
            logger.warning(f"Fehler bei TTS für Lückenauswertung: {e}")
            audio_b64 = None

    results.sort(key=lambda x: x.get("blank_id", 0))

    return {
        "status": "success",
        "results": results,
        "tutor_speech": tutor_speech,
        "audio_base64": audio_b64
    }


