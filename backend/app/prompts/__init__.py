"""
Zentrale Prompt-Sammlung für GoThea.
Bündelt alle System- und User-Prompts an einem transparenten, versionierten Ort.
"""

from backend.app.prompts.document_analysis import (
    DOCUMENT_ANALYSIS_SYSTEM_PROMPT,
    CANONICAL_SUBJECT_NAMES,
    CANONICAL_DOCUMENT_KINDS,
)
from backend.app.prompts.tutor import (
    TUTOR_SYSTEM_PROMPT,
    EXERCISE_SYSTEM_PROMPT,
    CLOZE_EVALUATION_SYSTEM_PROMPT,
)
from backend.app.prompts.timetable import TIMETABLE_SYSTEM_PROMPT
from backend.app.prompts.book_toc import BOOK_TOC_SYSTEM_PROMPT

__all__ = [
    "DOCUMENT_ANALYSIS_SYSTEM_PROMPT",
    "CANONICAL_SUBJECT_NAMES",
    "CANONICAL_DOCUMENT_KINDS",
    "TUTOR_SYSTEM_PROMPT",
    "EXERCISE_SYSTEM_PROMPT",
    "CLOZE_EVALUATION_SYSTEM_PROMPT",
    "TIMETABLE_SYSTEM_PROMPT",
    "BOOK_TOC_SYSTEM_PROMPT",
]
