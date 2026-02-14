import re
from datetime import UTC, datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from app.core.config import settings
from app.schemas.auth import Token
from app.utils.sanitization import sanitize_string
from app.core.config.logging import get_logger


logger = get_logger(__name__)
# ==================================================
# JWT Authentication Utilities
# ==================================================
def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> Token:
    """
    Creates a new JWT access token.
    
    Args:
        subject: The unique identifier (User ID or Session ID)
        expires_delta: Optional custom expiration time
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS)
    # The payload is what gets encoded into the token
    to_encode = {
        "sub": subject,           # Subject (standard claim)
        "exp": expire,            # Expiration time (standard claim)
        "iat": datetime.now(UTC), # Issued At (standard claim)
        
        # JTI (JWT ID): A unique identifier for this specific token instance.
        # Useful for blacklisting tokens if needed later.
        "jti": sanitize_string(f"{subject}-{datetime.now(UTC).timestamp()}"), 
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return Token(access_token=encoded_jwt, expires_at=expire)


def verify_token(token: str) -> Optional[str]:
    """
    Decodes and verifies a JWT token. Returns the subject (User ID) if valid.
    """
    # Basic format validation before attempting decode
    # JWT tokens consist of 3 base64url-encoded segments separated by dots
    if not re.match(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$", token):
        logger.warning("token_suspicious_format")
        raise ValueError("Token format is invalid - expected JWT format")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        thread_id: str = payload.get("sub")
        if thread_id is None:
            logger.warning("token_missing_thread_id")
            return None

        logger.info("token_verified", thread_id=thread_id)
        return thread_id

    except JWTError as e:
        logger.error("token_verification_failed", error=str(e))
        return None