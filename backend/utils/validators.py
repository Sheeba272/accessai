"""Input validation and URL sanitization"""
import re
from urllib.parse import urlparse
from backend.utils.config import settings


BLOCKED_SCHEMES = {"javascript", "data", "vbscript", "file"}
BLOCKED_HOSTS   = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def validate_url(url: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message)"""
    if not url:
        return False, "URL is required"
    if len(url) > settings.MAX_URL_LENGTH:
        return False, f"URL exceeds maximum length of {settings.MAX_URL_LENGTH}"

    # Must have scheme
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        return False, f"URL scheme '{parsed.scheme}' is not allowed"

    # Basic SSRF protection for production — remove for local dev
    # if parsed.hostname in BLOCKED_HOSTS:
    #     return False, "Scanning localhost is not permitted"

    # Must have a valid hostname
    if not parsed.hostname:
        return False, "URL must include a valid hostname"

    return True, ""


def sanitize_url(url: str) -> str:
    """Strip potentially dangerous characters"""
    url = url.strip()
    # Remove any null bytes or control chars
    url = re.sub(r'[\x00-\x1f\x7f]', '', url)
    return url
