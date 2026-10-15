# Vollständige Liste aller Modelle: wer dieses Paket importiert, hat alle Tabellen in
# Base.metadata registriert (Voraussetzung für create_all in main.py und den Tests).
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic, TopicBookRef
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material, MaterialChunk
from backend.app.models.material_page import MaterialPage
from backend.app.models.annotation import PageAnnotation
from backend.app.models.study_block import StudyBlock
from backend.app.models.test import Test
from backend.app.models.completed_task import CompletedTask
from backend.app.models.timetable import TimetableSlot
from backend.app.models.whiteboard import TutorSession, TutorMessage, TutorExercise
from backend.app.models.exercise_score import ExerciseScore

__all__ = [
    "User",
    "Subject",
    "Topic",
    "TopicBookRef",
    "Dossier",
    "Material",
    "MaterialChunk",
    "MaterialPage",
    "PageAnnotation",
    "StudyBlock",
    "Test",
    "CompletedTask",
    "TimetableSlot",
    "TutorSession",
    "TutorMessage",
    "TutorExercise",
    "ExerciseScore",
]
