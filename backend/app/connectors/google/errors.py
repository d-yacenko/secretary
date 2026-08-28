class GoogleConnectorError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class GoogleConfigurationError(GoogleConnectorError):
    pass


class GoogleOAuthError(GoogleConnectorError):
    pass


class GoogleApiError(GoogleConnectorError):
    pass
