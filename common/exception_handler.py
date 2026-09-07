from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import DomainError


def custom_exception_handler(exc, context):
    """Render :class:`DomainError` as ``{"detail": ...}`` with its status code."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, DomainError):
        return Response({"detail": exc.detail}, status=exc.status_code)
    return None
