class MattermostConnectorError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class MattermostConfigurationError(MattermostConnectorError):
    pass


class MattermostSecurityError(MattermostConnectorError):
    pass


class MattermostTransportError(MattermostConnectorError):
    pass


class MattermostEndpointNotFoundError(MattermostTransportError):
    pass


class MattermostUnauthorizedError(MattermostTransportError):
    pass

