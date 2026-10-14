from typing import Any, Dict, Optional


def supports_temperature(model: str) -> bool:
    """GPT-6- und o-Reasoning-Modelle lehnen den Parameter 'temperature' ab."""
    m = (model or "").lower()
    return not (m.startswith("gpt-6") or m.startswith("o"))


def chat_params(model: str, temperature: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
    """Baut die Parameter für chat.completions.create passend zum gewählten Modell."""
    params: Dict[str, Any] = {"model": model, **kwargs}
    if temperature is not None and supports_temperature(model):
        params["temperature"] = temperature
    return params
