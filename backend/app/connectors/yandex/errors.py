class YandexConnectorError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class YandexConfigurationError(YandexConnectorError):
    pass


class YandexImapError(YandexConnectorError):
    pass


class YandexCalDavError(YandexConnectorError):
    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        category: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.operation = operation
        self.path = path
        self.status_code = status_code
        self.category = category
        super().__init__(message, retryable=retryable)


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
