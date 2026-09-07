"""Domain-level errors raised by service functions.

Views catch :class:`DomainError` and return ``{"detail": <message>}`` with the
given HTTP status, keeping business rules out of the view layer.
"""


class DomainError(Exception):
    """A business rule was violated (bad state transition, insufficient stock, ...)."""

    status_code = 400

    def __init__(self, detail, status_code=None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
