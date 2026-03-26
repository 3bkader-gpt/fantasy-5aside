"""Rate limiting with SlowAPI; key by IP (supports X-Forwarded-For behind proxy)."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _get_client_ip(request) -> str:
    forwarded = getattr(request, "headers", None) and request.headers.get("x-forwarded-for")
    if settings.trust_proxy_headers and forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_client_ip,
    enabled=not settings.testing,  # disable in tests to avoid flakiness
)
