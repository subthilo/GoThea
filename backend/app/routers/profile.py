from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.profile import UserProfileRead, UserProfileUpdate
from backend.app.services.parent_auth import require_parent

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])

def get_or_create_default_user(db: Session) -> User:
    user = db.query(User).first()
    if not user:
        user = User(
            id="usr_thea",
            name="Thea",
            grade_level=7,
            school_type="Gymnasium",
            federal_state="Brandenburg"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.get("", response_model=UserProfileRead)
def get_profile(db: Session = Depends(get_db)):
    return get_or_create_default_user(db)

@router.patch("", response_model=UserProfileRead, dependencies=[Depends(require_parent)])
def update_profile(update_data: UserProfileUpdate, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
