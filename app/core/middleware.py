import time
from typing import Callable
from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.config.logging import bind_context, clear_context
from app.core.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)
# ==================================================
# Metrics Middleware
# ==================================================
class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically track request duration and status codes.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        status_code = 500  # Default if request fails before response
        try:
            # Process the actual request
            response = await call_next(request)
            status_code = response.status_code
            return response
            
        except Exception:
            # If the app crashes, we still want to record the 500 error
            raise
            
        finally:
            # Calculate duration even if it failed
            duration = time.time() - start_time
            
            # Record to Prometheus
            # We filter out /metrics and /health to avoid noise
            if request.url.path not in ["/metrics", "/health"]:
                http_requests_total.labels(
                    method=request.method, 
                    endpoint=request.url.path, 
                    status=status_code
                ).inc()
                
                http_request_duration_seconds.labels(
                    method=request.method, 
                    endpoint=request.url.path
                ).observe(duration)

# ==================================================
# Logging Context Middleware
# ==================================================
class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts User IDs from JWTs *before* the request hits the router.
    This ensures that even authentication errors are logged with the correct context.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            # 1. Reset context (crucial for async/thread safety)
            clear_context()
            # 2. Try to peek at the Authorization header
            # Note: We don't validate the token here (Auth Dependency does that),
            # we just want to extract IDs for logging purposes if possible.
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    # Unsafe decode just to get the 'sub' (User/Session ID)
                    # The actual signature verification happens later in the router.
                    payload = jwt.get_unverified_claims(token)
                    subject = payload.get("sub")
                    
                    if subject:
                        bind_context(subject_id=subject)
                        
                except JWTError:
                    pass # Ignore malformed tokens in logging middleware
            # 3. Process Request
            response = await call_next(request)
            
            # 4. If the route handler set specific context (like found_user_id), grab it
            if hasattr(request.state, "user_id"):
                bind_context(user_id=request.state.user_id)
            return response
            
        finally:
            # Clean up context to prevent leaking info to the next request sharing this thread
            clear_context()