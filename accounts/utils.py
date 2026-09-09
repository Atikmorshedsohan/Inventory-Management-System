"""Helpers for describing where a request came from."""

from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address

# Order matters: Edge and Opera user agents also contain "Chrome",
# and Chrome's contains "Safari".
_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Chrome/", "Chrome"),
    ("Firefox/", "Firefox"),
    ("Safari/", "Safari"),
    ("curl/", "curl"),
    ("PostmanRuntime", "Postman"),
    ("python-requests", "Python"),
)

_PLATFORMS = (
    ("Windows NT", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iPadOS"),
    ("Mac OS X", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)


def client_ip(request):
    """Best-effort client IP.

    ``X-Forwarded-For`` is honoured because the app may sit behind a proxy, but
    it is client-supplied and therefore spoofable - treat it as a hint, not
    proof. Anything that is not a valid address is discarded rather than
    allowed to blow up the login it was attached to.
    """
    if request is None:
        return None

    meta = getattr(request, "META", {}) or {}
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    candidates = [part.strip() for part in forwarded.split(",") if part.strip()]
    candidates.append((meta.get("REMOTE_ADDR") or "").strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            validate_ipv46_address(candidate)
        except ValidationError:
            continue
        return candidate
    return None


def user_agent(request):
    if request is None:
        return ""
    return (getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", "") or ""


def describe_client(raw_user_agent):
    """Turn a user-agent string into something like 'Chrome on Windows'."""
    if not raw_user_agent:
        return "Unknown client"

    browser = next((name for token, name in _BROWSERS if token in raw_user_agent), None)
    platform = next((name for token, name in _PLATFORMS if token in raw_user_agent), None)

    if browser and platform:
        return f"{browser} on {platform}"
    if browser:
        return browser
    if platform:
        return platform
    return "Unknown client"
