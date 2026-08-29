
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.schemas import NotificationOut, ObjectOut, TodayOut
from app.core.current_user import CurrentUserContext
from app.services.today_service import TodayService

router = APIRouter(tags=["today"])


@router.get("/today", response_model=TodayOut)
def get_today(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> TodayOut:
    snapshot = TodayService(session, current_user.user_id).snapshot()
    return TodayOut(
        date=snapshot["date"],
        timezone=snapshot["timezone"],
        day_start=snapshot["day_start"],
        tasks=[ObjectOut.from_model(obj) for obj in snapshot["tasks"]],
        calendar_events=[ObjectOut.from_model(obj) for obj in snapshot["calendar_events"]],
        notifications=[
            NotificationOut.from_model(notification)
            for notification in snapshot["notifications"]
        ],
    )
