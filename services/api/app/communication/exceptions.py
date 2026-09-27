class CommunicationError(Exception):
    """Base error for SMS / USSD provider failures."""


class ProviderDisabledError(CommunicationError):
    pass


class InvalidPhoneError(CommunicationError):
    pass


class ProviderRequestError(CommunicationError):
    pass
