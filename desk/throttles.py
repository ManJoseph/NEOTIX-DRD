from rest_framework.throttling import AnonRateThrottle


class LoginThrottle(AnonRateThrottle):
    # Limit repeated login attempts per IP; local cache is sufficient for development.
    rate = "20/min"
