class TeamsConnectorError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TeamsConfigurationError(TeamsConnectorError):
    pass


class TeamsOAuthError(TeamsConnectorError):
    pass


class TeamsSecurityError(TeamsConnectorError):
    pass


class TeamsSyncError(TeamsConnectorError):
    """Visible sync failure; correctness state must not advance."""


class TeamsWriteDefiniteError(TeamsConnectorError):
    """Provider rejected a write; delivery did not occur."""


class TeamsWriteUncertainError(TeamsConnectorError):
    """Write may have been delivered; do not retry blindly."""
