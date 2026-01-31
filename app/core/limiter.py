from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

# ==================================================
# Rate Limiter Configuration
# ==================================================
# We initialize the Limiter using the remote address (IP) as the key.
# you might need to adjust `key_func` to look at X-Forwarded-For headers.
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=settings.RATE_LIMIT_DEFAULT
)