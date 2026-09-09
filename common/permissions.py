"""Role-based DRF permissions shared by every API app.

Roles (see ``accounts.models.User``):

* ``admin``   - full access
* ``manager`` - read + create/update, no delete (delete is blocked at view level)
* ``staff``   - legacy alias, behaves like ``manager``
* ``viewer``  - read-only, and fully blocked from a few resources
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

WRITE_METHODS = ("POST", "PUT", "PATCH")
ELEVATED_ROLES = ("admin", "manager", "staff")


class RolePermission(BasePermission):
    """Allow access based on ``request.user.role``."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        role = getattr(user, "role", "viewer")
        if role == "admin":
            return True
        if request.method in SAFE_METHODS:
            return role in ("viewer",) + ELEVATED_ROLES
        return role in ELEVATED_ROLES and request.method in WRITE_METHODS


class NoDeletePermission(BasePermission):
    """Block ``DELETE`` for everyone except ``admin``."""

    def has_permission(self, request, view):
        if request.method != "DELETE":
            return True
        return getattr(request.user, "role", "viewer") == "admin"


class AdminOnlyPermission(BasePermission):
    """Only ``admin`` may touch this resource at all, reads included."""

    message = "Only admins can access this."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", "viewer") == "admin"


class AdminWritePermission(BasePermission):
    """Reads follow the other permission classes; every write needs ``admin``.

    Used for user administration, where ``RolePermission`` alone would let
    managers and staff create or edit other people's accounts.
    """

    message = "Only admins can make changes here."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, "role", "viewer") == "admin"


class NotViewerPermission(BasePermission):
    """Deny ``viewer`` role entirely (used for requisitions and audit logs)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", "viewer") != "viewer"
