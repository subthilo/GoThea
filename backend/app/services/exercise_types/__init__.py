"""Übungstypen. Der Kern (services/practice_exercises.py) kennt Kopf, Status, Liste und Versuche; alles,
was eine Aufgabenform ausmacht, bringt ihr Typ mit – in jedem Fach nutzbar.

Ein Typ ist ein Modul mit:
  TYP           Name, wie er in der Übungsdatei steht ("typ")
  STAGES        Hilfe-Stufen von viel nach wenig Hilfe (Zahlen, aufsteigend)
  BOARD_STAGES  Stufen, die auf einer Übungstafel laufen (Pencil; Prüfen über /practice/{id}/check)
  validate(ex)  Fehlerliste der Daten (leer = stimmig), z. B. Mathe rechnet jede Lösung nach
  prepare(ex)   zusätzliche Felder für die Ansicht (z. B. Bausteine)
  summary(ex)   zusätzliche Felder für die Liste
Die Ansicht für Thea liegt im Frontend: frontend/js/practice_<typ>.js meldet sich mit registerPracticeType an.
"""
from types import ModuleType
from typing import Dict, Optional

from backend.app.services.exercise_types import ordnen, sachaufgabe, zuordnen

TYPES: Dict[str, ModuleType] = {m.TYP: m for m in (sachaufgabe, zuordnen, ordnen)}


def get(typ: str) -> Optional[ModuleType]:
    return TYPES.get(typ)
