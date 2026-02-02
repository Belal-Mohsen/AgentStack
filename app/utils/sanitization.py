import html
import re
from typing import Any, Dict, List

# ==================================================
# Input Sanitization Utilities
# ==================================================
def sanitize_string(value: str) -> str:
    """
    Sanitize a string to prevent XSS and other injection attacks.
    """
    if not isinstance(value, str):
        value = str(value)
    # 1. HTML Escape: Converts <script> to &lt;script&gt;
    value = html.escape(value)
    # 2. Aggressive Scrubbing: Remove script tags entirely if they slipped through
    # (This is a defense-in-depth measure)
    value = re.sub(r"&lt;script.*?&gt;.*?&lt;/script&gt;", "", value, flags=re.DOTALL)
    # 3. Null Byte Removal: Prevents low-level binary exploitation attempts
    value = value.replace("\0", "")
    return value

def validate_password_strength(password: str) -> bool:
    """
    Validate password meets strength requirements. Raises ValueError if not.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one number")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError("Password must contain at least one special character")

    return True


def sanitize_email(email: str) -> str:
    """
    Sanitize and validate an email address format.
    """
    # Basic cleaning
    email = sanitize_string(email)
    # Regex validation for standard email format
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValueError("Invalid email format")
    return email.lower()


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize all string values in a dictionary."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_list(data: List[Any]) -> List[Any]:
    """Recursively sanitize all string values in a list."""
    sanitized = []
    for item in data:
        if isinstance(item, str):
            sanitized.append(sanitize_string(item))
        elif isinstance(item, dict):
            sanitized.append(sanitize_dict(item))
        elif isinstance(item, list):
            sanitized.append(sanitize_list(item))
        else:
            sanitized.append(item)
    return sanitized