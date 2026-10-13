from typing import Optional
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from backend.app.services import parent_auth

router = APIRouter(prefix="/api/v1/auth", tags=["Eltern-Modus"])


class UnlockRequest(BaseModel):
    pin: str


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


@router.post("/parent/unlock")
def unlock_parent_mode(req: UnlockRequest):
    token, expires_at = parent_auth.attempt_unlock(req.pin)
    return {
        "token": token,
        "expires_at": expires_at,
        "is_default_pin": parent_auth.is_default_pin(),
    }


@router.get("/parent/status")
def parent_status(x_parent_token: Optional[str] = Header(None)):
    return {
        "is_parent": parent_auth.validate_token(x_parent_token),
        "is_default_pin": parent_auth.is_default_pin(),
    }


@router.post("/parent/change-pin")
def change_parent_pin(req: ChangePinRequest, _: bool = Depends(parent_auth.require_parent)):
    parent_auth.change_pin(req.current_pin, req.new_pin)
    token, expires_at = parent_auth.issue_token()
    return {"status": "success", "token": token, "expires_at": expires_at}
