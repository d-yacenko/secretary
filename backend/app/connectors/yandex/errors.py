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
