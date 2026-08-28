from app.core.current_user import CurrentUserContext
from app.users.bootstrap import BOOTSTRAP_USER_ID


def resolve_current_user() -> CurrentUserContext:
    """Resolve the acting Secretary user until real authentication exists."""
    return CurrentUserContext(user_id=BOOTSTRAP_USER_ID)
