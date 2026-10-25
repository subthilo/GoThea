"""Theas Gestaltung der App: Farbschema (später auch bemalte Hintergründe pro Fach).

Die Schemen stehen in backend/app/design_themes.json (5 Palettenfarben je Schema). derive() rechnet
daraus alle CSS-Farben aus und sorgt für Lesbarkeit: zu dunkle Akzente werden aufgehellt, Karten
abgedunkelt, bis jede Fachfarbe darauf sichtbar bleibt. scripts/build_theme_css.py schreibt das CSS.
Theas Wahl liegt in DATA_DIR/design/settings.json; ändern darf sie sie ohne PIN.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from backend.app import config

logger = logging.getLogger(__name__)

THEMES_FILE = Path(__file__).resolve().parents[1] / "design_themes.json"
DEFAULT_THEME = "indigo"
# Frühere Schemen (bis Okt. 2026) → heutige
LEGACY_THEMES = {"space": "indigo", "sunset": "beere", "nature": "gruen", "candy": "lila"}

# Mindestkontraste (WCAG-Verhältnis)
MIN_ACCENT = 3.0        # Akzent auf Karte
MIN_SUBJECT = 3.0       # Fachfarbe auf Karte und Listenzeile


# ---- Farbrechnung ----
def _rgb(h: str) -> List[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _hex(rgb: Sequence[float]) -> str:
    return "#" + "".join(f"{round(max(0, min(255, v))):02x}" for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    x, y = _rgb(a), _rgb(b)
    return _hex([x[i] + (y[i] - x[i]) * t for i in range(3)])


def rgba(h: str, alpha: float) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r}, {g}, {b}, {alpha})"


def luminance(h: str) -> float:
    def f(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _ensure(color: str, ground: str, target: float, towards: str) -> str:
    for _ in range(40):
        if contrast(color, ground) >= target:
            break
        color = mix(color, towards, 0.08)
    return color


# Signalfarben für Schrift: hell auf dunklem Grund, dunkel auf hellem
SIGNAL_TEXT = {
    True: {"success-text": "#34d399", "warning-text": "#fbbf24", "info-text": "#38bdf8", "danger-text": "#f87171"},
    False: {"success-text": "#047857", "warning-text": "#b45309", "info-text": "#0369a1", "danger-text": "#b91c1c"},
}


def _rgb_list(h: str) -> str:
    return ", ".join(str(v) for v in _rgb(h))


def _extras(dark: bool, text: str) -> Dict[str, str]:
    """Gemeinsame Zusatzfarben: Überlagerungen (ink = zur Schrift hin, shade = vom Grund weg) und Signalschrift."""
    return {
        "ink-rgb": "255, 255, 255" if dark else _rgb_list(text),
        "shade-rgb": "0, 0, 0" if dark else "255, 255, 255",
        **SIGNAL_TEXT[dark],
    }


def derive(theme: dict, subject_colors: Sequence[str] = ()) -> Dict[str, str]:
    """CSS-Farben eines Schemas (Schlüssel ohne '--'). subject_colors: die Fachfarben für dieses Schema
    (dunkle Schemen die normalen, helle den zweiten Satz) – Karten werden angepasst, bis jede sichtbar ist."""
    dark = theme["dark"]
    if "tokens" in theme:
        tok = dict(theme["tokens"])
        return {**tok, **_extras(dark, tok["text-primary"])}
    c1, c2, c3, c4, c5 = theme["palette"]
    if dark:
        card = mix(c2, c3, 0.4)
        for _ in range(20):
            hover = mix(card, c3, 0.55)
            if all(contrast(s, g) >= MIN_SUBJECT for s in subject_colors for g in (card, hover)):
                break
            card = mix(card, c1, 0.15)
        secondary = c2
        accent = _ensure(c4, card, MIN_ACCENT, "#ffffff")
    else:
        card = mix("#ffffff", c1, 0.35)
        shade = 0.35
        for _ in range(20):
            hover = mix(c1, c2, shade)
            if all(contrast(s, g) >= MIN_SUBJECT for s in subject_colors for g in (card, hover)):
                break
            shade *= 0.8
        secondary = mix(c1, c2, 0.55)
        # Auf hellem Grund tragen Akzent-Knöpfe weiße Schrift: Akzent so dunkel, dass sie lesbar ist
        accent = _ensure(_ensure(c4, card, MIN_ACCENT, "#000000"), "#ffffff", 4.5, "#000000")
    white = contrast("#ffffff", accent)
    dark_on = c1 if dark else c5
    on_accent = "#ffffff" if white >= 4.4 or white >= contrast(dark_on, accent) else dark_on
    light_mix = "#ffffff" if dark else "#000000"
    return {
        "bg-primary": c1, "bg-secondary": secondary, "bg-card": card, "bg-card-hover": hover,
        "border-color": rgba(c5, 0.1 if dark else 0.14), "border-active": rgba(accent, 0.45),
        "text-primary": c5, "text-secondary": mix(c5, card, 0.28), "text-muted": mix(c5, card, 0.5 if dark else 0.4),
        "accent": accent, "accent-light": mix(accent, light_mix, 0.25 if dark else 0.15), "on-accent": on_accent,
        "success": "#10b981", "warning": "#f59e0b", "theme-glow": rgba(accent, 0.22),
        **_extras(dark, c5),
    }


@lru_cache(maxsize=1)
def themes() -> List[dict]:
    return json.loads(THEMES_FILE.read_text(encoding="utf-8"))["themes"]


def theme_ids() -> List[str]:
    return [t["id"] for t in themes()]


def theme_list() -> List[dict]:
    """Für die Auswahl: Name (Tooltip) und die zwei Farben des Tupfers."""
    out = []
    for t in themes():
        tok = derive(t)
        out.append({"id": t["id"], "name": t["name"], "dark": t["dark"],
                    "bg": tok["bg-primary"], "accent": tok["accent"]})
    return out


def normalize_theme(theme_id: Optional[str]) -> str:
    theme_id = LEGACY_THEMES.get(theme_id or "", theme_id or "")
    return theme_id if theme_id in theme_ids() else DEFAULT_THEME


# ---- Theas Einstellungen ----
def _settings_file() -> Path:
    return config.DATA_DIR / "design" / "settings.json"


def load_settings() -> dict:
    path = _settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as e:
        logger.error("Gestaltung: %s nicht lesbar (%s), Standard wird genutzt", path, e)
        data = {}
    data["theme"] = normalize_theme(data.get("theme"))
    return data


def save_theme(theme_id: str) -> dict:
    if theme_id not in theme_ids():
        raise ValueError(f"unbekanntes Farbschema: {theme_id}")
    data = load_settings()
    data["theme"] = theme_id
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return data
