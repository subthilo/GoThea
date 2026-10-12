"""
Abwärtskompatibilitäts-Modul für ClozePoolManager.
Delegiert an den universellen ExercisePoolManager in exercise_pool_service.py.
"""
from backend.app.services.exercise_pool_service import (
    ExercisePoolManager,
    exercise_pool_manager,
    TARGET_POOL_SIZE,
    DEFAULT_SUBJECTS
)

# Aliase für bestehende Importe und Tests
ClozePoolManager = ExercisePoolManager
cloze_pool_manager = exercise_pool_manager
