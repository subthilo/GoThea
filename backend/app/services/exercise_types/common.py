"""Kleine Bausteine, die mehrere Übungstypen brauchen."""
import hashlib
import random


def shuffled(items: list, seed: str) -> list:
    """Feste, aber gemischte Reihenfolge (gleiche Übung → gleiche Reihenfolge, auch nach Neustart)."""
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    out = list(items)
    rng.shuffle(out)
    return out
