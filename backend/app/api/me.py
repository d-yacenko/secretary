from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_schemas import UserMeOut
from app.api.deps import get_current_user, get_db
from app.core.current_user import CurrentUserContext
from app.db.models import User

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=UserMeOut)
def get_me(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> UserMeOut:
    user = session.scalar(select(User).where(User.id == current_user.user_id))
    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token user")
    return UserMeOut.model_validate(user)
