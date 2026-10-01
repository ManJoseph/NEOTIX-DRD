import json
import logging
from time import perf_counter

from django.utils import timezone


logger = logging.getLogger("desk.requests")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            # DRF sets the underlying Django request.user during authentication.
            user = getattr(request, "user", None)
            user_id = user.pk if user is not None and user.is_authenticated else None
            entry = {
                "timestamp": timezone.now().isoformat(),
                "method": request.method,
                "path": request.path,
                "status": response.status_code if response is not None else 500,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "user_id": user_id,
            }
            # Never log passwords, tokens, request bodies, or query strings.
            logger.info(json.dumps(entry))
