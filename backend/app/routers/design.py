"""Gestaltung der App durch Thea – ohne PIN (es ist ihre App)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services import design

router = APIRouter(prefix="/api/v1/design", tags=["Design"])


class ThemeChoice(BaseModel):
    theme: str


@router.get("")
def get_design():
    return {"theme": design.load_settings()["theme"], "themes": design.theme_list()}


@router.put("/theme")
def put_theme(choice: ThemeChoice):
    try:
        data = design.save_theme(choice.theme)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"theme": data["theme"]}
