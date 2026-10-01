from django.db import InterfaceError, OperationalError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(error, context):
    # Database connection failures may happen during token authentication too.
    if isinstance(error, (OperationalError, InterfaceError)):
        return Response({"detail": "Database unavailable. Try again later."}, status=503)
    return exception_handler(error, context)
