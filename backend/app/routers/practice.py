"""Übungen aus echten Aufgaben – Probebetrieb (Schalter GOTHEA_EXERCISE_TRIAL, Standard nur Staging).

Noch ohne Freigabe-Ablauf: Die Daten enthalten die Lösungen, die Prüfung läuft im Browser.
"""
from fastapi import APIRouter, HTTPException

from backend.app import config
from backend.app.services import practice_exercises

router = APIRouter(prefix="/api/v1/practice", tags=["Übungen"])


@router.get("")
def list_practice() -> dict:
    # Ausgeschaltet: leere Liste statt Fehler, das Frontend blendet den Bereich dann aus
    if not config.EXERCISE_TRIAL_ENABLED:
        return {"enabled": False, "exercises": []}
    return {"enabled": True, "exercises": practice_exercises.list_exercises()}


@router.get("/{exercise_id}")
def get_practice(exercise_id: str) -> dict:
    ex = practice_exercises.get_exercise(exercise_id) if config.EXERCISE_TRIAL_ENABLED else None
    if ex is None:
        raise HTTPException(status_code=404, detail="Übung nicht gefunden")
    return ex
