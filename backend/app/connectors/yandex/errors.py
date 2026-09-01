class YandexConnectorError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class YandexConfigurationError(YandexConnectorError):
    pass


class YandexImapError(YandexConnectorError):
    pass


class YandexCalDavError(YandexConnectorError):
    pass


class YandexCalDavStaleSyncTokenError(YandexCalDavError):
    pass


class YandexDiskApiError(YandexConnectorError):
    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        status_code: int | None = None,
        reason: str | None = None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.reason = reason
        super().__init__(message)
