from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def normalize_tool_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    tz = ZoneInfo(settings.secretary_timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)
