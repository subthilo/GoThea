"""Gestaltung der App durch Thea – ohne PIN (es ist ihre App)."""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services import design

router = APIRouter(prefix="/api/v1/design", tags=["Design"])


class ThemeChoice(BaseModel):
    theme: str


class PaintColors(BaseModel):
    colors: List[str]


@router.get("")
def get_design():
    data = design.load_settings()
    return {"theme": data["theme"], "themes": design.theme_list(), "paint_colors": design.paint_colors(data)}


@router.put("/theme")
def put_theme(choice: ThemeChoice):
    try:
        data = design.save_theme(choice.theme)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"theme": data["theme"]}


@router.put("/paint-colors")
def put_paint_colors(body: PaintColors):
    """Eigene Malfarben aus dem Farbmischer (Mal-Modus)."""
    try:
        data = design.save_paint_colors(body.colors)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"paint_colors": design.paint_colors(data)}
