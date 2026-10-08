"""The error a module's service raises when a request cannot be served."""


class ServiceError(Exception):
    """A refused or failed request. status is the HTTP status routes and tools answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
