"""
Zentrale Prompt-Sammlung für GoThea.
Bündelt alle System- und User-Prompts an einem transparenten, versionierten Ort.
"""

from backend.app.prompts.document_analysis import (
    DOCUMENT_ANALYSIS_SYSTEM_PROMPT,
    CANONICAL_SUBJECT_NAMES,
    CANONICAL_DOCUMENT_KINDS,
)

__all__ = [
    "DOCUMENT_ANALYSIS_SYSTEM_PROMPT",
    "CANONICAL_SUBJECT_NAMES",
    "CANONICAL_DOCUMENT_KINDS",
]
