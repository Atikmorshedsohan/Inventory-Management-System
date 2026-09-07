def user_display(user):
    """Best-effort human name for a user, tolerating unusual user models."""
    if not user:
        return "Unknown"
    for attr in ("name", "full_name"):
        value = getattr(user, attr, None)
        if value:
            return value
    if hasattr(user, "get_full_name"):
        value = user.get_full_name()
        if value:
            return value
    return getattr(user, "username", str(user))
