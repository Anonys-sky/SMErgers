"""Validate untrusted form return paths without trusting the request's Host header."""
from urllib.parse import unquote, urlsplit


def local_return_path(value, fallback):
    """Accept root-relative URLs only; reject browser URL-normalization bypasses."""
    if not isinstance(value, str) or not value:
        return fallback
    candidate = value
    for _ in range(6):
        if (
            not candidate.startswith("/")
            or candidate.startswith("//")
            or "\\" in candidate
            or any(ord(char) <= 32 or ord(char) == 127 for char in candidate)
        ):
            return fallback
        try:
            parts = urlsplit(candidate)
        except ValueError:
            return fallback
        if parts.scheme or parts.netloc:
            return fallback
        decoded = unquote(candidate)
        if decoded == candidate:
            return value
        candidate = decoded
    return fallback
